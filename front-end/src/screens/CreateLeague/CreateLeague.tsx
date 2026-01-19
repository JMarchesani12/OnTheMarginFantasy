import React, { useEffect, useState } from "react";
import "./CreateLeague.css";
import { useNavigate } from "react-router-dom";
import type { CreateLeaguePayload, TimeoutAction } from "../../types/league";
import { createLeague } from "../../api/leagues";
import {
  BonusesEditor,
  type BonusWithLocalId,
} from "./BonusesEditor";
import { getSportRounds } from "../../api/draft";
import { getSports } from "../../api/sport";
import type { Sport } from "../../types/sport";
import { useCurrentUser } from "../../context/currentUserContext";

interface CreateLeagueFormState {
  leagueName: string;
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
          setSportsError(err?.message ?? "Failed to load sports");
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

    if (!form.leagueName.trim()) {
      setError("League name is required.");
      return;
    }
    if (!form.sportId) {
      setError("Sport is required.");
      return;
    }
    if (!form.numPlayers) {
      setError("Number of players is required.");
      return;
    }

    const rounds = await getSportRounds(Number(form.sportId))

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
      console.error(err);
      setError("Failed to create league. Check console/backend logs.");
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

        <form className="cl-form" onSubmit={handleSubmit}>
          {/* Basics */}
          <div className="cl-field-group">
            <label className="cl-field-label">
              League Name <span className="cl-required">*</span>
            </label>
            <input
              type="text"
              value={form.leagueName}
              onChange={(e) => update({ leagueName: e.target.value })}
            />
          </div>

          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label">
                Sport <span className="cl-required">*</span>
              </label>
              <select
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
                <p className="cl-form-error">{sportsError}</p>
              )}
            </div>
          </div>

          {/* Dates */}
          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label">
                Draft Date
              </label>
              <input
                type="date"
                value={form.draftDate}
                onChange={(e) => update({ draftDate: e.target.value })}
              />
            </div>

            <div className="cl-field-group">
              <label className="cl-field-label">
                Free Agent Deadline
              </label>
              <input
                type="date"
                value={form.freeAgentDeadline}
                onChange={(e) =>
                  update({ freeAgentDeadline: e.target.value })
                }
              />
            </div>

            <div className="cl-field-group">
              <label className="cl-field-label">
                Trade Deadline
              </label>
              <input
                type="date"
                value={form.tradeDeadline}
                onChange={(e) => update({ tradeDeadline: e.target.value })}
              />
            </div>
          </div>

          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label">Draft Timeout Action</label>
              <select
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
              <label className="cl-field-label">Grace Period (seconds)</label>
              <input
                type="number"
                min={0}
                value={form.graceSeconds}
                onChange={(e) => update({ graceSeconds: e.target.value })}
              />
            </div>
          </div>

          {/* Transactions */}
          <div className="cl-field-group cl-field-inline">
            <label className="cl-field-label">Trade Veto</label>
            <label className="cl-inline-checkbox">
              <input
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
                <span>Required veto count: <span className="cl-required">*</span></span>
                <input
                  type="number"
                  min={1}
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

          {error && <p className="cl-form-error">{error}</p>}

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
