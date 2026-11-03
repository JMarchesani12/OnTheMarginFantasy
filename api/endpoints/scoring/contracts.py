"""Scoring-read failures independent of HTTP status or transport."""


class ScoringReadDenied(Exception):
    code = 'scoring_read_denied'


class ScoringRejected(ValueError):
    """Domain rejection with legacy ValueError compatibility."""
    code = 'scoring_rejected'
