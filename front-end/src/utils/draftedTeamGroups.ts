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

export function countConferenceDrafters(picks: readonly { memberId: number; conferenceName?: string | null }[], minimumPicks = 1) {
  const members = new Map<string, Map<number, number>>();
  for (const pick of picks) {
    const conference = pick.conferenceName?.trim() || "Independent";
    const group = members.get(conference) ?? new Map<number, number>();
    group.set(pick.memberId, (group.get(pick.memberId) ?? 0) + 1);
    members.set(conference, group);
  }
  return new Map([...members].map(([conference, group]) => [conference, [...group.values()].filter((count) => count >= minimumPicks).length]));
}

export function getFilledConferences(
  picks: readonly { memberId: number; conferenceName?: string | null }[],
  memberIds: readonly number[],
  limits: ReadonlyMap<string, number>,
) {
  const members = new Set(memberIds);
  const filled = new Set<string>();
  if (members.size === 0) return filled;
  const memberPicks = picks.filter((pick) => members.has(pick.memberId));
  for (const [conference, limit] of limits) {
    if (limit > 0 && countConferenceDrafters(memberPicks, limit).get(conference) === members.size) {
      filled.add(conference);
    }
  }
  return filled;
}
