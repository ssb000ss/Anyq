from __future__ import annotations

import re

import structlog

log = structlog.get_logger()

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
_MIN_SENTENCE = 30
_MAX_SENTENCE = 250


def _split_sentences(text: str) -> list[str]:
    raw = _SENTENCE_RE.split(text.strip())
    return [
        s.strip()
        for s in raw
        if _MIN_SENTENCE <= len(s.strip()) <= _MAX_SENTENCE
    ]


class TFIDFExtractor:
    """Extract key phrases and representative sentences from text."""

    @staticmethod
    def extract_key_phrases(text: str, top_n: int = 10) -> list[str]:
        if not text or len(text) < 50:
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer

            sentences = _split_sentences(text)
            if len(sentences) < 3:
                return []

            vectorizer = TfidfVectorizer(
                ngram_range=(2, 4),
                max_features=200,
                stop_words=None,
                min_df=1,
            )
            vectorizer.fit_transform(sentences)
            feature_names = vectorizer.get_feature_names_out()
            scores = vectorizer.idf_

            # lower idf = more common, higher idf = more unique
            # we want unique phrases: sort by idf descending
            ranked = sorted(zip(feature_names, scores), key=lambda x: -x[1])
            phrases = [phrase for phrase, _ in ranked[:top_n] if len(phrase) > 10]

            log.debug("tfidf.phrases", count=len(phrases))
            return phrases

        except Exception as exc:
            log.warning("tfidf.phrases.failed", error=str(exc))
            return []

    @staticmethod
    def extract_sample_sentences(text: str, n: int = 5) -> list[str]:
        if not text or len(text) < 100:
            return []

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            import numpy as np

            sentences = _split_sentences(text)
            if len(sentences) < 4:
                return sentences[:n]

            vectorizer = TfidfVectorizer(ngram_range=(1, 2), max_features=500)
            tfidf_matrix = vectorizer.fit_transform(sentences)

            # avg TF-IDF score per sentence
            scores = np.asarray(tfidf_matrix.mean(axis=1)).flatten()

            # skip first and last sentence (usually boilerplate)
            scores[0] = 0.0
            scores[-1] = 0.0

            top_indices = scores.argsort()[::-1][:n]
            sampled = [sentences[i] for i in sorted(top_indices)]

            log.debug("tfidf.samples", count=len(sampled))
            return sampled

        except Exception as exc:
            log.warning("tfidf.samples.failed", error=str(exc))
            # fallback: evenly spaced sentences
            sentences = _split_sentences(text)
            step = max(1, len(sentences) // n)
            return sentences[1::step][:n]
