import { useCurrentUser } from "../../context/currentUserContext";

/** Profile setup feedback only; discovery/route access remains owned by each page. */
export default function ProfileStatus() {
  const { authUserId, loading, error, refreshUser } = useCurrentUser();
  if (!authUserId) return null;
  if (loading) return <p role="status">Loading your profile…</p>;
  if (!error) return null;
  return <div className="profile-status">
    <p role="alert">{error}</p>
    <button type="button" onClick={() => refreshUser().catch(() => {})}>Retry profile</button>
  </div>;
}
