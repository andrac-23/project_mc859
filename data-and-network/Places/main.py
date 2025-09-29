from dataclasses import dataclass
import json
import logging
import os
from typing import Dict, List, Optional

from dacite import from_dict
import pandas as pd

import Shared.main as utils

logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))


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
    MODULE_DIR, 'top_cities_per_top_countries_per_continent.csv'
)
SAVED_JSON_PATH = os.path.join(
    MODULE_DIR, 'top_cities_per_top_countries_per_continent.json'
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

default_per_continent_quota = {
    'AF': 4,
    'AS': 4,
    'EU': 10,
    'NA': 4,
    'OC': 3,
    'SA': 5,
}

# Filtering these to get countries with more well-known attractions
default_filtered_countries = [
    'PK',  # Pakistan
    'BD',  # Bangladesh
    'ID',  # Indonesia
    'PL',  # Poland
    'RO',  # Romania
    'BE',  # Belgium
    'GT',  # Guatemala
    'PH',  # Philippines
    'VN',  # Vietnam
]

default_included_cities = ['Campinas', 'Recife', 'Manaus', 'Curitiba']


def get_places(
    num_countries=4,
    num_cities=3,
    per_continent_country_quota: Optional[Dict[str, int]] = default_per_continent_quota,
    removed_countries: Optional[List[str]] = default_filtered_countries,
    included_cities: Optional[List[str]] = default_included_cities,
) -> Places:
    """
    Get top X cities from top Y countries by population for each continent.
    Saves the results to a CSV file and a JSON file for future runs.
    """
    if os.path.exists(SAVED_JSON_PATH):
        with open(SAVED_JSON_PATH, 'r', encoding='utf-8') as f:
            saved_data = json.load(f)
            saved_data = from_dict(data_class=Places, data=saved_data)

            logger.info(
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
        dtype={'Population': 'Int64', 'Continent': 'string'},
        keep_default_na=False,
    )

    # Sort countries by population and get top X countries per continent
    sorted_countries = countriesDF[countriesDF['Continent'] != 'AN'].copy()
    sorted_countries = sorted_countries.sort_values('Population', ascending=False)
    filtered_countries = sorted_countries[
        ~sorted_countries['ISO'].isin(removed_countries)
    ]

    parts = []
    for continent, group in filtered_countries.groupby('Continent'):
        total_countries = int(per_continent_country_quota.get(continent, num_countries))
        parts.append(group.head(total_countries))

    top_countries = pd.concat(parts, ignore_index=True)
    top_cities = {}
    for _, row in top_countries.iterrows():
        country_code = row['ISO']
        country__cities_df = citiesDF[citiesDF['country_code'] == country_code].copy()

        included_df = country__cities_df[
            country__cities_df['name'].isin(included_cities)
            | country__cities_df['asciiname'].isin(included_cities)
        ]
        included_df = included_df.sort_values(
            'population', ascending=False
        ).drop_duplicates(subset=['name'], keep='first')

        top_df = country__cities_df.sort_values('population', ascending=False).head(
            num_cities
        )

        top_cities[country_code] = (
            pd.concat([included_df, top_df])
            .drop_duplicates()
            .sort_values('population', ascending=False)
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
    if not os.path.exists(SAVED_JSON_PATH):
        logger.info(
            'Saving places (continents, countries and cities) results from current run.'
        )
        with open(SAVED_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump(
                places, f, ensure_ascii=False, cls=utils.EnhancedJSONEncoder, indent=2
            )

    return places


def reset_places_data():
    logger.info('Resetting existing Places data...')

    if os.path.exists(SAVED_CSV_PATH):
        os.remove(SAVED_CSV_PATH)
    if os.path.exists(SAVED_JSON_PATH):
        os.remove(SAVED_JSON_PATH)

    logger.info('Places data reset complete. ✅')
