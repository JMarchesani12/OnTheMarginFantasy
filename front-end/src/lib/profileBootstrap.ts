import { createUser, getUserByUuid } from "../api/user";
import type { User } from "../types/user";
import { safeLocalStorage } from "../utils/safeStorage";

const PENDING_SIGNUP = "otm:pending-user-create";
export class ProfileSetupError extends Error {}

type Options = {
  subject: string;
  accessToken: string;
  email?: string;
  username?: unknown;
  signal: AbortSignal;
  isCurrent: () => boolean;
};
const nonempty = (value: unknown) => typeof value === "string" ? value.trim() : "";

/** One bounded, captured-credential attempt. Cancellation is not server rollback. */
export async function loadApplicationProfile(options: Options): Promise<User> {
  const { subject, accessToken, email, username, signal, isCurrent } = options;
  const current = () => {
    signal.throwIfAborted();
    if (!isCurrent()) throw new Error("Profile request superseded.");
  };
  current();
  const raw = safeLocalStorage.getItem(PENDING_SIGNUP);
  let hint: { email?: unknown; displayName?: unknown } | null = null;
  if (raw !== null) {
    try {
      const parsed: unknown = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error();
      hint = parsed;
    } catch {
      current();
      if (safeLocalStorage.getItem(PENDING_SIGNUP) === raw) safeLocalStorage.removeItem(PENDING_SIGNUP);
    }
  }
  const matchesHint = !!nonempty(email) && !!nonempty(hint?.email) &&
    nonempty(email).toLowerCase() === nonempty(hint?.email).toLowerCase();
  let profile = await getUserByUuid(subject, accessToken, signal);
  current();
  if (profile === null) {
    if (!nonempty(email)) throw new ProfileSetupError("A verified email is required to set up your profile.");
    const name = (matchesHint ? nonempty(hint?.displayName) : "") || nonempty(username) || nonempty(email).split("@")[0];
    try {
      profile = await createUser(name, accessToken, signal);
    } catch (error) {
      current();
      if ((error as { status?: number } | null)?.status !== 409) throw error;
      profile = await getUserByUuid(subject, accessToken, signal);
    }
    current();
  }
  if (!profile || profile.uuid !== subject || !Number.isSafeInteger(profile.id) || profile.id <= 0) {
    throw new ProfileSetupError("Profile response did not match this session. Please retry.");
  }
  current();
  if (matchesHint && safeLocalStorage.getItem(PENDING_SIGNUP) === raw) safeLocalStorage.removeItem(PENDING_SIGNUP);
  return profile;
}
