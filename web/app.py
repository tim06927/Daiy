"""Flask web app for grounded AI product recommendations.

Provides a user interface for bike component upgrade recommendations using
LLM-powered suggestions grounded in real product inventory.
"""

import base64
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from dotenv import load_dotenv
from flask import Flask, Response, redirect, render_template, request, session, url_for

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
    from privacy import run_lazy_purge, run_startup_purge
else:
    # Running as package
    from .config import (
        FLASK_DEBUG,
        FLASK_HOST,
        FLASK_PORT,
        SHOW_DEMO_NOTICE,
    )
    from .privacy import run_lazy_purge, run_startup_purge

app = Flask(__name__)

# Configure session for consent cookie (strictly necessary, no extra tracking)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(32).hex())
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# Use secure cookies in production (when not localhost)
app.config["SESSION_COOKIE_SECURE"] = os.getenv("FLASK_ENV") == "production"

# Run startup purge (schema migration + initial purge if needed)
run_startup_purge()

# Register API blueprint
if __package__ is not None and __package__ != "":
    # Running as package
    from .api import api
else:
    # Running directly
    from api import api

app.register_blueprint(api)


# ---------- CONSENT ALLOWLIST ----------

# Paths that don't require consent
CONSENT_ALLOWLIST = {
    "/consent",
    "/privacy",
    "/robots.txt",
    "/health",
}

# Prefixes that don't require consent
CONSENT_ALLOWLIST_PREFIXES = (
    "/static/",
)


def _path_requires_consent(path: str) -> bool:
    """Check if a path requires consent."""
    if path in CONSENT_ALLOWLIST:
        return False
    for prefix in CONSENT_ALLOWLIST_PREFIXES:
        if path.startswith(prefix):
            return False
    return True


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


@app.before_request
def require_consent() -> Optional[Response]:
    """Enforce consent before allowing access to tracking routes.

    Redirects to /consent if user hasn't consented and path requires consent.
    Also triggers lazy daily purge.
    """
    # Run lazy purge on first request of the day
    run_lazy_purge()

    # Check if path requires consent
    if not _path_requires_consent(request.path):
        return None

    # Check if user has consented
    if session.get("alpha_consent"):
        return None

    # Redirect to consent page with return URL
    next_url = request.full_path if request.query_string else request.path
    return redirect(url_for("consent", next=next_url))


# ---------- FLASK ROUTES ----------


@app.route("/consent", methods=["GET", "POST"])
def consent() -> Union[str, Response]:
    """Consent gate page.

    GET: Show consent form
    POST: Process consent and redirect to original destination
    """
    next_url = request.args.get("next", "/")

    if request.method == "POST":
        if request.form.get("consent"):
            # Store consent in session
            session["alpha_consent"] = True
            session["alpha_consent_ts"] = datetime.now(timezone.utc).isoformat()

            # Redirect to original destination
            post_next = request.form.get("next", "/")
            return redirect(post_next)
        # If checkbox not checked, show form again

    return render_template("consent.html", next_url=next_url)


@app.route("/privacy", methods=["GET"])
def privacy() -> str:
    """Render the privacy policy page."""
    return render_template("privacy.html")


@app.route("/robots.txt", methods=["GET"])
def robots_txt() -> Response:
    """Return robots.txt to discourage indexing."""
    content = "User-agent: *\nDisallow: /\n"
    return Response(content, mimetype="text/plain")


@app.route("/health", methods=["GET"])
def health() -> Response:
    """Health check endpoint for monitoring."""
    return Response("ok", mimetype="text/plain")


@app.route("/", methods=["GET"])
def index() -> str:
    """Render the main recommendation page."""
    return render_template("index.html", show_demo_notice=SHOW_DEMO_NOTICE)


if __name__ == "__main__":
    # For local demo use debug=True if you like
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
