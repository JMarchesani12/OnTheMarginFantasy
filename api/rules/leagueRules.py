"""Versioned scoring definitions. Never edit a published version; add a new one."""
import json
from copy import deepcopy
from types import MappingProxyType

CURRENT_VERSION = 'v1'
LEGACY_VERSION = 'v1'
# Each immutable version contains basketball and the existing default for other sports.
VERSIONS = MappingProxyType({'v1': MappingProxyType({
    'thresholds': MappingProxyType({1: 2, 'default': 1}),
    'favoredWinMultiplier': 0.5,
    'favoredLossMultiplier': 2,
    'rounding': 'away_from_zero',
    'doubleOwnedMargin': 0,
})})
SPORT_NAMES = {1: 'Basketball', 2: 'Football'}


def parse_settings(settings):
    if settings is None:
        return {}
    if isinstance(settings, str):
        try:
            settings = json.loads(settings)
        except (ValueError, TypeError) as exc:
            raise ValueError('League settings must be an object') from exc
    if not isinstance(settings, dict):
        raise ValueError('League settings must be an object')
    return deepcopy(settings)


def resolve_rules(sport_id, settings):
    settings = parse_settings(settings)
    version = settings.get('ruleSetVersion', LEGACY_VERSION)
    if not isinstance(version, str) or version not in VERSIONS:
        raise ValueError(f'Unsupported league rules version: {version}')
    sport_id = int(sport_id) if sport_id is not None else None
    definition = VERSIONS[version]
    return {
        'version': version,
        'minimumTierGap': definition['thresholds'].get(sport_id, definition['thresholds']['default']),
        **{key: definition[key] for key in ('favoredWinMultiplier', 'favoredLossMultiplier', 'rounding', 'doubleOwnedMargin')},
    }


def settings_for_creation(sport_id, settings):
    settings = parse_settings(settings)
    if 'ruleSetVersion' in settings:
        resolve_rules(sport_id, settings)
    settings['ruleSetVersion'] = CURRENT_VERSION
    resolve_rules(sport_id, settings)
    return settings


def settings_for_update(sport_id, existing, proposed):
    version = resolve_rules(sport_id, existing)['version']
    proposed = parse_settings(proposed)
    if 'ruleSetVersion' in proposed and proposed['ruleSetVersion'] != version:
        raise ValueError('The league rules version cannot be changed')
    proposed['ruleSetVersion'] = version
    return proposed


def rule_summary(rules):
    return (f"Tier adjustments apply when teams are {rules['minimumTierGap']} or more tiers apart. "
            'Against a lower-tier opponent, winning margins are halved and losing margins doubled; '
            'against a higher-tier opponent, the reverse applies.')


def adjust_margin(raw_margin, owned_tier, opponent_tier, rules, double_owned=False):
    raw_margin = int(raw_margin)
    result = {'rawMargin': raw_margin, 'adjustedMargin': raw_margin, 'tierGap': None,
              'minimumTierGap': rules['minimumTierGap'], 'applied': False,
              'multiplier': 1, 'tone': 'neutral', 'explanation': None}
    if double_owned:
        result.update(adjustedMargin=rules['doubleOwnedMargin'], explanation='You own both teams: 0 points.')
        return result
    if owned_tier is None or opponent_tier is None:
        return result
    gap = abs(int(owned_tier) - int(opponent_tier))
    result['tierGap'] = gap
    if gap < rules['minimumTierGap'] or raw_margin == 0:
        return result
    favored = int(owned_tier) < int(opponent_tier)
    multiplier = (rules['favoredWinMultiplier'] if raw_margin > 0 else rules['favoredLossMultiplier']) if favored else (
        rules['favoredLossMultiplier'] if raw_margin > 0 else rules['favoredWinMultiplier'])
    magnitude = (abs(raw_margin) + 1) // 2 if multiplier == 0.5 else abs(raw_margin) * multiplier
    adjusted = int(magnitude if raw_margin > 0 else -magnitude)
    outcome = 'Won' if raw_margin > 0 else 'Lost'
    direction = 'lower' if favored else 'higher'
    result.update(adjustedMargin=adjusted, applied=True, multiplier=multiplier,
                  tone='red' if favored else 'green',
                  explanation=f'{outcome} by {abs(raw_margin)} → {adjusted:+d} points: opponent is {gap} tiers {direction}.')
    return result


def describe_rules(sport_id, settings, teams):
    settings = parse_settings(settings)
    rules = resolve_rules(sport_id, settings)
    sections = [
        {'heading': 'Weekly scoring', 'paragraphs': [
            'Your weekly differential is the sum of adjusted game margins for the teams you own that week. Owning both sides of a game contributes zero.',
            'Members are ranked by weekly differential. In a league with N participating members, weekly points run from N for first place down to 1 for last place.',
            'Weekly ties are checked by raw head-to-head differential, then the biggest absolute adjusted single-game margin (a win or a loss). The next check runs only if every member of the tied group has the same value. If a check distinguishes any members, members still equal on that check are ordered by member ID. Fully unresolved ties also retain member-ID order; points are not split.']},
        {'heading': 'Tier adjustments', 'paragraphs': [rule_summary(rules),
            'Lower tier numbers indicate stronger teams. Halved odd margins round away from zero: +21 becomes +11 and −21 becomes −11. Zero remains zero. Larger tier gaps do not compound the multiplier.',
            'A team without a stored tier is treated as one tier below the highest numbered stored tier for that sport. If no tiers are stored, all such teams are treated as Tier 1.']},
        {'heading': 'Season standings and bonuses', 'paragraphs': [
            'Season standings include weekly points and the configured bonus awards. Bonus settings below are specific to this league.',
            'Season ties are checked using playoff depth, number of conference/segment championships, playoff head-to-head differential, conference postseason head-to-head differential, and the latest non-tied week, in that order.']},
        {'heading': 'League configuration', 'paragraphs': [
            'New trades are blocked after the configured trade deadline; free-agent requests are blocked after the configured free-agent deadline. An unset deadline imposes no date restriction.',
            'Draft and transaction settings below show the saved configuration for this league. Missing settings are not assigned new defaults here.',
            'This rules version preserves scoring definitions. Team tier assignments shown below are current; tier assignments and editable league bonus settings are not historical snapshots.']},
    ]
    groups = {}
    for team in teams:
        groups.setdefault(team['tier'], []).append(team)
    tiers = [{'tier': tier, 'teams': sorted(members, key=lambda t: t['teamName'].casefold())}
             for tier, members in sorted(groups.items(), key=lambda item: item[0])]
    gap = rules['minimumTierGap']
    examples = [adjust_margin(margin, a, b, rules)
                for margin, a, b in [(21, 1, 1 + gap), (-21, 1, 1 + gap), (21, 1 + gap, 1), (-21, 1 + gap, 1)]]
    return {'sportId': sport_id, 'sportName': SPORT_NAMES.get(sport_id, f'Sport {sport_id}'),
            'version': rules['version'], 'tierAdjustment': rules,
            'summary': rule_summary(rules), 'sections': sections,
            'settings': {key: settings[key] for key in ('bonuses', 'draft', 'transactions', 'timezone', 'subdivision') if key in settings},
            'tiers': tiers, 'examples': examples}
