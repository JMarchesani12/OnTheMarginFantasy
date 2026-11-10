"""Stored conference-cap policy shared by acquisition and reporting boundaries."""


def require_conference_cap(value, conference_id=None):
    """Zero permits no teams; missing/negative/noninteger values are configuration errors."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        conference = f' for conference {conference_id}' if conference_id is not None else ''
        raise ValueError(f'Invalid conference cap configuration{conference}: expected a nonnegative integer maxTeamsPerOwner')
    return value
