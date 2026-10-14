from flask import Blueprint

leave_bp = Blueprint('leave', __name__, url_prefix='/leave')

from app.leave import routes

