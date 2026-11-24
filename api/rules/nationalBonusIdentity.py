"""Verified provider phrases for the three bonus-eligible national brackets."""
import re

FINAL_ROUNDS = {'NCAA_TOURNEY':7, 'FCS_PLAYOFFS':5, 'FBS_PLAYOFFS':4}
PREFIXES = {'NCAA_TOURNEY': 'ncaa men s basketball championship',
            'FCS_PLAYOFFS': 'fcs championship',
            'FBS_PLAYOFFS': 'college football playoff'}


def national_game_identity(game):
    matches = set()
    for raw in game.get('tournamentLabels') or []:
        label = ' '.join(re.findall(r'[a-z0-9]+',str(raw).lower()))
        for code,prefix in PREFIXES.items():
            if not label.startswith(prefix): continue
            suffix = label[len(prefix):].strip()
            round_order = None
            if 'quarterfinal' in suffix or 'elite eight' in suffix or 'elite 8' in suffix:
                round_order = {'NCAA_TOURNEY':5,'FCS_PLAYOFFS':3,'FBS_PLAYOFFS':2}[code]
            elif 'semifinal' in suffix or 'final four' in suffix:
                round_order = FINAL_ROUNDS[code]-1
            elif 'national championship' in suffix or suffix=='championship' or (code=='FCS_PLAYOFFS' and not suffix):
                round_order = FINAL_ROUNDS[code]
            elif code=='NCAA_TOURNEY' and ('sweet sixteen' in suffix or 'sweet 16' in suffix):
                round_order = 4
            elif code=='NCAA_TOURNEY' and ('first four' in suffix or 'opening round' in suffix):
                round_order = 1
            elif re.search(r'\b(1st|first) round\b',suffix):
                round_order = 2 if code=='NCAA_TOURNEY' else 1
            elif re.search(r'\b(2nd|second) round\b',suffix):
                round_order = 3 if code=='NCAA_TOURNEY' else 2
            if round_order is not None: matches.add((code,round_order))
    return next(iter(matches)) if len(matches)==1 else (None,None)
