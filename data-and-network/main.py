import argparse
import logging
import os

from dotenv import load_dotenv

load_dotenv()
MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
LOGGING_PATH = os.path.join(MODULE_DIR, 'pipeline.log')

logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))
logger.setLevel(logging.INFO)
logger.propagate = False

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOGGING_PATH, mode='a', encoding='utf-8')
file_handler.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s')
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

if not logger.handlers:
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

import Network.main as network  # noqa: E402
import Pipeline.main as pipeline  # noqa: E402
import Places.main as places  # noqa: E402
import PlacesAPI.main as places_api  # noqa: E402


def reset_data_and_network():
    places.reset_places_data()
    network.reset_network_data()
    pipeline.reset_pipeline_data()
    places_api.clearCachedAttractions()
    # sentiments.clear_adjective_sentiment_cache()

    logger.info('All data reset complete. ✅')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Data and Network Pipeline')
    parser.add_argument(
        '--reset', action='store_true', help='Reset all data and network'
    )
    args = parser.parse_args()

    if args.reset:
        logger.info('Resetting all data and network...')
        reset_data_and_network()
        exit(0)
    else:
        logger.info('No reset flag provided. Skipping data reset.')

    pipeline.exec_net_build_pipeline()
