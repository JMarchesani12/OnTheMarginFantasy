# Database Schema

This document describes the current application database shape as used by the
API. It is based on the live Supabase schema and the SQL in `api/endpoints`,
`api/startSeasonJobs`, `api/cronJobs`, and `api/worker`.

## Overview

On The Margin Fantasy is a team-based fantasy league app for college sports.
Users join leagues, draft sport teams, manage weekly ownership, and score from
global game results.

The most important modeling distinction is:

```text
School      = institution-level identity
SportTeam   = a school's team in one sport
Conference  = base conference identity
SportConference = a conference instance for one sport
```

Example:

```text
Conference.id = 31                    # UAC
SportConference.id = 54
SportConference.conferenceId = 31
SportConference.sportId = 2           # football
```

## Core Tables

### Identity

- `User`: app user profile; maps to Supabase auth through `uuid`.
- `School`: institution identity, shared across sports.

### Sports And Seasons

- `Sport`: supported sports and API configuration.
- `SportSeason`: one sport/year season, such as football 2026.
- `SportSeasonSubdivision`: subdivision windows for a sport season, such as FBS
  and FCS.
- `SeasonPhase`: regular season, conference tournament/playoff, national
  tournament/playoff, or other configured season phase.
- `TournamentDefinition`: reusable tournament metadata used when creating
  postseason `SeasonPhase` rows.

### Teams And Conferences

- `SportTeam`: a team for one school and one sport.
- `Conference`: base conference identity.
- `SportConference`: sport-specific conference row.
- `ConferenceMembership`: sport-team membership in a sport conference.

### Leagues

- `League`: fantasy league for one sport and season year.
- `LeagueMember`: a user's team inside a league.
- `LeagueJoinRequest`: pending/approved/rejected requests to join a league.
- `Week`: league-specific scoring window.

### Ownership, Draft, And Transactions

- `LeagueTeamSlot`: ownership interval for a sport team in a league.
- `DraftState`: current draft state for a league.
- `DraftTurn`: expected member for each draft pick number.
- `DraftPick`: completed draft selections.
- `Transaction`: trade or free-agent move.
- `TransactionVote`: member votes on a transaction.

### Schedule And Scoring

- `GameResult`: global sport-season games and scores.
- `WeeklyTeamScore`: computed weekly fantasy score per league member.
- `BonusPointEvent`: season-level bonus event records, where present.

## Main Relationships

```text
User.id
  -> League.commissioner
  -> LeagueMember.userId

Sport.id
  -> League.sport
  -> SportSeason.sportId
  -> SportTeam.sportId
  -> SportConference.sportId
  -> ConferenceMembership.sportId
  -> GameResult.sport

School.id
  -> SportTeam.schoolId

League.id
  -> LeagueMember.leagueId
  -> LeagueJoinRequest.leagueId
  -> Week.leagueId
  -> LeagueTeamSlot.leagueId
  -> DraftState.leagueId
  -> DraftTurn.leagueId
  -> DraftPick.leagueId
  -> Transaction.leagueId
  -> WeeklyTeamScore.leagueId

LeagueMember.id
  -> LeagueTeamSlot.memberId
  -> DraftTurn.memberId
  -> DraftPick.memberId
  -> Transaction.memberFromId / memberToId
  -> TransactionVote.memberId
  -> WeeklyTeamScore.memberId

SportSeason.id
  -> SportSeasonSubdivision.sportSeasonId
  -> SeasonPhase.sportSeasonId
  -> GameResult.sportSeasonId

SportTeam.id
  -> ConferenceMembership.sportTeamId
  -> LeagueTeamSlot.sportTeamId
  -> DraftPick.sportTeamId
  -> GameResult.homeTeamId / awayTeamId

Conference.id
  -> SportConference.conferenceId

SportConference.id
  -> ConferenceMembership.sportConferenceId
```

## Conference Membership

`ConferenceMembership` is direct and sport-specific.

```text
ConferenceMembership.sportTeamId
  -> SportTeam.id

ConferenceMembership.sportId
  -> Sport.id

ConferenceMembership.sportConferenceId
  -> SportConference.id
```

Invariant:

```text
ConferenceMembership.sportId = SportTeam.sportId
ConferenceMembership.sportId = SportConference.sportId
```

Each non-independent sport team should have at most one conference membership
for a given sport and season. Independent teams have no membership row for that
sport/season.

Current guardrails:

```text
Unique current membership:
  ConferenceMembership(sportTeamId, sportId)
  WHERE seasonYear IS NULL

Unique season-scoped membership:
  ConferenceMembership(sportTeamId, sportId, seasonYear)
  WHERE seasonYear IS NOT NULL
```

Example UAC football query:

```sql
SELECT
  st.id AS "sportTeamId",
  st."displayName",
  st."externalId",
  cm."seasonYear"
FROM "ConferenceMembership" cm
JOIN "SportTeam" st
  ON st.id = cm."sportTeamId"
WHERE cm."sportConferenceId" = 54
  AND cm."sportId" = 2
ORDER BY st."displayName";
```

