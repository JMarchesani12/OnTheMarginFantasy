import { safeErrorMessage, CREATE_LEAGUE_UNCERTAIN, READ_ERROR } from "../../api/safeError";
import React, { useEffect, useState } from "react";
import "./CreateLeague.css";
import { useNavigate } from "react-router-dom";
import type { CreateLeaguePayload, TimeoutAction } from "../../types/league";
import { createLeague } from "../../api/leagues";
import {
  BonusesEditor,
  type BonusWithLocalId,
} from "../../components/League/BonusesEditor";
import { getSports } from "../../api/sport";
import type { Sport } from "../../types/sport";
import { useCurrentUser } from "../../context/currentUserContext";

interface CreateLeagueFormState {
  leagueName: string;
  teamName: string;
  sportId: string;          // string in form, converted to number on submit
  numPlayers: string;

  // read-only display fields
  status: string;
  seasonYear: string;

  draftDate: string;        // yyyy-mm-dd (date input)
  freeAgentDeadline: string;
  tradeDeadline: string;

  isDiscoverable: boolean;

  // settings.transactions
  tradeVetoEnabled: boolean;
  tradeVetoRequiredCount: string;

  // bonuses (local-only shape)
  bonuses: BonusWithLocalId[];

  // draft settings
  timeoutAction: TimeoutAction;
  graceSeconds: string;
}

const initialSeasonYear = new Date().getFullYear().toString();

const makeInitialState = (): CreateLeagueFormState => ({
  leagueName: "",
  teamName: "",
  sportId: "",
  numPlayers: "1",

  status: "Pre-Draft",
  seasonYear: initialSeasonYear,

  isDiscoverable: true,

  draftDate: "",
  freeAgentDeadline: "",
  tradeDeadline: "",

  tradeVetoEnabled: true,
  tradeVetoRequiredCount: "3",

  bonuses: [],

  timeoutAction: "AUTO-SKIP",
  graceSeconds: "3",
});

