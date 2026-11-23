"""
Environment configuration management for the Flask application.
"""
import os

from dotenv import load_dotenv

# loads .env file, will not overide already set enviroment variables (will do nothing when testing, building and deploying)
load_dotenv()


class Config:
    """
    Base configuration class. All other configuration classes should inherit from this.
    """
    SECRET_KEY = os.getenv("SECRET_KEY", "CHANGE_ME")
    POD_NAME = os.getenv("POD_NAME", "pod_name_not_set")
    PORT = int(os.getenv("PORT", "8080"))

    DISABLE_KEYCLOAK = os.getenv("DISABLE_KEYCLOAK", "False").lower() in ("true", "1", "t")

    KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "").strip()
    KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "").strip()
    KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID", "").strip()
    KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET", "").strip()

    SESSION_COOKIE_SAMESITE = "Lax"


# DevConfig will be used when FLASK_ENV=dev or is not set
class DevConfig(Config):
    """
    Development configuration.
    """
    DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "t")
    ALLOW_DUMMY_AUTH = True


# ProdConfig will be used when FLASK_ENV=prod
class ProdConfig(Config):
    """
    Production configuration.
    """
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "t")
    ALLOW_DUMMY_AUTH = False
    SESSION_COOKIE_SECURE = True


def get_config_class_path() -> str:
    """
    Get the full class path of the configuration class based on the FLASK_ENV environment variable.

    :return: The full class path of the configuration class.
    :raises ValueError: If the FLASK_ENV value is invalid.
    """
    name = _get_config_name()

    if name.lower() == "prod":
        return "utils.config.ProdConfig"
    elif name.lower() == "dev":
        return "utils.config.DevConfig"

    raise ValueError(f"Invalid FLASK_ENV value: {name}. Expected 'dev' or 'prod'.")


def _get_config_name() -> str:
    """
    Get the name of the configuration based on the FLASK_ENV environment variable.

    :return: The name of the configuration.
    """
    return os.getenv("FLASK_ENV", "dev").lower()
