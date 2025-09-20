# Get places API key from .env
import os
from dotenv import load_dotenv
from dataclasses import dataclass
import requests
from concurrent.futures import ThreadPoolExecutor
import logging
from typing import List, Dict, Literal

MAX_THREADS = 4

@dataclass
class Place:
    id: str
    location: Dict[Literal["latitude", "longitude"], float]
    rating: float
    googleMapsUri: str
    userRatingCount: int
    displayName: Dict[Literal["text", "languageCode"], str]

@dataclass
class NearbySearchResponse:
    places: List[Place]

@dataclass
class Location:
    latitude: float
    longitude: float

load_dotenv()
PLACES_API_KEY = os.getenv("PLACES_API_KEY")
if not PLACES_API_KEY:
    raise ValueError("PLACES_API_KEY not found in environment variables")

Search_Nearby_Constants = {
    "RESPONSE_FIELDS": ["places.id", "places.displayName", "places.googleMapsUri", "places.location", "places.userRatingCount", "places.rating"],
    "PLACE_TYPES": ["tourist_attraction", "point_of_interest", "establishment"],
    "MAX_RESULTS": 20,
    "RANK_PREFERENCE": "popularity",
    "RADIUS_METERS": 5000
}

def getNearbyAttractionsFromType(location: Location, place_type: str) -> NearbySearchResponse:
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

    headers = { "X-Goog-Api-Key": PLACES_API_KEY, }
    params = { "fields": Search_Nearby_Constants["RESPONSE_FIELDS"] }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": Search_Nearby_Constants["MAX_RESULTS"],
        "rankPreference": Search_Nearby_Constants["RANK_PREFERENCE"],
        "locationRestriction": {
            "circle": {
                "center": { "latitude": location.latitude, "longitude": location.longitude },
                "radius": Search_Nearby_Constants["RADIUS_METERS"]
            }
        }
    }

    response = requests.post(url, headers=headers, params=params, json=body)

    if response.status_code == 200:
        return response.json().get("results", [])
    else:
        logging.error(f"Error fetching nearby attractions: {response.status_code} - {response.text}")
        return NearbySearchResponse(places=[])

def getNearbyAttractions(location: Location) -> List[Place]:
    responses: List[NearbySearchResponse] = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = [executor.submit(getNearbyAttractionsFromType, location, place_type) for place_type in Search_Nearby_Constants["PLACE_TYPES"]]
        for future in futures:
            try:
                result = future.result()
                responses.extend(result)
            except Exception as e:
                logging.error(f"Error fetching attractions: {e}")

    attractions: List[Place] = []
    for i in range(len(responses)):
        attractions.extend(responses[i].places)

    # Deduplicate attractions by id
    unique_attractions = {attraction.id: attraction for attraction in attractions}

    return list(unique_attractions.values())
