import json
import logging
import os
import random
import time

from google.api_core import exceptions as gax_exceptions
import grpc
import spacy
from spacy.util import is_package
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import vertexai
from vertexai.generative_models import GenerativeModel

logger = logging.getLogger(os.getenv('DATA_NETWORK_LOGGER', 'data-and-network'))

VERTEX_AI_PROJECT_ID = os.getenv('VERTEX_AI_PROJECT_ID')
if not VERTEX_AI_PROJECT_ID:
    raise ValueError('VERTEX_AI_PROJECT_ID not found in environment variables')

vertexai.init(project=VERTEX_AI_PROJECT_ID, location='us-central1')
ai_model = GenerativeModel('gemini-2.0-flash')

MODULE_DIR = os.path.dirname(os.path.realpath(__file__))

CACHED_GEMINI_RESULTS_PATH = os.path.join(MODULE_DIR, 'cached_results.json')

adjective_to_sentiment_map = {}
if (
    os.path.exists(CACHED_GEMINI_RESULTS_PATH)
    and os.path.getsize(CACHED_GEMINI_RESULTS_PATH) > 0
):
    with open(CACHED_GEMINI_RESULTS_PATH, 'r', encoding='utf-8') as f:
        adjective_to_sentiment_map = json.load(f)

spacy_model = 'en_core_web_sm'
if not is_package(spacy_model):
    spacy.cli.download(spacy_model)
nlp = spacy.load(spacy_model)


def save_adjective_sentiment_cache():
    with open(CACHED_GEMINI_RESULTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(adjective_to_sentiment_map, f, ensure_ascii=False, indent=2)


def clear_adjective_sentiment_cache():
    global adjective_to_sentiment_map

    adjective_to_sentiment_map = {}
    if os.path.exists(CACHED_GEMINI_RESULTS_PATH):
        os.remove(CACHED_GEMINI_RESULTS_PATH)

    logger.info('Adjective sentiment cache cleared. ✅')


def extract_sentences_from_text(text):
    doc = nlp(text)

    return [sent.text for sent in doc.sents]


def extract_sentence_adjectives(sentence):
    doc = nlp(sentence)

    # Extract adjectives excluding ordinals
    return [
        token.text
        for token in doc
        if token.pos_ == 'ADJ' and not (token.like_num or token.ent_type_ == 'ORDINAL')
    ]


def extract_sentence_sentiment(sentence):
    sid_obj = SentimentIntensityAnalyzer()
    sentiment_dict = sid_obj.polarity_scores(sentence)

    return sentiment_dict


def generate_with_retry(prompt: str, max_retries: int = 12, base_delay: float = 1.0):
    """
    Calls Vertex AI with exponential backoff and jitter on transient errors.
    Retries on RESOURCE_EXHAUSTED (429), UNAVAILABLE (503), DEADLINE_EXCEEDED (504).
    """
    for attempt in range(max_retries):
        try:
            return ai_model.generate_content(prompt)
        except (
            gax_exceptions.ResourceExhausted,
            gax_exceptions.TooManyRequests,
            gax_exceptions.ServiceUnavailable,
            gax_exceptions.DeadlineExceeded,
        ) as e:
            delay = base_delay * (2**attempt) + random.uniform(0, 0.25)
            logger.warning(
                f'Gemini throttled ({type(e).__name__}); retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})'
            )
            time.sleep(delay)
        except grpc.RpcError as e:
            code = e.code()
            if code in (
                grpc.StatusCode.RESOURCE_EXHAUSTED,
                grpc.StatusCode.UNAVAILABLE,
                grpc.StatusCode.DEADLINE_EXCEEDED,
            ):
                delay = base_delay * (2**attempt) + random.uniform(0, 0.25)
                logger.warning(
                    f'Gemini gRPC {code.name}; retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})'
                )
                time.sleep(delay)
            else:
                raise

    raise RuntimeError('Exceeded max retries for Vertex AI generate_content')


def classify_adjective_to_emotions_gemini(adjective: str):
    sanitized_adjective = adjective.strip().lower()

    if sanitized_adjective in adjective_to_sentiment_map:
        return adjective_to_sentiment_map[sanitized_adjective]

    prompt = f"""
    Classify the adjective {sanitized_adjective} into one of the emotions:
    1. Happiness
    2. Joy
    3. Excitement
    4. Wonder (awe, amazement)
    5. Peace (calm, tranquility)
    6. Relaxation
    7. Satisfaction (contentment)
    8. Love (affection, admiration)
    9. Pride (cultural, historical value, achievement)
    10. Gratitude
    11. Trust (safety, reliability)
    12. Inspiration (uplift, creativity)
    13. Curiosity
    14. Anticipation (expectation, suspense)
    15. Nostalgia
    16. Surprise (can be positive or negative)
    17. Loneliness (esp. if attraction feels empty or isolating)
    18. Boredom
    19. Confusion
    20. Sadness
    21. Disappointment
    22. Frustration
    23. Annoyance
    24. Anger
    25. Fear
    26. Anxiety
    27. Stress (crowds, waiting, noise)
    28. Disgust (dirty, smelly)
    29. Regret (waste of time/money)
    30. Insecurity (unsafe, unwelcoming)

    You must choose only one emotion that best represents the adjective. Reply with only the emotion name, ignoring any other text.
    """

    response = generate_with_retry(prompt)

    adjective_to_sentiment_map[sanitized_adjective] = response.text.strip()

    return response.text


if __name__ == '__main__':
    adjective = 'wonderful'
    q = classify_adjective_to_emotions_gemini(adjective)
    answer = adjective_to_sentiment_map[adjective]
    print('Gemini answers:', answer)

    test_sentence = 'The first dog is bigger than the second beautiful dog, but the 11th dog is the smallest.'
    adjectives = extract_sentence_adjectives(test_sentence)

    print(adjectives)  # Output: ['wonderful', 'pleasing']
    extract_sentence_sentiment(test_sentence)
