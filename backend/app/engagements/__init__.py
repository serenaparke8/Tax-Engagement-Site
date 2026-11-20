from flask import Blueprint

engagements_bp = Blueprint("engagements", __name__)

from . import routes  # noqa: E402,F401
