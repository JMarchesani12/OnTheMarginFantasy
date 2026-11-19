"""Deterministic team aliases and conservative typo matching, mirrored in TS.

Aliases are supplied by database reads; this module never reads seed data.
"""
import re
import unicodedata
from functools import lru_cache

STRONG_MATCH = 50
MAX_QUERY_LENGTH = 120
MAX_QUERY_TOKENS = 8


def normalize_team_search_text(value):
    value = ''.join(c for c in unicodedata.normalize('NFKD', value or '') if not unicodedata.combining(c))
    value = value.lower().replace('&', ' and ').replace("'", '').replace('’', '').replace('.', '')
    tokens = re.sub(r'[^a-z0-9]+', ' ', value).split()
    return ' '.join('university' if token == 'univ' else token for token in tokens)


def _variants(value):
    normalized = normalize_team_search_text(value)
    if not normalized: return ()
    variants = {normalized}
    tokens = normalized.split()
    if 'st' in tokens:
        variants.update(' '.join(replacement if token == 'st' else token for token in tokens)
                        for replacement in ('state', 'saint'))
    for word in ('state', 'saint'):
        if word in tokens: variants.add(' '.join('st' if token == word else token for token in tokens))
    without_institution = re.sub(r'^university of | university$', '', normalized).strip()
    if without_institution: variants.add(without_institution)
    if len(tokens) > 1 and all(len(token) == 1 for token in tokens): variants.add(''.join(tokens))
    return tuple(sorted(variants))


@lru_cache(maxsize=4096)
def _candidate_names(candidate, supplied_aliases):
    original = _variants(candidate)
    aliases = {variant for alias in supplied_aliases for variant in _variants(alias)}
    return original, tuple(sorted(aliases.difference(original)))


def _all_tokens_match(query_tokens, candidate_tokens, predicate):
    # Bipartite matching: a repeated query word cannot reuse one candidate word.
    assigned = {}
    def assign(query_index, seen):
        for index, token in enumerate(candidate_tokens):
            if index in seen or not predicate(query_tokens[query_index], token): continue
            seen.add(index)
            if index not in assigned or assign(assigned[index], seen):
                assigned[index] = query_index
                return True
        return False
    return all(assign(index, set()) for index in range(len(query_tokens)))


def _prefix(query, candidate):
    return candidate.startswith(query) and not (candidate == 'university' and query != candidate)


def _lexical_rank(candidate, query):
    if candidate == query: return 100
    # UNI is a school abbreviation, not a substring of every "University".
    if len(query) <= 3:
        candidate = ' '.join(token for token in candidate.split() if token != 'university')
    if candidate.startswith(query): return 90
    if query in candidate: return 75
    return 50 if _all_tokens_match(query.split(), candidate.split(), _prefix) else 0


def _edit_distance(left, right):
    # Optimal-string-alignment distance includes adjacent transposed letters.
    previous_previous = None
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            distance = min(current[-1] + 1, previous[j] + 1, previous[j-1] + (a != b))
            if i > 1 and j > 1 and a == right[j-2] and left[i-2] == b:
                distance = min(distance, previous_previous[j-2] + 1)
            current.append(distance)
        previous_previous, previous = previous, current
    return previous[-1]


def _typo_word_matches(query, candidate):
    if _prefix(query, candidate): return True
    if min(len(query), len(candidate)) < 4 or max(len(query), len(candidate)) > 32: return False
    allowance = 2 if min(len(query), len(candidate)) >= 8 else 1
    return abs(len(query) - len(candidate)) <= allowance and _edit_distance(query, candidate) <= allowance


def rank_team_search_match(candidate, query, aliases=()):
    if len(query) > MAX_QUERY_LENGTH: return 0
    normalized_query = normalize_team_search_text(query)
    if not normalized_query or len(normalized_query.split()) > MAX_QUERY_TOKENS: return 0
    queries = _variants(query)
    originals, aliases = _candidate_names(candidate, tuple(aliases))
    score = max((_lexical_rank(name, term) for name in originals for term in queries), default=0)
    # Exact aliases outrank name prefixes; all lexical matches outrank typos.
    alias_ranks = {100: 98, 90: 88, 75: 70, 50: 50, 0: 0}
    for name in aliases:
        for term in queries: score = max(score, alias_ranks[_lexical_rank(name, term)])
    if score: return score
    for name in (*originals, *aliases):
        for term in queries:
            if _all_tokens_match(term.split(), name.split(), _typo_word_matches): return 30
    return 0
