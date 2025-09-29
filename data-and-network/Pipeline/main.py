from dataclasses import dataclass
import datetime
import json
import logging
import os
import shutil
import signal
import sys
import time
from typing import List, Literal

from dacite import from_dict

import Network.main as network
import Places.main as places
import PlacesAPI.main as places_api
import Scraper.main as scraper
import Sentiments.main as sentiments
import Shared.main as utils


@dataclass
class ReviewProgress:
    id: str
    progress: Literal['✅', '❌']


# Define the Attraction dataclass
@dataclass
class AttractionProgress:
    id: str
    name: str
    reviews: List[ReviewProgress]
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


logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))

MODULE_DIR = os.path.dirname(os.path.realpath(__file__))
PIPELINE_PROGRESS_PATH = os.path.join(MODULE_DIR, 'pipeline_progress.json')
SCRAPED_REVIEWS_PATH = os.path.join(
    MODULE_DIR,
    '..',
    'scraped_reviews',
)

interrupted = False
interrupted_count = 0


def handle_sigint(_sig, _frame):
    global interrupted
    global interrupted_count

    logger.info(
        'Termination signal received. Ending on end of current iteration... Press Ctrl+C again to force quit.'
    )
    interrupted = True

    interrupted_count += 1
    if interrupted_count >= 2:
        logger.info('Force quitting now.')
        sys.exit(1)


signal.signal(signal.SIGINT, handle_sigint)


def generate_reviews_directory(
    continent: str, country: str, city: str, attraction: str
) -> str:
    safe_continent = utils.make_string_filesystem_safe(continent)
    safe_country = utils.make_string_filesystem_safe(country)
    safe_city = utils.make_string_filesystem_safe(city)
    safe_attraction = utils.make_string_filesystem_safe(attraction)

    dir_path = os.path.join(
        SCRAPED_REVIEWS_PATH,
        safe_continent,
        safe_country,
        safe_city,
        safe_attraction,
    )
    os.makedirs(dir_path, exist_ok=True)

    return dir_path


def generate_json_reviews_path(
    continent: str, country: str, city: str, attraction: str
) -> str:
    reviews_directory = generate_reviews_directory(continent, country, city, attraction)

    return os.path.join(reviews_directory, 'google_reviews.json')


def generate_seen_ids_path(
    continent: str, country: str, city: str, attraction: str
) -> str:
    reviews_directory = generate_reviews_directory(continent, country, city, attraction)

    return os.path.join(reviews_directory, 'google_reviews.ids')