const CreateLeague: React.FC = () => {
  const { userId } = useCurrentUser();
  const localTimeZone = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const [form, setForm] = useState<CreateLeagueFormState>(makeInitialState);
  const [sports, setSports] = useState<Sport[]>([]);
  const [sportsLoading, setSportsLoading] = useState(false);
  const [sportsError, setSportsError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [errorField, setErrorField] = useState<string | null>(null);
  const fieldAccessibility = (id: string) => ({
    "aria-invalid": errorField === id ? true as const : undefined,
    "aria-describedby": [errorField === id ? "cl-form-error" : null, id === "league-sport" && sportsError ? "cl-sports-error" : null].filter(Boolean).join(" ") || undefined,
  });
  const navigate = useNavigate();

  const update = (patch: Partial<CreateLeagueFormState>) =>
    setForm((prev) => ({ ...prev, ...patch }));

  useEffect(() => {
    let isMounted = true;

    const loadSports = async () => {
      setSportsLoading(true);
      setSportsError(null);

      try {
        const data = await getSports();
        if (!isMounted) {
          return;
        }
        setSports(data);
        if (data.length > 0) {
          setForm((prev) =>
            prev.sportId ? prev : { ...prev, sportId: String(data[0].id) }
          );
        }
      } catch (err: any) {
        if (isMounted) {
          setSportsError(safeErrorMessage(err, READ_ERROR));
        }
      } finally {
        if (isMounted) {
          setSportsLoading(false);
        }
      }
    };

    loadSports();

    return () => {
      isMounted = false;
    };
  }, []);

  const toIsoOrNull = (dateStr: string): string | null => {
    if (!dateStr) return null;
    const d = new Date(dateStr + "T00:00:00");
    return d.toISOString();
  };

  const handleSubmit: React.FormEventHandler<HTMLFormElement> = async (e) => {
    e.preventDefault();
    setError(null);
    setErrorField(null);

    if (!form.leagueName.trim()) {
      setErrorField("league-name");
      setError("League name is required.");
      return;
    }
    if (!form.teamName.trim()) {
      setErrorField("creator-team-name");
      setError("Team name is required.");
      return;
    }
    if (!form.sportId) {
      setErrorField("league-sport");
      setError("Sport is required.");
      return;
    }
    if (!form.numPlayers) {
      setError("Number of players is required.");
      return;
    }

    const selectedSport = sports.find(
      (sport) => sport.id === Number(form.sportId),
    );
    if (
      selectedSport?.maxDraftRounds == null ||
      selectedSport.maxPlayersToHaveMaxRounds == null
    ) {
      setErrorField("league-sport");
      setError(
        `${selectedSport?.name ?? "Selected sport"} is missing its draft configuration.`,
      );
      return;
    }
    const rounds = Number(selectedSport.maxDraftRounds);

    // build bonuses object: { [bonusKey]: { [placementKey]: points } }
    const bonuses: Record<string, Record<string, number>> = {};
    for (const bonus of form.bonuses) {
      const placements: Record<string, number> = {};
      bonus.placements.forEach((p) => {
        if (p.points === "") return;
        placements[p.key] = Number(p.points);
      });
      if (Object.keys(placements).length > 0) {
        bonuses[bonus.bonusKey] = placements;
      }
    }

    const payload: CreateLeaguePayload = {
      name: form.leagueName.trim(),
      teamName: form.teamName.trim(),
      sport: Number(form.sportId),
      numPlayers: 1,
      status: "Pre-Draft",
      settings: {
        bonuses,
        timezone: localTimeZone,
        transactions: {
          tradeVeto: {
            enabled: form.tradeVetoEnabled,
            requiredVetoCount: Number(form.tradeVetoRequiredCount || 0),
          },
        },
        draft: {
          draftType: "SNAKE",
          selectionTime: 60,
          numberOfRounds: rounds,
          timeoutAction: form.timeoutAction,
          graceSeconds: Number(form.graceSeconds || 0),
        },
      },
      draftDate: toIsoOrNull(form.draftDate),
      freeAgentDeadline: toIsoOrNull(form.freeAgentDeadline),
      tradeDeadline: toIsoOrNull(form.tradeDeadline),
      commissioner: userId, // replace with value from auth when you wire that up
      seasonYear: Number(initialSeasonYear),
      isDiscoverable: true
    };

    try {
      setSubmitting(true);
      await createLeague(payload);
      setForm(makeInitialState());
      navigate("/leagues");
    } catch (err) {
      setError(safeErrorMessage(err, CREATE_LEAGUE_UNCERTAIN));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="cl-page">
      <div className="cl-page-inner">
        <header className="cl-header">
          <h1>Create League</h1>
          <p className="cl-subtitle">
            Configure scoring, tiebreakers, bonuses, and deadlines.
          </p>
        </header>

        <form className="cl-form" onSubmit={handleSubmit} aria-describedby={error ? "cl-form-error" : undefined}>
          {/* Basics */}
          <div className="cl-field-group">
            <label className="cl-field-label" htmlFor="league-name">
              League Name <span className="cl-required">*</span>
            </label>
            <input id="league-name" {...fieldAccessibility("league-name")}
              type="text"
              value={form.leagueName}
              onChange={(e) => update({ leagueName: e.target.value })}
            />
          </div>

          <div className="cl-field-group">
            <label className="cl-field-label" htmlFor="creator-team-name">Your Team Name <span className="cl-required">*</span></label>
            <input {...fieldAccessibility("creator-team-name")} id="creator-team-name" type="text" required placeholder="My Team"
              value={form.teamName} onChange={(e) => update({ teamName: e.target.value })} />
          </div>

          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label" htmlFor="league-sport">
                Sport <span className="cl-required">*</span>
              </label>
              <select id="league-sport" {...fieldAccessibility("league-sport")}
                value={form.sportId}
                onChange={(e) => update({ sportId: e.target.value })}
                disabled={sportsLoading}
              >
                <option value="" disabled>
                  Select a sport
                </option>
                {sports.map((sport) => (
                  <option key={sport.id} value={String(sport.id)}>
                    {sport.name}
                  </option>
                ))}
              </select>
              {sportsError && (
                <p id="cl-sports-error" className="cl-form-error">{sportsError}</p>
              )}
            </div>

          </div>

          {/* Dates */}
          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label" htmlFor="draft-date">
                Draft Date
              </label>
              <input id="draft-date"
                type="date"
                value={form.draftDate}
                onChange={(e) => update({ draftDate: e.target.value })}
              />
            </div>

            <div className="cl-field-group">
              <label className="cl-field-label" htmlFor="free-agent-deadline">
                Free Agent Deadline
              </label>
              <input id="free-agent-deadline"
                type="date"
                value={form.freeAgentDeadline}
                onChange={(e) =>
                  update({ freeAgentDeadline: e.target.value })
                }
              />
            </div>

            <div className="cl-field-group">
              <label className="cl-field-label" htmlFor="trade-deadline">
                Trade Deadline
              </label>
              <input id="trade-deadline"
                type="date"
                value={form.tradeDeadline}
                onChange={(e) => update({ tradeDeadline: e.target.value })}
              />
            </div>
          </div>

          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label" htmlFor="draft-timeout-action">Draft Timeout Action</label>
              <select id="draft-timeout-action"
                value={form.timeoutAction}
                onChange={(e) =>
                  update({ timeoutAction: e.target.value as TimeoutAction })
                }
              >
                <option value="AUTO-SKIP">Auto-skip</option>
                <option value="AUTO-PICK">Auto-pick</option>
              </select>
            </div>
            <div className="cl-field-group">
              <label className="cl-field-label" htmlFor="draft-grace-seconds">Grace Period (seconds)</label>
              <input id="draft-grace-seconds"
                type="number"
                min={0}
                value={form.graceSeconds}
                onChange={(e) => update({ graceSeconds: e.target.value })}
              />
            </div>
          </div>

          {/* Transactions */}
          <div className="cl-field-group cl-field-inline">
            <label className="cl-field-label" htmlFor="trade-veto-enabled">Trade Veto</label>
            <label className="cl-inline-checkbox" htmlFor="trade-veto-enabled">
              <input
                id="trade-veto-enabled"
                type="checkbox"
                checked={form.tradeVetoEnabled}
                onChange={(e) =>
                  update({ tradeVetoEnabled: e.target.checked })
                }
              />
              Enabled
            </label>
            {form.tradeVetoEnabled && (
              <div className="cl-inline-number">
                <label htmlFor="trade-veto-count">Required veto count: <span className="cl-required">*</span></label>
                <input
                  type="number"
                  min={1}
                  id="trade-veto-count"
                  value={form.tradeVetoRequiredCount}
                  onChange={(e) =>
                    update({ tradeVetoRequiredCount: e.target.value })
                  }
                />
              </div>
            )}
          </div>

          {/* Bonuses */}
          <BonusesEditor
            value={form.bonuses}
            onChange={(bonuses) => update({ bonuses })}
          />

          {error && <p id="cl-form-error" role="alert" className="cl-form-error">{error}</p>}

          <div className="cl-form-actions">
            <button
              type="button"
              className="cl-btn-secondary"
              onClick={() => navigate(-1)}
              disabled={submitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="cl-btn-primary"
              disabled={submitting}
            >
              {submitting ? "Creating…" : "Create League"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default CreateLeague;
