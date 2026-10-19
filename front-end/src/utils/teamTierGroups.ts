type TierSport = string | number | null | undefined;

export function getTierLabel(tier: number | null, sport?: TierSport): string {
  if (tier == null) return "Unassigned tier";
  const name = String(sport ?? "").toLowerCase();
  const labels = name === "1" || name.includes("basketball")
    ? ["Power", "High Major", "Mid Major", "Low Major", "Play-In Bound"]
    : name === "2" || name.includes("football") ? ["FBS", "FCS"] : [];
  return labels[tier - 1] ?? `Tier ${tier}`;
}

type TierTeam = { teamName: string; tier?: number | null; conferenceName?: string | null };

export function groupTeamsByTier<T extends TierTeam>(teams: readonly T[], sport?: TierSport): {
  tier: number | null;
  label: string | null;
  teams: T[];
}[] {
  const tiers = new Map<number | null, T[]>();
  for (const team of teams) {
    const tier = team.tier ?? null;
    const group = tiers.get(tier) ?? [];
    group.push(team);
    tiers.set(tier, group);
  }
  return [...tiers.entries()]
    .sort(([a], [b]) => (a ?? Infinity) - (b ?? Infinity))
    .map(([tier, members]) => ({
      tier,
      label: tiers.size > 1 ? getTierLabel(tier, sport) : null,
      teams: [...members].sort((a, b) =>
        (a.conferenceName?.trim() || "Independent").localeCompare(b.conferenceName?.trim() || "Independent")
        || a.teamName.localeCompare(b.teamName)),
    }));
}
