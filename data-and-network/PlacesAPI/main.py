# Get places API key from .env
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import logging
import os
import random
from typing import Dict, List, Literal

from dacite import from_dict
import requests

logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))
MAX_THREADS = 4


@dataclass
class Place:
    id: str
    location: Dict[Literal['latitude', 'longitude'], float]
    rating: float
    googleMapsUri: str
    userRatingCount: int
    displayName: Dict[Literal['text', 'languageCode'], str]


@dataclass
class NearbySearchResponse:
    places: List[Place]


@dataclass
class Location:
    latitude: float
    longitude: float


PLACES_API_KEY = os.getenv('PLACES_API_KEY')
if not PLACES_API_KEY:
    raise ValueError('PLACES_API_KEY not found in environment variables')

Search_Nearby_Constants = {
    'RESPONSE_FIELDS': [
        'places.id',
        'places.displayName',
        'places.googleMapsUri',
        'places.location',
        'places.userRatingCount',
        'places.rating',
    ],
    'MAX_RESULTS': 5,
    'RANK_PREFERENCE': 'popularity',
    'RADIUS_METERS': 5000,
}

Considered_Place_Types_Filters = {
    'nature': [
        'park',
        'garden',
        'national_park',
        'botanical_garden',
        'state_park',
        'wildlife_park',
        'zoo',
        'beach',
        'hiking_area',
    ],
    'culture': [
        'museum',
        'historical_place',
        'cultural_landmark',
        'historical_landmark',
        'monument',
        'art_gallery',
    ],
    'performing_art': [
        'opera_house',
        'concert_hall',
        'philharmonic_hall',
        'performing_arts_theater',
        'cultural_center',
        'amphitheatre',
    ],
    'entertainment': [
        'amusement_park',
        'water_park',
        'roller_coaster',
        'casino',
        'movie_theater',
        'planetarium',
        'aquarium',
    ],
    'religion': ['church', 'hindu_temple', 'mosque', 'synagogue'],
    'general': ['tourist_attraction', 'visitor_center', 'plaza'],
}


def getNearbyAttractionsFromType(
    location: Location, place_types: List[str]
) -> NearbySearchResponse:
    url = 'https://places.googleapis.com/v1/places:searchNearby'

    headers = {
        'X-Goog-Api-Key': PLACES_API_KEY,
        'Content-Type': 'application/json',
    }
    params = {'fields': ','.join(Search_Nearby_Constants['RESPONSE_FIELDS'])}
    body = {
        'includedTypes': place_types,
        'maxResultCount': Search_Nearby_Constants['MAX_RESULTS'],
        'rankPreference': Search_Nearby_Constants['RANK_PREFERENCE'],
        'locationRestriction': {
            'circle': {
                'center': {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                },
                'radius': Search_Nearby_Constants['RADIUS_METERS'],
            }
        },
    }

    response = requests.post(url, headers=headers, params=params, json=body)

    if response.status_code == 200:
        places_json = response.json().get('places', [])
        places = [from_dict(data_class=Place, data=place) for place in places_json]
        return NearbySearchResponse(places=places)
    else:
        logger.error(
            f'Error fetching nearby attractions: {response.status_code} - {response.text}'
        )
        return NearbySearchResponse(places=[])


def getNearbyAttractions(location: Location, maximum_results: int = 5) -> List[Place]:
    responses: List[NearbySearchResponse] = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [
            executor.submit(getNearbyAttractionsFromType, location, place_types)
            for place_types in Considered_Place_Types_Filters.values()
        ]
        for future in futures:
            try:
                result = future.result()
                responses.append(result)
            except Exception as e:
                logger.error(f'Error fetching attractions: {e}')

    attractions: List[Place] = []
    for i in range(len(responses)):
        attractions.extend(responses[i].places)

    # Deduplicate attractions by id
    unique_attractions = list(
        {attraction.id: attraction for attraction in attractions}.values()
    )
    # Shuffle and return max of N
    random.shuffle(unique_attractions)

    return unique_attractions[:maximum_results]


if __name__ == '__main__':
    # Example usage
    location = Location(
        latitude=-22.90556, longitude=-47.06083
    )  # Example: Campinas, Brazil
    attractions = getNearbyAttractions(location)
    print(f'Found {len(attractions)} attractions:')
    for attraction in attractions:
        print(f'{attraction.displayName["text"]} - {attraction.googleMapsUri}')
