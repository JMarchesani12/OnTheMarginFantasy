import type { UpdateUser, User } from "../types/user";
import { apiFetch, API_BASE_URL } from "./client";

export async function createUser(
  uuid: string | undefined,
  email: string,
  displayName: string
): Promise<User> {

const payload = {
    "uuid": uuid,
    "email": email,
    "displayName": displayName
};

  const res = await apiFetch(`${API_BASE_URL}/api/user`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
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
