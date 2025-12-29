import React from "react";

const makeId = () => Math.random().toString(36).slice(2);

export interface BonusPlacementRow {
  id: string;      // local ID for React
  key: string;     // JSON key, e.g. "first", "secondLast"
  label: string;   // label to show, e.g. "First"
  points: string;  // string in form, convert to number on submit
}

export interface BonusWithLocalId {
  id: string;                // local ID for React
  bonusKey: string;          // e.g. "conferenceChampion"
  label: string;             // "Conference Champs"
  hint: string;
  placements: BonusPlacementRow[];
}

interface BonusesEditorProps {
  value: BonusWithLocalId[];
  onChange: (next: BonusWithLocalId[]) => void;
}

export interface BonusTemplatePlacement {
  key: string;
  label: string;
  defaultPoints: number;
}

export interface BonusTemplate {
  bonusKey: string;
  label: string;
  hint: string;
  placements: BonusTemplatePlacement[];
}

export const BONUS_TEMPLATES: BonusTemplate[] = [
  {
    bonusKey: "conferenceChampion",
    label: "Conference Champs",
    hint: "Bonus points for every team you draft that is in the top 3 in their conference at the end of the season",
    placements: [
      { key: "first", label: "First", defaultPoints: 1.5 },
      { key: "second", label: "Second", defaultPoints: 1 },
      { key: "third", label: "Third", defaultPoints: 0.5 },
    ],
  },
  {
    bonusKey: "conferenceBottom",
    label: "Conference Losers",
    hint: "Points lost for every team you draft that is in the bottom 3 in their conference at the end of the season",
    placements: [
      { key: "last", label: "Last", defaultPoints: -1.5 },
      { key: "secondLast", label: "Second last", defaultPoints: -1 },
      { key: "thirdLast", label: "Third last", defaultPoints: -0.5 },
    ],
  },
  {
    bonusKey: "farthestInPlayoffs",
    label: "Team that went farthest in playoffs",
    hint: "Bonus points awarded if a team you drafted gets the farthers in the playoffs",
    placements: [
      { key: "farthest", label: "Farthest", defaultPoints: 3 },
    ],
  },
];

export const BonusesEditor: React.FC<BonusesEditorProps> = ({
  value,
  onChange,
}) => {
  const selectedKeys = new Set(value.map((b) => b.bonusKey));
  const availableTemplates = BONUS_TEMPLATES.filter(
    (tpl) => !selectedKeys.has(tpl.bonusKey)
  );

  const addBonusFromTemplate = (template: BonusTemplate) => {
    const newBonus: BonusWithLocalId = {
      id: makeId(),
      bonusKey: template.bonusKey,
      label: template.label,
      hint: template.hint,
      placements: template.placements.map((p) => ({
        id: makeId(),
        key: p.key,
        label: p.label,
        points: p.defaultPoints.toString(),
      })),
    };
    onChange([...value, newBonus]);
  };

  const handleAdd: React.ChangeEventHandler<HTMLSelectElement> = (e) => {
    const bonusKey = e.target.value;
    if (!bonusKey) return;
    const template = BONUS_TEMPLATES.find((t) => t.bonusKey === bonusKey);
    if (!template) return;
    addBonusFromTemplate(template);
    e.target.value = "";
  };

  const updatePlacementPoints = (
    bonusId: string,
    placementId: string,
    points: string
  ) => {
    onChange(
      value.map((b) =>
        b.id !== bonusId
          ? b
          : {
              ...b,
              placements: b.placements.map((p) =>
                p.id === placementId ? { ...p, points } : p
              ),
            }
      )
    );
  };

  const removeBonus = (bonusId: string) => {
    onChange(value.filter((b) => b.id !== bonusId));
  };

  return (
    <div className="cl-field-group">
      <label className="cl-field-label">
        Bonuses / Penalties
      </label>

      {availableTemplates.length > 0 && (
        <div className="cl-bonus-add-row">
          <select defaultValue="" onChange={handleAdd}>
            <option value="" disabled>
              Add bonus / penalty…
            </option>
            {availableTemplates.map((tpl) => (
              <option key={tpl.bonusKey} value={tpl.bonusKey}>
                {tpl.label}
              </option>
            ))}
          </select>
        </div>
      )}

      {value.map((bonus) => (
        <div key={bonus.id} className="cl-bonus-card">
          <div className="cl-bonus-header">
            <div className="cl-bonus-title">
              {bonus.label}

              {bonus.hint && (
                <span className="cl-tooltip">
                  ?
                  <span className="cl-tooltip-content">
                    {bonus.hint}
                  </span>
                </span>
              )}
            </div>
            <button
              type="button"
              className="cl-bonus-remove"
              onClick={() => removeBonus(bonus.id)}
            >
              Remove
            </button>
          </div>

          <div className="cl-bonus-placements">
            {bonus.placements.map((p) => (
              <div key={p.id} className="cl-placement-row">
                <div className="cl-placement-label">{p.label}</div>
                <input
                  type="number"
                  step="0.5"
                  value={p.points}
                  onChange={(e) =>
                    updatePlacementPoints(
                      bonus.id,
                      p.id,
                      e.target.value
                    )
                  }
                />
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};
