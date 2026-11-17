"""Invocation-local scoreboard sharing; legacy ingestion entry points stay intact."""
from copy import deepcopy
from operations import GateLost


class SharedScoreboardIngestionService:
    def __init__(self, ingestion_service, check_gate):
        self.service = ingestion_service
        self.check_gate = check_gate
        self._configs = {}
        self._units = {}

    def _config_for_sport(self, sport_id):
        if sport_id not in self._configs:
            keyword, groups, _ = self.service._get_sport_api_config(sport_id)
            self._configs[sport_id] = (self.service.espn_base_url, keyword, tuple(dict.fromkeys(groups)))
        return self._configs[sport_id]

    def _resolve_league_unit(self, league_id, target_date):
        league = self.service._get_league(league_id)
        sport_id = int(league['sport'])
        season = self.service._get_sport_season_for_league(league_id)
        if int(season['sportId']) != sport_id:
            raise ValueError('League sport/season changed during ingestion resolution')
        season_id = int(season['sportSeasonId'])
        base_url, keyword, groups = self._config_for_sport(sport_id)
        key = (sport_id, season_id, target_date, base_url, keyword, groups)
        return key

    def _ingest_unit(self, context, target_date):
        sport_id, season_id, _, base_url, keyword, groups = context
        client = self.service._new_client(base_url, keyword)
        last_applied = {}
        events_seen = games_upserted = duplicate_skips = 0
        for group_id in groups:
            self.check_gate()
            payload = client.fetch_scoreboard_for_date(target_date.strftime('%Y%m%d'), group_id)
            for event in client.iter_scoreboard_events(payload):
                events_seen += 1
                game = client.extract_game_from_event(event)
                if not game or not game.get('externalGameId'):
                    continue
                external_id = str(game['externalGameId'])
                candidate = deepcopy(game)
                if last_applied.get(external_id) == candidate:
                    duplicate_skips += 1
                    continue
                self.check_gate()
                self.service._insert_or_update_game(sport_id, season_id, game)
                # Only committed writes advance the last-applied revision.
                last_applied[external_id] = candidate
                games_upserted += 1
        return dict(sportId=sport_id, sportSeasonId=season_id, date=target_date.isoformat(),
                    eventsSeen=events_seen, gamesUpserted=games_upserted, duplicateSkips=duplicate_skips)

    def iter_league_outcomes(self, league_ids, target_date):
        for league_id in league_ids:
            self.check_gate()
            try:
                key = self._resolve_league_unit(league_id, target_date)
                if key not in self._units:
                    try:
                        self._units[key] = (self._ingest_unit(key, target_date), None)
                    except GateLost:
                        raise
                    except Exception as exc:
                        self._units[key] = (None, exc)
                summary, error = self._units[key]
            except GateLost:
                raise
            except Exception as exc:
                summary, error = None, exc
            self.check_gate()
            yield dict(leagueId=league_id, date=target_date.isoformat(),
                       summary=dict(summary, leagueId=league_id) if summary is not None else None, error=error)
