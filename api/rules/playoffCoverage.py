"""Known bracket formats and coverage checks before awarding final bonuses.

2027 NCAA expansion: ncaa.org/championships/march-madness/expansion-what-to-know/
2026 CFP: collegefootballplayoff.com/news/2026/1/23/2627-format
2026 FCS: ncaa.com/news/football/article/2026-11-22/2026-ncaa-division-i-football-championship-field-announced
Unknown formats stay pending rather than guessing a bracket size.
"""
from collections import Counter


def expected_round_counts(code, year):
    if code=='NCAA_TOURNEY':
        opening=12 if year==2027 else 4 if 2011<=year<=2026 and year!=2020 else None
        return {1:opening,2:32,3:16,4:8,5:4,6:2,7:1} if opening else None
    if code=='FBS_PLAYOFFS':
        if 2024<=year<=2026: return {1:4,2:4,3:2,4:1}
        if 2014<=year<=2023: return {3:2,4:1}
    if code=='FCS_PLAYOFFS' and 2022<=year<=2026:
        return {1:8,2:8,3:4,4:2,5:1}
    return None


def bracket_complete(games, expected):
    if not expected or Counter(g['roundOrder'] for g in games)!=Counter(expected):
        return False
    participants={rnd:set() for rnd in expected}
    winners={rnd:set() for rnd in expected}
    losers=set()
    for rnd in sorted(expected):
        for game in (g for g in games if g['roundOrder']==rnd):
            home,away=game['homeTeamId'],game['awayTeamId']
            if home==away or home in participants[rnd] or away in participants[rnd] or home in losers or away in losers:
                return False
            participants[rnd].update((home,away))
            winner,loser=(home,away) if game['homeScore']>game['awayScore'] else (away,home)
            winners[rnd].add(winner);losers.add(loser)
    rounds=sorted(expected)
    for previous,current in zip(rounds,rounds[1:]):
        if not winners[previous].issubset(participants[current]): return False
        # New entrants are byes only when the next round has more slots than
        # the previous round has winners (CFP/FCS/opening-round byes).
        if len(participants[current]-winners[previous]) != 2*expected[current]-expected[previous]:
            return False
    return True
