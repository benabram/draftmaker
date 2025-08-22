"""UPC processor component for reading and validating UPC codes."""

import re
from typing import List, Optional
from pathlib import Path
from google.cloud import storage
import tempfile

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class UPCProcessor:
    """Processes UPC codes from text files in Google Cloud Storage."""

    def __init__(self):
        """Initialize the UPC processor."""
        self.upc_pattern = re.compile(r"^\d{12,13}$")
        # Initialize GCS client
        self.storage_client = storage.Client()

    def validate_upc(self, upc: str) -> bool:
        """
        Validate a UPC code.

        Args:
            upc: The UPC code to validate

        Returns:
            True if valid, False otherwise
        """
        if not upc:
            return False

        # Remove any whitespace
        upc = upc.strip()

        # Check if it matches the pattern (12 or 13 digits)
        if not self.upc_pattern.match(upc):
            return False

        # Could add checksum validation here if needed
        return True

    def load_upcs_from_gcs(self, bucket_name: str, file_name: str) -> List[str]:
        """
        Load UPC codes from a text file in Google Cloud Storage.

        Args:
            bucket_name: Name of the GCS bucket
            file_name: Name of the text file in the bucket

        Returns:
            List of valid UPC codes
        """
        upcs = []

        try:
            # Get the bucket and blob
            bucket = self.storage_client.bucket(bucket_name)
            blob = bucket.blob(file_name)

            if not blob.exists():
                logger.error(f"File not found in GCS: gs://{bucket_name}/{file_name}")
                return upcs

            # Download the file content
            content = blob.download_as_text()

            # Process each line
            lines = content.strip().split("\n")
            for line_num, line in enumerate(lines, start=1):
                upc_value = line.strip()

                # Skip empty lines
                if not upc_value:
                    continue

                # Validate and add
                if self.validate_upc(upc_value):
                    upcs.append(upc_value)
                    logger.debug(f"Added UPC: {upc_value}")
                else:
                    logger.warning(f"Invalid UPC on line {line_num}: {upc_value}")

            logger.info(
                f"Loaded {len(upcs)} valid UPCs from gs://{bucket_name}/{file_name}"
            )

        except Exception as e:
            logger.error(f"Error reading file from GCS: {e}")

        return upcs

    def load_upcs_from_local_txt(self, file_path: str) -> List[str]:
        """
        Load UPC codes from a local text file (for testing).

        Args:
            file_path: Path to the text file

        Returns:
            List of valid UPC codes
        """
        upcs = []
        path = Path(file_path)

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return upcs

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, start=1):
                    upc_value = line.strip()

                    # Skip empty lines
                    if not upc_value:
                        continue

                    # Validate and add
                    if self.validate_upc(upc_value):
                        upcs.append(upc_value)
                        logger.debug(f"Added UPC: {upc_value}")
                    else:
                        logger.warning(f"Invalid UPC on line {line_num}: {upc_value}")

            logger.info(f"Loaded {len(upcs)} valid UPCs from {file_path}")

        except Exception as e:
            logger.error(f"Error reading text file: {e}")

        return upcs

    def calculate_checksum(self, upc: str) -> bool:
        """
        Calculate and validate UPC checksum.

        Args:
            upc: The UPC code to validate

        Returns:
            True if checksum is valid, False otherwise
        """
        if len(upc) not in [12, 13]:
            return False

        try:
            # For UPC-A (12 digits) or EAN-13 (13 digits)
            digits = [int(d) for d in upc]

            if len(upc) == 12:
                # UPC-A checksum calculation
                odd_sum = sum(digits[i] for i in range(0, 11, 2))
                even_sum = sum(digits[i] for i in range(1, 10, 2))
                total = odd_sum * 3 + even_sum
                check_digit = (10 - (total % 10)) % 10
                return check_digit == digits[-1]
            else:
                # EAN-13 checksum calculation
                odd_sum = sum(digits[i] for i in range(1, 12, 2))
                even_sum = sum(digits[i] for i in range(0, 12, 2))
                total = odd_sum * 3 + even_sum
                check_digit = (10 - (total % 10)) % 10
                return check_digit == digits[-1]

        except (ValueError, IndexError):
            return False


# Global processor instance
_upc_processor = None


def get_upc_processor() -> UPCProcessor:
    """Get the global UPC processor instance."""
    global _upc_processor
    if _upc_processor is None:
        _upc_processor = UPCProcessor()
    return _upc_processor
