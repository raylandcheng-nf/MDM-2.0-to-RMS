import json
import os
import ssl
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def load_env_file():
	env_path = Path(__file__).with_name(".env")
	for line in env_path.read_text(encoding="utf-8").splitlines():
		line = line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue
		name, value = line.split("=", 1)
		os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


def create_ssl_context():
	ca_bundle = os.environ.get("MDM_CA_BUNDLE")
	context = ssl.create_default_context(cafile=ca_bundle)
	if os.name == "nt" and not ca_bundle:
		certificates = []
		for store_name in ("ROOT", "CA"):
			for certificate, encoding, trust in ssl.enum_certificates(store_name):
				trusted_for_server = trust is True or "1.3.6.1.5.5.7.3.1" in trust
				if encoding == "x509_asn" and trusted_for_server:
					certificates.append(ssl.DER_cert_to_PEM_cert(certificate))
		if certificates:
			context.load_verify_locations(cadata="".join(certificates))
	return context


def main():
	load_env_file()
	token_url = os.environ["MDM_TOKEN_URL"]
	api_key = os.environ["MDM_KEY"]
	employee_url = os.environ["MDM_EMPLOYEE_URL"]
	ssl_context = create_ssl_context()

	token_request = Request(token_url, headers={"x-api-key": api_key})
	with urlopen(token_request, context=ssl_context) as response:
		access_token = json.load(response)["AccessToken"]

	query_size = int(os.environ["MDM_QUERY_SIZE"])
	if query_size < 1:
		raise ValueError("MDM_QUERY_SIZE must be a positive integer")
	separator = "&" if "?" in employee_url else "?"
	employee_list = None
	all_employees = []
	page = 1
	while True:
		query = urlencode({"Page": page, "Size": query_size})
		employee_request = Request(
			f"{employee_url}{separator}{query}",
			headers={"Authorization": f"Bearer {access_token}"},
		)
		print(f"Requesting MDM employee page {page}")
		with urlopen(employee_request, context=ssl_context) as response:
			page_data = json.load(response)
		if employee_list is None:
			employee_list = page_data
		page_results = page_data.get("Results", [])
		all_employees.extend(page_results)
		total_pages = page_data.get("TotalPages")
		if not page_results or (total_pages is not None and page >= int(total_pages)):
			break
		page += 1
	employee_list["Results"] = all_employees
	cutoff_date = date.fromisoformat(os.environ["MDM_ORIGINAL_HIRE_DATE"])
	employee_list["Results"] = [
		employee
		for employee in employee_list["Results"]
		if employee.get("OriginalHireDate")
		and date.fromisoformat(employee["OriginalHireDate"][:10]) > cutoff_date
	]
	employee_list["Count"] = len(employee_list["Results"])
	for employee in employee_list["Results"]:
		primary_department = employee.get("PrimaryDepartment") or {}
		phones = employee.get("Phones") or []
		emails = employee.get("Emails") or []
		staff_cards = employee.get("StaffCards") or []
		active_primary_email = next(
			(
				email.get("Email")
				for email in emails
				if email.get("IsPrimary") and email.get("IsActive")
			),
			None,
		)
		employee_summary = {
			"UserID": employee.get("EmployeeNo"),
			"UserNameEng": employee.get("PreferredName", employee.get("PreferedName")),
			"Department": primary_department.get("Name"),
			"Tel": next(
				(phone.get("PhoneNumber") for phone in phones if phone.get("PhoneNumber")),
				None,
			),
			"Email": active_primary_email,
			"NFCs": [card.get("StaffCardId") for card in staff_cards if card.get("StaffCardId")],
			"IsActive": 1
		}
		print(json.dumps(employee_summary, ensure_ascii=False, indent=2))

	output_path = Path(__file__).with_name("employeeList.json")
	output_path.write_text(
		json.dumps(employee_list, indent=2, ensure_ascii=False) + "\n",
		encoding="utf-8",
	)


if __name__ == "__main__":
	main()
