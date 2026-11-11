import { safeErrorMessage, WRITE_UNCERTAIN } from "../../api/safeError";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useCurrentUser } from "../../context/currentUserContext";
import ProfileStatus from "../../components/Profile/ProfileStatus";
import { useRequestScope } from "../../hooks/useRequestScope";
import { updateUser } from "../../api/user";
import "./SettingsPage.css";

const SettingsPage = () => {
  const profile = useCurrentUser();
  return <SettingsForm key={profile.identityKey} profile={profile} />;
};

const SettingsForm = ({ profile }: { profile: ReturnType<typeof useCurrentUser> }) => {
  const navigate = useNavigate();
  const { userId, displayName, email, loading, refreshUser, isCurrentIdentity } = profile;
  const scope = useRequestScope(isCurrentIdentity);
  const [nameInput, setNameInput] = useState(displayName ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && userId && displayName !== null) setNameInput(displayName);
  }, [displayName, loading, userId]);

  const handleSave: React.FormEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault();
    if (!scope.isCurrent() || loading || saving) return;
    const current = scope.capture();
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

    let saved = false;
    try {
      setSaving(true);
      await updateUser(userId, nextName);
      saved = true;
      if (!current()) return;
      await refreshUser();
      if (!current()) return;
      setSuccess("Display name updated.");
    } catch (err: any) {
      if (current()) setError(saved
        ? "Display name saved, but your profile could not be refreshed. Retry loading your profile."
        : safeErrorMessage(err, WRITE_UNCERTAIN));
    } finally {
      if (current()) setSaving(false);
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
        <ProfileStatus />
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
              disabled={saving || loading || !userId}
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
