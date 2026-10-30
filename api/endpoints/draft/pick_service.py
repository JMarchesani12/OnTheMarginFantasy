"""Draft allocation and timeout policy, owning each write transaction.

Interactive callers use pick_live(UserActor, ...); worker/trusted callers use
explicit job methods. Legacy names remain for the inherited DraftModel facade.
Repository calls always use the current connection, including finalization.
"""
import logging
import math
import secrets
from sqlalchemy.exc import IntegrityError
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta

from sqlalchemy.engine import Engine

from .snapshot_service import DraftSnapshotService
from .control_service import DraftControlService
from .pick_repository import DraftPickRepository
from actors import UserActor
from .draft_rules import compute_round_and_pos, draft_order_for_pick


class DraftPickService:
    def __init__(self, db: Engine, repository=None):
        self.db = db
        self._pick_repository = repository if repository is not None else DraftPickRepository()

    @property
    def pick_repository(self):
        repository = getattr(self, '_pick_repository', None)
        if repository is None:
            repository = DraftPickRepository()
            self._pick_repository = repository
        return repository

    def finalize_draft(self, league_id: int, conn=None) -> Dict[str, Any]:
        return DraftControlService(getattr(self, "db", None)).finalize_for_job(league_id, conn)


    def is_supabase_user_in_league(self, league_id: int, supabase_uuid: str) -> bool:
        """
        supabase_uuid should be the JWT 'sub' claim (a UUID string).
        """

        with self.db.connect() as conn:
            row = self.pick_repository.membership_for_subject(conn, {"leagueId": league_id, "uuid": supabase_uuid}).fetchone()
            return row is not None

    def _get_draft_settings(self, conn, league_id: int) -> Dict[str, Any]:
        return DraftControlService(None).draft_settings(conn, league_id)

    def _compute_round_and_pos(self, overall_pick: int, num_players: int) -> tuple[int, int]:
        return compute_round_and_pos(overall_pick, num_players)

    def _draft_order_for_pick(self, draft_type: str, round_number: int, pos_in_round: int, num_players: int) -> int:
        return draft_order_for_pick(draft_type, round_number, pos_in_round, num_players)

    def _member_id_for_draft_order(self, conn, league_id: int, draft_order: int) -> int:
        row = self.pick_repository.member_for_order(conn, {"leagueId": league_id, "draftOrder": draft_order}).fetchone()
        if not row:
            raise ValueError(f"Missing LeagueMember for draftOrder={draft_order} in league={league_id}")
        return int(row._mapping["id"])

    # -----------------------------
    # Live draft pick (safe)
    # -----------------------------

    def create_draft_pick_live(
        self,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int = 1,
        *, acting_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Live draft pick (concurrency-safe):
        - Locks DraftState FOR UPDATE
        - Enforces on-the-clock member
        - Allows late picks only within graceSeconds
        - Inserts DraftPick + LeagueTeamSlot
        - Advances DraftState and resets expiresAt
        """

        # Interactive callers supply only their resolved principal ID. Trusted
        # model callers keep the default path without an HTTP identity.

        actor_params = {}
        if acting_user_id is not None:

            actor_params = {'actingUserId': acting_user_id}

        with self.db.begin() as conn:
            if acting_user_id is not None:
                owned = self.pick_repository.live_owned_member(conn, {
                    'memberId': member_id, 'leagueId': league_id, **actor_params,
                }).fetchone()
                if not owned:
                    raise PermissionError('League member not found')
            cfg = self._get_draft_settings(conn, league_id)
            num_players = cfg["numPlayers"]
            rounds = cfg["numberOfRounds"]
            selection_time = cfg["selectionTime"]
            grace_seconds = cfg["graceSeconds"]
            draft_type = cfg["draftType"]

            total_picks = rounds * num_players

            # 1) Lock DraftState
            state = self.pick_repository.live_state_for_update(conn, {"leagueId": league_id}).fetchone()

            if not state:
                raise ValueError(f"DraftState not found for league {league_id}")

            status = str(state._mapping["status"])
            current_overall = int(state._mapping["currentOverallPickNumber"])
            current_member = state._mapping["currentMemberId"]

            if status != "live":
                raise ValueError(f"Draft is not live (status={status})")

            if current_overall > total_picks:
                raise ValueError("Draft already completed")

            expected_member_id = self._get_expected_member_for_overall(conn, league_id, current_overall)
            if expected_member_id is None:
                raise ValueError("DraftTurn missing for this pick number")
            if expected_member_id != member_id:
                raise ValueError("Not your turn")

            # 2) Enforce expiry + grace (server-side)
            # Allow pick if now() <= expiresAt + graceSeconds
            expires_at = state._mapping["expiresAt"]
            if expires_at is not None:
                # expires_at is timezone-aware (timestamptz), compare in UTC
                now_utc = datetime.now(timezone.utc)
                deadline = expires_at + timedelta(seconds=grace_seconds)
                if now_utc > deadline:
                    raise ValueError("Pick window expired")

            # 3) Your existing “already owned” check (still valuable)
            ownership_row = self.pick_repository.live_team_ownership(conn, {"leagueId": league_id, "sportTeamId": sport_team_id, "week": acquired_week}).fetchone()
            if ownership_row:
                raise ValueError("Team is already owned in this league for this week")

            # 3b) Conference cap check (keep your current helper)
            self._assert_member_can_add_team_conference_cap(
                conn=conn,
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=acquired_week,
            )

            # 4) Compute round/pickInRound based on DraftState
            round_number, pos_in_round = self._compute_round_and_pos(current_overall, num_players)
            pick_in_round = self._draft_order_for_pick(draft_type, round_number, pos_in_round, num_players)

            # 5) Insert DraftPick (unique constraints protect races)
            try:
                draft_row = self.pick_repository.insert_live_pick(conn, {
                        "leagueId": league_id,
                        "overallPickNumber": current_overall,
                        "roundNumber": round_number,
                        "pickInRound": pick_in_round,
                        "memberId": member_id,
                        "sportTeamId": sport_team_id,
                        **actor_params,
                    }).fetchone()
            except IntegrityError as e:
                raise ValueError("Pick conflict (team already drafted or slot already filled).") from e

            if not draft_row:
                if acting_user_id is not None:
                    raise PermissionError('League member not found')
                raise RuntimeError("Failed to insert DraftPick")

            draft_pick = dict(draft_row._mapping)

            # 6) Insert LeagueTeamSlot
            slot_row = self.pick_repository.insert_live_slot(conn, {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id,
                    "acquiredWeek": acquired_week,
                    "acquiredVia": "Draft",
                }).fetchone()

            draft_pick["leagueTeamSlotId"] = int(slot_row._mapping["id"])

            # 7) Advance DraftState
            next_overall = current_overall + 1

            if next_overall > total_picks:
                self.pick_repository.live_advance_past_end(conn, {"leagueId": league_id, "nextOverall": next_overall})
                self.finalize_draft(league_id, conn=conn)

                draft_pick["draftComplete"] = True
                self.pick_repository.notify(conn, league_id, "draft_pick")
                return draft_pick

            nxt = self._get_next_unpicked_turn_from(conn, league_id, next_overall)
            if not nxt:
                # No turns left (safety)
                self.pick_repository.live_advance_without_turn(conn, {"leagueId": league_id, "nextOverall": next_overall})
                self.finalize_draft(league_id, conn=conn)
                draft_pick["draftComplete"] = True
                self.pick_repository.notify(conn, league_id, "draft_pick")
                return draft_pick

            next_overall, next_member_id = nxt

            self.pick_repository.live_advance_next(conn, {
                    "leagueId": league_id,
                    "nextOverall": next_overall,
                    "nextMemberId": next_member_id,
                    "selectionTime": selection_time,
                })

            draft_pick["draftComplete"] = False
            draft_pick["nextMemberId"] = next_member_id
            draft_pick["nextOverallPickNumber"] = next_overall

            return draft_pick

    # -----------------------------
    # Timeout processing (AUTO-SKIP / AUTO-PICK)
    # -----------------------------

    def process_expired_pick_if_needed(self, league_id: int) -> Optional[Dict[str, Any]]:
        """
        Call this from a scheduler/cron loop.
        If the current pick is expired past grace, apply timeoutAction:
          - AUTO-SKIP: advance state to next member
          - AUTO-PICK: (stub) you choose a team and call create_draft_pick_live-like insertion
        Returns a dict describing what happened, or None if nothing happened.
        """

        with self.db.begin() as conn:
            cfg = self._get_draft_settings(conn, league_id)
            num_players = cfg["numPlayers"]
            rounds = cfg["numberOfRounds"]
            selection_time = cfg["selectionTime"]
            grace_seconds = cfg["graceSeconds"]
            draft_type = cfg["draftType"]
            timeout_action = cfg["timeoutAction"]

            total_picks = rounds * num_players

            state = self.pick_repository.timeout_state_for_update(conn, {"leagueId": league_id}).fetchone()

            if not state:
                return None

            if str(state._mapping["status"]) != "live":
                return None

            current_overall = int(state._mapping["currentOverallPickNumber"])
            if current_overall > total_picks:
                # already past end
                return None

            # If no expiresAt, treat as not expirable
            if state._mapping["expiresAt"] is None:
                return None

            is_expired = self.pick_repository.timeout_expired(conn, {"leagueId": league_id, "graceSeconds": grace_seconds}).fetchone()

            if not is_expired or not bool(is_expired._mapping["isExpired"]):
                return None

            # Expired beyond grace: act
            if timeout_action == "AUTO-SKIP":
                # Safety: ensure DraftTurn exists for this overall pick
                expected_row = self.pick_repository.timeout_expected_member(conn, {"leagueId": league_id, "overall": current_overall}).fetchone()

                if not expected_row:
                    raise ValueError(f"DraftTurn missing for leagueId={league_id}, overallPickNumber={current_overall}")

                timed_out_member_id = int(expected_row._mapping["memberId"])

                # Find last overall pick number that is still unpicked
                last_unpicked = self.pick_repository.timeout_last_unpicked(conn, {"leagueId": league_id}).fetchone()

                last_unpicked_overall = int(last_unpicked._mapping["lastUnpicked"] or 0)

                # If nothing left, draft is complete
                if last_unpicked_overall == 0 or current_overall > last_unpicked_overall:
                    self.finalize_draft(league_id, conn=conn)
                    return {"type": "AUTO-SKIP-MOVE-TO-END", "draftComplete": True}

                # If current_overall is the last unpicked already, "moving to end" changes nothing.
                if current_overall == last_unpicked_overall:
                    self.pick_repository.timeout_extend_clock(conn, {"leagueId": league_id, "selectionTime": selection_time})
                    return {
                        "type": "AUTO-SKIP-MOVE-TO-END",
                        "moved": False,
                        "reason": "already last unpicked",
                        "draftComplete": False,
                    }

                # Rotate DraftTurn assignments for remaining UNPICKED picks from current_overall..last_unpicked_overall:
                # - save member at current_overall
                # - shift later unpicked members forward (skipping already-picked slots)
                # - place saved member at the last unpicked slot
                self.pick_repository.timeout_rotate_turns(conn, {"leagueId": league_id, "cur": current_overall, "last": last_unpicked_overall})

                # Advance DraftState to next unpicked overall (>= current_overall)
                next_row = self.pick_repository.timeout_next_turn(conn, {"leagueId": league_id, "cur": current_overall}).fetchone()

                if not next_row:
                    self.finalize_draft(league_id, conn=conn)
                    return {"type": "AUTO-SKIP-MOVE-TO-END", "draftComplete": True}

                next_overall = int(next_row._mapping["nextOverall"])
                next_member_id = int(next_row._mapping["nextMemberId"])

                self.pick_repository.timeout_advance(conn, {
                        "leagueId": league_id,
                        "nextOverall": next_overall,
                        "nextMemberId": next_member_id,
                        "selectionTime": selection_time,
                    })

                return {
                    "type": "AUTO-SKIP-MOVE-TO-END",
                    "timedOutOverallPickNumber": current_overall,
                    "timedOutMemberId": timed_out_member_id,
                    "movedToOverallPickNumber": last_unpicked_overall,
                    "nextOverallPickNumber": next_overall,
                    "nextMemberId": next_member_id,
                    "draftComplete": False,
                }


            if timeout_action == "AUTO-PICK":
                # Who is actually on the clock? Use DraftTurn as source of truth.
                turn_row = self.pick_repository.timeout_auto_member(conn, {"leagueId": league_id, "overall": current_overall}).fetchone()

                if not turn_row:
                    raise ValueError(f"DraftTurn missing for leagueId={league_id}, overallPickNumber={current_overall}")

                on_clock_member_id = int(turn_row._mapping["memberId"])

                # Pick truly random by conference-bucket (plus Independent bucket), retrying buckets as needed
                sport_team_id = self._choose_random_team_for_auto_pick(
                    conn=conn,
                    league_id=league_id,
                    member_id=on_clock_member_id,
                    week=1,  # draft week; adjust if your draft uses a different acquired_week
                )

                if sport_team_id is None:
                    # No valid teams exist under caps/availability => nothing to pick
                    # You can either:
                    # - return None
                    # - OR fall back to your AUTO-SKIP-MOVE-TO-END logic
                    return None

                # Insert pick + slot, advance DraftState, without expiry rejection
                return self._insert_draft_pick_and_advance_state_no_expiry_check(
                    conn=conn,
                    league_id=league_id,
                    member_id=on_clock_member_id,
                    sport_team_id=sport_team_id,
                    acquired_week=1,
                    selection_time=int(selection_time),
                    num_players=int(num_players),
                    rounds=int(rounds),
                    draft_type=str(draft_type),
                )

            return None


    # Shared allocation cap policy and compatibility helper dispatch.
    def _get_conference_info_for_team(
        self,
        conn,
        league_id: int,
        sport_team_id: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns:
          { sportConferenceId, conferenceName, maxTeamsPerOwner }
        or None if the team has no conference membership (Independent).
        """

        row = self.pick_repository.conference_info(conn, {"leagueId": league_id, "sportTeamId": sport_team_id}).fetchone()
        return dict(row._mapping) if row else None

    def _count_member_teams_in_sport_conference(
        self,
        conn,
        league_id: int,
        member_id: int,
        week_number: int,
        sport_conference_id: int,
    ) -> int:
        """
        Counts how many teams this member owns (for the given week) in this sportConferenceId.
        Uses DISTINCT to avoid double counting if ConferenceMembership has duplicates.
        """

        row = self.pick_repository.member_conference_count(conn, {
                "leagueId": league_id,
                "memberId": member_id,
                "weekNumber": week_number,
                "sportConferenceId": sport_conference_id,
            }).fetchone()

        return int(row._mapping["cnt"]) if row else 0

    def _assert_member_can_add_team_conference_cap(
        self,
        conn,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int,
    ) -> None:
        """
        Raises ValueError if the member has already hit maxTeamsPerOwner
        for the conference of sport_team_id.

        Policy for teams with no conference membership:
          - allowed (treated as Independent).
        """
        conf = self._get_conference_info_for_team(conn, league_id, sport_team_id)
        if conf is None:
            # Independent / no membership: allow
            return

        max_allowed = int(conf["maxTeamsPerOwner"])
        if max_allowed <= 0:
            # 0 or negative = treat as "no cap"
            return

        sport_conference_id = int(conf["sportConferenceId"])
        current_count = self._count_member_teams_in_sport_conference(
            conn=conn,
            league_id=league_id,
            member_id=member_id,
            week_number=acquired_week,
            sport_conference_id=sport_conference_id,
        )

        if current_count >= max_allowed:
            conference_name = conf.get("conferenceName") or "Unknown Conference"
            raise ValueError(
                f"Conference cap reached for {conference_name}: "
                f"{current_count}/{max_allowed}."
            )

    def create_draft_pick(
        self,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int = 1
    ) -> Dict[str, Any]:
        """
        Creates a DraftPick row AND a LeagueTeamSlot row in a single transaction.

        - Computes overallPickNumber / roundNumber / pickInRound based on
          existing picks and League.numPlayers (snake draft).
        - Fails if the team is already owned in this league for that week.
        - NEW: Fails if the member has already hit maxTeamsPerOwner for the team’s conference.
        """

        with self.db.begin() as conn:
            # 1) Get league info (numPlayers) to compute rounds
            league_row = self.pick_repository.manual_league(conn, {"leagueId": league_id}).fetchone()

            if not league_row:
                raise ValueError(f"League {league_id} not found")

            num_players = league_row._mapping["numPlayers"]

            # 2) Make sure this team isn't already owned in this league for this week
            ownership_row = self.pick_repository.manual_team_ownership(conn, {"leagueId": league_id, "sportTeamId": sport_team_id, "week": acquired_week}).fetchone()

            if ownership_row:
                raise ValueError("Team is already owned in this league for this week")

            # NEW: 2b) Enforce conference cap (maxTeamsPerOwner) for this member
            self._assert_member_can_add_team_conference_cap(
                conn=conn,
                league_id=league_id,
                member_id=member_id,
                sport_team_id=sport_team_id,
                acquired_week=acquired_week,
            )

            # 3) Count existing picks to get next overall pick number
            pick_count_row = self.pick_repository.manual_pick_count(conn, {"leagueId": league_id}).fetchone()

            existing_picks = pick_count_row._mapping["cnt"]
            overall_pick = existing_picks + 1

            # 4) Compute roundNumber & pickInRound for snake draft
            round_number = math.ceil(overall_pick / num_players)
            pos_in_round = overall_pick - (round_number - 1) * num_players

            if round_number % 2 == 1:
                # odd round: pick order 1..num_players
                pick_in_round = pos_in_round
            else:
                # even round: reversed order
                pick_in_round = num_players - pos_in_round + 1

            # 5) Insert DraftPick


            draft_row = self.pick_repository.insert_manual_pick(conn, {
                    "leagueId": league_id,
                    "overallPickNumber": overall_pick,
                    "roundNumber": round_number,
                    "pickInRound": pick_in_round,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id
                }).fetchone()

            if not draft_row:
                raise RuntimeError("Failed to insert DraftPick")

            draft_pick = dict(draft_row._mapping)

            # 6) Insert into LeagueTeamSlot as the roster ownership


            slot_row = self.pick_repository.insert_manual_slot(conn, {
                    "leagueId": league_id,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id,
                    "acquiredWeek": acquired_week,
                    "acquiredVia": "Draft",
                }).fetchone()

            draft_pick["leagueTeamSlotId"] = slot_row._mapping["id"]
            self.pick_repository.notify(conn, league_id, "manual_pick")

        logging.debug("Created draft pick: %s", draft_pick)
        return draft_pick


    def get_rounds(self, sportId):
        with self.db.begin() as conn:
            rounds = self.pick_repository.sport_rounds(conn, {"sportId": sportId}).scalar_one_or_none()

        return rounds


    def _get_expected_member_for_overall(self, conn, league_id: int, overall_pick_number: int) -> Optional[int]:
        return DraftControlService(None).expected_member(conn, league_id, overall_pick_number)


    def _get_next_unpicked_turn_from(self, conn, league_id: int, start_overall: int) -> Optional[tuple[int, int]]:
        return DraftSnapshotService(None).next_unpicked_turn(conn, league_id, start_overall)


    # Optional but recommended: prevent changing order mid-live draft

    def _get_league_sport_id(self, conn, league_id: int) -> int:
        row = self.pick_repository.league_sport(conn, {"leagueId": league_id}).fetchone()
        if not row:
            raise ValueError(f"League {league_id} not found")
        return int(row._mapping["sport"])


    def _list_sport_conference_ids_for_sport(self, conn, sport_id: int) -> List[int]:
        rows = self.pick_repository.sport_conference_ids(conn, {"sportId": sport_id}).fetchall()
        return [int(r._mapping["id"]) for r in rows]


    def _random_choice_with_independent_bucket(self, sport_conference_ids: List[int]) -> Optional[int]:
        """
        Option A: choose a random conference uniformly.
        Independent teams are included as an extra bucket (None) with equal probability.
        """
        buckets: List[Optional[int]] = [None] + sport_conference_ids  # None = Independent
        return secrets.choice(buckets)


    def _count_owned_in_conference(
        self,
        conn,
        league_id: int,
        member_id: int,
        sport_conference_id: int,
        week: int,
    ) -> int:
        # Count currently-owned teams for this member in this conference as of 'week'
        row = self.pick_repository.owned_conference_count(conn, {
                "leagueId": league_id,
                "memberId": member_id,
                "sportConferenceId": sport_conference_id,
                "week": week,
            }).fetchone()
        return int(row._mapping["cnt"] or 0)


    def _get_conference_cap(self, conn, sport_conference_id: int) -> int:
        row = self.pick_repository.conference_cap(conn, {"sportConferenceId": sport_conference_id}).fetchone()
        if not row:
            raise ValueError(f"SportConference {sport_conference_id} not found")
        return int(row._mapping["maxTeamsPerOwner"])


    def _pick_random_available_team_in_conference(
        self,
        conn,
        league_id: int,
        sport_conference_id: int,
        week: int,
    ) -> Optional[int]:
        """
        Returns a random sportTeamId that:
        - belongs to the sport_conference_id
        - not already drafted in DraftPick (league-wide)
        - not currently owned in LeagueTeamSlot for the target week
        """
        row = self.pick_repository.random_conference_team(conn, {"leagueId": league_id, "sportConferenceId": sport_conference_id, "week": week}).fetchone()

        return int(row._mapping["sportTeamId"]) if row else None


    def _pick_random_available_independent_team(
        self,
        conn,
        league_id: int,
        sport_id: int,
        week: int,
    ) -> Optional[int]:
        """
        Independent = team in this sport that has NO ConferenceMembership row.
        NOTE: This assumes SportTeam has a column "sportId".
        If your column is named differently, update this query.
        """
        row = self.pick_repository.random_independent_team(conn, {"leagueId": league_id, "sportId": sport_id, "week": week}).fetchone()

        return int(row._mapping["sportTeamId"]) if row else None


    def _choose_random_team_for_auto_pick(
        self,
        conn,
        league_id: int,
        member_id: int,
        week: int,
    ) -> Optional[int]:
        """
        Option A (uniform by conference bucket, plus Independent bucket):
        - Choose a random bucket: one SportConference OR Independent
        - If bucket yields no valid teams, remove it and retry
        - Conference bucket must also satisfy maxTeamsPerOwner
        """
        sport_id = self._get_league_sport_id(conn, league_id)
        conference_ids = self._list_sport_conference_ids_for_sport(conn, sport_id)

        # Buckets: None = Independent, plus each SportConference id
        remaining: List[Optional[int]] = [None] + conference_ids

        while remaining:
            bucket = secrets.choice(remaining)

            if bucket is None:
                team_id = self._pick_random_available_independent_team(conn, league_id, sport_id, week)
                if team_id is not None:
                    return team_id
                remaining.remove(bucket)
                continue

            # Conference bucket: enforce cap first
            cap = self._get_conference_cap(conn, bucket)
            owned = self._count_owned_in_conference(conn, league_id, member_id, bucket, week)
            if owned >= cap:
                remaining.remove(bucket)
                continue

            team_id = self._pick_random_available_team_in_conference(conn, league_id, bucket, week)
            if team_id is not None:
                return team_id

            remaining.remove(bucket)

        return None


    def _insert_draft_pick_and_advance_state_no_expiry_check(
        self,
        conn,
        league_id: int,
        member_id: int,
        sport_team_id: int,
        acquired_week: int,
        selection_time: int,
        num_players: int,
        rounds: int,
        draft_type: str,
    ) -> Dict[str, Any]:
        """
        Same output shape as create_draft_pick_live, but does NOT reject for expired timer.
        Assumes caller already locked DraftState FOR UPDATE and confirmed it's the member's turn.
        """
        total_picks = int(rounds) * int(num_players)

        state = self.pick_repository.auto_state_for_update(conn, {"leagueId": league_id}).fetchone()
        if not state:
            raise ValueError(f"DraftState not found for league {league_id}")

        status = str(state._mapping["status"])
        current_overall = int(state._mapping["currentOverallPickNumber"])
        if status != "live":
            raise ValueError(f"Draft is not live (status={status})")
        if current_overall > total_picks:
            raise ValueError("Draft already completed")

        expected_member_id = self._get_expected_member_for_overall(conn, league_id, current_overall)
        if expected_member_id is None:
            raise ValueError(f"DraftTurn missing for leagueId={league_id}, overallPickNumber={current_overall}")
        if expected_member_id != member_id:
            raise ValueError("AUTO-PICK attempted for non-on-the-clock member")


        # Compute round/pickInRound for DraftPick row (keeps your existing fields consistent)
        round_number, pos_in_round = self._compute_round_and_pos(current_overall, int(num_players))
        pick_in_round = self._draft_order_for_pick(draft_type, round_number, pos_in_round, int(num_players))

        # Insert DraftPick
        try:
            draft_row = self.pick_repository.insert_auto_pick(conn, {
                    "leagueId": league_id,
                    "overallPickNumber": current_overall,
                    "roundNumber": round_number,
                    "pickInRound": pick_in_round,
                    "memberId": member_id,
                    "sportTeamId": sport_team_id,
                }).fetchone()
        except IntegrityError as e:
            raise ValueError("Pick conflict (team already drafted or slot already filled).") from e

        draft_pick = dict(draft_row._mapping)

        # Insert LeagueTeamSlot
        slot_row = self.pick_repository.insert_auto_slot(conn, {
                "leagueId": league_id,
                "memberId": member_id,
                "sportTeamId": sport_team_id,
                "acquiredWeek": acquired_week,
                "acquiredVia": "Draft",
            }).fetchone()
        draft_pick["leagueTeamSlotId"] = int(slot_row._mapping["id"])

        # Advance DraftState using DraftTurn order (next unpicked)
        next_overall = current_overall + 1
        if next_overall > total_picks:
            self.pick_repository.auto_advance_past_end(conn, {"leagueId": league_id, "nextOverall": next_overall})
            self.finalize_draft(league_id, conn=conn)
            draft_pick["draftComplete"] = True
            self.pick_repository.notify(conn, league_id, "auto_pick")
            return draft_pick

        nxt = self._get_next_unpicked_turn_from(conn, league_id, next_overall)
        if not nxt:
            # Safety: treat as complete
            self.finalize_draft(league_id, conn=conn)
            draft_pick["draftComplete"] = True
            self.pick_repository.notify(conn, league_id, "auto_pick")
            return draft_pick

        next_overall, next_member_id = nxt

        self.pick_repository.auto_advance_next(conn, {
                "leagueId": league_id,
                "nextOverall": next_overall,
                "nextMemberId": next_member_id,
                "selectionTime": selection_time,
            })
        draft_pick["draftComplete"] = False
        draft_pick["nextMemberId"] = next_member_id
        draft_pick["nextOverallPickNumber"] = next_overall
        self.pick_repository.notify(conn, league_id, "auto_pick")
        return draft_pick

    def pick_live(self, actor, league_id, member_id, sport_team_id, acquired_week=1):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return self.create_draft_pick_live(league_id, member_id, sport_team_id, acquired_week, acting_user_id=actor.user_id)

    def pick_live_for_job(self, league_id, member_id, sport_team_id, acquired_week=1):
        return self.create_draft_pick_live(league_id, member_id, sport_team_id, acquired_week)

    def allocate_manual_for_job(self, league_id, member_id, sport_team_id, acquired_week=1):
        return self.create_draft_pick(league_id, member_id, sport_team_id, acquired_week)

    def process_timeout_for_job(self, league_id):
        return self.process_expired_pick_if_needed(league_id)
