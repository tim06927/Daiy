"""Flask web app for grounded AI product recommendations.

Provides a user interface for bike component upgrade recommendations using
LLM-powered suggestions grounded in real product inventory.
"""

import base64
import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request

# Load environment variables from .env file (explicitly specify path)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Handle imports for both direct execution and package import
# When run directly (python web/app.py), __package__ is None
# When imported as module (from web.app import app), __package__ is "web"
if __package__ is None or __package__ == "":
    # Running directly - add parent to path for absolute imports
    sys.path.insert(0, str(Path(__file__).parent))
    from config import (
        FLASK_DEBUG,
        FLASK_HOST,
        FLASK_PORT,
        SHOW_DEMO_NOTICE,
    )
else:
    # Running as package
    from .config import (
        FLASK_DEBUG,
        FLASK_HOST,
        FLASK_PORT,
        SHOW_DEMO_NOTICE,
    )

app = Flask(__name__)

# Register API blueprint (only when running as package to avoid circular imports)
if __package__ is not None and __package__ != "":
    from .api import api
    app.register_blueprint(api)


# ---------- BASIC AUTH ----------


def _basic_auth_creds() -> tuple[Optional[str], Optional[str]]:
    """Get demo credentials from environment."""
    return os.getenv("DEMO_USER"), os.getenv("DEMO_PASS")


def _unauthorized() -> Response:
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="Login Required"'},
    )


@app.before_request
def require_basic_auth() -> Optional[Response]:
    """
    Enforce HTTP Basic Auth for all routes.
    Skips enforcement if credentials are not configured (DEMO_USER/DEMO_PASS unset).
    """
    user, password = _basic_auth_creds()
    if not user or not password:
        return None  # auth disabled

    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return _unauthorized()

    try:
        decoded = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
        username, passwd = decoded.split(":", 1)
    except Exception:
        return _unauthorized()

    if username == user and passwd == password:
        return None
    return _unauthorized()


# ---------- FLASK ROUTES ----------


@app.route("/", methods=["GET"])
def index() -> str:
    """Render the main recommendation page."""
    return render_template("index.html", show_demo_notice=SHOW_DEMO_NOTICE)


if __name__ == "__main__":
    # For local demo use debug=True if you like
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
