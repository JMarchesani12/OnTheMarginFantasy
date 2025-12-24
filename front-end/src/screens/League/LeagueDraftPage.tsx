import { useCallback, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { League } from "../../types/league";
import type { OwnedTeam } from "../../types/schedule";
import { getAvailableTeams } from "../../api/roster";
import { createDraftPick } from "../../api/draft";
import { normalizeOwnedTeams, type RawOwnedTeam } from "../../utils/teams";
import "./LeagueDraftPage.css";

type LocationState = {
  league?: League;
};

type GroupedTeams = [string, OwnedTeam[]][];

const LeagueDraftPage = () => {
  const navigate = useNavigate();
  const { league_id } = useParams();
  const location = useLocation();
  const state = location.state as LocationState | null;
  const league = state?.league;

  const leagueId = league?.leagueId ?? (league_id ? Number(league_id) : null);

  const [availableTeams, setAvailableTeams] = useState<OwnedTeam[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<OwnedTeam | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [conferenceFilter, setConferenceFilter] = useState("all");
  const [draftSelections, setDraftSelections] = useState<OwnedTeam[]>([]);
  const draftWeekNumber = 1;

  const isBrowser = typeof window !== "undefined";
  const storageKey = leagueId ? `draftSelections:${leagueId}` : null;

  const loadTeams = useCallback(async () => {
    if (!leagueId) {
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const data = await getAvailableTeams(draftWeekNumber, leagueId);
      const normalized = normalizeOwnedTeams(data as RawOwnedTeam[]);
      setAvailableTeams(normalized);
    } catch (err: any) {
      setError(err?.message ?? "Failed to load available teams");
    } finally {
      setLoading(false);
    }
  }, [leagueId, draftWeekNumber]);

  useEffect(() => {
    let cancelled = false;
    loadTeams();

    if (!leagueId) {
      return () => {
        cancelled = true;
      };
    }

    const interval = window.setInterval(() => {
      if (!cancelled) {
        loadTeams();
      }
    }, 10000);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [loadTeams, leagueId]);

  useEffect(() => {
    if (!storageKey || !isBrowser) {
      return;
    }

    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored) {
        const parsed = JSON.parse(stored) as RawOwnedTeam[];
        setDraftSelections(normalizeOwnedTeams(parsed));
      }
    } catch (err) {
      console.warn("Failed to load draft selections", err);
    }
  }, [storageKey]);

  const persistSelections = (teams: OwnedTeam[]) => {
    if (!storageKey || !isBrowser) {
      return;
    }

    try {
      window.localStorage.setItem(storageKey, JSON.stringify(teams));
    } catch (err) {
      console.warn("Failed to persist draft selections", err);
    }
  };

  const groupTeams = (teams: OwnedTeam[]): GroupedTeams => {
    const map = new Map<string, OwnedTeam[]>();

    teams.forEach((team) => {
      const key = team.conferenceName ?? "Independent";
      const current = map.get(key) ?? [];
      current.push(team);
      map.set(key, current);
    });

    return Array.from(map.entries()).sort(([a], [b]) => a.localeCompare(b));
  };

  const uniqueConferences = useMemo(() => {
    const all = availableTeams
      .map((team) => team.conferenceName ?? "Independent")
      .filter(Boolean);
    return Array.from(new Set(all)).sort((a, b) => a.localeCompare(b));
  }, [availableTeams]);

  const applyFilters = (teams: OwnedTeam[]) =>
    teams.filter((team) => {
      const matchesSearch = team.teamName
        .toLowerCase()
        .includes(searchTerm.toLowerCase());
      const matchesConference =
        conferenceFilter === "all" ||
        (team.conferenceName ?? "Independent") === conferenceFilter;
      return matchesSearch && matchesConference;
    });

  const groupedAvailable = useMemo(
    () => groupTeams(applyFilters(availableTeams)),
    [availableTeams, searchTerm, conferenceFilter]
  );

  if (!league || !leagueId) {
    return (
      <div className="draft-page">
        <button
          className="draft-page__back"
          type="button"
          onClick={() => navigate(-1)}
        >
          ← Back
        </button>
        <p className="draft-page__empty">
          League context missing. Return to your leagues list and try again.
        </p>
      </div>
    );
  }

  const toggleTeam = (team: OwnedTeam) => {
    setSelectedTeam((current) =>
      current?.teamId === team.teamId ? null : team
    );
  };

  const handleSubmit = async () => {
    if (!selectedTeam) {
      return;
    }

    try {
      await createDraftPick(league.memberId, league.leagueId, selectedTeam.teamId);

      const updatedSelections = [selectedTeam, ...draftSelections];
      setDraftSelections(updatedSelections);
      persistSelections(updatedSelections);
      setSelectedTeam(null);
      setAvailableTeams((current) =>
        current.filter((team) => team.teamId !== selectedTeam.teamId)
      );
    } catch (err: any) {
      setError(err?.message ?? "Failed to submit draft pick");
    }
  };

  const submitDisabled = loading || !selectedTeam;

  return (
    <div className="draft-page">
      <button
        className="draft-page__back"
        type="button"
        onClick={() => navigate(-1)}
      >
        ← Back to League
      </button>

      <header className="draft-page__header">
        <div>
          <p className="draft-page__eyebrow">Draft Center</p>
          <h1>{league.leagueName}</h1>
          <p className="draft-page__subhead">
            Browse all available teams for week {draftWeekNumber} and lock in your pick.
          </p>
        </div>
      </header>

      <section className="draft-page__controls" aria-label="Draft filters">
        <div className="draft-page__control">
          <label htmlFor="draft-search">Search teams</label>
          <input
            id="draft-search"
            type="text"
            placeholder="Search by team name"
            value={searchTerm}
            onChange={(evt) => setSearchTerm(evt.target.value)}
          />
        </div>
        <div className="draft-page__control">
          <label htmlFor="draft-conference">Conference</label>
          <select
            id="draft-conference"
            value={conferenceFilter}
            onChange={(evt) => setConferenceFilter(evt.target.value)}
          >
            <option value="all">All conferences</option>
            {uniqueConferences.map((conf) => (
              <option key={conf} value={conf}>
                {conf}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error && <p className="draft-page__error">{error}</p>}
      {loading && <p className="draft-page__loading">Loading teams…</p>}

      <section className="draft-page__list" role="region" aria-label="Available teams">
        {groupedAvailable.length === 0 && !loading ? (
          <p className="draft-page__empty">No teams available.</p>
        ) : (
          groupedAvailable.map(([conference, teams]) => (
            <div className="draft-page__group" key={conference}>
              <p className="draft-page__group-label">{conference}</p>
              <div className="draft-page__team-grid">
                {teams.map((team) => {
                  const isSelected = selectedTeam?.teamId === team.teamId;
                  return (
                    <button
                      key={team.teamId}
                      type="button"
                      className={`draft-page__team-btn ${
                        isSelected ? "is-selected" : ""
                      }`}
                      onClick={() => toggleTeam(team)}
                      aria-pressed={isSelected}
                    >
                      {team.teamName}
                    </button>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </section>

      <section className="draft-page__queue">
        <p className="draft-page__queue-label">Selected Team</p>
        {!selectedTeam ? (
          <p className="draft-page__queue-empty">No team selected.</p>
        ) : (
          <div className="draft-page__queue-entry">
            <span>{selectedTeam.teamName}</span>
            <button
              type="button"
              className="draft-page__queue-remove"
              onClick={() => setSelectedTeam(null)}
              aria-label="Remove selected team"
            >
              ×
            </button>
          </div>
        )}
      </section>

      <section className="draft-page__history">
        <p className="draft-page__queue-label">Recent Picks</p>
        {draftSelections.length === 0 ? (
          <p className="draft-page__queue-empty">No selections recorded yet.</p>
        ) : (
          <ol className="draft-page__history-list">
            {draftSelections.map((team, index) => (
              <li key={`${team.teamId}-${index}`}>{team.teamName}</li>
            ))}
          </ol>
        )}
      </section>

      <footer className="draft-page__footer">
        <button
          type="button"
          className="draft-page__submit"
          onClick={handleSubmit}
          disabled={submitDisabled}
        >
          Draft Selected Team
        </button>
      </footer>
    </div>
  );
};

export default LeagueDraftPage;