def get_pipeline_progress(places_info: places.Places) -> PipelineProgress:
    if os.path.exists(PIPELINE_PROGRESS_PATH):
        with open(PIPELINE_PROGRESS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return from_dict(data_class=PipelineProgress, data=data)
    else:
        pipeline_progress = PipelineProgress(continents=[])
        for continent in places_info.continents:
            continent_progress = ContinentProgress(
                name=continent.name, progress='❌', countries=[]
            )
            for country in continent.countries:
                country_progress = CountryProgress(
                    name=country.name, progress='❌', cities=[]
                )
                for city in country.cities:
                    city_progress = CityProgress(
                        name=city.name, progress='❌', attractions=[]
                    )
                    country_progress.cities.append(city_progress)
                continent_progress.countries.append(country_progress)
            pipeline_progress.continents.append(continent_progress)

    return pipeline_progress


def save_pipeline_progress(progress: PipelineProgress, start_time: float = None):
    logger.info('Saving progress before exiting...')
    # Save pipeline
    with open(PIPELINE_PROGRESS_PATH, 'w', encoding='utf-8') as f:
        json.dump(
            progress, f, ensure_ascii=False, cls=utils.EnhancedJSONEncoder, indent=2
        )
    # Save network
    network.save_graph()
    network.save_network_info()

    logger.info('Elapsed time: {:.2f} seconds'.format(time.time() - start_time))


def reset_pipeline_data():
    logger.info('Resetting existing Pipeline data...')

    if os.path.exists(PIPELINE_PROGRESS_PATH):
        os.remove(PIPELINE_PROGRESS_PATH)
    if os.path.exists(SCRAPED_REVIEWS_PATH):
        shutil.rmtree(SCRAPED_REVIEWS_PATH)

    logger.info('Pipeline data reset complete. ✅')


def mark_empty_attractions(pipeline_progress: PipelineProgress):
    logger.info('Identifying attractions with no reviews...')
    for continent in pipeline_progress.continents:
        for country in continent.countries:
            for city in country.cities:
                for attraction in city.attractions:
                    if len(attraction.reviews) == 0:
                        logger.info(
                            f'Attraction {attraction.name} in city {city.name}, country {country.name}, continent {continent.name} has no reviews. Marking as not started.'
                        )
                        attraction.progress = '❌'
                        city.progress = '❌'
                        country.progress = '❌'
                        continent.progress = '❌'


def exec_net_build_pipeline():
    global interrupted

    logger.info(f'\nStarting Pipeline execution... {datetime.datetime.now()}')
    start_time = time.time()

    places_info = places.get_places()

    pipeline_progress = get_pipeline_progress(places_info)
    mark_empty_attractions(pipeline_progress)

    try:
        for continent in places_info.continents:
            continent_progress = next(
                (c for c in pipeline_progress.continents if c.name == continent.name),
                None,
            )
            if continent_progress.progress == '✅':
                logger.info(
                    f'Skipping continent {continent.name} as it is already completed.'
                )
                continue

            for country in continent.countries:
                country_progress = next(
                    (c for c in continent_progress.countries if c.name == country.name),
                    None,
                )
                if country_progress and country_progress.progress == '✅':
                    logger.info(
                        f'Skipping country {country.name} as it is already completed.'
                    )
                    continue
                if country_progress is None:
                    country_progress = CountryProgress(
                        name=country.name, progress='❌', cities=[]
                    )
                    continent_progress.countries.append(country_progress)

                for city in country.cities:
                    city_progress = next(
                        (c for c in country_progress.cities if c.name == city.name),
                        None,
                    )
                    if city_progress and city_progress.progress == '✅':
                        logger.info(
                            f'Skipping city {city.name} as it is already completed.'
                        )
                        continue
                    if city_progress is None:
                        city_progress = CityProgress(
                            name=city.name, progress='❌', attractions=[]
                        )
                        country_progress.cities.append(city_progress)

                    logger.info(
                        f'Processing city: {city.name} in country: {country.name}, continent: {continent.name}'
                    )

                    places_api_city_info = places_api.Location(
                        name=city.name, latitude=city.latitude, longitude=city.longitude
                    )
                    city_attractions = places_api.getNearbyAttractions(
                        places_api_city_info, maximum_results=15
                    )
                    logger.info(
                        f'Found {len(city_attractions)} attractions for city: {city.name}: {[a.displayName["text"] for a in city_attractions]}'
                    )

                    for attraction in city_attractions:
                        attraction_progress = next(
                            (
                                a
                                for a in city_progress.attractions
                                if a.id == attraction.id
                            ),
                            None,
                        )
                        if not attraction_progress:
                            attraction_progress = AttractionProgress(
                                id=attraction.id,
                                name=attraction.displayName['text'],
                                progress='❌',
                                reviews=[],
                            )
                            city_progress.attractions.append(attraction_progress)

                        if (
                            attraction_progress
                            and attraction_progress.progress == '✅'
                            and len(attraction_progress.reviews) > 0
                        ):
                            logger.info(
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
                                'seen_ids_path': generate_seen_ids_path(
                                    continent.name,
                                    country.name,
                                    city.name,
                                    attraction.displayName['text'],
                                ),
                                'stop_on_match': False,
                            }
                        )

                        for review in reviews:
                            review_progress = next(
                                (
                                    r
                                    for r in attraction_progress.reviews
                                    if r.id == review.review_id
                                ),
                                None,
                            )
                            if not review_progress:
                                review_progress = ReviewProgress(
                                    id=review.review_id, progress='❌'
                                )
                                attraction_progress.reviews.append(review_progress)
                            if review_progress and review_progress.progress == '✅':
                                logger.info(
                                    f'Skipping review {review.review_id} for attraction {attraction.displayName["text"]} as it is already completed.'
                                )
                                continue

                            logger.info(
                                f'Processing review {review.review_id} for attraction {attraction.displayName["text"]}'
                            )
                            review_sentences = sentiments.extract_sentences_from_text(
                                review.description.get('en', '')
                            )

                            for sentence in review_sentences:
                                adjectives = sentiments.extract_sentence_adjectives(
                                    sentence
                                )
                                sentiment_score = sentiments.extract_sentence_sentiment(
                                    sentence
                                )

                                for adjective in adjectives:
                                    network.add_edge(
                                        attraction,
                                        adjective,
                                        'adjective',
                                        sentiment_score['compound'],
                                        review.rating,
                                        associated_emotion=sentiments.classify_adjective_to_emotions_gemini(
                                            adjective
                                        ),
                                        review_date=review.review_date,
                                        continent=continent.name,
                                        country=country.name,
                                        city=city.name,
                                    )

                            review_progress.progress = '✅'

                        attraction_progress.progress = '✅'
                        logger.info(
                            f'Finished processing attraction {attraction.displayName["text"]} with {len(reviews)} reviews.'
                        )

                        if interrupted:
                            raise StopIteration

                    city_progress.progress = '✅'
                    logger.info(f'Finished processing city {city.name}.')

                country_progress.progress = '✅'
                network.save_network_info()
                logger.info(f'Finished processing country {country.name}.')

            continent_progress.progress = '✅'
            logger.info(f'Finished processing continent {continent.name}.')

        logger.info('Pipeline execution completed successfully! ✅')

    except StopIteration:
        logger.info('Pipeline interrupted. Saving and exiting gracefully.')

    finally:
        save_pipeline_progress(pipeline_progress, start_time)

    sys.exit(0)
    return
