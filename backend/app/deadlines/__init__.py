from flask import Blueprint


deadlines_bp = Blueprint("deadlines", __name__)

from . import routes
