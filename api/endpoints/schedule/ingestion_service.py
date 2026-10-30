"""Trusted provider ingestion/bootstrap with original checkpoint/transaction policy."""
import datetime as dt
import json
from typing import Any, Dict, List, Optional
from rules.tournamentRules import select_phase
from .read_service import ScheduleReadService
from .ingestion_repository import ScheduleIngestionRepository
from .helpers.espn.espnClient import ESPNClient
from .helpers.bootstrapCheckpoint import BootstrapCheckpoint, default_checkpoint_path, fingerprint


class ScheduleIngestionService(ScheduleReadService):
    def __init__(self, db, espn_base_url, repository=None, client_factory=None):
        super().__init__(db)
        self.espn_base_url = espn_base_url.rstrip("/")
        self._ingestion_repository = repository if repository is not None else ScheduleIngestionRepository()
        self._client_factory = client_factory

    @property
    def ingestion_repository(self):
        repository = getattr(self, '_ingestion_repository', None)
        if repository is None:
            repository = ScheduleIngestionRepository()
            self._ingestion_repository = repository
        return repository

    def _new_client(self, base_url, api_keyword):
        factory = getattr(self, '_client_factory', None)
        return (factory if factory is not None else ESPNClient)(base_url, api_keyword)

    def _get_sport_api_config(self, sport_id: int) -> tuple[str, List[int]]:
        """
        Returns (api_keyword, api_group_ids)

        Assumes your Sport table has *two* columns, e.g.:
        - "apiKeyword"  (text)
        - "apiGroupIds"
        """

        with self.db.begin() as conn:
            row = self.ingestion_repository.api_config(conn, {"sportId": sport_id}).fetchone()

        if not row or row[0] is None:
            raise ValueError(f"Sport {sport_id} missing apiKeyword")

        api_keyword = row[0]
        raw_groups = row[1]
        base_url = row[2]

        # Normalize apiGroupIds into List[int]
        group_ids: List[int] = []
        if raw_groups is None:
            group_ids = []
        elif isinstance(raw_groups, list):
            group_ids = [int(x) for x in raw_groups]
        elif isinstance(raw_groups, str):
            s = raw_groups.strip()
            # could be JSON like "[50,55]" or comma string like "50,55"
            if s.startswith("["):
                group_ids = [int(x) for x in json.loads(s)]
            else:
                group_ids = [int(x.strip()) for x in s.split(",") if x.strip()]
        else:
            # e.g. psycopg may return tuples for int[]
            group_ids = [int(x) for x in raw_groups]

        return api_keyword, group_ids, base_url

    def _lookup_sport_team_id(self, sport_id: int, espn_team_id: str) -> Optional[int]:

        with self.db.begin() as conn:
            row = self.ingestion_repository.team_id(conn, {"sportId": sport_id, "externalId": espn_team_id}).fetchone()
        return int(row[0]) if row else None

    def _insert_or_update_game(
        self,
        sport_id: int,
        sport_season_id: int,
        game: Dict[str, Any],
    ) -> int:
        external_game_id = str(game["externalGameId"])
        event_dt: dt.datetime = game["date"]

        home_team_id = self._lookup_sport_team_id(sport_id, game["homeEspnId"])
        away_team_id = self._lookup_sport_team_id(sport_id, game["awayEspnId"])

        season_phase_id = self._lookup_season_phase_id_for_game(
            sport_season_id,
            event_dt,
            game=game, home_team_id=home_team_id, away_team_id=away_team_id,
        )


        params = {
            "sport": sport_id,
            "sportSeasonId": sport_season_id,
            "seasonPhaseId": season_phase_id,
            "externalGameId": external_game_id,
            "date": event_dt,
            "homeTeamId": home_team_id,
            "awayTeamId": away_team_id,
            "homeScore": game["homeScore"],
            "awayScore": game["awayScore"],
            "homeTeamExternalId": str(game["homeEspnId"]),
            "awayTeamExternalId": str(game["awayEspnId"]),
            "homeTeamName": game["homeName"],
            "awayTeamName": game["awayName"],
            "broadcast": game["broadcast"]
        }

        with self.db.begin() as conn:
            row = self.ingestion_repository.upsert_game(conn, params).fetchone()

        return int(row[0])

    def _get_all_sport_teams(self, sport_id: int, max_teams: Optional[int] = None) -> List[Dict[str, Any]]:


        params: Dict[str, Any] = {"sportId": sport_id}
        if max_teams is not None:
            params["maxTeams"] = max_teams

        with self.db.begin() as conn:
            rows = self.ingestion_repository.sport_teams(conn, params).fetchall()

        return [dict(r._mapping) for r in rows]

    def bootstrap_league_schedule(
        self,
        sport_id: int,
        sport_season_id: int,
        max_teams: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        - Ensures Week rows for this league (regular + postseason)
        - If SportSeason.scheduleBootstrapped is false OR force=True:
            * Calls /teams/{id}/schedule for all SportTeams in this sport
            * Inserts games into global GameResult
            * Marks SportSeason.scheduleBootstrapped = true
        Otherwise:
            * Skips the heavy ESPN work and just returns a summary.
        """
        api_keyword, api_group_ids, base_url = self._get_sport_api_config(sport_id)

        teams = self._get_all_sport_teams(sport_id, max_teams=max_teams)
        client = self._new_client(self.espn_base_url, api_keyword)

        for t in teams:
            external_id = t["externalId"]
            if not external_id:
                continue

            try:
                schedule_json = client.fetch_team_schedule(str(external_id))
            except Exception as e:
                print(f"Failed to fetch schedule for team {external_id}: {e}")
                continue

            for event in client.iter_scoreboard_events(schedule_json):
                game = client.extract_game_from_event(event)
                if not game:
                    continue

                self._insert_or_update_game(sport_id, sport_season_id, game)

        # Mark SportSeason as bootstrapped

        with self.db.begin() as conn:
            self.ingestion_repository.mark_team_bootstrapped(conn, {"sportSeasonId": sport_season_id})

        return {
            "sportId": sport_id,
            "sportSeasonId": sport_season_id,
            "teamsProcessed": len(teams),
        }

    def ingest_scoreboard_for_date_for_sport_season(
        self,
        sport_season_id: int,
        target_date: dt.date,
    ) -> Dict[str, Any]:
        """
        Ingest ESPN scoreboard for one date and upsert into GameResult.
        No leagues involved.
        """
        with self.db.begin() as conn:
            ss = self.ingestion_repository.season_for_ingestion(conn, {"id": sport_season_id}).mappings().first()

        if not ss:
            raise ValueError(f"SportSeason {sport_season_id} not found")

        sport_id = int(ss["sportId"])
        api_keyword, api_group_ids, base_url = self._get_sport_api_config(sport_id)

        client = self._new_client(self.espn_base_url, api_keyword)
        datestr = target_date.strftime("%Y%m%d")

        events_seen = 0
        games_upserted = 0
        seen_external_game_ids = set()

        for group_id in api_group_ids:
            try:
                scoreboard_json = client.fetch_scoreboard_for_date(
                    datestr=datestr,
                    group_id=group_id,
                )
            except Exception as e:
                raise RuntimeError(f"Scoreboard fetch failed for sport={sport_id}, date={datestr}, group={group_id}") from e

            for event in client.iter_scoreboard_events(scoreboard_json):
                game = client.extract_game_from_event(event)
                if not game:
                    continue

                external_game_id = game.get("externalGameId")
                if not external_game_id:
                    continue

                # Prevent duplicate upserts across groups
                if external_game_id in seen_external_game_ids:
                    continue

                seen_external_game_ids.add(external_game_id)
                events_seen += 1

                self._insert_or_update_game(
                    sport_id,
                    sport_season_id,
                    game,
                )
                games_upserted += 1

        return {
            "sportId": sport_id,
            "sportSeasonId": sport_season_id,
            "date": str(target_date),
            "eventsSeen": events_seen,
            "gamesUpserted": games_upserted,
        }

    def bootstrap_sport_season_schedule_by_scoreboard(
        self,
        sport_season_id: int,
        *,
        force: bool = False,
        max_days: Optional[int] = None,
        checkpoint_path=None,
    ) -> Dict[str, Any]:
        """
        Ingest pending dates, checkpointing each successful day. Reruns resume;
        force discards checkpoints and refreshes the full date range.
        """

        with self.db.begin() as conn:
            ss = self.ingestion_repository.season_for_bootstrap(conn, {"id": sport_season_id}).mappings().first()

        if not ss:
            raise ValueError(f"SportSeason {sport_season_id} not found")

        start_date = ss["seasonStart"]
        end_date = ss["seasonEnd"]

        if not start_date or not end_date:
            raise ValueError("SportSeason missing seasonStart/seasonEnd")

        if end_date < start_date:
            raise ValueError(f"Invalid season window: {start_date} -> {end_date}")

        if max_days is not None and (isinstance(max_days, bool) or max_days <= 0):
            raise ValueError("max_days must be a positive integer")
        api_keyword, api_groups, _ = self._get_sport_api_config(int(ss["sportId"]))
        identity = fingerprint({
            "database": str(self.db.url), "season": sport_season_id,
            "sport": ss["sportId"], "start": start_date, "end": end_date,
            "source": self.espn_base_url, "apiKeyword": api_keyword,
            "apiGroups": sorted(set(api_groups)),
            "phases": sorted([
                {key: phase.get(key) for key in
                 ('id', 'type', 'tournamentId', 'sportConferenceId', 'startDate', 'endDate', 'rules')}
                for phase in self._get_season_phases(sport_season_id)
            ], key=lambda phase: phase['id']),
        })
        checkpoint = BootstrapCheckpoint(
            checkpoint_path or default_checkpoint_path(self.db.url, sport_season_id), identity, reset=force)
        if ss["scheduleBootstrapped"] and not force and not (checkpoint.resuming and not checkpoint.complete):
            return {
                "sportId": int(ss["sportId"]), "sportSeasonId": sport_season_id,
                "skipped": True, "reason": "already scheduleBootstrapped (use force=True to re-run)",
            }
        all_dates = [start_date + dt.timedelta(days=n) for n in range((end_date - start_date).days + 1)]
        pending = [d for d in all_dates if d not in checkpoint.completed]
        days_skipped = len(all_dates) - len(pending)
        if max_days is not None:
            pending = pending[:max_days]
        checkpoint.complete = False
        checkpoint.save()
        with self.db.begin() as conn:
            self.ingestion_repository.bootstrap_start(conn, {"id": sport_season_id})
        print(f"[bootstrap] Checkpoint: {checkpoint.path}")
        print(f"[bootstrap] Skipping {days_skipped} completed dates; processing {len(pending)} dates")
        days_processed = failed_days = events_seen_total = games_upserted_total = 0
        for d in pending:
            try:
                summary = self.ingest_scoreboard_for_date_for_sport_season(sport_season_id, d)
            except Exception as e:
                failed_days += 1
                print(f"[bootstrap-by-date] ERROR sportSeasonId={sport_season_id} date={d}: {e}")
            else:
                events_seen_total += int(summary.get("eventsSeen", 0))
                games_upserted_total += int(summary.get("gamesUpserted", 0))
                checkpoint.completed.add(d)
                checkpoint.save()
                print(f"[bootstrap] Completed {d}: {summary.get('gamesUpserted', 0)} games")
            days_processed += 1
        complete = all(d in checkpoint.completed for d in all_dates)
        checkpoint.complete = complete
        checkpoint.save()
        with self.db.begin() as conn:
            self.ingestion_repository.bootstrap_finish(conn, {"id": sport_season_id, "complete": complete})

        return {
            "sportId": int(ss["sportId"]),
            "sportSeasonId": sport_season_id,
            "startDate": str(start_date),
            "endDate": str(end_date),
            "daysProcessed": days_processed,
            "daysSkipped": days_skipped,
            "checkpointPath": str(checkpoint.path),
            "failedDays": failed_days,
            "complete": complete,
            "eventsSeenTotal": events_seen_total,
            "gamesUpsertedTotal": games_upserted_total,
        }

    def ingest_scoreboard_for_date_for_league(
        self,
        league_id: int,
        target_date: dt.date,
    ) -> Dict[str, Any]:
        """
        Convenience wrapper: use league to determine sportSeason and ingest
        scoreboard games for that date.
        """
        league = self._get_league(league_id)
        sport_id = int(league["sport"])
        api_keyword, api_group_ids, base_url = self._get_sport_api_config(sport_id)

        season = self._get_sport_season_for_league(league_id)
        sport_season_id = int(season["sportSeasonId"])

        client = self._new_client(self.espn_base_url, api_keyword)
        datestr = target_date.strftime("%Y%m%d")

        print(f"Ingesting scoreboard for league {league_id} (sport={sport_id}, sportSeasonId={sport_season_id}) date={datestr}")

        events_seen = 0

        for group_id in api_group_ids:
            scoreboard_json = client.fetch_scoreboard_for_date(datestr, group_id)

            for event in client.iter_scoreboard_events(scoreboard_json):
                events_seen += 1
                game = client.extract_game_from_event(event)
                if not game:
                    continue

                self._insert_or_update_game(sport_id, sport_season_id, game)

        return {
            "leagueId": league_id,
            "sportId": sport_id,
            "sportSeasonId": sport_season_id,
            "date": target_date.isoformat(),
            "eventsSeen": events_seen
        }

    def _lookup_season_phase_id_for_game(
        self,
        sport_season_id: int,
        event_dt: dt.datetime,
        game=None, home_team_id=None, away_team_id=None,
        ) -> Optional[int]:
        """
        Given a sportSeason + game datetime, find the matching SeasonPhase (if any).
        Assumes SeasonPhase has a date range for the phase.
        """

        phases = self._get_season_phases(sport_season_id)
        if any(p.get('rules') for p in phases):
            conference_ids = set()
            if home_team_id is not None and away_team_id is not None:
                with self.db.begin() as conn:
                    rows = self.ingestion_repository.shared_conferences(conn, {"season": sport_season_id, "home": home_team_id, "away": away_team_id}).fetchall()
                conference_ids = {int(row[0]) for row in rows}
            dated = [p for p in phases if p['startDate'] is not None and p['endDate'] is not None]
            return select_phase(dated, game or {}, event_dt, conference_ids)


        with self.db.begin() as conn:
            row = self.ingestion_repository.fallback_phase(conn, {
                    "sportSeasonId": sport_season_id,
                    "eventDate": event_dt,
                }).fetchone()

        return int(row[0]) if row else None

    def upsert_sport_season(
        self,
        conn,
        sport_id: int,
        season_year: int,
        season_start: dt.date,
        season_end: dt.date,
    ) -> int:
        row = self.ingestion_repository.upsert_season(conn, {
                "sportId": sport_id,
                "year": season_year,
                "seasonStart": season_start,
                "seasonEnd": season_end,
            }).fetchone()

        return int(row[0])

    def ingest_season_for_job(self, sport_season_id, target_date):
        return self.ingest_scoreboard_for_date_for_sport_season(sport_season_id, target_date)

    def ingest_league_for_job(self, league_id, target_date):
        return self.ingest_scoreboard_for_date_for_league(league_id, target_date)

    def bootstrap_for_job(self, sport_season_id, *, force=False, max_days=None, checkpoint_path=None):
        return self.bootstrap_sport_season_schedule_by_scoreboard(sport_season_id, force=force, max_days=max_days, checkpoint_path=checkpoint_path)

    def bootstrap_teams_for_job(self, sport_id, sport_season_id, max_teams=None):
        return self.bootstrap_league_schedule(sport_id, sport_season_id, max_teams)

    def upsert_season_for_job(self, conn, sport_id, season_year, season_start, season_end):
        return self.upsert_sport_season(conn, sport_id, season_year, season_start, season_end)

    def active_leagues_for_job(self, target_date):
        with self.db.begin() as conn:
            rows = self.ingestion_repository.active_leagues(conn, {"d": target_date}).fetchall()
        return [int(row[0]) for row in rows]
