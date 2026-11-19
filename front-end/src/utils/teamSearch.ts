import type { TeamSearchCatalogEntry } from "../types/teamSearch.ts";

export const STRONG_TEAM_SEARCH_MATCH = 50;
const MAX_QUERY_LENGTH = 120;
const MAX_QUERY_TOKENS = 8;

export function normalizeTeamSearchText(value: string): string {
  return value.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase()
    .replace(/&/g, " and ").replace(/['’.]/g, "").replace(/[^a-z0-9]+/g, " ")
    .trim().split(/\s+/).filter(Boolean)
    .map(token => token === "univ" ? "university" : token).join(" ");
}

function variants(value: string): string[] {
  const normalized = normalizeTeamSearchText(value);
  if (!normalized) return [];
  const result = new Set([normalized]);
  const tokens = normalized.split(" ");
  if (tokens.includes("st")) {
    for (const replacement of ["state", "saint"])
      result.add(tokens.map(token => token === "st" ? replacement : token).join(" "));
  }
  for (const word of ["state", "saint"])
    if (tokens.includes(word)) result.add(tokens.map(token => token === word ? "st" : token).join(" "));
  const withoutInstitution = normalized.replace(/^university of | university$/g, "").trim();
  if (withoutInstitution) result.add(withoutInstitution);
  if (tokens.length > 1 && tokens.every(token => token.length === 1)) result.add(tokens.join(""));
  return [...result].sort();
}

export type TeamSearchCandidate = string | { teamName: string; teamId?: number | null };
export type TeamSearchIndex = { aliasesFor: (candidate: TeamSearchCandidate) => readonly string[] };

export function buildTeamSearchIndex(teams: readonly TeamSearchCatalogEntry[]): TeamSearchIndex {
  const byId = new Map(teams.map(team => [team.teamId, team.aliases]));
  const byName = new Map<string, { schoolId: number; aliases: string[] } | null>();
  for (const team of teams) {
    const name = normalizeTeamSearchText(team.teamName);
    const previous = byName.get(name);
    if (previous === null || (previous && previous.schoolId !== team.schoolId)) byName.set(name, null);
    else byName.set(name, { schoolId: team.schoolId, aliases: team.aliases });
  }
  return { aliasesFor(candidate) {
    if (typeof candidate !== "string" && candidate.teamId != null) return byId.get(candidate.teamId) ?? [];
    const name = typeof candidate === "string" ? candidate : candidate.teamName;
    return byName.get(normalizeTeamSearchText(name))?.aliases ?? [];
  } };
}

const nameCache = new Map<string, { originals: string[]; aliases: string[] }>();
function candidateNames(candidate: string, suppliedAliases: readonly string[]) {
  const key = JSON.stringify([candidate, suppliedAliases]);
  const cached = nameCache.get(key);
  if (cached) return cached;
  const originals = variants(candidate);
  const originalSet = new Set(originals);
  const aliases = [...new Set(suppliedAliases.flatMap(variants))].filter(name => !originalSet.has(name)).sort();
  const result = { originals, aliases };
  if (nameCache.size >= 4096) nameCache.delete(nameCache.keys().next().value!);
  nameCache.set(key, result);
  return result;
}

function allTokensMatch(query: string[], candidate: string[], predicate: (left: string, right: string) => boolean): boolean {
  const assigned = new Map<number, number>();
  const assign = (queryIndex: number, seen: Set<number>): boolean => {
    for (let index = 0; index < candidate.length; index++) {
      if (seen.has(index) || !predicate(query[queryIndex], candidate[index])) continue;
      seen.add(index);
      if (!assigned.has(index) || assign(assigned.get(index)!, seen)) {
        assigned.set(index, queryIndex);
        return true;
      }
    }
    return false;
  };
  return query.every((_token, index) => assign(index, new Set()));
}

function prefix(query: string, candidate: string) {
  return candidate.startsWith(query) && !(candidate === "university" && query !== candidate);
}

function lexicalRank(candidate: string, query: string): number {
  if (candidate === query) return 100;
  if (query.length <= 3) candidate = candidate.split(" ").filter(token => token !== "university").join(" ");
  if (candidate.startsWith(query)) return 90;
  if (candidate.includes(query)) return 75;
  return allTokensMatch(query.split(" "), candidate.split(" "), prefix) ? 50 : 0;
}

function editDistance(left: string, right: string): number {
  let previousPrevious: number[] | undefined;
  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  for (let i = 1; i <= left.length; i++) {
    const current = [i];
    for (let j = 1; j <= right.length; j++) {
      let distance = Math.min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + Number(left[i - 1] !== right[j - 1]));
      if (i > 1 && j > 1 && left[i - 1] === right[j - 2] && left[i - 2] === right[j - 1])
        distance = Math.min(distance, previousPrevious![j - 2] + 1);
      current.push(distance);
    }
    previousPrevious = previous;
    previous = current;
  }
  return previous[right.length];
}

function typoWordMatches(query: string, candidate: string) {
  if (prefix(query, candidate)) return true;
  if (Math.min(query.length, candidate.length) < 4 || Math.max(query.length, candidate.length) > 32) return false;
  const allowance = Math.min(query.length, candidate.length) >= 8 ? 2 : 1;
  return Math.abs(query.length - candidate.length) <= allowance && editDistance(query, candidate) <= allowance;
}

export function rankTeamSearchMatch(candidate: TeamSearchCandidate, query: string, suppliedAliases: readonly string[] = []): number {
  if (query.length > MAX_QUERY_LENGTH) return 0;
  const normalizedQuery = normalizeTeamSearchText(query);
  if (!normalizedQuery || normalizedQuery.split(" ").length > MAX_QUERY_TOKENS) return 0;
  const queries = variants(query);
  const { originals, aliases } = candidateNames(typeof candidate === "string" ? candidate : candidate.teamName, suppliedAliases);
  let score = 0;
  for (const name of originals) for (const term of queries) score = Math.max(score, lexicalRank(name, term));
  const aliasRanks: Record<number, number> = { 100: 98, 90: 88, 75: 70, 50: 50, 0: 0 };
  for (const name of aliases) for (const term of queries) score = Math.max(score, aliasRanks[lexicalRank(name, term)]);
  if (score) return score;
  for (const name of [...originals, ...aliases]) for (const term of queries)
    if (allTokensMatch(term.split(" "), name.split(" "), typoWordMatches)) return 30;
  return 0;
}

export function teamSearchMatches(candidate: TeamSearchCandidate, query: string, aliases: readonly string[] = []): boolean {
  return !normalizeTeamSearchText(query) || rankTeamSearchMatch(candidate, query, aliases) > 0;
}

export function filterTeamSearch<T>(items: readonly T[], query: string, names: (item: T) => TeamSearchCandidate | readonly TeamSearchCandidate[], searchIndex?: TeamSearchIndex): T[] {
  if (!normalizeTeamSearchText(query)) return [...items];
  const ranked = items.map((item, index) => {
    const values = names(item);
    const score = Math.max(0, ...(Array.isArray(values) ? values : [values]).map(name => rankTeamSearchMatch(name, query, searchIndex?.aliasesFor(name) ?? [])));
    return { item, index, score };
  });
  const threshold = ranked.some(row => row.score >= STRONG_TEAM_SEARCH_MATCH) ? STRONG_TEAM_SEARCH_MATCH : 1;
  return ranked.filter(row => row.score >= threshold).sort((a, b) => b.score - a.score || a.index - b.index).map(row => row.item);
}
