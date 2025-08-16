"""Local file-based token storage for development."""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)


class LocalTokenStorage:
    """Local file storage for tokens during development."""
    
    def __init__(self):
        """Initialize local storage."""
        # Create a .tokens directory in the project root
        self.tokens_dir = Path(__file__).parent.parent.parent / ".tokens"
        self.tokens_dir.mkdir(exist_ok=True)
        
        # Add to .gitignore if not already there
        gitignore_path = Path(__file__).parent.parent.parent / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                content = f.read()
            if '.tokens/' not in content:
                with open(gitignore_path, 'a') as f:
                    f.write('\n# Token storage (local development)\n.tokens/\n')
                    
    def save_token(self, api_name: str, token_data: Dict[str, Any]):
        """
        Save token to local file.
        
        Args:
            api_name: The API name (spotify or ebay)
            token_data: Token data to save
        """
        file_path = self.tokens_dir / f"{api_name}_token.json"
        
        # Convert datetime objects to ISO format strings
        serializable_data = {}
        for key, value in token_data.items():
            if isinstance(value, datetime):
                serializable_data[key] = value.isoformat()
            else:
                serializable_data[key] = value
                
        try:
            with open(file_path, 'w') as f:
                json.dump(serializable_data, f, indent=2)
            logger.info(f"Saved {api_name} token to local file: {file_path}")
        except Exception as e:
            logger.error(f"Error saving {api_name} token to local file: {e}")
            raise
            
    def load_token(self, api_name: str) -> Optional[Dict[str, Any]]:
        """
        Load token from local file.
        
        Args:
            api_name: The API name (spotify or ebay)
            
        Returns:
            Token data or None if not found
        """
        file_path = self.tokens_dir / f"{api_name}_token.json"
        
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            # Convert ISO format strings back to datetime objects
            for key in ['expires_at', 'created_at', 'updated_at']:
                if key in data and isinstance(data[key], str):
                    data[key] = datetime.fromisoformat(data[key])
                    
            return data
        except Exception as e:
            logger.error(f"Error loading {api_name} token from local file: {e}")
            return None
            
    def delete_token(self, api_name: str):
        """
        Delete token file.
        
        Args:
            api_name: The API name (spotify or ebay)
        """
        file_path = self.tokens_dir / f"{api_name}_token.json"
        if file_path.exists():
            file_path.unlink()
            logger.info(f"Deleted {api_name} token file")
