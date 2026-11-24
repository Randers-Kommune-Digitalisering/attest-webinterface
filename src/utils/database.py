"""Temporary compatibility adapter for shared database configuration."""

from __future__ import annotations

from collections.abc import Mapping

from rkdigi import DatabaseManager as RkDigiDatabaseManager


class DatabaseConfigurationError(ValueError):
    """Invalid database settings supplied to the manager factory."""


class DatabaseManager(RkDigiDatabaseManager):
    """Local adapter matching the planned rkdigi ``from_config`` API."""

    @classmethod
    def from_config(
        cls: type[DatabaseManager],
        config: Mapping[str, object],
        *,
        profile_name: str,
        prefix: str,
    ) -> DatabaseManager:
        """
        Create a manager using the database settings for a config prefix.

        Translates a prefixed application configuration into the connection
        settings for a database manager profile. Validates the selected
        settings before initializing the manager so configuration errors are
        reported during application setup.

        :param config: Mapping containing database connection settings.
        :param profile_name: Non-empty manager profile name used by rkdigi.
        :param prefix: Prefix for the ``TYPE``, ``HOST``, ``PORT``, ``NAME``,
            ``USERNAME``, and ``PASSWORD`` settings.
        :return: A manager initialized with the validated connection settings.
        :raises DatabaseConfigurationError: If a required setting is missing
            or a setting has an invalid value.
        """
        normalized_prefix = prefix.strip().rstrip("_")
        if not normalized_prefix:
            raise DatabaseConfigurationError(
                "Database setting prefix is required",
            )

        if not profile_name.strip():
            raise DatabaseConfigurationError("Database profile name is required")

        required_suffixes = ("TYPE", "HOST", "NAME", "USERNAME", "PASSWORD")
        required_keys = [
            f"{normalized_prefix}_{suffix}"
            for suffix in required_suffixes
        ]
        settings = {
            key: value
            for key in required_keys
            if isinstance((value := config.get(key)), str) and value.strip()
        }
        missing_keys = [key for key in required_keys if key not in settings]
        if missing_keys:
            raise DatabaseConfigurationError(
                "Missing database configuration: " + ", ".join(missing_keys),
            )

        db_type = settings[f"{normalized_prefix}_TYPE"].strip().lower()
        if db_type not in {"postgres", "mssql"}:
            raise DatabaseConfigurationError(
                f"{normalized_prefix}_TYPE must be 'postgres' or 'mssql'",
            )

        port_key = f"{normalized_prefix}_PORT"
        port_value = config.get(port_key)
        if port_value is None or (
            isinstance(port_value, str) and not port_value.strip()
        ):
            port = None
        elif isinstance(port_value, bool) or not isinstance(
            port_value,
            (str, int),
        ):
            raise DatabaseConfigurationError(
                f"{port_key} must be a valid port number",
            )
        else:
            try:
                port = int(port_value)
            except ValueError as error:
                raise DatabaseConfigurationError(
                    f"{port_key} must be a valid port number",
                ) from error

            if not 1 <= port <= 65535:
                raise DatabaseConfigurationError(
                    f"{port_key} must be between 1 and 65535",
                )

        return cls(
            profile_name=profile_name,
            db_type=db_type,
            database=settings[f"{normalized_prefix}_NAME"].strip(),
            username=settings[f"{normalized_prefix}_USERNAME"].strip(),
            password=settings[f"{normalized_prefix}_PASSWORD"],
            host=settings[f"{normalized_prefix}_HOST"].strip(),
            port=port,
        )
