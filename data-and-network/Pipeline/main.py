from dataclasses import dataclass
import json
import logging
import os
import shutil
import signal
import sys
from typing import List, Literal

from dacite import from_dict

import Network.main as network
import Places.main as places
import PlacesAPI.main as places_api
import Scraper.main as scraper
import Sentiments.main as sentiments
import Shared.main as utils


# Define the Attraction dataclass
@dataclass
class AttractionProgress:
    id: str
    name: str
    progress: Literal['✅', '❌']


# Define the City dataclass
@dataclass
class CityProgress:
    name: str
    progress: Literal['✅', '❌']
    attractions: List[AttractionProgress]


# Define the Country dataclass
@dataclass
class CountryProgress:
    name: str
    progress: Literal['✅', '❌']
    cities: List[CityProgress]


# Define the Continent dataclass
@dataclass
class ContinentProgress:
    name: str
    progress: Literal['✅', '❌']
    countries: List[CountryProgress]


@dataclass
class PipelineProgress:
    continents: List[ContinentProgress]


logging.basicConfig(level=logging.INFO)

MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
PIPELINE_PROGRESS_PATH = os.path.join(MODULE_DIR, 'pipeline_progress.json')

interrupted = False


def handle_sigint(_sig, _frame):
    global interrupted

    logging.info('Termination signal received. Ending on end of current iteration...')
    interrupted = True


signal.signal(signal.SIGINT, handle_sigint)


def generate_json_reviews_path(
    continent: str, country: str, city: str, attraction: str
) -> str:
    safe_continent = utils.make_string_filesystem_safe(continent)
    safe_country = utils.make_string_filesystem_safe(country)
    safe_city = utils.make_string_filesystem_safe(city)
    safe_attraction = utils.make_string_filesystem_safe(attraction)

    dir_path = os.path.join('scraped_reviews', safe_continent, safe_country, safe_city)
    os.makedirs(dir_path, exist_ok=True)

    return os.path.join(dir_path, f'{safe_attraction}_reviews.json')


def get_pipeline_progress() -> PipelineProgress:
    if os.path.exists(PIPELINE_PROGRESS_PATH):
        with open(PIPELINE_PROGRESS_PATH, 'r') as f:
            data = json.load(f)
            return from_dict(data_class=PipelineProgress, data=data)
    else:
        return PipelineProgress(continents=[])


def save_pipeline_progress(progress: PipelineProgress):
    with open(PIPELINE_PROGRESS_PATH, 'w') as f:
        json.dump(progress, f, cls=utils.EnhancedJSONEncoder, indent=2)


def reset_pipeline_data():
    logging.info('Resetting existing Pipeline data...')

    if os.path.exists(PIPELINE_PROGRESS_PATH):
        os.remove(PIPELINE_PROGRESS_PATH)
    if os.path.exists('scraped_reviews'):
        shutil.rmtree('scraped_reviews')

    logging.info('Pipeline data reset complete. ✅')


def exec_net_build_pipeline():
    global interrupted

    pipeline_progress = get_pipeline_progress()

    places_info = places.get_places()
    for continent in places_info.continents:
        continent_progress = next(
            (c for c in pipeline_progress.continents if c.name == continent.name), None
        )
        if continent_progress.progress == '✅':
            logging.info(
                f'Skipping continent {continent.name} as it is already completed.'
            )
            continue

        for country in continent.countries:
            country_progress = next(
                (c for c in continent_progress.countries if c.name == country.name),
                None,
            )
            if country_progress and country_progress.progress == '✅':
                logging.info(
                    f'Skipping country {country.name} as it is already completed.'
                )
                continue

            for city in country.cities:
                city_progress = next(
                    (c for c in country_progress.cities if c.name == city.name), None
                )
                if city_progress and city_progress.progress == '✅':
                    logging.info(
                        f'Skipping city {city.name} as it is already completed.'
                    )
                    continue

                logging.info(
                    f'Processing city: {city.name} in country: {country.name}, continent: {continent.name}'
                )

            places_api_city_info = places_api.Location(
                latitude=city.latitude, longitude=city.longitude
            )
            city_attractions = places_api.getNearbyAttractions(places_api_city_info)

            for attraction in city_attractions:
                attraction_progress = next(
                    (a for a in city_progress.attractions if a.id == attraction.id),
                    None,
                )
                if attraction_progress and attraction_progress.progress == '✅':
                    logging.info(
                        f'Skipping attraction {attraction.displayName["text"]} as it is already completed.'
                    )
                    continue

                reviews = scraper.scrape_google_maps(
                    {
                        'url': f'{attraction.googleMapsUri}&hl=en',
                        'json_path': generate_json_reviews_path(
                            continent.name,
                            country.name,
                            city.name,
                            attraction.displayName['text'],
                        ),
                    }
                )

                for review in reviews:
                    review_sentences = sentiments.extract_sentences_from_text(
                        review.description['en']
                    )

                    for sentence in review_sentences:
                        adjectives = sentiments.extract_sentence_adjectives(sentence)
                        sentiment_score = sentiments.extract_sentence_sentiment(
                            sentence
                        )
                        weighted_sentiment_score = review.rating * (
                            1 + sentiment_score['compound']
                        )

                        for adjective in adjectives:
                            network.add_edge(
                                city.name,
                                attraction.name,
                                adjective,
                                weighted_sentiment_score,
                            )

                if interrupted:
                    # Save progress before exiting
                    logging.info('Saving progress before exiting...')

                    save_pipeline_progress(pipeline_progress)
                    network.save_graph()
                    break

    sys.exit(0)
