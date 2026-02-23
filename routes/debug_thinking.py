from flask import Blueprint, jsonify
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

bp = Blueprint("thinking", __name__, url_prefix="/debug/thinking")

@bp.get("/ping")
def ping():
    return jsonify({"pong": True})


def register(app):
    app.register_blueprint(bp)
    return app