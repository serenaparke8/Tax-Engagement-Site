# Tax Engagement Management System

Milestones 1 through 7 provide the React/Vite frontend, Flask API, SQLite schema, demonstration accounts, login flow, client and tax-engagement management, required-item tracking, upcoming deadlines, the UC-10 engagement dashboard, and the UC-11 engagement report.

## Requirements

- Node.js 20.19+ (Vite requirement)
- Python 3.9+

## Start locally

From the project root, open two PowerShell terminals.

For a fresh local setup, copy `backend/.env.example` to `backend/.env` and replace the placeholder values with private local values. Do not publish or commit `backend/.env`.

Backend terminal:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Frontend terminal:

```powershell
cd frontend
npm install
npm run dev
```

If pnpm is installed instead, use `pnpm install` and `pnpm dev`.

Open <http://localhost:5173>. Vite forwards `/api` requests to Flask at `http://127.0.0.1:5000`.

## Demonstration login

The local demonstration accounts are configured through the `TEM_DEMO_*` variables in `backend/.env`. Passwords are not listed in this README or the example environment file. For a fresh setup, choose private usernames and passwords in `backend/.env` before starting Flask. Earlier Git history contains the original demo credentials, so do not use those historical values for a shared or deployed instance. Demo accounts are seeded on the first API request when the `USERS` table is empty, using Werkzeug password hashes. Both accounts share the same business records and access level. Do not use real client or taxpayer data.

For an HTTPS deployment, set `TEM_ENV=production` and provide a unique `TEM_SECRET_KEY` of at least 32 characters. The app rejects missing, short, and example placeholder keys in production and marks session cookies `Secure`.

## Database

SQLite uses `backend/instance/tax_engagement.db`. The schema contains `USERS`, `CLIENT`, `TAX_ENGAGEMENT`, and `REQUIRED_ITEM`, with foreign-key enforcement enabled. `CLIENT.client_name` is required; contact name, email, and phone may be blank. Tax-engagement status is restricted to `In Progress`, `Waiting on Client`, or `Completed` and defaults to `In Progress`. Required-item status is restricted to `Outstanding` or `Received` and defaults to `Outstanding`. Client deletion is restricted when engagements reference that client.

## Foundation API

- `GET /api/health` reports whether the API is available.
- `GET /api/auth/csrf` creates or returns the session's CSRF token.
- `POST /api/auth/login` authenticates a username and password and requires a CSRF token.
- `GET /api/auth/me` reports the current session.
- `POST /api/auth/logout` ends the current session and requires a CSRF token.
- `GET /api/clients` lists clients (login required).
- `POST /api/clients` adds a client (login required).
- `PUT /api/clients/<client_id>` updates a client (login required).
- `DELETE /api/clients/<client_id>` deletes a client only when it has no tax engagements (login required).
- `GET /api/engagements?q=<search>` lists and searches engagements with their associated client information (login required).
- `POST /api/engagements` creates an engagement linked to an existing client with initial status `In Progress` (login required).
- `PUT /api/engagements/<engagement_id>` updates tax year, return type, assigned preparer, engagement start date, and filing deadline (login required).
- `PATCH /api/engagements/<engagement_id>/status` updates status using the three approved values (login required).
- `GET /api/required-items?engagement_id=<id>` lists required items for one tax engagement (login required).
- `POST /api/required-items` adds a required-item description to an existing engagement with status `Outstanding` (login required).
- `DELETE /api/required-items/<required_item_id>` deletes one required-item record after the application confirms the request (login required).
- `PATCH /api/required-items/<required_item_id>/status` updates a required-item status to `Outstanding` or `Received` (login required).
- `GET /api/required-items/outstanding` lists outstanding items with their client and engagement information (login required).
- `GET /api/deadlines/upcoming` lists filing deadlines from today through the next 14 calendar days, inclusive, with client, engagement, tax-year, return-type, and days-remaining information (login required).
- `GET /api/dashboard` returns active and completed engagements, status counts, outstanding-item counts, and an upcoming filing-deadline overview (login required).
- `GET /api/reports/criteria` returns available engagement statuses, tax years, and assigned preparers for report filters (login required).
- `GET /api/reports/engagements?status=<status>&tax_year=<year>&assigned_preparer=<name>` generates an engagement report using any combination of the three supplied filters (login required).

State-changing API requests require the session CSRF token in the `X-CSRF-Token` request header.

## Run backend checks

From the `backend` directory:

```powershell
python -m unittest discover -s tests -v
```

From the `frontend` directory, run `npm run build` to create a production build.

The authenticated application currently implements UC-1 through UC-11. UC-5 includes `filing_deadline`, clarifying the Program Specification 2.2 omission in accordance with UC-5 and the existing engagement design. Status changes remain separate under UC-6. UC-7 updates the status of existing required items; adding a required item is a supporting operation to populate the approved table, not an additional documented use case. UC-8 shows only outstanding items with their associated client and engagement information. UC-9 uses a dynamic inclusive window from today through the date 14 calendar days later. UC-10 shows active and completed engagements with status, deadline, and outstanding-item summaries. UC-11 supports combined status, tax-year, and assigned-preparer filters.
