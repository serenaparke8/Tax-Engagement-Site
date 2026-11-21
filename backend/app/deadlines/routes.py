from datetime import date, timedelta

from flask import jsonify, session

from ..db import get_db
from . import deadlines_bp


UPCOMING_WINDOW_DAYS = 14


def current_date():
    return date.today()


@deadlines_bp.before_request
def require_authenticated_user():
    if "user_id" not in session:
        return jsonify(error="Sign in to view upcoming deadlines."), 401
    return None


def upcoming_deadline_rows(today=None):
    """Return filing deadlines from today through the inclusive 14-day window."""
    window_start = today or current_date()
    window_end = window_start + timedelta(days=UPCOMING_WINDOW_DAYS)
    rows = get_db().execute(
        """SELECT e.engagement_id, e.client_id, c.client_name, e.tax_year,
                  e.return_type, e.filing_deadline
           FROM TAX_ENGAGEMENT AS e
           JOIN CLIENT AS c ON c.client_id = e.client_id
           WHERE e.filing_deadline >= ? AND e.filing_deadline <= ?
           ORDER BY e.filing_deadline ASC, e.engagement_id ASC""",
        (window_start.isoformat(), window_end.isoformat()),
    ).fetchall()

    deadlines = []
    for row in rows:
        deadline = date.fromisoformat(row["filing_deadline"])
        deadlines.append({
            "engagement_id": row["engagement_id"],
            "client_id": row["client_id"],
            "client_name": row["client_name"],
            "tax_year": row["tax_year"],
            "return_type": row["return_type"],
            "filing_deadline": row["filing_deadline"],
            "days_remaining": (deadline - window_start).days,
        })
    return deadlines


@deadlines_bp.get("/upcoming")
def list_upcoming_deadlines():
    return jsonify(deadlines=upcoming_deadline_rows())
