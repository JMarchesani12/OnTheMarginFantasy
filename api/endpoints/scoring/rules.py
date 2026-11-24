"""Pure bonus-award rules: supplied facts only, no database or transport."""
from typing import Dict, List

def playoff_depth_bonus(depths, member_ids, config) -> Dict[int, float]:
    """
        Bonus based on how deep a member's teams go in primary postseason.

        Config keys (optional):
          - "first", "second", "third", "fourth", ... -> points

        Only members with depth > 0 can receive points.
        """
    results: Dict[int, float] = {mid: 0.0 for mid in member_ids}
    if not member_ids:
        return results
    POS_KEYS = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth'}
    ordered = sorted(member_ids, key=lambda mid: (-depths[mid], mid))
    current_pos = 1
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and depths[ordered[j]] == depths[ordered[i]]:
            j += 1
        tier_key = POS_KEYS.get(current_pos)
        if tier_key and tier_key in config:
            pts = float(config[tier_key])
            for mid in ordered[i:j]:
                if depths[mid] > 0:
                    results[mid] += pts
        current_pos += j - i
        i = j
    return results

def conference_champion_bonus(champ_counts, member_ids, config) -> Dict[int, float]:
    """
        Bonus based on how many segment-level tournaments a member won.

        Config keys:
          - "first", "second", "third", "fourth", ... -> points
        """
    results: Dict[int, float] = {mid: 0.0 for mid in member_ids}
    if not member_ids:
        return results
    POS_KEYS = {1: 'first', 2: 'second', 3: 'third', 4: 'fourth'}
    ordered = sorted(member_ids, key=lambda mid: (-champ_counts[mid], mid))
    current_pos = 1
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and champ_counts[ordered[j]] == champ_counts[ordered[i]]:
            j += 1
        tier_key = POS_KEYS.get(current_pos)
        if tier_key and tier_key in config:
            pts = float(config[tier_key])
            for mid in ordered[i:j]:
                if champ_counts[mid] > 0:
                    results[mid] += pts
        current_pos += j - i
        i = j
    return results

def conference_bottom_bonus(pd_totals, member_ids, config) -> Dict[int, float]:
    """
        Negative bonus (penalty) for poor performance in segment-level tournaments.

        Config keys:
          - "last", "secondLast", "thirdLast", ... -> negative points

        We rank members by total segment-tournament PD (worst = most negative).
        """
    results: Dict[int, float] = {mid: 0.0 for mid in member_ids}
    if not member_ids:
        return results
    NEG_POS_KEYS = {1: 'last', 2: 'secondLast', 3: 'thirdLast', 4: 'fourthLast'}
    ordered = sorted(member_ids, key=lambda mid: (pd_totals[mid], mid))
    current_pos = 1
    i = 0
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and pd_totals[ordered[j]] == pd_totals[ordered[i]]:
            j += 1
        tier_key = NEG_POS_KEYS.get(current_pos)
        if tier_key and tier_key in config:
            pts = float(config[tier_key])
            for mid in ordered[i:j]:
                if pd_totals[mid] != 0:
                    results[mid] += pts
        current_pos += j - i
        i = j
    return results


NATIONAL_BONUS_CODES = frozenset({'NCAA_TOURNEY', 'FCS_PLAYOFFS', 'FBS_PLAYOFFS'})


def conference_placement_bonus(placements, owned_teams, config, *, bottom=False):
    """Sum each current team's configured final conference placement award."""
    keys = {1:'last',2:'secondLast',3:'thirdLast',4:'fourthLast'} if bottom else {1:'first',2:'second',3:'third',4:'fourth'}
    field = 'bottomRank' if bottom else 'rank'
    return {mid: sum(float(config.get(keys.get(placements.get(team,{}).get(field)),0))
                     for team in set(teams)) for mid,teams in owned_teams.items()}


def national_playoff_bonus(depths_by_tournament, member_ids, points):
    """One full farthest award per manager per eligible national competition."""
    results = {mid:0.0 for mid in member_ids}
    for code,depths in depths_by_tournament.items():
        if code not in NATIONAL_BONUS_CODES:
            continue
        farthest = max((depths.get(mid,0) for mid in member_ids), default=0)
        if farthest > 0:
            for mid in member_ids:
                if depths.get(mid,0)==farthest:
                    results[mid] += float(points)
    return results
