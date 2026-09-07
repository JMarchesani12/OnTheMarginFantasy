const ABBREVIATIONS: Record<string, string> = {
  st: "state",
  univ: "university",
};

export function normalizeTeamSearchText(value: string): string {
  return value
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((token) => ABBREVIATIONS[token] ?? token)
    .join(" ");
}

export function teamSearchMatches(candidate: string, query: string): boolean {
  const normalizedCandidate = normalizeTeamSearchText(candidate);
  const normalizedQuery = normalizeTeamSearchText(query);

  if (!normalizedQuery) return true;
  if (normalizedCandidate.includes(normalizedQuery)) return true;

  const candidateTokens = normalizedCandidate.split(" ");
  const queryTokens = normalizedQuery.split(" ");
  return queryTokens.every((queryToken) =>
    candidateTokens.some((candidateToken) => candidateToken.startsWith(queryToken))
  );
}

export function rankTeamSearchMatch(candidate: string, query: string): number {
  const normalizedCandidate = normalizeTeamSearchText(candidate);
  const normalizedQuery = normalizeTeamSearchText(query);

  if (!normalizedQuery) return 0;
  if (normalizedCandidate === normalizedQuery) return 100;
  if (normalizedCandidate.startsWith(normalizedQuery)) return 90;
  if (normalizedCandidate.includes(normalizedQuery)) return 75;
  return teamSearchMatches(candidate, query) ? 50 : 0;
}
