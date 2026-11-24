import { useRef, useState } from "react";
import { normalizeTeamSearchText } from "../utils/teamSearch";
import "./SearchableSelect.css";

type Option = { value: string; label: string };
type Props = {
  id: string;
  value: string;
  options: Option[];
  onChange: (value: string) => void;
  disabled?: boolean;
};

export default function SearchableSelect({ id, value, options, onChange, disabled }: Props) {
  const inputId = id;
  const listId = `${inputId}-options`;
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const selected = options.find(option => option.value === value);
  const matches = options.filter(option => normalizeTeamSearchText(option.label).includes(normalizeTeamSearchText(query)));
  const active = Math.min(activeIndex, Math.max(0, matches.length - 1));
  const choose = (option: Option) => {
    onChange(option.value);
    setOpen(false);
    setQuery("");
    inputRef.current?.focus();
  };

  return (
    <div className="searchable-select" onBlur={event => {
      if (!event.currentTarget.contains(event.relatedTarget)) {
        setOpen(false);
        setQuery("");
      }
    }}>
      <input
        ref={inputRef}
        id={inputId}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={open && matches.length ? `${listId}-${active}` : undefined}
        autoComplete="off"
        disabled={disabled}
        placeholder={open ? "Search conferences…" : "Select conference…"}
        value={open ? query : selected?.label ?? ""}
        onFocus={() => { setOpen(true); setQuery(""); setActiveIndex(0); }}
        onClick={() => setOpen(true)}
        onChange={event => { setQuery(event.target.value); setOpen(true); setActiveIndex(0); }}
        onKeyDown={event => {
          if (event.key === "Escape") {
            event.preventDefault();
            setOpen(false);
            setQuery("");
          } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            setOpen(true);
            setActiveIndex(index => Math.max(0, Math.min(matches.length - 1, index + (event.key === "ArrowDown" ? 1 : -1))));
          } else if (event.key === "Enter" && open) {
            event.preventDefault();
            if (matches[active]) choose(matches[active]);
          }
        }}
      />
      {open && <div className="searchable-select__menu">
        <ul id={listId} role="listbox" aria-label="Conferences">
          {matches.map((option, index) => (
            <li key={option.value} id={`${listId}-${index}`} role="option"
              aria-selected={option.value === value}
              className={index === active ? "is-active" : undefined}
              onMouseDown={event => event.preventDefault()}
              onMouseEnter={() => setActiveIndex(index)}
              onClick={() => choose(option)}>{option.label}</li>
          ))}
        </ul>
        {matches.length === 0 && <p role="status">No conferences match.</p>}
      </div>}
    </div>
  );
}
