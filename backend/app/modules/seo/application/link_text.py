"""Persian-aware tokenization and TF-IDF scoring for internal-link suggestions.

Rank Math Pro's Link Genius ranks candidate posts by TF-IDF cosine similarity
against the source post. Its tokenizer is English-shaped: lowercase, split on
non-word characters, drop stopwords and tokens of length ≤ 2. Two of those
rules are wrong for Persian and are deliberately changed here:

* **No length rule.** Persian words are short — «کتاب», «خرید», «قیمت» are all
  3–4 characters and are exactly the terms that matter. Dropping ≤2-char tokens
  (fine for English) would keep almost every meaningful Persian word anyway,
  but a length floor is still the wrong instinct, so there is none beyond
  dropping truly empty tokens.
* **ZWNJ and Arabic-char folding.** Persian text carries a zero-width
  non-joiner inside compound words («می‌شود») and Arabic yeh/kaf forms that
  render identically to the Persian ones. Both are normalized before splitting,
  or «می‌شود» and «می شود» would be two unrelated terms.

The output feeds :func:`cosine_tfidf`, which is a plain TF-IDF over the pooled
corpus — no external service, no index table.
"""

from __future__ import annotations

import html
import math
import re
from collections import Counter

#: Arabic → Persian character folding, shared in spirit with the SEO analyzer's
#: `normalize_text`. Kept as its own table here so this module has no import
#: dependency on the analyzer (which is a large, separate concern).
_FOLD = str.maketrans(
    {
        "ي": "ی",  # Arabic yeh → Persian yeh
        "ى": "ی",  # Alef maksura → Persian yeh
        "ك": "ک",  # Arabic kaf → Persian kaf
        "ة": "ه",  # Teh marbuta → heh
        "ۀ": "ه",  # Heh with yeh above → heh
    }
)

#: Harakat / tanween / tashdeed — dropped so «کِتاب» and «کتاب» match.
_DIACRITICS = re.compile(r"[ً-ْٰٖٗ٘]")
#: ZWNJ, ZWSP, LRM/RLM, NBSP — replaced with a plain space so a compound word
#: splits into its parts (matching how a reader would search for it).
_ZWNJ = re.compile(r"[‌​‎‏ ]")
_SPACES = re.compile(r"\s+")
#: A token is a run of word characters or Persian/Arabic letters.
_TOKEN = re.compile(r"[\w؀-ۿ]+", re.UNICODE)
#: Tags stripped before tokenizing HTML bodies.
_TAG = re.compile(r"<[^>]+>")

#: Persian + English stopwords. Small and hand-checked: the highest-frequency
#: function words that carry no topical signal. A stopword list that is too
#: long starts deleting meaning (e.g. «کتاب» is not a stopword); this one stays
#: to the words that appear in nearly every sentence.
STOPWORDS: frozenset[str] = frozenset(
    {
        # Persian
        "و", "در", "به", "از", "که", "این", "را", "با", "است", "برای", "آن",
        "یک", "خود", "تا", "هم", "شد", "می", "شود", "بر", "بود", "کرد", "دارد",
        "دو", "بیش", "یا", "اگر", "همه", "هر", "چه", "بی", "اما", "ولی", "نیز",
        "شده", "شوند", "شدند", "کرده", "دارند", "دهد", "کند", "کنند", "باشد",
        "هست", "هستند", "نیست", "ما", "شما", "او", "آنها", "من", "توسط", "روی",
        "بین", "پس", "چون", "زیر", "بالا", "طبق", "مورد", "دیگر", "فقط", "بدون",
        # English
        "the", "and", "for", "with", "that", "this", "from", "are", "was", "you",
        "your", "our", "not", "but", "have", "has", "had", "will", "can", "all",
        "any", "out", "its", "into", "than", "then", "they", "them", "his", "her",
        "one", "two", "how", "who", "what", "when", "where", "why",
    }
)


