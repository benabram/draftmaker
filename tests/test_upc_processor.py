"""Tests for the UPC processor component."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.components.upc_processor import UPCProcessor


class TestUPCProcessor:
    """Test suite for UPC processor."""
    
    @pytest.fixture
    def processor(self):
        """Create a UPC processor instance with mocked GCS client."""
        with patch('src.components.upc_processor.storage.Client'):
            processor = UPCProcessor()
            processor.storage_client = Mock()
            return processor
    
    def test_validate_upc_valid_12_digits(self, processor):
        """Test validation of valid 12-digit UPC."""
        assert processor.validate_upc("123456789012") == True
    
    def test_validate_upc_valid_13_digits(self, processor):
        """Test validation of valid 13-digit UPC."""
        assert processor.validate_upc("1234567890123") == True
    
    def test_validate_upc_invalid_length(self, processor):
        """Test validation rejects invalid length."""
        assert processor.validate_upc("12345") == False
        assert processor.validate_upc("12345678901234") == False
    
    def test_validate_upc_non_numeric(self, processor):
        """Test validation rejects non-numeric characters."""
        assert processor.validate_upc("12345678901A") == False
        assert processor.validate_upc("ABCDEFGHIJKL") == False
    
    def test_validate_upc_empty(self, processor):
        """Test validation rejects empty string."""
        assert processor.validate_upc("") == False
        assert processor.validate_upc("   ") == False
    
    def test_validate_upc_with_whitespace(self, processor):
        """Test validation handles whitespace."""
        assert processor.validate_upc("  123456789012  ") == True
        assert processor.validate_upc("\n123456789012\t") == True
    
    def test_calculate_checksum_valid_upc12(self, processor):
        """Test checksum calculation for valid UPC-A."""
        # Real UPC with valid checksum
        assert processor.calculate_checksum("036000291452") == True
    
    def test_calculate_checksum_invalid_upc12(self, processor):
        """Test checksum calculation for invalid UPC-A."""
        assert processor.calculate_checksum("036000291450") == False
    
    def test_calculate_checksum_valid_ean13(self, processor):
        """Test checksum calculation for valid EAN-13."""
        # Real EAN with valid checksum
        assert processor.calculate_checksum("5901234123457") == True
    
    def test_calculate_checksum_invalid_ean13(self, processor):
        """Test checksum calculation for invalid EAN-13."""
        assert processor.calculate_checksum("5901234123450") == False
    
    @patch('src.components.upc_processor.Path')
    def test_load_upcs_from_local_txt_success(self, mock_path, processor):
        """Test loading UPCs from local text file."""
        # Setup mock file
        mock_path.return_value.exists.return_value = True
        mock_file_content = """123456789012
987654321098
invalid_upc
456789012345

789012345678"""
        
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            upcs = processor.load_upcs_from_local_txt("test.txt")
        
        assert len(upcs) == 4  # Should skip invalid and empty
        assert "123456789012" in upcs
        assert "987654321098" in upcs
        assert "456789012345" in upcs
        assert "789012345678" in upcs
    
    @patch('src.components.upc_processor.Path')
    def test_load_upcs_from_local_txt_file_not_found(self, mock_path, processor):
        """Test handling of missing local file."""
        mock_path.return_value.exists.return_value = False
        
        upcs = processor.load_upcs_from_local_txt("missing.txt")
        assert upcs == []
    
    def test_load_upcs_from_gcs_success(self, processor):
        """Test loading UPCs from GCS."""
        # Setup mock GCS client
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = """123456789012
987654321098
456789012345"""
        
        mock_bucket.blob.return_value = mock_blob
        processor.storage_client.bucket.return_value = mock_bucket
        
        upcs = processor.load_upcs_from_gcs("test-bucket", "upcs.txt")
        
        assert len(upcs) == 3
        assert "123456789012" in upcs
        assert "987654321098" in upcs
        assert "456789012345" in upcs
        
        # Verify GCS methods were called
        processor.storage_client.bucket.assert_called_with("test-bucket")
        mock_bucket.blob.assert_called_with("upcs.txt")
        mock_blob.exists.assert_called_once()
        mock_blob.download_as_text.assert_called_once()
    
    def test_load_upcs_from_gcs_file_not_found(self, processor):
        """Test handling of missing GCS file."""
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.exists.return_value = False
        
        mock_bucket.blob.return_value = mock_blob
        processor.storage_client.bucket.return_value = mock_bucket
        
        upcs = processor.load_upcs_from_gcs("test-bucket", "missing.txt")
        
        assert upcs == []
        mock_blob.download_as_text.assert_not_called()
    
    def test_load_upcs_from_gcs_with_empty_lines(self, processor):
        """Test GCS loader handles empty lines correctly."""
        mock_bucket = Mock()
        mock_blob = Mock()
        mock_blob.exists.return_value = True
        mock_blob.download_as_text.return_value = """123456789012

987654321098


456789012345"""
        
        mock_bucket.blob.return_value = mock_blob
        processor.storage_client.bucket.return_value = mock_bucket
        
        upcs = processor.load_upcs_from_gcs("test-bucket", "upcs.txt")
        
        assert len(upcs) == 3  # Should skip empty lines
        assert "123456789012" in upcs
        assert "987654321098" in upcs
        assert "456789012345" in upcs


def mock_open(read_data=""):
    """Helper to create a mock file object."""
    from unittest.mock import mock_open as _mock_open
    return _mock_open(read_data=read_data)
