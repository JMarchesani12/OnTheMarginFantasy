type DraftedPick = { overallPickNumber: number; roundNumber: number; conferenceName?: string | null };

export function groupDraftedTeams<T extends DraftedPick>(picks: readonly T[], view: "conference" | "round") {
  const groups = new Map<string | number, T[]>();
  for (const pick of [...picks].sort((a, b) => a.overallPickNumber - b.overallPickNumber)) {
    const key = view === "round" ? pick.roundNumber : pick.conferenceName?.trim() || "Independent";
    const group = groups.get(key) ?? [];
    group.push(pick);
    groups.set(key, group);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => view === "round" ? Number(a) - Number(b) : String(a).localeCompare(String(b)))
    .map(([key, members]) => ({ label: view === "round" ? `Round ${key}` : String(key), picks: members }));
}

export function countConferenceDrafters(picks: readonly { memberId: number; conferenceName?: string | null }[]) {
  const members = new Map<string, Set<number>>();
  for (const pick of picks) {
    const conference = pick.conferenceName?.trim() || "Independent";
    const group = members.get(conference) ?? new Set<number>();
    group.add(pick.memberId);
    members.set(conference, group);
  }
  return new Map([...members].map(([conference, group]) => [conference, group.size]));
}
