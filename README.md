# Tax Engagement Management System

Milestones 1 through 3 provide the React/Vite frontend, Flask API, SQLite schema, demonstration accounts, login flow, client management, and tax engagement management. Required-item tracking, deadline views, dashboard, and reporting are reserved for later milestones.

## Requirements

- Node.js 20.19+ (Vite requirement)
- Python 3.9+

## Start locally

From the project root, open two PowerShell terminals.

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

## Demonstration accounts

| Username | Password |
|---|---|
| `serena` | `***REMOVED***` |
| `professor` | `***REMOVED***` |

The accounts are created on first database initialization with Werkzeug password hashes. Both have the same access and share all business records. These are demonstration credentials for local use only; do not use real client data or reuse these passwords in another system.

## Database

SQLite creates `backend/instance/tax_engagement.db` when the Flask app starts. The schema contains `USERS`, `CLIENT`, `TAX_ENGAGEMENT`, and `REQUIRED_ITEM`, with foreign-key enforcement enabled. `CLIENT.client_name` is required; contact name, email, and phone may be blank. Tax-engagement status is restricted to `In Progress`, `Waiting on Client`, or `Completed` and defaults to `In Progress`. Required-item status is restricted to `Outstanding` or `Received` and defaults to `Outstanding`. Client deletion is restricted when engagements reference that client.

## Foundation API

- `GET /api/health` reports whether the API is available.
- `POST /api/auth/login` authenticates a username and password.
- `GET /api/auth/me` reports the current session.
- `POST /api/auth/logout` ends the current session.
- `GET /api/clients` lists clients (login required).
- `POST /api/clients` adds a client (login required).
- `PUT /api/clients/<client_id>` updates a client (login required).
- `DELETE /api/clients/<client_id>` deletes a client only when it has no tax engagements (login required).
- `GET /api/engagements?q=<search>` lists and searches engagements with their associated client information (login required).
- `POST /api/engagements` creates an engagement linked to an existing client with initial status `In Progress` (login required).
- `PUT /api/engagements/<engagement_id>` updates tax year, return type, assigned preparer, engagement start date, and filing deadline (login required).
- `PATCH /api/engagements/<engagement_id>/status` updates status using the three approved values (login required).

## Run backend checks

From the `backend` directory:

```powershell
python -m unittest discover -s tests -v
```

From the `frontend` directory, run `npm run build` to create a production build.

The authenticated application currently implements UC-1 through UC-6. UC-5 includes `filing_deadline`, clarifying the Program Specification 2.2 omission in accordance with UC-5 and the existing engagement design. Status changes remain separate under UC-6. Required-item/document tracking is not implemented yet.
