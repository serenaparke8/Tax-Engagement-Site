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

The local demonstration accounts are configured through the `TEM_DEMO_ACCOUNT_*` variables in `backend/.env`. Passwords are not listed in this README or the example environment file. For a fresh local setup, choose private usernames and passwords in `backend/.env`; during local SQLite development only, the accounts are seeded on the first API request if the `USERS` table is empty. Production requests never seed accounts. Both demonstration accounts share the same business records and access level. Do not use real client or taxpayer data.

For an HTTPS deployment, set `TEM_ENV=production` and provide a unique `TEM_SECRET_KEY` of at least 32 characters. The app rejects missing, short, and example placeholder keys in production and marks session cookies `Secure`.

## Vercel deployment configuration

The repository-root `vercel.json` defines one Vercel project with two Services: the Vite frontend rooted at `frontend/` and the Flask backend rooted at `backend/`. The backend entrypoint is `run:app`. Requests under `/api/` route to Flask; all other paths route to the frontend. The frontend already calls same-origin relative `/api/...` URLs, so it needs no production API host setting. The backend Python version is pinned to 3.12 in `backend/.python-version`.

In Vercel, import the repository as one project and set its framework preset to **Services**. Keep the repository root as the project root so Vercel can read the top-level `vercel.json` and build each service from its configured root. The frontend build uses the existing Vite package configuration and lockfile; the backend installs from `backend/requirements.txt` and exports the Flask `app` through `backend/run.py`.

Configure these variables in the Vercel project’s private Environment Variables settings for Production (and separately for Preview if previews need a database):

- `TEM_ENV` — set to `production`.
- `TEM_SECRET_KEY` — a unique random signing key of at least 32 characters; do not reuse the local key.
- `TEM_DATABASE_URL` — the private PostgreSQL connection URL for the hosted database.

Do not put real values in `vercel.json`, README files, or `.env.example`. Create the PostgreSQL schema and provision the demo accounts as separate, deliberate setup steps before asking the professor to sign in. Services are currently documented by Vercel as Beta; confirm access is enabled for the Vercel account and review current service and function usage limits before deployment. This repository change configures the project but does not create a Vercel project, database, schema, accounts, or deployment.

## Database

Local development continues to use SQLite at `backend/instance/tax_engagement.db` by default. Set `TEM_DATABASE` to choose a different local SQLite file. SQLite foreign-key enforcement remains enabled. The schema contains `USERS`, `CLIENT`, `TAX_ENGAGEMENT`, and `REQUIRED_ITEM`; `CLIENT.client_name` is required, engagement status is restricted to `In Progress`, `Waiting on Client`, or `Completed`, and required-item status is restricted to `Outstanding` or `Received`.

The database foundation now includes SQLAlchemy Core, Psycopg 3, and Alembic. Production configuration uses `TEM_ENV=production` and requires `TEM_DATABASE_URL` to point to PostgreSQL; the app will fail at startup if that URL is missing and will not fall back to SQLite. `TEM_SECRET_KEY` must also be set to a unique value of at least 32 characters. Keep connection URLs and secrets in private environment settings, never in source control.

The initial Alembic migration describes the four-table schema for a new PostgreSQL database. It must be applied explicitly to a PostgreSQL database before the application starts there; local SQLite databases continue to use the existing initialization path. Backend routes now use SQLAlchemy Core statements intended to run on both databases. PostgreSQL behavior still requires verification against an actual PostgreSQL server before production use.

For a new production PostgreSQL database, configure `TEM_ENV=production`, `TEM_DATABASE_URL`, and `TEM_SECRET_KEY` privately, then apply the Alembic migration from the project root with `python -m alembic upgrade head`. Provision the two demo accounts once from the backend directory with `python provision_demo_accounts.py`. The command asks for usernames and display names, then collects each new password through hidden terminal prompts and asks for confirmation. It refuses to run unless production PostgreSQL is configured and the `USERS` table is empty. It inserts both accounts in one transaction using the same Werkzeug password hashing used by login. Do not put production demo passwords in environment variables or source files. The provisioning command does not create the database schema; apply the Alembic migration first.

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
