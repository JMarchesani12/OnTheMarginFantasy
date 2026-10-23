"""Sport-independent phase matching and per-game tournament scoring."""
import datetime as dt
from decimal import Decimal, ROUND_HALF_UP
import re
from zoneinfo import ZoneInfo


def score_margin(margin, rules):
    value = max(0, margin) if rules.get('positiveOnly') else margin
    return int((Decimal(value) * Decimal(str(rules.get('marginMultiplier', 1))))
               .quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def _normalized(value):
    return ' '.join(re.findall(r'[a-z0-9]+', str(value).lower()))


def select_phase(phases, game, when, conference_ids=frozenset()):
    """Explicit event overrides win; otherwise require source identity + date.

    Conference IDs represent memberships shared by both competing teams. Dates
    alone never select a tournament. Ambiguity fails rather than silently scoring.
    """
    active = [p for p in phases if p['startDate'] <= when < p['endDate']]
    event_id = str(game.get('externalGameId', ''))
    known_overrides = [p for p in phases if event_id and event_id in (p.get('rules') or {}).get('eventIds', [])]
    overrides = [p for p in known_overrides if p in active]
    if known_overrides and not overrides:
        raise ValueError(f'Tournament event {event_id} is outside its configured dates')
    if len(overrides) == 1:
        return overrides[0]['id']
    if overrides:
        raise ValueError(f'Ambiguous tournament override for event {event_id}')
    labels = [_normalized(label) for label in game.get('tournamentLabels', [])]
    source_ids = set(map(str, game.get('tournamentIds', [])))
    matches = []
    identified = False
    for p in phases:
        rules = p.get('rules') or {}
        label_match = any(f' {_normalized(alias)} ' in f' {label} '
                          for alias in rules.get('sourceLabels', []) for label in labels)
        id_match = bool(source_ids.intersection(rules.get('sourceIds', [])))
        if not (label_match or id_match):
            continue
        identified = True
        if p not in active:
            continue
        if p['type'] == 'ConferenceTournament' and p.get('sportConferenceId') not in conference_ids:
            continue
        matches.append(p)
    if len(matches) == 1:
        return matches[0]['id']
    if matches or identified or game.get('seasonType') == 3:
        raise ValueError(f'Unmatched or ambiguous postseason event {event_id}: {labels}')
    # Missing labels during a known conference window must not silently become regular games.
    if any(p['type'] == 'ConferenceTournament' and p.get('sportConferenceId') in conference_ids
           for p in active) or (game.get('seasonType') != 2 and any(
               (p.get('rules') or {}).get('scoringPeriod') for p in active)):
        raise ValueError(f'Tournament metadata required for event {event_id}')
    regular = [p for p in active if p['type'] == 'RegularSeason']
    if len(regular) != 1:
        raise ValueError(f'Expected one regular season phase for event {event_id}')
    return regular[0]['id']


def final_period(phases, calendar_timezone=None):
    periods = [p for p in phases if (p.get('rules') or {}).get('scoringPeriod') == 'BASKETBALL_FINAL']
    if not periods:
        return None
    return (min(p['startDate'].astimezone(calendar_timezone or ZoneInfo(p['rules'].get('timezone', 'UTC'))).date() for p in periods),
            max((p['endDate'] - dt.timedelta(microseconds=1)).astimezone(
                calendar_timezone or ZoneInfo(p['rules'].get('timezone', 'UTC'))).date() for p in periods))
