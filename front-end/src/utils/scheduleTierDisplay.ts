export type TierDisplayTone = "neutral" | "red" | "green";

export function getOpponentTierDisplayTone(
  adjustment?: { applied: boolean; tone: TierDisplayTone } | null,
): TierDisplayTone {
  return adjustment?.applied ? adjustment.tone : "neutral";
}
