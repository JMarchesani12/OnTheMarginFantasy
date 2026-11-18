-- Read-only aggregate audit. No rows, cleanup, locks or schema mutation.
SELECT
 (SELECT count(*) FROM "ConferenceMembership" cm LEFT JOIN "SportTeam" st ON st.id=cm."sportTeamId"
    LEFT JOIN "SportConference" sc ON sc.id=cm."sportConferenceId"
    WHERE cm."sportId" IS NULL OR st.id IS NULL OR sc.id IS NULL OR cm."sportId"<>st."sportId" OR cm."sportId"<>sc."sportId") AS invalid_membership_sports,
 (SELECT count(*) FROM (SELECT "sportTeamId","sportId","seasonYear" FROM "ConferenceMembership"
    GROUP BY "sportTeamId","sportId","seasonYear" HAVING count(*)>1) duplicates) AS duplicate_membership_scopes,
 (SELECT count(*) FROM "GameResult" gr JOIN "SportSeason" ss ON ss.id=gr."sportSeasonId"
    WHERE gr.sport<>ss."sportId") AS game_season_sport_mismatches,
 (SELECT count(*) FROM "GameResult" gr JOIN "SeasonPhase" sp ON sp.id=gr."seasonPhaseId"
    WHERE gr."sportSeasonId"<>sp."sportSeasonId") AS game_phase_season_mismatches,
 (SELECT count(*) FROM "GameResult" gr LEFT JOIN "SportTeam" h ON h.id=gr."homeTeamId" LEFT JOIN "SportTeam" a ON a.id=gr."awayTeamId"
    WHERE (h.id IS NOT NULL AND h."sportId"<>gr.sport) OR (a.id IS NOT NULL AND a."sportId"<>gr.sport)) AS game_team_sport_mismatches,
 (SELECT count(*) FROM "SeasonPhase" sp JOIN "SportSeason" ss ON ss.id=sp."sportSeasonId"
    JOIN "TournamentDefinition" td ON td.id=sp."tournamentId" WHERE td."sportId"<>ss."sportId") AS phase_tournament_sport_mismatches,
 (SELECT count(*) FROM "TournamentDefinition" td JOIN "SportConference" sc ON sc.id=td."sportConferenceId"
    WHERE td."sportId"<>sc."sportId") AS tournament_conference_sport_mismatches,
 (SELECT count(*) FROM "LeagueTeamSlot" lts JOIN "League" l ON l.id=lts."leagueId" JOIN "SportTeam" st ON st.id=lts."sportTeamId"
    WHERE l.sport<>st."sportId") AS slot_team_sport_mismatches,
 (SELECT count(*) FROM "SportSeason" ss JOIN "SportTeam" st ON st."sportId"=ss."sportId"
    WHERE NOT EXISTS (SELECT 1 FROM "ConferenceMembership" cm JOIN "SportConference" sc ON sc.id=cm."sportConferenceId" AND sc."sportId"=st."sportId"
      WHERE cm."sportTeamId"=st.id AND cm."sportId"=st."sportId"
        AND (cm."seasonYear"=ss."seasonYear" OR (cm."seasonYear" IS NULL AND NOT EXISTS (
          SELECT 1 FROM "ConferenceMembership" specific WHERE specific."sportTeamId"=st.id AND specific."seasonYear"=ss."seasonYear"))))) AS season_teams_missing_effective_mapping;
