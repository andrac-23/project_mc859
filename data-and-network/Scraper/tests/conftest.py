"""
Test configuration and fixtures for Google Reviews Scraper tests.
"""

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def config():
    """Load configuration from config.yaml"""
    config_path = Path(__file__).parent.parent / 'config.yaml'
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


@pytest.fixture
def mongodb_config(config):
    """Extract MongoDB configuration"""
    return config.get('mongodb', {})


@pytest.fixture
def s3_config(config):
    """Extract S3 configuration"""
    return config.get('s3', {})


@pytest.fixture
def use_mongodb(config):
    """Check if MongoDB is enabled"""
    return config.get('use_mongodb', False)


@pytest.fixture
def use_s3(config):
    """Check if S3 is enabled"""
    return config.get('use_s3', False)