## League Ownership Model

`LeagueTeamSlot` stores ownership over time rather than just the current roster.

```text
LeagueTeamSlot.leagueId
LeagueTeamSlot.memberId
LeagueTeamSlot.sportTeamId
LeagueTeamSlot.acquiredWeek
LeagueTeamSlot.droppedWeek
LeagueTeamSlot.acquiredVia
```

A team is owned in a week when:

```sql
acquiredWeek <= :weekNumber
AND (droppedWeek IS NULL OR droppedWeek > :weekNumber)
```

This same window is used by roster views, schedule views, transaction logic, and
weekly scoring.

## Draft Model

Draft state is split into:

- `DraftState`: one row per league with live/paused/complete status and current
  pick.
- `DraftTurn`: generated turn order for every overall pick.
- `DraftPick`: completed selections.
- `LeagueTeamSlot`: ownership created by completed picks.

Draft picks validate:

- the draft is live,
- the member is on the clock,
- the team is not already owned,
- the member does not exceed per-conference limits from `SportConference`,
- unique draft constraints are respected.

## Transaction Model

`Transaction` stores both trades and free-agent moves.

Common fields include:

```text
leagueId
weekId
memberFromId
memberToId
fromTeamIds
toTeamIds
type
status
```

Team IDs are stored in JSON arrays for multi-team moves. Applying a transaction
updates `LeagueTeamSlot` by ending dropped ownership and inserting acquired
ownership.

Conference limits are validated through:

```text
LeagueTeamSlot.sportTeamId
  -> SportTeam.id
  -> ConferenceMembership.sportTeamId
  -> SportConference.maxTeamsPerOwner
```

## Schedule And Game Results

`GameResult` is global by sport season. Leagues consume those rows through their
matching `League.sport` and `League.seasonYear`.

Important links:

```text
League.sport + League.seasonYear
  -> SportSeason.sportId + SportSeason.seasonYear

GameResult.sportSeasonId
  -> SportSeason.id

GameResult.homeTeamId / awayTeamId
  -> SportTeam.id

GameResult.seasonPhaseId
  -> SeasonPhase.id
```

`Week` is league-specific, so different leagues can have different scoring
windows even when they use the same sport season.

## Scoring Model

Weekly scoring is computed from:

```text
League
Week
LeagueMember
LeagueTeamSlot
GameResult
WeeklyTeamScore
```

The main weekly score is based on point differential for games involving teams a
member owns during that week. Season bonuses and tiebreakers also use
`SeasonPhase`, final standings, and configured bonus rules in `League.settings`.

## Useful Queries

Find all conferences for a sport:

```sql
SELECT
  sc.id AS "sportConferenceId",
  sc."sportId",
  sc."conferenceId",
  c.name,
  sc."maxTeamsPerOwner"
FROM "SportConference" sc
JOIN "Conference" c
  ON c.id = sc."conferenceId"
WHERE sc."sportId" = :sportId
ORDER BY c.name;
```

Find all teams in a sport conference:

```sql
SELECT
  st.id,
  st."displayName",
  st."externalId",
  cm."seasonYear"
FROM "ConferenceMembership" cm
JOIN "SportTeam" st
  ON st.id = cm."sportTeamId"
WHERE cm."sportConferenceId" = :sportConferenceId
ORDER BY st."displayName";
```

Find active owned teams for a league member and week:

```sql
SELECT
  lts.id AS "slotId",
  st.id AS "sportTeamId",
  st."displayName"
FROM "LeagueTeamSlot" lts
JOIN "SportTeam" st
  ON st.id = lts."sportTeamId"
WHERE lts."leagueId" = :leagueId
  AND lts."memberId" = :memberId
  AND lts."acquiredWeek" <= :weekNumber
  AND (lts."droppedWeek" IS NULL OR lts."droppedWeek" > :weekNumber)
ORDER BY st."displayName";
```

Check conference membership invariants:

```sql
SELECT
  cm.id AS "conferenceMembershipId",
  cm."sportTeamId",
  st."sportId" AS "teamSportId",
  cm."sportId" AS "membershipSportId",
  cm."sportConferenceId",
  sc."sportId" AS "conferenceSportId"
FROM "ConferenceMembership" cm
JOIN "SportTeam" st
  ON st.id = cm."sportTeamId"
JOIN "SportConference" sc
  ON sc.id = cm."sportConferenceId"
WHERE cm."sportId" IS DISTINCT FROM st."sportId"
   OR cm."sportId" IS DISTINCT FROM sc."sportId";
```

## Environment

`VITE_SUPABASE_URL` is the public Supabase API URL used by the frontend.

`SUPABASE_DB_URL` is the Postgres connection string used by the backend and by
schema inspection scripts. Do not expose it in frontend code.
