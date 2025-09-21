from dataclasses import dataclass
import json
import logging
import os
from typing import List

from dacite import from_dict
import pandas as pd

import Shared.main as utils


@dataclass
class City:
    name: str
    latitude: float
    longitude: float
    population: int


@dataclass
class Country:
    name: str
    cities: List[City]


@dataclass
class Continent:
    name: str
    countries: List[Country]


@dataclass
class Places:
    continents: List[Continent]


MODULE_DIR = os.path.dirname(os.path.realpath(__file__))

CITIES_DATA_PATH = os.path.join(MODULE_DIR, 'geoNames', 'cities15000.txt')
COUNTRIES_DATA_PATH = os.path.join(MODULE_DIR, 'geoNames', 'countryInfo.txt')
SAVED_CSV_PATH = os.path.join(
    MODULE_DIR, 'top50_cities_per_top10_countries_per_continent.csv'
)
SAVED_JSON_PATH = os.path.join(
    MODULE_DIR, 'top50_cities_per_top10_countries_per_continent.json'
)

# Load the cities15000 dataset
citiesCols = [
    'geonameid',
    'name',
    'asciiname',
    'alternatenames',
    'latitude',
    'longitude',
    'feature_class',
    'feature_code',
    'country_code',
    'cc2',
    'admin1_code',
    'admin2_code',
    'admin3_code',
    'admin4_code',
    'population',
    'elevation',
    'dem',
    'timezone',
    'modification_date',
]

countriesCols = [
    'ISO',
    'ISO3',
    'ISO-Numeric',
    'fips',
    'Country',
    'Capital',
    'Area(in sq km)',
    'Population',
    'Continent',
    'tld',
    'CurrencyCode',
    'CurrencyName',
    'Phone',
    'Postal Code Format',
    'Postal Code Regex',
    'Languages',
    'geonameid',
    'neighbours',
    'EquivalentFipsCode',
]

continents_map = {
    'AF': 'Africa',
    'AS': 'Asia',
    'EU': 'Europe',
    'NA': 'North America',
    'OC': 'Oceania',
    'SA': 'South America',
    'AN': 'Antarctica',
}


def get_places(top_countries=10, top_cities=50) -> Places:
    """
    Get top X cities from top Y countries by population for each continent.
    Saves the results to a CSV file and a JSON file for future runs.
    """
    if os.path.exists(SAVED_JSON_PATH):
        with open(SAVED_JSON_PATH, 'r') as f:
            saved_data = json.load(f)
            saved_data = from_dict(data_class=Places, data=saved_data)

            logging.info(
                'Loaded saved places (continents, countries and cities) results from previous run.'
            )

            return saved_data

    # Load TSV file (change path to where you extracted cities15000.txt)
    citiesDF = pd.read_csv(
        CITIES_DATA_PATH,
        sep='\t',
        names=citiesCols,
        header=None,
        dtype={'population': 'Int64'},
    )
    countriesDF = pd.read_csv(
        COUNTRIES_DATA_PATH,
        sep='	',
        names=countriesCols,
        header=None,
        dtype={'Population': 'Int64'},
    )

    # Sort countries by population and get top 10 per continent
    top_countries = (
        countriesDF[countriesDF['Continent'] != 'AN']
        .sort_values('Population', ascending=False)
        .groupby('Continent')
        .head(top_countries)
    )
    top_cities = {}
    for _, row in top_countries.iterrows():
        country_code = row['ISO']
        top_cities[country_code] = (
            citiesDF[citiesDF['country_code'] == country_code]
            .sort_values('population', ascending=False)
            .head(top_cities)
        )
        top_cities[country_code]['continent'] = row['Continent']

    # Relabel the column country_code to the name of the country
    for country_code, df in top_cities.items():
        country_name = countriesDF[countriesDF['ISO'] == country_code][
            'Country'
        ].values[0]
        df.rename(columns={'country_code': 'country'}, inplace=True)
        df['country'] = country_name
        df['continent'] = df['continent'].map(continents_map)

    # Combine all top cities into a single DataFrame
    combined_top_cities = pd.concat(top_cities.values(), ignore_index=True)
    # Only leave relevant columns
    combined_top_cities = combined_top_cities[
        ['name', 'country', 'population', 'latitude', 'longitude', 'continent']
    ]

    # Get the Places dataclass structure
    places = Places(continents=[])
    for continents in combined_top_cities['continent'].unique():
        continent_countries = []
        continent_df = combined_top_cities[
            combined_top_cities['continent'] == continents
        ]
        for country in continent_df['country'].unique():
            country_cities = []
            country_df = continent_df[continent_df['country'] == country]
            for _, city_row in country_df.iterrows():
                city = City(
                    name=city_row['name'],
                    latitude=city_row['latitude'],
                    longitude=city_row['longitude'],
                    population=city_row['population'],
                )
                country_cities.append(city)
            country_obj = Country(name=country, cities=country_cities)
            continent_countries.append(country_obj)
        continent_obj = Continent(name=continents, countries=continent_countries)
        places.continents.append(continent_obj)

    # Save raw table to CSV
    combined_top_cities.to_csv(SAVED_CSV_PATH, index=False)

    # Save processed and separated places to JSON
    if os.path.exists(SAVED_JSON_PATH):
        logging.info(
            'Saving places (continents, countries and cities) results from current run.'
        )
        with open(SAVED_JSON_PATH, 'w') as f:
            json.dump(places, f, cls=utils.EnhancedJSONEncoder, indent=2)

    return places


def reset_places_data():
    logging.info('Resetting existing Places data...')

    if os.path.exists(SAVED_CSV_PATH):
        os.remove(SAVED_CSV_PATH)
    if os.path.exists(SAVED_JSON_PATH):
        os.remove(SAVED_JSON_PATH)

    logging.info('Places data reset complete. ✅')
