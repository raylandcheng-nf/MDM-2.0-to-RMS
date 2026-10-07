"""Send error notifications through the Email Center API."""

import os
from pathlib import Path


def load_env_file(path=".env", override=True):
	"""Load simple KEY=value lines from a .env file."""
	env_path = Path(path)
	if not env_path.exists():
		return

	for raw_line in env_path.read_text(encoding="utf-8").splitlines():
		line = raw_line.strip()
		if not line or line.startswith("#") or "=" not in line:
			continue

		key, value = line.split("=", 1)
		key = key.strip()
		value = value.strip().strip('"').strip("'")
		if key and (override or key not in os.environ):
			os.environ[key] = value


def send_error_notification(to=None, subject=None, body=None):
	"""Request an Email Center access token and queue an error email."""
	import requests

	print("[notification] Loading environment configuration...")
	load_env_file()
	default_to = os.getenv("default_to")
	default_subject = os.getenv("default_subject")
	default_body = os.getenv("default_body")
	required = {
		"EMAIL_TOKEN_URL": os.getenv("EMAIL_TOKEN_URL"),
		"EMAIL_TOKEN_SCOPE": os.getenv("EMAIL_TOKEN_SCOPE"),
		"EMAIL_TOKEN_CLIENT_SECRET": os.getenv("EMAIL_TOKEN_CLIENT_SECRET"),
		"EMAIL_TOKEN_CLIENT_ID": os.getenv("EMAIL_TOKEN_CLIENT_ID"),
		"EMAIL_API_URL": os.getenv("EMAIL_API_URL"),
	}
	if to is None:
		required["default_to"] = default_to
	if subject is None:
		required["default_subject"] = default_subject
	if body is None:
		required["default_body"] = default_body
	missing = [name for name, value in required.items() if not value]
	if missing:
		raise RuntimeError(f"Missing email notification configuration: {', '.join(missing)}")

	print("[notification] Requesting access token...")
	token_response = requests.post(
		required["EMAIL_TOKEN_URL"],
		data={
			"client_id": required["EMAIL_TOKEN_CLIENT_ID"],
			"client_secret": required["EMAIL_TOKEN_CLIENT_SECRET"],
			"scope": required["EMAIL_TOKEN_SCOPE"],
			"grant_type": os.getenv("EMAIL_TOKEN_GRANT_TYPE", "client_credentials"),
		},
		headers={"Content-Type": os.getenv("EMAIL_TOKEN_CONTENT_TYPE", "application/x-www-form-urlencoded")},
		timeout=30,
	)
	print(f"[notification] Token server response: HTTP {token_response.status_code}")
	try:
		token_body = token_response.json()
		safe_token_body = dict(token_body) if isinstance(token_body, dict) else token_body
		if isinstance(safe_token_body, dict) and "access_token" in safe_token_body:
			safe_token_body["access_token"] = "<redacted>"
		print(f"[notification] Token response body: {safe_token_body}")
	except ValueError:
		print(f"[notification] Token response body: {token_response.text}")
	token_response.raise_for_status()
	access_token = token_body.get("access_token") if isinstance(token_body, dict) else None
	if not access_token:
		raise RuntimeError("Email notification token response missing access_token")

	print("[notification] Access token received.")
	payload = {
		"applicationName": "MDM 2.0 to RMS",
		"applicationRefId": "54323",
		"templateName": "ErrorMessage",
		"sender": "noreply@nanfung.com",
		"senderName": "No reply",
		"to": default_to if to is None else to,
		"cc": "",
		"bcc": "",
		"subject": default_subject if subject is None else subject,
		"body": default_body if body is None else body,
		"highImportant": False,
	}
	response = requests.post(
		required["EMAIL_API_URL"],
		json=payload,
		headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
		timeout=30,
	)
	print(f"[notification] Email API server response: HTTP {response.status_code}")
	try:
		print(f"[notification] Email API response body: {response.json()}")
	except ValueError:
		print(f"[notification] Email API response body: {response.text}")
	response.raise_for_status()
	print("[notification] Error email queued successfully.")


if __name__ == "__main__":
	try:
		send_error_notification()
	except Exception as error:
		print(f"[notification] Failed: {error}")
		raise
