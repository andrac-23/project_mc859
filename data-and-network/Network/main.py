from dataclasses import dataclass
import json
import logging
import os
from typing import Dict

from dacite import from_dict
import geopandas as gpd
from matplotlib.patches import Rectangle
import matplotlib.pyplot as plt
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
GEXT_GRAPH_PATH = os.path.join(MODULE_PATH, 'graph.gexf')
EXISTING_EMOTIONS_PATH = os.path.join(MODULE_PATH, 'emotions.json')

NETWORK_INFO_PATH = os.path.join(MODULE_PATH, '..', '..', 'network_info.json')

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
    review_date: str = None,
    continent: str = None,
    country: str = None,
    city: str = None,
):
    if not AttractionSentimentNet.has_node(attraction.id):
        AttractionSentimentNet.add_node(
            attraction.id,
            type='attraction',
            name=attraction.displayName['text'],
            rating=attraction.rating,
            location={
                **attraction.location,
                'continent': continent,
                'country': country,
                'city': city,
            },
            attraction_types=attraction.types,
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
        AttractionSentimentNet[attraction.id][emotion.id]['review_dates'].append(
            review_date
        )
    else:
        AttractionSentimentNet.add_edge(
            attraction.id,
            emotion.id,
            weight=edge_weight,
            count=1,
            review_dates=[review_date],
        )


def plot_degree_distribution():
    all_degrees = [degree for _, degree in AttractionSentimentNet.degree()]

    low_degrees = [d for d in all_degrees if d <= 50]
    high_degrees = [d for d in all_degrees if d > 50]

    low_bins = range(0, 51 + 1)
    high_max = max(high_degrees) if high_degrees else 51
    high_bins = range(51, high_max + 50, 1)

    fig, (ax1, ax2) = plt.subplots(
        1,
        2,
        figsize=(18, 6),
    )

    # 0-50
    counts1, bins1, patches1 = ax1.hist(
        low_degrees,
        bins=low_bins,
        align='left',
        color='cornflowerblue',
        edgecolor='cornflowerblue',
    )
    ax1.set_title('Distribuição de Graus (0–50)')
    ax1.set_xlabel('Grau')
    ax1.set_ylabel('Número de Nós')
    ax1.set_xticks(range(0, 51, 3))
    ax1.set_yticks(range(0, 5000, 300))
    ax1.grid(axis='y', linestyle='--', alpha=0.7)

    # 51+
    counts2, bins2, patches2 = ax2.hist(
        high_degrees,
        bins=high_bins,
        align='left',
        color='mediumseagreen',
        edgecolor='cornflowerblue',
    )
    ax2.set_title(f'Distribuição de Graus (51–{high_max})')
    ax2.set_xlabel('Grau')
    ax2.set_xticks(range(50, high_max + 100, 100))
    ax2.set_yticks(range(0, 16))
    ax2.grid(axis='y', linestyle='--', alpha=0.7)

    plt.suptitle('Distribuição de Graus da Rede de Atrações e Sentimentos', fontsize=16)
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])

    plt.show()


def plot_world_map_with_tooltips():
    url = (
        'https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip'
    )

    world = gpd.read_file(url)

    highlight = [
        data['location']['country']
        for node, data in AttractionSentimentNet.nodes.items()
        if data['type'] == 'attraction'
    ]
    # Different format than our database <- not renaming anything as this is just for visualization
    highlight.extend(['Dem. Rep. Congo', 'United States of America'])

    fig, ax = plt.subplots(figsize=(12, 6))

    world.plot(ax=ax, color='lightgray', edgecolor='black', linewidth=0.35)

    world[world['NAME'].isin(highlight)].plot(
        ax=ax, color='cornflowerblue', edgecolor='black', linewidth=0.35
    )

    tooltip_points = [
        {
            'lon': data['location']['longitude'],
            'lat': data['location']['latitude'],
            'name': data['name'],
        }
        for node, data in AttractionSentimentNet.nodes.items()
        if data['type'] == 'attraction'
    ]
    for point in tooltip_points:
        ax.scatter(point['lon'], point['lat'], s=2.5, color='black')

    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_linewidth(1.2)
        spine.set_edgecolor('black')
    ax.tick_params(left=False, bottom=False, labelleft=False, labelbottom=False)

    legend_elements = [
        Rectangle(
            (0, 0),
            1,
            1,
            facecolor='cornflowerblue',
            edgecolor='black',
            label='Países com Atrações',
        ),
        plt.Line2D(
            [0],
            [0],
            marker='o',
            color='w',
            label='Localização das Atrações',
            markerfacecolor='black',
            markersize=5,
        ),
    ]
    ax.legend(
        handles=legend_elements,
        loc='lower left',
        fontsize=9,
        frameon=True,
        framealpha=1,
        edgecolor='black',
        bbox_to_anchor=(0.035, 0.09),
    )

    ax.set_title('Mapa das Atrações Coletadas', fontsize=13)

    plt.tight_layout()
    plt.show()


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
    attraction_nodes = [
        node
        for node, data in AttractionSentimentNet.nodes.items()
        if data['type'] == 'attraction'
    ]
    if attraction_nodes:
        avg_attraction_degree = sum(
            dict(AttractionSentimentNet.degree(attraction_nodes)).values()
        ) / len(attraction_nodes)
        network_info['avg_attraction_degree'] = avg_attraction_degree

    emotion_nodes = [
        node
        for node, data in AttractionSentimentNet.nodes.items()
        if data['type'] != 'attraction'
    ]
    if emotion_nodes:
        avg_emotion_degree = sum(
            dict(AttractionSentimentNet.degree(emotion_nodes)).values()
        ) / len(emotion_nodes)
        network_info['avg_emotion_degree'] = avg_emotion_degree

    if attraction_nodes:
        highest_degree_attraction = max(
            attraction_nodes, key=lambda n: AttractionSentimentNet.degree(n)
        )
        network_info['highest_degree_attraction'] = {
            **AttractionSentimentNet.nodes[highest_degree_attraction],
            'degree': AttractionSentimentNet.degree(highest_degree_attraction),
        }

    if emotion_nodes:
        highest_degree_emotion = max(
            emotion_nodes, key=lambda n: AttractionSentimentNet.degree(n)
        )
        network_info['highest_degree_emotion'] = {
            **AttractionSentimentNet.nodes[highest_degree_emotion],
            'degree': AttractionSentimentNet.degree(highest_degree_emotion),
        }

    if AttractionSentimentNet.number_of_edges() > 0:
        highest_weight_edge = max(
            AttractionSentimentNet.edges(data=True), key=lambda e: e[2]['weight']
        )
        network_info['highest_weight_edge'] = {
            'attraction': AttractionSentimentNet.nodes[highest_weight_edge[0]],
            'emotion': AttractionSentimentNet.nodes[highest_weight_edge[1]],
            'weight': highest_weight_edge[2]['weight'],
            'count': highest_weight_edge[2]['count'],
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
