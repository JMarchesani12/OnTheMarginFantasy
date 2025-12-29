import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser } from "../../context/currentUserContext";
import { updateUser } from "../../api/user";
import "./SettingsPage.css";

const SettingsPage = () => {
  const navigate = useNavigate();
  const { userId, displayName, email, loading, refreshUser } = useCurrentUser();
  const [nameInput, setNameInput] = useState(displayName ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    setNameInput(displayName ?? "");
  }, [displayName]);

  const handleSave: React.FormEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault();
    setError(null);
    setSuccess(null);

    if (!userId) {
      setError("You must be signed in to update settings.");
      return;
    }

    const nextName = nameInput.trim();
    if (!nextName) {
      setError("Display name is required.");
      return;
    }

    try {
      setSaving(true);
      await updateUser(userId, nextName);
      await refreshUser();
      setSuccess("Display name updated.");
    } catch (err: any) {
      setError(err?.message ?? "Failed to update display name.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="settings">
      <header className="settings__header">
        <div>
          <h1>Settings</h1>
          <p className="settings__subtitle">Update your profile details.</p>
        </div>
        <button
          className="settings__back"
          type="button"
          onClick={() => navigate("/leagues")}
        >
          ← Back to Leagues
        </button>
      </header>

      <section className="settings__card">
        <h2>Profile</h2>
        <form onSubmit={handleSave} className="settings__form">
          <label className="settings__field">
            <span>Display Name</span>
            <input
              type="text"
              value={nameInput}
              onChange={(event) => setNameInput(event.target.value)}
              disabled={loading || saving}
            />
          </label>

          <label className="settings__field">
            <span>Email</span>
            <input type="text" value={email ?? ""} readOnly />
          </label>

          {error && <p className="settings__error">{error}</p>}
          {success && <p className="settings__success">{success}</p>}

          <div className="settings__actions">
            <button
              className="settings__save"
              type="submit"
              disabled={saving}
            >
              {saving ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
};

export default SettingsPage;
