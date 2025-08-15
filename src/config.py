"""Configuration module for Draft Maker application."""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file for local development
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Google Cloud Configuration
    gcp_project_id: str = Field(default=os.getenv("GCP_PROJECT_ID", ""), env="GCP_PROJECT_ID")
    gcp_region: str = Field(default=os.getenv("GCP_REGION", "us-west1"), env="GCP_REGION")
    storage_bucket_name: str = Field(default=os.getenv("STORAGE_BUCKET_NAME", ""), env="STORAGE_BUCKET_NAME")
    
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
    # Discogs
    discogs_consumer_key: str = Field(default=os.getenv("DISCOGS_CONSUMER_KEY", ""), env="DISCOGS_CONSUMER_KEY")
    discogs_consumer_secret: str = Field(
        default=os.getenv("DISCOGS_CONSUMER_SECRET", ""),
        env="DISCOGS_CONSUMER_SECRET"
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
    ebay_fulfillment_policy_id: str = Field(default="345923687022", env="EBAY_FULFILLMENT_POLICY_ID")
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


def get_settings() -> Settings:
    """Get the application settings instance."""
    return settings


def is_production() -> bool:
    """Check if the application is running in production."""
    return settings.environment.lower() == "production"


def is_development() -> bool:
    """Check if the application is running in development."""
    return settings.environment.lower() == "development"
