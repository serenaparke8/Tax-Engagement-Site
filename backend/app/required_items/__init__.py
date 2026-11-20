from flask import Blueprint

required_items_bp = Blueprint("required_items", __name__)

from . import routes  # noqa: E402,F401
