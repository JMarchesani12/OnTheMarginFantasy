export type TierDisplayTone = "neutral" | "red" | "green";

export function getOpponentTierDisplayTone({
  sportId,
  ownedTeamTier,
  opponentTeamTier,
}: {
  sportId: number | null | undefined;
  ownedTeamTier: number | null | undefined;
  opponentTeamTier: number | null | undefined;
}): TierDisplayTone {
  if (ownedTeamTier == null || opponentTeamTier == null) {
    return "neutral";
  }

  const tierGap = Math.abs(ownedTeamTier - opponentTeamTier);
  const adjustmentThreshold = sportId === 1 ? 2 : 1;

  if (tierGap < adjustmentThreshold) {
    return "neutral";
  }

  if (opponentTeamTier > ownedTeamTier) {
    return "red";
  }

  if (opponentTeamTier < ownedTeamTier) {
    return "green";
  }

  return "neutral";
}
