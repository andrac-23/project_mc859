"""
Configuration management for Google Maps Reviews Scraper.
"""

import logging

# Configure logging - can be overridden by environment variable
import os
from pathlib import Path
from typing import Any, Dict

import yaml

logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))

# Default configuration path
MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
DEFAULT_CONFIG_PATH = Path(os.path.join(MODULE_DIR, '..', 'config.yaml'))

# Default configuration - will be overridden by config file
DEFAULT_CONFIG = {
    'url': 'https://maps.app.goo.gl/6tkNMDjcj3SS6LJe9',
    'headless': True,
    'sort_by': 'relevance',
    'stop_on_match': False,
    'overwrite_existing': False,
    'use_mongodb': True,
    'mongodb': {
        'uri': 'mongodb://localhost:27017',
        'database': 'reviews',
        'collection': 'google_reviews',
    },
    'backup_to_json': True,
    'json_path': 'google_reviews.json',
    'seen_ids_path': 'google_reviews.ids',
    'convert_dates': True,
    'download_images': True,
    'image_dir': 'review_images',
    'download_threads': 4,
    'store_local_paths': True,  # Option to control storing local image paths
    'replace_urls': False,  # Option to control URL replacement
    'custom_url_base': 'https://mycustomurl.com',  # Base URL for replacement
    'custom_url_profiles': '/profiles/',  # Path for profile images
    'custom_url_reviews': '/reviews/',  # Path for review images
    'preserve_original_urls': True,  # Option to preserve original URLs
    'min_scroll_delay': 0.9,
    'max_scroll_delay': 1.7,
    'pause_every_n_reviews': 150,
    'long_pause_seconds': 75,
    'daily_max_reviews': 2500,
    'jitter_probability': 0.12,
    'jitter_extra_seconds': 2.5,
}


def load_config(config_path: Path = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    """Load configuration from YAML file or use defaults"""
    config = DEFAULT_CONFIG.copy()

    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Merge configs, with nested dictionary support
                    def deep_update(d, u):
                        for k, v in u.items():
                            if (
                                isinstance(v, dict)
                                and k in d
                                and isinstance(d[k], dict)
                            ):
                                deep_update(d[k], v)
                            else:
                                d[k] = v

                    deep_update(config, user_config)
        except Exception as e:
            logger.error(f'Error loading config from {config_path}: {e}')
            logger.info('Using default configuration')
    else:
        logger.info(f'Config file {config_path} not found, using default configuration')
        # Create a default config file for future use
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            logger.info(f'Created default configuration file at {config_path}')

    return config
