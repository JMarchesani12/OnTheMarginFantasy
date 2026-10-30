"""Roster domain failures; adapters/facades choose their own translations."""


class RosterAccessDenied(Exception):
    code = 'roster_read_denied'


class RosterWeekUnavailable(Exception):
    code = 'roster_week_unavailable'
