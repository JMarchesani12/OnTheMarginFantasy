import type { UpdateUser, User } from "../types/user";

const API_BASE_URL = import.meta.env.API_BASE_URL ?? "http://127.0.0.1:5050";

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

  const res = await fetch(`${API_BASE_URL}/api/user`, {
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

  const res = await fetch(`${API_BASE_URL}/api/user/${userId}`, {
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
