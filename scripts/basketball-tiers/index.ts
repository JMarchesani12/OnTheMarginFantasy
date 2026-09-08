#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { calculateAnalysis } from "./analyze.ts";
import { createConferenceResolver } from "./conferences.ts";
import { collectEspnTeams, loadSeasonScoreboards, parseEspnGames } from "./espn.ts";
import { normalizeGames } from "./normalize.ts";
import { DEFAULT_RANGE_DAYS, determineCompletedSeasons, parseSeasonLabels, seasonRangeFromLabel, splitDateRange } from "./seasons.ts";
import type { CliOptions, ConferenceOverrides, ParsedEspnGame, SeasonRange } from "./types.ts";
import { validateGames, validateStatLines, validateVsConferenceSymmetry } from "./validate.ts";
import { summarizeWarnings, createWarningCollector } from "./warnings.ts";
import { writeOutputs } from "./output.ts";

const TOOL_DIR = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = resolve(TOOL_DIR, "../..");

async function main(): Promise<void> {
  const options = parseCliOptions(process.argv.slice(2));
  const warnings = createWarningCollector();
  const rangesBySeason = new Map(options.seasons.map((season) => [
    season.label,
    splitDateRange(season.start, season.end, options.rangeDays),
  ]));

  const overrides = JSON.parse(await readFile(options.overridesPath, "utf8")) as ConferenceOverrides;
  const responses = await loadSeasonScoreboards(options.seasons, rangesBySeason, options.cacheDir, warnings, options.rangeDays);

  const parsedGames: ParsedEspnGame[] = [];
  for (let index = 0; index < responses.length; index += 1) {
    const season = seasonForResponseIndex(options.seasons, rangesBySeason, index);
    parsedGames.push(...parseEspnGames(responses[index], season, warnings));
  }

  const resolver = createConferenceResolver(filterOverridesToSeasons(overrides, options.seasons), collectEspnTeams(parsedGames));
  for (const warning of resolver.unmatchedOverrides) {
    warnings.add({
      code: "unmatched_override",
      message: `Override could not be matched to an ESPN team: ${warning.season} ${warning.teamName} -> ${warning.conference}`,
      season: warning.season,
    });
  }
  for (const warning of resolver.ambiguousOverrides) {
    warnings.add({
      code: "ambiguous_override",
      message: `Override matched multiple ESPN teams: ${warning.season} ${warning.teamName} -> ${warning.matchedTeamIds.join(", ")}`,
      season: warning.season,
    });
  }
  for (const conference of resolver.unknownConferenceNames) {
    warnings.add({
      code: "unknown_conference_name",
      message: `Conference name could not be normalized: ${conference}`,
    });
  }

  const normalized = normalizeGames(parsedGames, resolver, warnings);
  const validGames = validateGames(normalized.crossConferenceGames, warnings);
  const analysis = calculateAnalysis(validGames);

  const validationErrors = [
    ...validateStatLines(analysis.aggregate.values(), "aggregate"),
    ...validateVsConferenceSymmetry(analysis.vsConference),
    ...[...analysis.bySeason.entries()].flatMap(([season, stats]) => validateStatLines(stats.values(), `season ${season}`)),
    ...[...analysis.vsConferenceBySeason.entries()].flatMap(([season, stats]) => validateVsConferenceSymmetry(stats).map((error) => `season ${season}: ${error}`)),
  ];

  if (validationErrors.length > 0) {
    for (const error of validationErrors) {
      warnings.add({ code: "invalid_espn_response", message: `Calculation validation failed: ${error}` });
    }
    throw new Error(`Calculation validation failed:\n${validationErrors.join("\n")}`);
  }

  const outputFiles = await writeOutputs(
    options.outputDir,
    options.seasons.map((season) => season.label),
    validGames,
    analysis,
    warnings.all(),
  );

  printSummary(options, normalized.inspected, validGames.length, analysis.aggregate.size, outputFiles, warnings.all());
}

function parseCliOptions(args: string[]): CliOptions {
  const options: Record<string, string> = {};
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (!arg.startsWith("--")) {
      throw new Error(`Unexpected argument: ${arg}`);
    }
    const key = arg.slice(2);
    const value = args[index + 1];
    if (!value || value.startsWith("--")) {
      throw new Error(`Missing value for --${key}`);
    }
    options[key] = value;
    index += 1;
  }

  const seasons: SeasonRange[] = options.seasons
    ? parseSeasonLabels(options.seasons).map(seasonRangeFromLabel)
    : determineCompletedSeasons();

  return {
    seasons,
    rangeDays: options["range-days"] ? Number(options["range-days"]) : DEFAULT_RANGE_DAYS,
    cacheDir: resolveFromRepo(options["cache-dir"] ?? ".cache/basketball-tiers"),
    outputDir: resolveFromRepo(options["output-dir"] ?? "output/basketball-tiers"),
    overridesPath: resolveFromRepo(options["overrides"] ?? "api/conferenceOverrides.json"),
  };
}

function resolveFromRepo(path: string): string {
  return resolve(REPO_ROOT, path);
}

function seasonForResponseIndex(
  seasons: SeasonRange[],
  rangesBySeason: Map<string, unknown[]>,
  responseIndex: number,
): string {
  let cursor = 0;
  for (const season of seasons) {
    const count = rangesBySeason.get(season.label)?.length ?? 0;
    if (responseIndex < cursor + count) {
      return season.label;
    }
    cursor += count;
  }
  throw new Error(`Could not determine season for response index ${responseIndex}`);
}

function filterOverridesToSeasons(overrides: ConferenceOverrides, seasons: SeasonRange[]): ConferenceOverrides {
  const wanted = new Set<string>(seasons.map((season) => season.label));
  return Object.fromEntries(Object.entries(overrides).filter(([season]) => wanted.has(season))) as ConferenceOverrides;
}

function printSummary(
  options: CliOptions,
  gamesInspected: number,
  crossConferenceGames: number,
  conferenceCount: number,
  outputFiles: string[],
  warnings: ReturnType<typeof createWarningCollector>["all"] extends () => infer T ? T : never,
): void {
  console.log("Basketball conference analysis complete");
  console.log("");
  console.log("Seasons analyzed:");
  for (const season of options.seasons) {
    console.log(season.label);
  }
  console.log("");
  console.log(`Games inspected: ${gamesInspected.toLocaleString()}`);
  console.log(`Cross-conference games analyzed: ${crossConferenceGames.toLocaleString()}`);
  console.log(`Conferences found: ${conferenceCount}`);
  console.log("");
  console.log("Output:");
  for (const file of outputFiles) {
    console.log(file);
  }
  console.log("");

  const warningSummary = summarizeWarnings(warnings);
  if (warningSummary.size === 0) {
    console.log("Warnings: 0");
  } else {
    console.log(`Warnings: ${warnings.length}`);
    for (const [code, count] of [...warningSummary.entries()].sort()) {
      console.log(`${code}: ${count}`);
    }
  }
}

await main();
