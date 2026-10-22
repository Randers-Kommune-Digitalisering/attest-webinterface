"""
Main entry point for the Flask application.
"""
from authlib.integrations.flask_client import OAuth
from flask import Flask, Response, jsonify, redirect, request, session, url_for
from backend.src.utils.config import get_config_class_path
from backend.src.api_endpoints import api
from backend.src.utils.logging import error_counter, set_logging_configuration

REQUIRED_ROLE = "attest-admin"
PUBLIC_PATHS = {"/api/login", "/api/auth", "/healthz", "/metrics"}


def create_app(config_object: str = "utils.config.DevConfig") -> Flask:
    """
    Create and configure the Flask application.

    :param config_object: The configuration object to use.
    :return: The Flask application instance.
    :raises RuntimeError: If Keycloak is disabled in an environment where dummy authentication is not allowed,
    or if required Keycloak environment variables are missing.
    """
    app = Flask(__name__)
    app.config.from_object(config_object)

    keycloak_url = app.config["KEYCLOAK_URL"]
    keycloak_realm = app.config["KEYCLOAK_REALM"]
    client_id = app.config["KEYCLOAK_CLIENT_ID"]
    client_secret = app.config["KEYCLOAK_CLIENT_SECRET"]

    debug = bool(app.config.get("DEBUG", False))
    set_logging_configuration(debug=debug)

    app.register_blueprint(api)

    if app.config["DISABLE_KEYCLOAK"]:
        if not app.config.get("ALLOW_DUMMY_AUTH", False):
            raise RuntimeError("DISABLE_KEYCLOAK is not allowed in this environment")

        # Dummy authentication for development/testing without Keycloak
        @app.before_request
        def set_dummy_user() -> None:
            if "user" not in session:
                session["user"] = {
                    "name": "Test Testsen",
                    "email": "test@test.dk",
                    "roles": [REQUIRED_ROLE],
                }

        @app.route("/api/userinfo")
        def user_info() -> Response:
            return jsonify(session["user"])

    else:
        # Setup Keycloak OAuth
        # Verify required environment variables for Keycloak
        secret_key = app.config.get("SECRET_KEY")
        if not secret_key or secret_key == "CHANGE_ME":
            raise RuntimeError("Missing or invalid SECRET_KEY environment variable")

        if not all([keycloak_url, client_id, client_secret, keycloak_realm]):
            raise RuntimeError("Missing environment variable(s) for Keycloak - set DISABLE_KEYCLOAK=true to run without Keycloak")

        oauth = OAuth(app)
        oauth.register(
            name="keycloak",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url=(
                f'{keycloak_url.rstrip("/")}/realms/{keycloak_realm}'
                "/.well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid profile email"},
        )

        @app.before_request
        def check_authenticated() -> tuple[Response, int] | None:
            if "user" not in session and request.path not in PUBLIC_PATHS:
                return jsonify({"success": False, "error": "Not authenticated"}), 401

            return None

        @app.route("/api/login")
        def login() -> Response:
            redirect_uri = url_for("auth", _external=True)
            return oauth.keycloak.authorize_redirect(redirect_uri)

        @app.route("/api/auth")
        def auth() -> tuple[Response, int] | Response:
            token = oauth.keycloak.authorize_access_token()
            user = _minimal_userinfo(token.get("userinfo"), client_id)
            if REQUIRED_ROLE not in user.get("roles", []):
                session.clear()
                return jsonify({"success": False, "error": "Forbidden"}), 403
            # Store minimal user info to avoid exceeding browser cookie size limits
            session["user"] = user
            return redirect("/")

        @app.route("/api/userinfo")
        def user_info() -> Response:
            return jsonify(session["user"])

    @app.after_request
    def count_server_errors(response: Response) -> Response:
        """
        Count server-side (5xx) HTTP responses using Prometheus metrics.

        :param response: The outgoing Flask response object.
        :return: The unmodified response.
        """
        if 500 <= response.status_code <= 599:
            error_counter.labels(
                endpoint=request.path,
                status=str(response.status_code),
            ).inc()

        return response

    @app.get("/healthz")
    def healthz() -> tuple[dict, int]:
        """
        Health check endpoint.

        :return: A JSON response indicating the health status.
        """
        return jsonify({"status": "ok"}), 200

    return app


def _minimal_userinfo(userinfo: dict | None, client_id: str) -> dict:
    if not isinstance(userinfo, dict):
        return {}

    roles = (
        userinfo.get("resource_access", {})
        .get(client_id, {})
        .get("roles", [])
    )
    if not isinstance(roles, list):
        roles = []

    return {
        "name": userinfo.get("name"),
        "email": userinfo.get("email"),
        "roles": roles,
    }


# WSGI entrypoint for `gunicorn --chdir src main:app`
app = create_app(config_object=get_config_class_path())


if __name__ == "__main__":  # pragma: no cover
    app.run(debug=app.config["DEBUG"], host="0.0.0.0", port=int(app.config.get("PORT")))
