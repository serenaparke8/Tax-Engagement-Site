from flask import jsonify, request, session

from ..db import get_db
from ..engagements.routes import ENGAGEMENT_STATUSES
from . import reports_bp


REPORT_FIELDS = (
    "client_name",
    "engagement_id",
    "tax_year",
    "return_type",
    "assigned_preparer",
    "engagement_start_date",
    "filing_deadline",
    "engagement_status",
)


@reports_bp.before_request
def require_authenticated_user():
    if "user_id" not in session:
        return jsonify(error="Sign in to generate engagement reports."), 401
    return None


def report_select_sql(where=""):
    return f"""SELECT c.client_name, e.engagement_id, e.tax_year, e.return_type,
                      e.assigned_preparer, e.engagement_start_date,
                      e.filing_deadline, e.engagement_status
               FROM TAX_ENGAGEMENT AS e
               JOIN CLIENT AS c ON c.client_id = e.client_id
               {where}"""


@reports_bp.get("/criteria")
def list_report_criteria():
    db = get_db()
    tax_years = db.execute(
        "SELECT DISTINCT tax_year FROM TAX_ENGAGEMENT ORDER BY tax_year DESC"
    ).fetchall()
    preparers = db.execute(
        """SELECT DISTINCT assigned_preparer FROM TAX_ENGAGEMENT
           WHERE TRIM(assigned_preparer) <> ''
           ORDER BY assigned_preparer COLLATE NOCASE"""
    ).fetchall()
    return jsonify(criteria={
        "statuses": list(ENGAGEMENT_STATUSES),
        "tax_years": [row["tax_year"] for row in tax_years],
        "assigned_preparers": [row["assigned_preparer"] for row in preparers],
    })


@reports_bp.get("/engagements")
def generate_engagement_report():
    status = (request.args.get("status") or "").strip()
    if status and status not in ENGAGEMENT_STATUSES:
        return jsonify(error="Select one of the approved engagement statuses."), 400

    tax_year_text = (request.args.get("tax_year") or "").strip()
    tax_year = None
    if tax_year_text:
        try:
            tax_year = int(tax_year_text)
        except ValueError:
            return jsonify(error="Tax year must be a positive whole number."), 400
        if tax_year <= 0 or str(tax_year) != tax_year_text:
            return jsonify(error="Tax year must be a positive whole number."), 400

    assigned_preparer = (request.args.get("assigned_preparer") or "").strip()
    conditions = []
    parameters = []
    if status:
        conditions.append("e.engagement_status = ?")
        parameters.append(status)
    if tax_year is not None:
        conditions.append("e.tax_year = ?")
        parameters.append(tax_year)
    if assigned_preparer:
        conditions.append("e.assigned_preparer = ?")
        parameters.append(assigned_preparer)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = get_db().execute(
        report_select_sql(where) + " ORDER BY e.filing_deadline ASC, e.engagement_id ASC",
        parameters,
    ).fetchall()
    return jsonify(engagements=[{field: row[field] for field in REPORT_FIELDS} for row in rows])
