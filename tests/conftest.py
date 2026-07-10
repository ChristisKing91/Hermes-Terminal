"""
Test fixtures and configuration
"""

import pytest
import tempfile
from pathlib import Path


@pytest.fixture
def temp_config_dir():
    """Create temporary config directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_db_path(temp_config_dir):
    """Create temporary database path"""
    return temp_config_dir / "test.db"
