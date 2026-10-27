export type TierDisplayTone = "neutral" | "red" | "green";

export function getOpponentTierDisplayTone(
  adjustment?: {
    applied: boolean;
    tone: TierDisplayTone;
    tierGap?: number | null;
    minimumTierGap?: number;
  } | null,
  ownedTier?: number | null,
  opponentTier?: number | null,
): TierDisplayTone {
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
