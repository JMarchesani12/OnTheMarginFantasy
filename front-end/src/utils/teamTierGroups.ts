type TierTeam = { teamName: string; tier?: number | null };

export function groupTeamsByTier<T extends TierTeam>(teams: readonly T[]): {
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
      label: tiers.size > 1 ? (tier == null ? "Unassigned tier" : `Tier ${tier}`) : null,
      teams: [...members].sort((a, b) => a.teamName.localeCompare(b.teamName)),
    }));
}
