import type { DateRange, SeasonLabel, SeasonRange } from "./types.ts";

export const DEFAULT_RANGE_DAYS = 1;

export function parseSeasonLabels(raw: string): SeasonLabel[] {
  return raw.split(",").map((part) => part.trim()).filter(Boolean) as SeasonLabel[];
}

export function determineCompletedSeasons(today = new Date()): SeasonRange[] {
  const year = today.getFullYear();
  const month = today.getMonth() + 1;
  const mostRecentEndYear = month >= 5 ? year : year - 1;
  const seasons: SeasonRange[] = [];

  for (let endYear = mostRecentEndYear - 4; endYear <= mostRecentEndYear; endYear += 1) {
    seasons.push(seasonRangeFromLabel(`${endYear - 1}-${String(endYear).slice(2)}` as SeasonLabel));
  }

  return seasons;
}

export function seasonRangeFromLabel(label: SeasonLabel): SeasonRange {
  const [startYearRaw, endYearSuffix] = label.split("-");
  const startYear = Number(startYearRaw);
  const endYear = Number(`${String(startYear).slice(0, 2)}${endYearSuffix}`);

  if (!Number.isInteger(startYear) || !Number.isInteger(endYear) || endYear !== startYear + 1) {
    throw new Error(`Invalid season label "${label}". Expected format like 2025-26.`);
  }

  return {
    label,
    start: `${startYear}-11-01`,
    end: `${endYear}-04-15`,
  };
}

export function splitDateRange(start: string, end: string, rangeDays: number): DateRange[] {
  if (!Number.isInteger(rangeDays) || rangeDays < 1) {
    throw new Error(`rangeDays must be a positive integer. Received ${rangeDays}.`);
  }

  const ranges: DateRange[] = [];
  let cursor = parseDate(start);
  const finalDate = parseDate(end);

  while (cursor.getTime() <= finalDate.getTime()) {
    const rangeStart = cursor;
    const rangeEnd = addDays(rangeStart, rangeDays - 1);
    ranges.push({
      start: formatDate(rangeStart),
      end: formatDate(rangeEnd.getTime() > finalDate.getTime() ? finalDate : rangeEnd),
    });
    cursor = addDays(rangeEnd, 1);
  }

  return ranges;
}

export function formatEspnDateRange(range: DateRange): string {
  const start = range.start.replaceAll("-", "");
  const end = range.end.replaceAll("-", "");
  return start === end ? start : `${start}-${end}`;
}

function parseDate(value: string): Date {
  return new Date(`${value}T00:00:00.000Z`);
}

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setUTCDate(next.getUTCDate() + days);
  return next;
}

function formatDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}
