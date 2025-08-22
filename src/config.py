"""Configuration module for Draft Maker application."""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Google Cloud Configuration
    gcp_project_id: str = Field(default=os.getenv("GCP_PROJECT_ID", "draft-maker-468923"), env="GCP_PROJECT_ID")
    gcp_region: str = Field(default=os.getenv("GCP_REGION", "us-west1"), env="GCP_REGION")
    storage_bucket_name: str = Field(default=os.getenv("STORAGE_BUCKET_NAME", "draft-maker-bucket"), env="STORAGE_BUCKET_NAME")
    
    # Firestore Collections
    firestore_collection_mbid: str = Field(
        default=os.getenv("FIRESTORE_COLLECTION_MBID", "mbid_cache"),
        env="FIRESTORE_COLLECTION_MBID"
    )
    firestore_collection_logs: str = Field(
        default=os.getenv("FIRESTORE_COLLECTION_LOGS", "function_logs"),
        env="FIRESTORE_COLLECTION_LOGS"
    )
    firestore_collection_tokens: str = Field(default="api_tokens", env="FIRESTORE_COLLECTION_TOKENS")
    firestore_collection_processed_files: str = Field(
        default="processed_files", 
        env="FIRESTORE_COLLECTION_PROCESSED_FILES"
    )
    firestore_collection_draft_listings: str = Field(
        default="draft_listings",
        env="FIRESTORE_COLLECTION_DRAFT_LISTINGS"
    )
    
    # API Credentials
    # Discogs - Using Personal Access Token for authentication
    discogs_personal_access_token: str = Field(
        default=os.getenv("DISCOGS_PERSONAL_ACCESS_TOKEN", ""),
        env="DISCOGS_PERSONAL_ACCESS_TOKEN"
    )
    
    # eBay
    ebay_app_id: str = Field(default=os.getenv("EBAY_APP_ID", ""), env="EBAY_APP_ID")
    ebay_dev_id: str = Field(default=os.getenv("EBAY_DEV_ID", ""), env="EBAY_DEV_ID")
    ebay_cert_id: str = Field(default=os.getenv("EBAY_CERT_ID", ""), env="EBAY_CERT_ID")
    ebay_client_secret: str = Field(default=os.getenv("EBAY_CLIENT_SECRET", ""), env="EBAY_CLIENT_SECRET")
    
    # Spotify
    spotify_client_id: str = Field(default=os.getenv("SPOTIFY_CLIENT_ID", ""), env="SPOTIFY_CLIENT_ID")
    spotify_client_secret: str = Field(default=os.getenv("SPOTIFY_CLIENT_SECRET", ""), env="SPOTIFY_CLIENT_SECRET")
    
    # MusicBrainz
    musicbrainz_user_agent: str = Field(
        default=os.getenv("MUSICBRAINZ_USER_AGENT", "draftmaker/1.0 ( benjaminabramowitz@gmail.com )"),
        env="MUSICBRAINZ_USER_AGENT"
    )
    
    # Application Settings
    environment: str = Field(default=os.getenv("ENVIRONMENT", "development"), env="ENVIRONMENT")
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"), env="LOG_LEVEL")
    
    # eBay Listing Policies (for creating drafts)
    ebay_fulfillment_policy_id: str = Field(default="381603015022", env="EBAY_FULFILLMENT_POLICY_ID")
    ebay_payment_policy_id: str = Field(default="345889112022", env="EBAY_PAYMENT_POLICY_ID")
    ebay_return_policy_id: str = Field(default="345889054022", env="EBAY_RETURN_POLICY_ID")
    ebay_category_id: str = Field(default="176984", env="EBAY_CATEGORY_ID")  # Music CDs category
    
    # Test UPC codes
    test_upc_codes: list[str] = Field(
        default_factory=lambda: [
            "722975007524",
            "638812705228",
            "724383030422",
            "652637281521",
            "606949007423",
            "074645276922",
            "017837709525",
            "075678304026",
            "074646850626",
            "075992412025"
        ]
    )
    
    class Config:
        """Pydantic configuration."""
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env


# Create a global settings instance
settings = Settings()

# Load secrets from Secret Manager in production
def _load_production_secrets():
    """Load secrets from Google Secret Manager if in production."""
    if settings.environment.lower() == "production":
        try:
            from src.utils.secrets_loader import get_secrets_loader
            loader = get_secrets_loader()
            secrets = loader.load_all_secrets()
            
            # Update settings with secrets from Secret Manager
            if secrets.get("discogs_personal_access_token"):
                settings.discogs_personal_access_token = secrets["discogs_personal_access_token"]
            if secrets.get("ebay_app_id"):
                settings.ebay_app_id = secrets["ebay_app_id"]
            if secrets.get("ebay_dev_id"):
                settings.ebay_dev_id = secrets["ebay_dev_id"]
            if secrets.get("ebay_cert_id"):
                settings.ebay_cert_id = secrets["ebay_cert_id"]
            if secrets.get("ebay_client_secret"):
                settings.ebay_client_secret = secrets["ebay_client_secret"]
            if secrets.get("spotify_client_id"):
                settings.spotify_client_id = secrets["spotify_client_id"]
            if secrets.get("spotify_client_secret"):
                settings.spotify_client_secret = secrets["spotify_client_secret"]
                
        except Exception as e:
            print(f"Warning: Failed to load secrets from Secret Manager: {e}")

# Load production secrets on module import
_load_production_secrets()


def get_settings() -> Settings:
    """Get the application settings instance."""
    return settings


def is_production() -> bool:
    """Check if the application is running in production."""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if the application is running in development."""
    return settings.environment.lower() == "development"


REDIRECT_URI = "https://draft-maker-541660382374.us-west1.run.app/oauth/callback"