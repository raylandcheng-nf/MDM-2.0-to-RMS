# MDM Employee Export

`app.py` retrieves employee records from the MDM API, filters them to active employees whose original hire date is later than the configured cutoff, and can create corresponding employee records in RMS when updates are enabled. It saves the filtered MDM response to `employeeList.json` and prints a compact summary of each included employee to the console.

## Requirements

- Python 3.9 or later
- Network access to the MDM token and employee endpoints
- Any required API key and TLS certificate authority configuration
- `Mapping.xlsx` next to `app.py`, with a table containing `MDM Department` and `Department Code` columns

Install the dependencies with:

```powershell
pip install -r requirements.txt
```

## Configuration

Start by copying `.env.example` to `.env`, then replace the placeholder values with your environment's endpoints and credentials. The sample includes Email Center settings used when the app sends error notifications.

Create a `.env` file in the same directory as `app.py` with these settings:

```dotenv
MDM_TOKEN_URL=<MDM token endpoint>
MDM_KEY=<MDM API key>
MDM_EMPLOYEE_URL=<MDM employee endpoint>
MDM_QUERY_SIZE=100
MDM_ORIGINAL_HIRE_DATE=2026-01-01
RMS_TOKEN_URL=<RMS token endpoint>
RMS_USER=<RMS username>
RMS_PASSWORD=<RMS password>
RMS_EMPLOYEE_URL=<RMS employee endpoint>
RMS_EMPLOYEE_NFC_URL=<RMS EmployeeNFC endpoint>
RMS_UPDATE_ENABLED=false
```

Choose the query size and hire-date cutoff appropriate for your export. `MDM_ORIGINAL_HIRE_DATE` must be an ISO date (`YYYY-MM-DD`). Only employees with top-level `IsActive` set to `true` and an `OriginalHireDate` strictly later than this cutoff are included.

Optional TLS setting:

```dotenv
MDM_CA_BUNDLE=<path to a CA certificate bundle>
```

When `MDM_CA_BUNDLE` is unset, the script uses the system's default certificate authorities. On Windows, it also attempts to load server-trusted certificates from the Windows `ROOT` and `CA` stores.

Keep `.env` private; do not commit API keys or other credentials.
Values from `.env` override same-named process environment variables when the script starts.

## Run

From the project directory, run:

```powershell
python app.py
```

The script requests an MDM access token with the `x-api-key` header, then fetches employee records using bearer authentication. It requests pages using the `Page` and `Size` query parameters until there are no results or the API's `TotalPages` count is reached.

For each employee, `PrimaryDepartment.Name` is matched against the `MDM Department` column in the `Department` table in `Mapping.xlsx`. The corresponding `Department Code` is used in the RMS employee payload. An employee with missing department data or no matching code is reported and skipped. Invalid or conflicting entries in the shared mapping table stop processing because the mapping cannot be trusted.

RMS writes are controlled by `RMS_UPDATE_ENABLED`. Set it to `true` to enable RMS updates; `false` disables all RMS token and employee requests while MDM fetching and the local export continue. It defaults to `false`, and any other value is rejected.

When RMS updates are enabled, the script checks `ProcessedUserID.json` for separate employee and EmployeeNFC success flags. It calls each API only when that user's corresponding flag is false, and writes each successful update immediately. EmployeeNFC is considered successful without a request when MDM has no non-blank staff-card ID. Failed requests remain false and can be retried independently. Older files containing a JSON array of completed user IDs are migrated as successes for both APIs.

Employee-specific data, department mapping, RMS lookup, and RMS create errors are reported by email and skipped so processing can continue for other employees. If an RMS token cannot be obtained, the affected RMS work is skipped and the local export can still complete. Errors that prevent obtaining or validating the shared MDM data, loading required configuration or mapping/state files, or writing the export remain run-wide and stop processing after an error notification attempt. Email delivery is best-effort; notification failures are printed to the console.

## Output

- `employeeList.json` is written next to `app.py`. It contains the first page's response metadata and the combined `Results` from all fetched pages, filtered to active employees with `OriginalHireDate` later than the cutoff. Its `Count` is updated to the number of included employees.
- `ProcessedUserID.json` is written next to `app.py` and maps each employee ID to `EmployeeUpdateSuccess` and `EmployeeNFCUpdateSuccess` boolean values. It is initialized as an empty object if it does not exist. For example, this record retries only EmployeeNFC:

	```json
	{
		"010340": {
			"EmployeeUpdateSuccess": true,
			"EmployeeNFCUpdateSuccess": false
		}
	}
	```
- The console displays one summary per included employee, with user ID, English preferred name, primary department, first available phone number, active primary email, staff card IDs, and an active flag.

The output file is overwritten each time the script runs. If a request, response parse, configuration lookup, or date validation fails, the script raises an error and does not complete the export.
