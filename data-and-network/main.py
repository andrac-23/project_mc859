import argparse
import logging

import Network.main as network
import Pipeline.main as pipeline
import Places.main as places


def reset_data_and_network():
    places.reset_places_data()
    network.reset_network_data()
    pipeline.reset_pipeline_data()

    logging.info('All data reset complete. ✅')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Data and Network Pipeline')
    parser.add_argument(
        '--reset', action='store_true', help='Reset all data and network'
    )
    args = parser.parse_args()

    if args.reset:
        logging.info('Resetting all data and network...')
        reset_data_and_network()
    else:
        logging.info('No reset flag provided. Skipping data reset.')

    # pipeline.exec_net_build_pipeline()
