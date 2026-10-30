"""Trade/free-agent workflows, actor policy and original transaction scopes.

The initial TransactionService read/apply pilot remains an independent capability.
Legacy public/helpers remain inherited by the SQL-free TransactionModel facade.
"""
import json
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from sqlalchemy.engine import Engine
from .service import TransactionService
from .workflow_repository import TransactionWorkflowRepository
from actors import UserActor
from .contracts import TradeRejected, TransactionNotFound, TransactionAccessDenied


class TransactionWorkflowService:
    TYPE_TRADE = "TRADE"
    TYPE_FREE_AGENT = "FREE_AGENT"

    STATUS_PROPOSED = "PROPOSED"
    STATUS_REJECTED = "REJECTED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CANCELLED = "CANCELLED"
    STATUS_PENDING = "PENDING_APPLY"
    STATUS_VETOED = "VETOED"

    class SwapLimitExceeded(Exception):
        pass

    def __init__(self, db, repository=None, pilot_service=None):
        self.db = db
        self._transaction_service = pilot_service if pilot_service is not None else TransactionService(db)
        self._workflow_repository = repository if repository is not None else TransactionWorkflowRepository()

    @property
    def workflow_repository(self):
        repository = getattr(self, '_workflow_repository', None)
        if repository is None:
            repository = TransactionWorkflowRepository()
            self._workflow_repository = repository
        return repository

    # ---------- League / settings helpers ----------

    def _get_league_settings(self, league_id: int) -> Dict[str, Any]:


        with self.db.connect() as conn:
            row = self.workflow_repository.league_settings(conn, {"league_id": league_id}).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        settings = row._mapping["settings"]
        if isinstance(settings, str):
            settings = json.loads(settings)

        if not isinstance(settings, dict):
            raise ValueError("League.settings must be a JSON object")

        return settings

    def _get_max_swaps_for_league(self, league_id: int) -> Optional[int]:
        settings = self._get_league_settings(league_id)
        roster_settings = settings.get("roster") or {}
        max_swaps = roster_settings.get("maxSwaps")

        if max_swaps is None:
            return None

        try:
            return int(max_swaps)
        except (TypeError, ValueError):
            return None

    def _get_member_swap_count(self, league_id: int, member_id: int) -> int:
        """
        Counts how many FREE_AGENT transactions this member has in this league.
        Adjust WHERE if you later track statuses (e.g. only COMPLETED).
        """


        with self.db.connect() as conn:
            row = self.workflow_repository.member_swap_count(conn, {
                    "league_id": league_id,
                    "member_id": member_id,
                    "type": self.TYPE_FREE_AGENT,
                }).fetchone()

        return int(row._mapping["count"])

    def _ensure_member_can_swap(self, league_id: int, member_id: int):
        max_swaps = self._get_max_swaps_for_league(league_id)

        # None or <= 0 => unlimited
        if max_swaps is None or max_swaps <= 0:
            return

        used = self._get_member_swap_count(league_id, member_id)

        if used >= max_swaps:
            raise self.SwapLimitExceeded(
                f"Member {member_id} has used {used}/{max_swaps} free agency swaps"
            )

    def _validate_members_in_league(
        self, league_id: int, member_ids: List[int]
    ):
        if not member_ids:
            return


        params = {
            "league_id": league_id,
            "member_ids": member_ids,
        }

        with self.db.connect() as conn:
            row = self.workflow_repository.member_count(conn, params).fetchone()

        count = int(row._mapping["count"])
        if count != len(set(member_ids)):
            raise ValueError("One or more members do not belong to this league")

    def _assert_trade_deadline(self, conn, league_id: int) -> None:
        try:
            self._transaction_service.assert_trade_deadline_in_transaction(conn, league_id)
        except (TradeRejected, TransactionNotFound) as exc:
            raise ValueError(str(exc)) from exc

    def _assert_free_agent_deadline(self, conn, league_id: int) -> None:
        row = self.workflow_repository.free_agent_deadline(conn, {"league_id": league_id}).fetchone()

        if not row:
            raise ValueError(f"League {league_id} not found")

        if bool(row._mapping["pastDeadline"]):
            raise ValueError("Free agent deadline has passed")


    def _get_week_for_league(self, league_id: int, week_id: int) -> Dict[str, Any]:
        """
        Fetches the Week row for a league and validates ownership.
        Returns: { id, weekNumber, isLocked }
        """


        with self.db.connect() as conn:
            row = self.workflow_repository.week_for_league(conn, {"week_id": week_id, "league_id": league_id}).fetchone()

        if not row:
            raise ValueError(f"Week {week_id} does not belong to league {league_id}")

        return dict(row._mapping)

    def _get_pending_free_agent_team_ids_for_week(
        self,
        conn,
        league_id: int,
        week_id: int,
    ) -> Dict[str, set[int]]:
        params = {
            "league_id": league_id,
            "week_id": week_id,
            "status": self.STATUS_PENDING,
            "type": self.TYPE_FREE_AGENT,
        }

        add_rows = self.workflow_repository.pending_add_ids(conn, params).scalars().all()

        drop_rows = self.workflow_repository.pending_drop_ids(conn, params).scalars().all()

        return {
            "adds": {int(x) for x in add_rows},
            "drops": {int(x) for x in drop_rows},
        }

    def _parse_team_ids(self, raw) -> List[int]:
        if not raw:
            return []
        if isinstance(raw, list):
            return [int(x) for x in raw]
        if isinstance(raw, str):
            return [int(x) for x in json.loads(raw)]
        return [int(x) for x in list(raw)]

    def apply_free_agent_transaction(self, transaction_id: int) -> None:
        with self.db.begin() as conn:
            tx = self.workflow_repository.free_agent_for_update(conn, {"id": transaction_id}).fetchone()

            if not tx:
                raise ValueError("Transaction not found")

            txm = tx._mapping
            if txm["type"] != self.TYPE_FREE_AGENT:
                raise ValueError("Transaction is not a free agent add/drop")
            if txm["status"] != self.STATUS_PENDING:
                raise ValueError("Transaction is not pending apply")

            week = self._get_week_for_league(txm["leagueId"], txm["weekId"])
            week_number = int(week["weekNumber"])

            drop_team_ids = self._parse_team_ids(txm["fromTeamIds"])
            add_team_ids = self._parse_team_ids(txm["toTeamIds"])

            if drop_team_ids:
                self.workflow_repository.drop_free_agent_slots(conn, {
                        "league_id": txm["leagueId"],
                        "member_id": txm["memberFromId"],
                        "team_ids": drop_team_ids,
                        "week_number": week_number,
                    })

            if add_team_ids:

                rows = [
                    {
                        "league_id": txm["leagueId"],
                        "member_id": txm["memberFromId"],
                        "team_id": int(tid),
                        "week_number": week_number,
                        "acquired_via": self.TYPE_FREE_AGENT,
                    }
                    for tid in add_team_ids
                ]
                self.workflow_repository.add_free_agent_slots(conn, rows)

            self.workflow_repository.complete_free_agent(conn, {"status": self.STATUS_COMPLETED, "id": transaction_id})

    def apply_pending_transaction(self, transaction_id: int) -> None:
        with self.db.connect() as conn:
            tx = self.workflow_repository.pending_transaction(conn, {"id": transaction_id}).fetchone()

        if not tx:
            raise ValueError("Transaction not found")

        txm = tx._mapping
        if txm["status"] != self.STATUS_PENDING:
            raise ValueError("Transaction is not pending apply")

        if txm["type"] == self.TYPE_TRADE:
            self.apply_trade(transaction_id)
        elif txm["type"] == self.TYPE_FREE_AGENT:
            self.apply_free_agent_transaction(transaction_id)
        else:
            raise ValueError(f"Unsupported transaction type: {txm['type']}")

    def _get_next_unlocked_week_for_league(
        self,
        league_id: int,
        after_week_number: int,
    ) -> Dict[str, Any]:
        """
        Returns the next unlocked week after the given week number.
        """


        with self.db.connect() as conn:
            row = self.workflow_repository.next_unlocked_week(conn, {"league_id": league_id, "week_number": after_week_number}).fetchone()

        if not row:
            raise ValueError(
                f"No unlocked future week found after week {after_week_number}"
            )

        return dict(row._mapping)


    # ------------------------------------------------------------------
    # TRADE VALIDATION (ownership + conference limits)
    # ------------------------------------------------------------------

    def _validate_trade(
        self,
        conn,
        league_id: int,
        week_number: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
    ) -> None:
        try:
            self._transaction_service.validate_trade_in_transaction(
                conn, league_id, week_number, from_member_id, to_member_id,
                from_team_ids, to_team_ids,
            )
        except TradeRejected as exc:
            raise ValueError(str(exc)) from exc

    # ------------------------------------------------------------------
    # APPLY TRADE
    # ------------------------------------------------------------------

    def _apply_trade(
        self,
        conn,
        league_id: int,
        week_number: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
    ) -> None:
        self._transaction_service.repository.transfer_ownership(
            conn, league_id, week_number, from_member_id, to_member_id,
            from_team_ids, to_team_ids,
        )

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def propose_trade(
        self,
        league_id: int,
        week_id: int,
        from_member_id: int,
        to_member_id: int,
        from_team_ids: List[int],
        to_team_ids: List[int],
        *, acting_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        # Only verified HTTP actors opt into ownership checks; trusted direct
        # callers keep the context-free model contract.
        if acting_user_id is not None:
            with self.db.connect() as conn:
                self.workflow_repository.assert_owned_member(conn, league_id, from_member_id, acting_user_id)
        week = self._get_week_for_league(league_id, week_id)
        if week["isLocked"]:
            raise ValueError("Week is locked")

        self._validate_members_in_league(league_id, [from_member_id, to_member_id])

        with self.db.begin() as conn:
            if acting_user_id is not None:
                self.workflow_repository.assert_owned_member(conn, league_id, from_member_id, acting_user_id)
            self._assert_trade_deadline(conn, league_id)
            self._validate_trade(
                conn,
                league_id,
                week["weekNumber"],
                from_member_id,
                to_member_id,
                from_team_ids,
                to_team_ids,
            )

            row = self.workflow_repository.insert_trade(conn, {
                    "league": league_id,
                    "week": week_id,
                    "type": self.TYPE_TRADE,
                    "from_id": from_member_id,
                    "to_id": to_member_id,
                    "status": self.STATUS_PROPOSED,
                    "from_teams": json.dumps(from_team_ids),
                    "to_teams": json.dumps(to_team_ids),
                }).fetchone()
            if acting_user_id is not None:
                self.workflow_repository.assert_owned_member(conn, league_id, from_member_id, acting_user_id)

        return {"transactionId": row._mapping["id"], "status": self.STATUS_PROPOSED}

    @contextmanager
    def _trade_actor_transaction(
        self, transaction_id: int, member_id: int, role: str,
        league_id: Optional[int], acting_user_id: Optional[int],
    ):
        """Share trade actor/scope checks while keeping each action's state rules local.

        HTTP must supply both verified actor and URL league. Trusted model calls
        omit both. Role predicates come only from this fixed server-side mapping.
        Existing transaction row locking is retained; no new concurrency guarantee.
        """
        if (league_id is None) != (acting_user_id is None):
            raise ValueError('league_id and acting_user_id must be supplied together')
        if role not in ('receiving', 'proposing', 'voter'):
            raise KeyError(role)
        interactive = acting_user_id is not None

        params = {'id': transaction_id}
        if interactive:
            params.update(league_id=league_id, member_id=member_id)
        with self.db.begin() as conn:
            if interactive:
                self.workflow_repository.assert_owned_member(conn, league_id, member_id, acting_user_id)
            tx = self.workflow_repository.trade_for_action(conn, params, role).fetchone()
            if tx is None:
                if interactive:
                    raise PermissionError('Trade not found')
                raise ValueError('Transaction not found')
            yield conn, tx
            if interactive:
                self.workflow_repository.assert_owned_member(conn, league_id, member_id, acting_user_id)
                current = self.workflow_repository.trade_current_scope(conn, params, role).fetchone()
                if current is None:
                    raise PermissionError('Trade not found')

    def respond_to_trade(
        self,
        transaction_id: int,
        action: str,
        responder_member_id: int,
        reject_reason: str | None = None,
        *, league_id: Optional[int] = None, acting_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        action = action.upper()
        if action not in ("ACCEPT", "REJECT"):
            raise ValueError("Invalid action")

        with self._trade_actor_transaction(
            transaction_id, responder_member_id, 'receiving', league_id, acting_user_id,
        ) as (conn, tx):
            txm = tx._mapping

            if txm["status"] != self.STATUS_PROPOSED:
                raise ValueError("Trade already resolved")

            if responder_member_id != txm["memberToId"]:
                raise ValueError("Only receiving member may respond")

            if action == "REJECT":
                self.workflow_repository.reject_trade(conn, {
                        "status": self.STATUS_REJECTED,
                        "by": responder_member_id,
                        "reason": reject_reason,
                        "id": transaction_id,
                    })
                return {"transactionId": transaction_id, "status": self.STATUS_REJECTED}

            self._assert_trade_deadline(conn, txm["leagueId"])
            week = self._get_week_for_league(txm["leagueId"], txm["weekId"])
            if week["isLocked"]:
                raise ValueError("Week is locked")

            self._validate_trade(
                conn,
                txm["leagueId"],
                week["weekNumber"],
                txm["memberFromId"],
                txm["memberToId"],
                list(txm["fromTeamIds"]),
                list(txm["toTeamIds"]),
            )

            self.workflow_repository.accept_trade(conn, {
                    "status": self.STATUS_PENDING,
                    "by": responder_member_id,
                    "id": transaction_id,
                })

        return {"transactionId": transaction_id, "status": self.STATUS_PENDING}

    def apply_trade(
        self,
        transaction_id: int,
    ):
        # Compatibility boundary for the dispatcher, jobs and existing callers.
        try:
            return self._transaction_service.apply_trade_for_job(transaction_id)
        except (TradeRejected, TransactionNotFound) as exc:
            raise ValueError(str(exc)) from exc


    def cancel_trade_proposal(
        self, transaction_id: int, requester_member_id: int,
        *, league_id: Optional[int] = None, acting_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        with self._trade_actor_transaction(
            transaction_id, requester_member_id, 'proposing', league_id, acting_user_id,
        ) as (conn, tx):
            txm = tx._mapping

            if txm["type"] != self.TYPE_TRADE:
                raise ValueError("Not a trade transaction")

            if txm["status"] != self.STATUS_PROPOSED:
                raise ValueError("Only PROPOSED trades can be cancelled")

            if requester_member_id != txm["memberFromId"]:
                raise ValueError("Only the proposing member can cancel this trade")

            self.workflow_repository.cancel_trade(conn, {"status": self.STATUS_CANCELLED, "by": requester_member_id, "id": transaction_id})

        return {"transactionId": transaction_id, "status": self.STATUS_CANCELLED}


    # ---------- Free agency helpers ----------

    def _is_team_owned_in_week(
        self,
        conn,
        league_id: int,
        team_id: int,
        week_number: int,
    ) -> bool:
        """
        True if *anyone* owns this team in this league during this week.
        """

        row = self.workflow_repository.team_owned(conn, {
            "league_id": league_id,
            "team_id": team_id,
            "week_number": week_number,
        }).fetchone()
        return row is not None


    def _is_team_owned_by_member_in_week(
        self,
        conn,
        league_id: int,
        member_id: int,
        team_id: int,
        week_number: int,
    ) -> bool:
        """
        True if this member owns this team in this league during this week.
        """

        row = self.workflow_repository.member_team_owned(conn, {
            "league_id": league_id,
            "member_id": member_id,
            "team_id": team_id,
            "week_number": week_number,
        }).fetchone()
        return row is not None


    def _get_team_conference_info(self, conn, team_ids: List[int]) -> Dict[int, Dict[str, int]]:
        """
        For each team_id, returns its sportConferenceId and that conference's maxTeamsPerOwner.

        Assumes:
        ConferenceMembership.sportTeamId -> SportTeam.id
        ConferenceMembership.sportConferenceId -> SportConference.id
        SportConference has maxTeamsPerOwner
        """
        if not team_ids:
            return {}

        rows = self.workflow_repository.team_conference_info(conn, {"team_ids": team_ids}).mappings().all()

        info: Dict[int, Dict[str, int]] = {}
        for r in rows:
            tid = int(r["sportTeamId"])
            # If you ever add seasonYear to ConferenceMembership filtering,
            # this is where you'd apply it.
            info[tid] = {
                "sportConferenceId": int(r["sportConferenceId"]),
                "maxTeamsPerOwner": int(r["maxTeamsPerOwner"]),
            }

        # Safety: if any requested team is missing conference membership data
        missing = [t for t in team_ids if t not in info]
        if missing:
            raise ValueError(f"Missing ConferenceMembership rows for team(s): {missing}")

        return info

    def _get_member_conference_counts(
        self,
        conn,
        league_id: int,
        member_id: int,
        week_number: int,
    ) -> Dict[int, int]:
        """
        Returns: { sportConferenceId: countOwnedInThatConferenceForWeek }
        """
        rows = self.workflow_repository.member_conference_counts(conn, {"league_id": league_id, "member_id": member_id, "week_number": week_number}).mappings().all()

        return {int(r["sportConferenceId"]): int(r["cnt"]) for r in rows}

    def _get_member_roster_team_ids_for_week(self, conn, league_id: int, member_id: int, week_number: int) -> List[int]:
        rows = self.workflow_repository.member_roster_ids(conn, {"league_id": league_id, "member_id": member_id, "week_number": week_number}).scalars().all()

        return [int(x) for x in rows]


    # ---------- Free agency add / drop ----------

    def free_agency_add_drop(
        self,
        league_id: int,
        week_id: int,
        week_number: int,
        member_id: int,
        add_team_id: Optional[int],
        drop_team_id: Optional[int],
        *, acting_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Performs a free-agency add/drop for a single league member…
        """
        # HTTP supplies the verified actor; None is only for trusted model calls.
        if acting_user_id is not None:
            with self.db.connect() as conn:
                self.workflow_repository.assert_owned_member(conn, league_id, member_id, acting_user_id)
        week_info = self._get_week_for_league(league_id, week_id)
        week_number = week_info["weekNumber"]
        if week_info["isLocked"]:
            next_week = self._get_next_unlocked_week_for_league(
                league_id,
                after_week_number=int(week_number),
            )
            week_id = int(next_week["id"])
            week_number = int(next_week["weekNumber"])

        # Enforce swap limit first
        self._ensure_member_can_swap(league_id, member_id)

        # Ensure member belongs to league
        self._validate_members_in_league(league_id, [member_id])

        with self.db.begin() as conn:
            if acting_user_id is not None:
                self.workflow_repository.assert_owned_member(conn, league_id, member_id, acting_user_id)
            self._assert_free_agent_deadline(conn, league_id)
            pending = self._get_pending_free_agent_team_ids_for_week(
                conn,
                league_id=league_id,
                week_id=week_id,
            )
            pending_adds = pending["adds"]
            pending_drops = pending["drops"]

            if add_team_id is not None and add_team_id in pending_adds:
                raise ValueError(
                    f"Team {add_team_id} already has a pending add for week {week_number}"
                )
            if drop_team_id is not None and drop_team_id in pending_drops:
                raise ValueError(
                    f"Team {drop_team_id} already has a pending drop for week {week_number}"
                )

            # Conference info for any teams involved
            involved_team_ids: List[int] = []
            if add_team_id is not None:
                involved_team_ids.append(add_team_id)
            if drop_team_id is not None:
                involved_team_ids.append(drop_team_id)

            team_conf_info = (
                self._get_team_conference_info(conn, involved_team_ids)
                if involved_team_ids
                else {}
            )

            # Current conference counts
            counts = self._get_member_conference_counts(
                conn, league_id, member_id, week_number
            )

            # Build conference limits map
            conf_limits: Dict[int, int] = {}
            for info in team_conf_info.values():
                cid = info["sportConferenceId"]
                limit = info["maxTeamsPerOwner"]
                if cid in conf_limits and conf_limits[cid] != limit:
                    raise ValueError(
                        f"Inconsistent maxTeamsPerOwner for conference {cid}"
                    )
                conf_limits[cid] = limit

            # 1) Validate / simulate drop
            counts_after = dict(counts)

            if drop_team_id is not None:
                # Ensure team is on member's roster this week
                owned = self._is_team_owned_by_member_in_week(
                    conn, league_id, member_id, drop_team_id, week_number
                )
                if not owned:
                    raise ValueError(
                        f"Member {member_id} does not own team {drop_team_id} in week {week_number}"
                    )

                info = team_conf_info.get(drop_team_id)
                if info:
                    cid = info["sportConferenceId"]
                    counts_after[cid] = counts_after.get(cid, 0) - 1
                    if counts_after[cid] < 0:
                        raise ValueError(
                            f"Member {member_id} would have negative count in conference {cid}"
                        )

            # 2) Validate / simulate add
            if add_team_id is not None:
                # Ensure team is a free agent
                if self._is_team_owned_in_week(
                    conn, league_id, add_team_id, week_number
                ):
                    if add_team_id not in pending_drops:
                        raise ValueError(
                            f"Team {add_team_id} is not a free agent in week {week_number}"
                        )

                info = team_conf_info[add_team_id]
                cid = info["sportConferenceId"]
                max_per = conf_limits.get(cid)
                new_count = counts_after.get(cid, 0) + 1
                if max_per is not None and new_count > max_per:
                    raise ValueError(
                        f"Member {member_id} would exceed maxTeamsPerOwner "
                        f"({new_count}/{max_per}) in conference {cid}"
                    )
                counts_after[cid] = new_count

            # 3) Log Transaction (pending apply)
            from_team_ids = [drop_team_id] if drop_team_id is not None else []
            to_team_ids = [add_team_id] if add_team_id is not None else []


            tx_row = self.workflow_repository.insert_free_agent(conn, {
                    "league_id": league_id,
                    "week_id": week_id,
                    "type": self.TYPE_FREE_AGENT,
                    "member_from_id": member_id,
                    "member_to_id": member_id,
                    "status": self.STATUS_PENDING,
                    "from_teams": json.dumps(from_team_ids),
                    "to_teams": json.dumps(to_team_ids),
                }).fetchone()

            transaction_id = int(tx_row._mapping["id"])

            # 4) Current roster (does not include pending move)
            member_roster = self._get_member_roster_team_ids_for_week(
                conn, league_id, member_id, week_number
            )
            if drop_team_id is not None and drop_team_id in member_roster:
                member_roster = [t for t in member_roster if t != drop_team_id]
            if add_team_id is not None and add_team_id not in member_roster:
                member_roster.append(add_team_id)
            member_roster = sorted({int(t) for t in member_roster})
            if acting_user_id is not None:
                self.workflow_repository.assert_owned_member(conn, league_id, member_id, acting_user_id)

        return {
            "leagueId": league_id,
            "weekId": week_id,
            "weekNumber": week_number,
            "transactionId": transaction_id,
            "type": self.TYPE_FREE_AGENT,
            "status": self.STATUS_PENDING,
            "memberId": member_id,
            "added": add_team_id,
            "dropped": drop_team_id,
            "memberRosterTeamIds": member_roster,
        }

    def get_transactions_for_league(
        self,
        league_id: int,
        status: Optional[str] = None,
        *, reader_user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        try:
            if reader_user_id is None:
                return self._transaction_service.list_transactions_for_job(league_id, status)
            return self._transaction_service.list_transactions_for_legacy_reader(
                reader_user_id, league_id, status,
            )
        except TransactionAccessDenied as exc:
            raise PermissionError(str(exc)) from exc

    def get_week_roster_violations(
        self,
        league_id: int,
        week_id: int,
    ):
        """
        Returns a list of roster violations for the given week.
        A "violation" is: member has more than maxTeamsPerOwner in a conference.

        Result shape:
        [
          {
            "memberId": 123,
            "sportConferenceId": 5,
            "count": 4,
            "maxTeamsPerOwner": 3
          },
          ...
        ]
        """
        week_info = self._get_week_for_league(league_id, week_id)
        week_number = week_info["weekNumber"]


        with self.db.connect() as conn:
            rows = self.workflow_repository.roster_violations(conn, {
                    "league_id": league_id,
                    "week_number": week_number,
                }).mappings().all()

        violations = []
        for r in rows:
            violations.append(
                {
                    "memberId": int(r["memberId"]),
                    "sportConferenceId": int(r["sportConferenceId"]),
                    "count": int(r["count"]),
                    "maxTeamsPerOwner": int(r["maxTeamsPerOwner"]),
                }
            )

        return violations

    def assert_week_rosters_valid(
        self,
        league_id: int,
        week_id: int,
    ):
        """
        Raises ValueError if any member exceeds maxTeamsPerOwner in any conference
        for this week.
        """
        violations = self.get_week_roster_violations(league_id, week_id)
        if not violations:
            return

        # Build a simple summary string
        parts = []
        for v in violations:
            parts.append(
                f'member {v["memberId"]} has {v["count"]}/'
                f'{v["maxTeamsPerOwner"]} teams in conference {v["sportConferenceId"]}'
            )

        details = "; ".join(parts)
        raise ValueError(f"Roster violations for week {week_id}: {details}")

    def get_open_trade_transactions_for_member(
        self,
        league_id: int,
        member_id: int,
        *, reader_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Returns all non-finalized TRADE transactions involving this member,
        split into incoming/outgoing, plus an 'all' list.
        Excludes FREE_AGENT transactions entirely.
        """
        # Personalized vote/party context requires the reader's own member ID.
        # Trusted callers omit reader_user_id and keep their original contract.
        params = {"league_id": league_id, "member_id": member_id}

        if reader_user_id is not None:
            with self.db.connect() as conn:
                self.workflow_repository.assert_owned_member(conn, league_id, member_id, reader_user_id)
            params['reader_user_id'] = reader_user_id


        with self.db.connect() as conn:
            rows = self.workflow_repository.open_trades(conn, params).mappings().all()

        mine_all: List[Dict[str, Any]] = []
        mine_incoming: List[Dict[str, Any]] = []
        mine_outgoing: List[Dict[str, Any]] = []
        others: List[Dict[str, Any]] = []

        for r in rows:
            item = {
                "transactionId": int(r["id"]),
                "leagueId": int(r["leagueId"]),
                "weekId": int(r["weekId"]),
                "type": r["type"],
                "status": r["status"],
                "memberFromId": int(r["memberFromId"]),
                "memberToId": int(r["memberToId"]) if r["memberToId"] is not None else None,
                "memberFromTeamName": r["memberFromTeamName"],
                "memberFromDisplayName": r["memberFromDisplayName"],
                "memberToTeamName": r["memberToTeamName"],
                "memberToDisplayName": r["memberToDisplayName"],
                "fromTeams": list(r["fromTeams"] or []),
                "toTeams": list(r["toTeams"] or []),
                "memberHasVetoed": bool(r["memberHasVetoed"]),
                "isParticipant": bool(r["isParticipant"]),
                "vetoCount": int(r["vetoCount"] or 0),
                "createdAt": r["createdAt"].isoformat() if r["createdAt"] else None,
            }

            if item["isParticipant"]:
                if item["memberToId"] == member_id:
                    mine_incoming.append(item)
                if item["memberFromId"] == member_id:
                    mine_outgoing.append(item)
            else:
                others.append(item)

        return {
            "memberId": member_id,
            "mine": {
                "incoming": mine_incoming,
                "outgoing": mine_outgoing,
            },
            "others": others,
        }

    def _get_trade_veto_settings(self, league_id: int) -> Dict[str, Any]:
        settings = self._get_league_settings(league_id)
        tx = (settings.get("transactions") or {})
        veto = (tx.get("tradeVeto") or {})
        enabled = bool(veto.get("enabled", False))
        required = veto.get("requiredVetoCount")
        try:
            required_int = int(required) if required is not None else 0
        except (TypeError, ValueError):
            required_int = 0
        return {"enabled": enabled, "requiredVetoCount": required_int}


    def veto_trade(
        self, transaction_id: int, league_member_id: int,
        *, league_id: Optional[int] = None, acting_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Toggles a member's veto vote for a trade.
        If veto_count reaches requiredVetoCount, marks Transaction as VETOED.
        league_member_id is LeagueMember.id (not User.id).
        """
        with self._trade_actor_transaction(
            transaction_id, league_member_id, 'voter', league_id, acting_user_id,
        ) as (conn, tx):
            txm = tx._mapping

            if txm["type"] != self.TYPE_TRADE:
                raise ValueError("Only TRADE transactions can be vetoed")

            if txm["status"] in (
                self.STATUS_COMPLETED,
                self.STATUS_REJECTED,
                self.STATUS_CANCELLED,
                getattr(self, "STATUS_VETOED", "VETOED"),
            ):
                raise ValueError(f"Trade is not vetoable in status {txm['status']}")

            league_id = int(txm["leagueId"])

            # Ensure voter belongs to the league
            self._validate_members_in_league(league_id, [int(league_member_id)])

            # Prevent proposer/receiver from vetoing (optional rule)
            if int(league_member_id) in (int(txm["memberFromId"]), int(txm["memberToId"])):
                raise ValueError("Trade participants cannot veto their own trade")

            veto_settings = self._get_trade_veto_settings(league_id)
            if not veto_settings["enabled"]:
                raise ValueError("Trade veto is not enabled for this league")

            required = int(veto_settings["requiredVetoCount"] or 0)
            if required <= 0:
                raise ValueError("League veto requiredVetoCount is not configured")

            # 1) Toggle if row exists
            toggled = self.workflow_repository.toggle_veto(conn, {"tx_id": transaction_id, "lm_id": league_member_id}).fetchone()

            if toggled:
                current_veto = bool(toggled._mapping["veto"])
            else:
                # 2) Otherwise insert a new veto = true
                inserted = self.workflow_repository.insert_veto(conn, {"tx_id": transaction_id, "lm_id": league_member_id}).fetchone()
                current_veto = bool(inserted._mapping["veto"])

            # Count active vetoes
            vote_row = self.workflow_repository.veto_count(conn, {"tx_id": transaction_id}).fetchone()

            veto_count = int(vote_row._mapping["cnt"])

            # If threshold reached, mark transaction as VETOED
            new_status = txm["status"]
            if veto_count >= required:
                self.workflow_repository.mark_vetoed(conn, {"status": getattr(self, "STATUS_VETOED", "VETOED"), "id": transaction_id})
                new_status = getattr(self, "STATUS_VETOED", "VETOED")

        return {
            "transactionId": int(transaction_id),
            "status": str(new_status),
            "memberVetoed": bool(current_veto),
            "vetoCount": int(veto_count),
            "requiredVetoCount": int(required),
        }

    @staticmethod
    def _actor_id(actor):
        if not isinstance(actor, UserActor):
            raise TypeError('A verified UserActor is required')
        return actor.user_id

    def propose(self, actor, league_id, week_id, from_member_id, to_member_id, from_team_ids, to_team_ids):
        return self.propose_trade(league_id, week_id, from_member_id, to_member_id, from_team_ids, to_team_ids, acting_user_id=self._actor_id(actor))

    def respond(self, actor, league_id, transaction_id, action, responder_member_id, reject_reason=None):
        return self.respond_to_trade(transaction_id, action, responder_member_id, reject_reason, league_id=league_id, acting_user_id=self._actor_id(actor))

    def cancel(self, actor, league_id, transaction_id, requester_member_id):
        return self.cancel_trade_proposal(transaction_id, requester_member_id, league_id=league_id, acting_user_id=self._actor_id(actor))

    def veto(self, actor, league_id, transaction_id, league_member_id):
        return self.veto_trade(transaction_id, league_member_id, league_id=league_id, acting_user_id=self._actor_id(actor))

    def free_agency(self, actor, league_id, week_id, week_number, member_id, add_team_id, drop_team_id):
        return self.free_agency_add_drop(league_id, week_id, week_number, member_id, add_team_id, drop_team_id, acting_user_id=self._actor_id(actor))

    def open_trades(self, actor, league_id, member_id):
        return self.get_open_trade_transactions_for_member(league_id, member_id, reader_user_id=self._actor_id(actor))

    def propose_for_job(self, league_id, week_id, from_member_id, to_member_id, from_team_ids, to_team_ids):
        return self.propose_trade(league_id, week_id, from_member_id, to_member_id, from_team_ids, to_team_ids)

    def respond_for_job(self, transaction_id, action, responder_member_id, reject_reason=None):
        return self.respond_to_trade(transaction_id, action, responder_member_id, reject_reason)

    def cancel_for_job(self, transaction_id, requester_member_id):
        return self.cancel_trade_proposal(transaction_id, requester_member_id)

    def veto_for_job(self, transaction_id, league_member_id):
        return self.veto_trade(transaction_id, league_member_id)

    def free_agency_for_job(self, league_id, week_id, week_number, member_id, add_team_id, drop_team_id):
        return self.free_agency_add_drop(league_id, week_id, week_number, member_id, add_team_id, drop_team_id)

    def open_trades_for_job(self, league_id, member_id):
        return self.get_open_trade_transactions_for_member(league_id, member_id)

    def apply_pending_for_job(self, transaction_id):
        return self.apply_pending_transaction(transaction_id)

    def apply_free_agent_for_job(self, transaction_id):
        return self.apply_free_agent_transaction(transaction_id)

    def lock_week_for_job(self, league_id, week_id):
        self.assert_week_rosters_valid(league_id, week_id)
        with self.db.begin() as conn:
            self.workflow_repository.lock_week(conn, {'week_id': week_id, 'league_id': league_id})
        return {'message': 'Week locked successfully', 'leagueId': league_id, 'weekId': week_id}
