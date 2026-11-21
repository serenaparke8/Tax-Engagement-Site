from datetime import date, timedelta

from flask import jsonify, session

from ..db import get_db
from . import dashboard_bp


ACTIVE_STATUSES = ("In Progress", "Waiting on Client")
UPCOMING_WINDOW_DAYS = 14


def current_date():
    return date.today()


@dashboard_bp.before_request
def require_authenticated_user():
    if "user_id" not in session:
        return jsonify(error="Sign in to view the engagement dashboard."), 401
    return None


def get_dashboard_data(today=None):
    today = today or current_date()
    window_end = today + timedelta(days=UPCOMING_WINDOW_DAYS)
    rows = get_db().execute(
        """SELECT e.engagement_id, e.client_id, c.client_name, e.tax_year,
                  e.return_type, e.assigned_preparer, e.engagement_start_date,
                  e.filing_deadline, e.engagement_status,
                  COUNT(ri.required_item_id) AS outstanding_item_count
           FROM TAX_ENGAGEMENT AS e
           JOIN CLIENT AS c ON c.client_id = e.client_id
           LEFT JOIN REQUIRED_ITEM AS ri
             ON ri.engagement_id = e.engagement_id AND ri.item_status = 'Outstanding'
           GROUP BY e.engagement_id
           ORDER BY e.filing_deadline ASC, e.engagement_id ASC"""
    ).fetchall()

    engagements = []
    upcoming_deadlines = []
    for row in rows:
        item = {key: row[key] for key in (
            "engagement_id", "client_id", "client_name", "tax_year", "return_type",
            "assigned_preparer", "engagement_start_date", "filing_deadline",
            "engagement_status",
        )}
        item["outstanding_item_count"] = row["outstanding_item_count"]
        engagements.append(item)

        if not row["filing_deadline"]:
            continue
        deadline = date.fromisoformat(row["filing_deadline"])
        if today <= deadline <= window_end:
            upcoming_deadlines.append({
                "engagement_id": row["engagement_id"],
                "client_id": row["client_id"],
                "client_name": row["client_name"],
                "tax_year": row["tax_year"],
                "return_type": row["return_type"],
                "filing_deadline": row["filing_deadline"],
                "days_remaining": (deadline - today).days,
                "engagement_status": row["engagement_status"],
            })

    active = [item for item in engagements if item["engagement_status"] in ACTIVE_STATUSES]
    completed = [item for item in engagements if item["engagement_status"] == "Completed"]
    waiting = sum(item["engagement_status"] == "Waiting on Client" for item in active)
    return {
        "has_engagements": bool(engagements),
        "summary": {
            "active_engagements": len(active),
            "waiting_on_client": waiting,
            "deadlines_within_14_days": len(upcoming_deadlines),
            "completed_engagements": len(completed),
        },
        "active_engagements": active,
        "completed_engagements": completed,
        "upcoming_deadlines": upcoming_deadlines,
    }


@dashboard_bp.get("")
def view_dashboard():
    return jsonify(dashboard=get_dashboard_data())
