import spacy
from spacy.util import is_package
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

model = 'en_core_web_sm'

if not is_package(model):
    spacy.cli.download(model)

nlp = spacy.load(model)


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


if __name__ == '__main__':
    test_sentence = 'The first dog is bigger than the second beautiful dog, but the 11th dog is the smallest.'
    adjectives = extract_sentence_adjectives(test_sentence)

    print(adjectives)  # Output: ['wonderful', 'pleasing']
    extract_sentence_sentiment(test_sentence)
