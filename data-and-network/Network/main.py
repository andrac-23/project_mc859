from dataclasses import dataclass
import json
import logging
import os
from typing import Dict

from dacite import from_dict
import networkx as nx

from PlacesAPI.main import Place
import Sentiments.main as Sentiments
import Shared.main as utils

logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))


@dataclass
class Attraction:
    id: str
    name: str
    description: str


@dataclass
class Emotion:
    id: str
    name: str
    type: str
    associated_emotion: str = None


MODULE_PATH = os.path.dirname(os.path.realpath(__file__))

EXISTING_GRAPH_PATH = os.path.join(MODULE_PATH, 'graph.gml')
EXISTING_EMOTIONS_PATH = os.path.join(MODULE_PATH, 'emotions.json')

NETWORK_INFO_PATH = os.path.join(MODULE_PATH, '..', 'network_info.json')

AttractionSentimentNet = nx.Graph()
emotions_dict: Dict[str, Emotion] = {}

if os.path.exists(EXISTING_GRAPH_PATH) and os.path.getsize(EXISTING_GRAPH_PATH) > 0:
    AttractionSentimentNet = nx.read_gml(EXISTING_GRAPH_PATH)
if (
    os.path.exists(EXISTING_EMOTIONS_PATH)
    and os.path.getsize(EXISTING_EMOTIONS_PATH) > 0
):
    with open(EXISTING_EMOTIONS_PATH, 'r', encoding='utf-8') as f:
        adjectives = json.load(f)
        for adjective in adjectives:
            processed_adjective = from_dict(data_class=Emotion, data=adjective)
            emotions_dict[processed_adjective.name.lower()] = processed_adjective


def calculate_adequacy_weight(sentiment_score, user_rating):
    """
    Calculate adequacy weight in [1,5] given:
    - sentiment_score in [-1,1]
    - user_rating in [1,5]
    """
    score = max(-1.0, min(1.0, sentiment_score))
    rating = max(1.0, min(5.0, float(user_rating)))
    polarity_rating = (rating - 3.0) / 2.0

    adequacy_weight = 3.0 + 2.0 * (score * polarity_rating)
    adequacy_weight = max(1.0, min(5.0, adequacy_weight))

    return int(round(adequacy_weight))


def add_edge(
    attraction: Place,
    emotion_name: str,
    emotion_type: str,
    sentiment_score: float,
    review_rating: float,
    associated_emotion: str = None,
):
    if not AttractionSentimentNet.has_node(attraction.id):
        AttractionSentimentNet.add_node(
            attraction.id,
            type='attraction',
            name=attraction.displayName['text'],
            rating=attraction.rating,
            location=attraction.location,
        )

    emotion = emotions_dict.get(emotion_name.lower())
    if not emotion:
        emotion = Emotion(
            id=f'{emotion_type}_{len(emotions_dict) + 1}',
            name=emotion_name.lower(),
            type=emotion_type,
            associated_emotion=associated_emotion,
        )
        emotions_dict[emotion.name] = emotion

    if not AttractionSentimentNet.has_node(emotion.id):
        AttractionSentimentNet.add_node(
            emotion.id,
            type=emotion.type,
            name=emotion.name,
            associated_emotion=emotion.associated_emotion,
        )

    edge_weight = calculate_adequacy_weight(sentiment_score, review_rating)
    if AttractionSentimentNet.has_edge(attraction.id, emotion.id):
        AttractionSentimentNet[attraction.id][emotion.id]['weight'] += edge_weight
        AttractionSentimentNet[attraction.id][emotion.id]['count'] += 1
    else:
        AttractionSentimentNet.add_edge(
            attraction.id, emotion.id, weight=edge_weight, count=1
        )


def save_network_info():
    logger.info('Calculating network information...')
    network_info = {
        'num_nodes': AttractionSentimentNet.number_of_nodes(),
        'num_edges': AttractionSentimentNet.number_of_edges(),
        'avg_degree': sum(dict(AttractionSentimentNet.degree()).values())
        / AttractionSentimentNet.number_of_nodes()
        if AttractionSentimentNet.number_of_nodes() > 0
        else 0,
        'num_components': nx.number_connected_components(AttractionSentimentNet),
    }
    with open(NETWORK_INFO_PATH, 'w', encoding='utf-8') as f:
        json.dump(network_info, f, ensure_ascii=False, indent=2)

    logger.info('Network information saved to network_info.json')


def save_emotions():
    Sentiments.save_adjective_sentiment_cache()
    with open(EXISTING_EMOTIONS_PATH, 'w', encoding='utf-8') as f:
        emotions_list = [
            json.dumps(
                emotion, cls=utils.EnhancedJSONEncoder, ensure_ascii=False, indent=2
            )
            for emotion in emotions_dict.values()
        ]
        f.write('[\n' + ',\n'.join(emotions_list) + '\n]')


def save_graph():
    save_emotions()
    nx.write_gml(AttractionSentimentNet, EXISTING_GRAPH_PATH)


def reset_network_data():
    logger.info('Resetting existing Network data...')

    global AttractionSentimentNet, emotions_dict
    AttractionSentimentNet = nx.Graph()
    emotions_dict = {}
    if os.path.exists(EXISTING_GRAPH_PATH):
        os.remove(EXISTING_GRAPH_PATH)
    if os.path.exists(EXISTING_EMOTIONS_PATH):
        os.remove(EXISTING_EMOTIONS_PATH)
    if os.path.exists(NETWORK_INFO_PATH):
        os.remove(NETWORK_INFO_PATH)

    logger.info('Network data reset complete. ✅')
