import React, { useState } from "react";
import "./CreateLeague.css";
import { useNavigate } from "react-router-dom";
import type { CreateLeaguePayload } from "../../types/league";
import { createLeague } from "../../api/leagues";
import {
  BonusesEditor,
  type BonusWithLocalId,
} from "./BonusesEditor";

// TODO: replace this with the current user's id from your AuthContext
const CURRENT_USER_ID = 1;

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

  // settings.transactions
  tradeVetoEnabled: boolean;
  tradeVetoRequiredCount: string;

  // bonuses (local-only shape)
  bonuses: BonusWithLocalId[];
}

// sport IDs: update values if your Sport table uses different ids
const SPORT_OPTIONS: { value: string; label: string }[] = [
  {
    value: "1",
    label: "NCAA Men’s College Basketball",
  },
  {
    value: "2",
    label: "College Football",
  }
];

const initialSeasonYear = new Date().getFullYear().toString();

const makeInitialState = (): CreateLeagueFormState => ({
  leagueName: "",
  sportId: "1",
  numPlayers: "1",

  status: "Pre-Draft",
  seasonYear: initialSeasonYear,

  draftDate: "",
  freeAgentDeadline: "",
  tradeDeadline: "",

  tradeVetoEnabled: true,
  tradeVetoRequiredCount: "3",

  bonuses: [],
});

const CreateLeague: React.FC = () => {
  const [form, setForm] = useState<CreateLeagueFormState>(makeInitialState);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const update = (patch: Partial<CreateLeagueFormState>) =>
    setForm((prev) => ({ ...prev, ...patch }));

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
    if (!form.numPlayers) {
      setError("Number of players is required.");
      return;
    }

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
        transactions: {
          transactionsApplyOn: "nextMonday",
          tradeVeto: {
            enabled: form.tradeVetoEnabled,
            requiredVetoCount: Number(form.tradeVetoRequiredCount || 0),
          },
        },
      },
      draftDate: toIsoOrNull(form.draftDate),
      freeAgentDeadline: toIsoOrNull(form.freeAgentDeadline),
      tradeDeadline: toIsoOrNull(form.tradeDeadline),
      commissioner: CURRENT_USER_ID, // replace with value from auth when you wire that up
      seasonYear: Number(initialSeasonYear),
    };

    try {
      setSubmitting(true);
      await createLeague(payload);
      setForm(makeInitialState());
      navigate("/");
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
                Sport
              </label>
              <select
                value={form.sportId}
                onChange={(e) => update({ sportId: e.target.value })}
              >
                {SPORT_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Dates */}
          <div className="cl-form-grid">
            <div className="cl-field-group">
              <label className="cl-field-label">
                Draft Date (You can set this later)
              </label>
              <input
                type="date"
                value={form.draftDate}
                onChange={(e) => update({ draftDate: e.target.value })}
              />
            </div>

            <div className="cl-field-group">
              <label className="cl-field-label">
                Free Agent Deadline (optional)
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
                Trade Deadline (optional)
              </label>
              <input
                type="date"
                value={form.tradeDeadline}
                onChange={(e) => update({ tradeDeadline: e.target.value })}
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
                <span>Required veto count:</span>
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
