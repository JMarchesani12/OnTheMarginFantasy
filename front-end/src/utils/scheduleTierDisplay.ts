export type TierDisplayTone = "neutral" | "red" | "green" | "purple";

export function getMatchupHoverExplanation(
  tone: TierDisplayTone,
  adjustment?: { tierGap: number | null; minimumTierGap: number; explanation?: string | null },
): string | null {
  if (tone === "purple") return "You own both teams. This game contributes 0 points overall.";
  if (tone === "neutral") return null;
  const eligible = adjustment?.tierGap != null && adjustment.tierGap >= adjustment.minimumTierGap;
  const matchup = tone === "red" ? "Lower-tier opponent." : "Higher-tier opponent.";
  const scoring = eligible
    ? tone === "red"
      ? "Winning margins are halved; losing margins are doubled."
      : "Winning margins are doubled; losing margins are halved."
    : "No tier multiplier applies to this matchup.";
  return [matchup, scoring, adjustment?.explanation].filter(Boolean).join(" ");
}

export function getOpponentTierDisplayTone(
  adjustment?: {
    applied: boolean;
    tone: TierDisplayTone;
    tierGap?: number | null;
    minimumTierGap?: number;
  } | null,
  ownedTier?: number | null,
  opponentTier?: number | null,
  opponentUnranked = false,
  bothOwned = false,
): TierDisplayTone {
  if (bothOwned) return "purple";
  if (opponentUnranked) return "red";
  if (adjustment?.applied) return adjustment.tone;
  // Zero-margin games have no scoring adjustment yet. The backend's gap
  // still identifies eligible matchups; null excludes double-owned games.
  if (
    adjustment?.tierGap != null &&
    adjustment.minimumTierGap != null &&
    adjustment.tierGap >= adjustment.minimumTierGap &&
    ownedTier != null && opponentTier != null && ownedTier !== opponentTier
  ) {
    return ownedTier < opponentTier ? "red" : "green";
  }
  return "neutral";
}
