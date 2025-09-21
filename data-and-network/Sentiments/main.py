import spacy
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

nlp = spacy.load('en_core_web_sm')


def extract_sentences_from_text(text):
    doc = nlp(text)
    return [sent.text for sent in doc.sents]


def extract_sentence_adjectives(sentence):
    doc = nlp(sentence)

    return [token.text for token in doc if token.pos_ == 'ADJ']


def extract_sentence_sentiment(sentence):
    sid_obj = SentimentIntensityAnalyzer()
    sentiment_dict = sid_obj.polarity_scores(sentence)

    return sentiment_dict


if __name__ == '__main__':
    test_sentence = 'The food was absolutely wonderful, from preparation to presentation, very pleasing.'
    adjectives = extract_sentence_adjectives(test_sentence)
    print(adjectives)  # Output: ['wonderful', 'pleasing']
    extract_sentence_sentiment(test_sentence)