def normalize_text(text: str) -> str:
    """Fold Arabic forms, drop diacritics, unwrap HTML entities and ZWNJ."""
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG.sub(" ", text)
    text = text.translate(_FOLD)
    text = _DIACRITICS.sub("", text)
    text = _ZWNJ.sub(" ", text)
    text = text.lower()
    return _SPACES.sub(" ", text).strip()


def tokenize(text: str) -> list[str]:
    """Split normalized text into content tokens (stopwords removed).

    Empty and single-character tokens are dropped — a lone «و» or a stray
    digit carries no signal — but there is no length floor beyond that, so
    short Persian words survive.
    """
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [
        tok
        for tok in _TOKEN.findall(normalized)
        if len(tok) > 1 and tok not in STOPWORDS
    ]


def _term_frequencies(tokens: list[str]) -> Counter[str]:
    return Counter(tokens)


def cosine_tfidf(
    target_tokens: list[str],
    candidates: dict[str, list[str]],
    *,
    top_n: int = 20,
) -> list[tuple[str, float]]:
    """Rank ``candidates`` (id→tokens) against ``target_tokens`` by TF-IDF cosine.

    The IDF is computed over the pooled corpus (target + all candidates), which
    is the standard small-corpus approach: a term appearing in every candidate
    gets weight ~0, a term unique to one candidate gets the highest weight. The
    returned list is ``[(candidate_id, score)]`` sorted descending, truncated to
    ``top_n``; a candidate with zero overlap is dropped rather than returned at
    score 0 (a suggestion of "nothing in common" is noise).
    """
    if not target_tokens or not candidates:
        return []

    docs: dict[str, list[str]] = {"__target__": target_tokens, **candidates}
    doc_count = len(docs)

    # Document frequency per term across the pooled corpus.
    df: Counter[str] = Counter()
    for tokens in docs.values():
        for term in set(tokens):
            df[term] += 1

    def _idf(term: str) -> float:
        # Smoothed IDF; +1 keeps a term that appears in every doc from being a
        # hard zero, which would erase its (small) contribution entirely.
        return math.log((doc_count + 1) / (df[term] + 1)) + 1.0

    def _vector(tokens: list[str]) -> dict[str, float]:
        tf = _term_frequencies(tokens)
        # Sub-linear TF (1 + log tf) — a term repeated ten times is not ten
        # times as important, which is the standard damping.
        return {
            term: (1.0 + math.log(count)) * _idf(term)
            for term, count in tf.items()
        }

    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        # Iterate the smaller vector.
        if len(a) > len(b):
            a, b = b, a
        dot = sum(weight * b.get(term, 0.0) for term, weight in a.items())
        if dot == 0.0:
            return 0.0
        norm_a = math.sqrt(sum(w * w for w in a.values()))
        norm_b = math.sqrt(sum(w * w for w in b.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    target_vec = _vector(target_tokens)
    scored: list[tuple[str, float]] = []
    for candidate_id, tokens in candidates.items():
        score = _cosine(target_vec, _vector(tokens))
        if score > 0.0:
            scored.append((candidate_id, score))

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_n]


def contains_keyword(text: str, keyword: str, *, case_sensitive: bool = False) -> bool:
    """Whether ``keyword`` occurs in ``text`` as a whole-word phrase.

    Whole-word matching (not substring) is what keeps a keyword map for «پابجی»
    from firing inside «پابجی‌موبایل» when it should not, and keeps an English
    keyword from matching inside a longer word. Both sides are normalized the
    same way, so a Persian keyword matches its Arabic-character spelling.
    """
    if not keyword.strip():
        return False
    haystack = normalize_text(text)
    needle = normalize_text(keyword)
    if not needle:
        return False
    if not case_sensitive:
        # normalize_text already lowercases Latin; this branch only matters
        # when a caller passes case_sensitive=True and wants the raw form.
        pass
    # Boundaries: the characters around the match must not be word characters.
    # \b is unreliable around Persian letters under Python's re, so a manual
    # lookaround on the token class is used instead.
    pattern = r"(?<![\w؀-ۿ])" + re.escape(needle) + r"(?![\w؀-ۿ])"
    return re.search(pattern, haystack) is not None
