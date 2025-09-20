from PlacesAPI.main import Place
import Utils.main as utils

import networkx as nx
from dataclasses import dataclass
from dacite import from_dict
from typing import Dict
import json
import os

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

MODULE_PATH = os.path.dirname(os.path.realpath(__file__))

EXISTING_GRAPH_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "graph.gml")
EXISTING_EMOTIONS_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "emotions.json")

AttractionSentimentNet = nx.Graph()
adjectives_dict: Dict[str, Emotion] = {}

if EXISTING_GRAPH_PATH:
    AttractionSentimentNet = nx.read_gml(EXISTING_GRAPH_PATH)
if EXISTING_EMOTIONS_PATH:
    import json
    with open(EXISTING_EMOTIONS_PATH, 'r', encoding='utf-8') as f:
        adjectives = json.load(f)
        for adjective in adjectives:
            processed_adjective = from_dict(data_class=Emotion, data=adjective)
            adjectives_dict[processed_adjective.name.lower()] = processed_adjective

def add_edge(attraction: Place, emotion: str, emotion_type: str, weight: float):
    if not AttractionSentimentNet.has_node(attraction.id):
        AttractionSentimentNet.add_node(attraction.id, type='attraction', name=attraction.displayName['text'], description=attraction.description, rating=attraction.rating, location=attraction.location)

    emotion = adjectives_dict.get(emotion.lower())
    if not emotion:
        emotion = Emotion(id=f"{emotion_type}_{len(adjectives_dict) + 1}", name=emotion, type=emotion_type)
        adjectives_dict[emotion.name.lower()] = emotion

    if not AttractionSentimentNet.has_node(emotion.id):
        AttractionSentimentNet.add_node(emotion.id, type='emotion', name=emotion.name, description=emotion.description)

    if AttractionSentimentNet.has_edge(attraction.id, emotion.id):
        AttractionSentimentNet[attraction.id][emotion.id]['weight'] += weight
    else:
        AttractionSentimentNet.add_edge(attraction.id, emotion.id, weight=weight)

def get_network_info():
    return {
        "num_nodes": AttractionSentimentNet.number_of_nodes(),
        "num_edges": AttractionSentimentNet.number_of_edges(),
        "avg_degree": sum(dict(AttractionSentimentNet.degree()).values()) / AttractionSentimentNet.number_of_nodes() if AttractionSentimentNet.number_of_nodes() > 0 else 0,
        "num_components": nx.number_connected_components(AttractionSentimentNet)
    }

def save_adjectives(path: str):
    with open(path, 'w', encoding='utf-8') as f:
        adjectives_list = [json.dumps(adj, cls=utils.EnhancedJSONEncoder, ensure_ascii=False, indent=2) for adj in adjectives_dict.values()]
        f.write("\n".join(adjectives_list))

def save_graph():
    nx.write_gml(AttractionSentimentNet, EXISTING_GRAPH_PATH)
