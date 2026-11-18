import { safeResponse, safeJson, READ_ERROR, WRITE_UNCERTAIN } from "./safeError";
import type { UpdateUser, User } from "../types/user";
import { apiFetch, API_BASE_URL } from "./client";

export async function getUser(
  userId: string
): Promise<User> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/user/${userId}`), READ_ERROR);

  
    const data = (await safeJson(res, READ_ERROR)) as User;
    return data;
}

export async function getUserByUuid(
  uuid: string,
  accessToken?: string,
  signal?: AbortSignal
): Promise<User | null> {
  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/user/byUuid/${uuid}`, {
    signal,
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  }), READ_ERROR, true);

  if (res.status === 404) {
    return null;
  }

  const data: unknown = await safeJson(res, READ_ERROR);
  if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("Invalid profile response");
  return data as User;
}

export async function createUser(
  displayName: string,
  accessToken?: string,
  signal?: AbortSignal
): Promise<User> {
  const payload = { displayName };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/user`, {
    signal,
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload)
  }), WRITE_UNCERTAIN);

  const data = (await safeJson(res, WRITE_UNCERTAIN)) as User;
  return data;
}

export async function updateUser(
  userId: number,
  displayName: string
): Promise<User> {

  const payload: UpdateUser = {
      displayName: displayName
  };

  const res = await safeResponse(apiFetch(`${API_BASE_URL}/api/user/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  }), WRITE_UNCERTAIN);

  const data = (await safeJson(res, WRITE_UNCERTAIN)) as User;
  return data;
}
