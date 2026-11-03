import type { UpdateUser, User } from "../types/user";
import { apiFetch, API_BASE_URL } from "./client";


export async function getUser(
  userId: string
): Promise<User> {
  const res = await apiFetch(`${API_BASE_URL}/api/user/${userId}`);

  if (!res.ok) {
      throw new Error(`Failed to get sports: ${res.status}`);
    }
  
    const data = (await res.json()) as User;
    return data;
}

export async function getUserByUuid(
  uuid: string,
  accessToken?: string
): Promise<User | null> {
  const res = await apiFetch(`${API_BASE_URL}/api/user/byUuid/${uuid}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
  });

  if (res.status === 404) {
    return null;
  }

  if (!res.ok) {
    throw new Error(`Failed to get user: ${res.status}`);
  }

  const data = (await res.json()) as User;
  return data;
}

export async function createUser(
  displayName: string,
  accessToken?: string
): Promise<User> {
  const payload = { displayName };

  const res = await apiFetch(`${API_BASE_URL}/api/user`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    throw new Error(`Failed to create user: ${res.status}`);
  }

  const data = (await res.json()) as User;
  return data;
}

export async function updateUser(
  userId: number,
  displayName: string
): Promise<User> {

  const payload: UpdateUser = {
      displayName: displayName
  };

  const res = await apiFetch(`${API_BASE_URL}/api/user/${userId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    throw new Error(`Failed to update user: ${res.status}`);
  }

  const data = (await res.json()) as User;
  return data;
}
