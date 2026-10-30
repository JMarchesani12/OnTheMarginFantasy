"""Scoring-read failures independent of HTTP status or transport."""


class ScoringReadDenied(Exception):
    code = 'scoring_read_denied'
