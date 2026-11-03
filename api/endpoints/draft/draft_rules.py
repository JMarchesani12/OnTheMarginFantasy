"""Pure draft settings validation and turn-order arithmetic."""
import math


def settings_from_league(league):
    settings = league["settings"] or {}
    draft = (settings.get("draft") or {})

    # Exact keys based on what you provided
    draft_type_raw = (draft.get("draftType") or "SNAKE")
    selection_time = draft.get("selectionTime")
    number_of_rounds = draft.get("numberOfRounds")
    timeout_action_raw = (draft.get("timeoutAction") or "AUTO-SKIP")
    grace_seconds = draft.get("graceSeconds", 0)

    try:
        selection_time = int(selection_time)
        number_of_rounds = int(number_of_rounds)
        grace_seconds = int(grace_seconds)
    except Exception as e:
        raise ValueError("Invalid draft settings types. Expected integers for selectionTime/numberOfRounds/graceSeconds.") from e

    if selection_time <= 0:
        raise ValueError("League settings draft.selectionTime must be > 0")
    if number_of_rounds <= 0:
        raise ValueError("League settings draft.numberOfRounds must be > 0")
    if grace_seconds < 0:
        raise ValueError("League settings draft.graceSeconds must be >= 0")

    draft_type = str(draft_type_raw).upper()
    if draft_type not in ("SNAKE", "STRAIGHT"):
        raise ValueError("League settings draft.draftType must be SNAKE or STRAIGHT")

    timeout_action = str(timeout_action_raw).upper()
    if timeout_action not in ("AUTO-PICK", "AUTO-SKIP"):
        raise ValueError("League settings draft.timeoutAction must be AUTO-PICK or AUTO-SKIP")

    num_players = int(league["numPlayers"])
    if num_players <= 0:
        raise ValueError("League numPlayers must be > 0")

    return {
        "draftType": draft_type,                 # "SNAKE" | "STRAIGHT"
        "selectionTime": selection_time,         # seconds
        "numberOfRounds": number_of_rounds,
        "timeoutAction": timeout_action,         # "AUTO-PICK" | "AUTO-SKIP"
        "graceSeconds": grace_seconds,
        "numPlayers": num_players,
    }


def compute_round_and_pos(overall_pick, num_players):
    """round_number is 1-indexed; pos_in_round is 1..num_players"""
    round_number = math.ceil(overall_pick / num_players)
    pos_in_round = overall_pick - (round_number - 1) * num_players
    return round_number, pos_in_round


def draft_order_for_pick(draft_type, round_number, pos_in_round, num_players):
    """
    Returns the draftOrder (1..num_players) who is on the clock for this pick.
    """
    if draft_type == "STRAIGHT":
        return pos_in_round
    # SNAKE
    if round_number % 2 == 1:
        return pos_in_round
    return num_players - pos_in_round + 1
