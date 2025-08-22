"""
Utility for loading secrets from Google Secret Manager in production.
Falls back to environment variables for local development.
"""

import os
from typing import Optional
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Try to import Secret Manager
try:
    from google.cloud import secretmanager

    SECRET_MANAGER_AVAILABLE = True
except ImportError:
    SECRET_MANAGER_AVAILABLE = False
    logger.info("Google Secret Manager not available, using environment variables")


class SecretsLoader:
    """Loads secrets from Secret Manager in production or env vars locally."""

    def __init__(self):
        """Initialize the secrets loader."""
        self.project_id = os.getenv("GCP_PROJECT_ID", "draft-maker-468923")
        self.environment = os.getenv("ENVIRONMENT", "development")

        if SECRET_MANAGER_AVAILABLE and self.environment == "production":
            try:
                self.client = secretmanager.SecretManagerServiceClient()
                self.use_secret_manager = True
                logger.info("Using Google Secret Manager for secrets")
            except Exception as e:
                logger.warning(f"Failed to initialize Secret Manager client: {e}")
                self.client = None
                self.use_secret_manager = False
        else:
            self.client = None
            self.use_secret_manager = False
            logger.info("Using environment variables for secrets")

    def get_secret(
        self, secret_name: str, env_var_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Get a secret value from Secret Manager or environment variable.

        Args:
            secret_name: Name of the secret in Secret Manager
            env_var_name: Name of the environment variable (defaults to secret_name)

        Returns:
            The secret value or None if not found
        """
        if env_var_name is None:
            env_var_name = secret_name

        # Try Secret Manager first in production
        if self.use_secret_manager and self.client:
            try:
                # Build the resource name
                name = (
                    f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
                )

                # Access the secret
                response = self.client.access_secret_version(request={"name": name})
                secret_value = response.payload.data.decode("UTF-8")

                if secret_value:
                    logger.debug(
                        f"Successfully loaded secret {secret_name} from Secret Manager"
                    )
                    return secret_value

            except Exception as e:
                logger.warning(
                    f"Failed to load secret {secret_name} from Secret Manager: {e}"
                )

        # Fall back to environment variable
        env_value = os.getenv(env_var_name)
        if env_value:
            logger.debug(
                f"Loaded secret {secret_name} from environment variable {env_var_name}"
            )
            return env_value

        logger.warning(
            f"Secret {secret_name} not found in Secret Manager or environment"
        )
        return None

    def load_all_secrets(self) -> dict:
        """
        Load all required secrets for the application.

        Returns:
            Dictionary of secret values
        """
        secrets = {
            "discogs_personal_access_token": self.get_secret(
                "DISCOGS_PERSONAL_ACCESS_TOKEN"
            ),
            "ebay_app_id": self.get_secret("EBAY_APP_ID"),
            "ebay_dev_id": self.get_secret("EBAY_DEV_ID"),
            "ebay_cert_id": self.get_secret("EBAY_CERT_ID"),
            "ebay_client_secret": self.get_secret("EBAY_CLIENT_SECRET"),
            "spotify_client_id": self.get_secret("SPOTIFY_CLIENT_ID"),
            "spotify_client_secret": self.get_secret("SPOTIFY_CLIENT_SECRET"),
        }

        # Log which secrets were successfully loaded (without revealing values)
        loaded = [k for k, v in secrets.items() if v]
        missing = [k for k, v in secrets.items() if not v]

        if loaded:
            logger.info(f"Successfully loaded secrets: {', '.join(loaded)}")
        if missing:
            logger.warning(f"Missing secrets: {', '.join(missing)}")

        return secrets


# Singleton instance
_secrets_loader = None


def get_secrets_loader() -> SecretsLoader:
    """Get or create the singleton SecretsLoader instance."""
    global _secrets_loader
    if _secrets_loader is None:
        _secrets_loader = SecretsLoader()
    return _secrets_loader
