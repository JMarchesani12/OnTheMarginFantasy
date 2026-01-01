export const LEAGUE_TIME_ZONE = "America/Chicago";
const localTimeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: "numeric",
  minute: "2-digit",
});

export type LocalDateParts = {
  year: number;
  month: number;
  day: number;
};

export type DateHeader = {
  key: string;
  label: string;
};

export function getLocalYMD(dateStr: string): LocalDateParts {
  const d = new Date(dateStr);

  const fmt = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });

  const parts = fmt.formatToParts(d);
  const year = Number(parts.find((p) => p.type === "year")?.value);
  const month = Number(parts.find((p) => p.type === "month")?.value);
  const day = Number(parts.find((p) => p.type === "day")?.value);

  return { year, month, day };
}

export function getWeekYMD(dateStr: string): LocalDateParts {
  const d = new Date(dateStr);
  return {
    year: d.getUTCFullYear(),
    month: d.getUTCMonth() + 1,
    day: d.getUTCDate(),
  };
}

export function buildDateHeadersFromWeek(
  startDateStr: string,
  endDateStr: string
): DateHeader[] {
  const startParts = getWeekYMD(startDateStr);
  const endParts = getWeekYMD(endDateStr);

  const start = new Date(startParts.year, startParts.month - 1, startParts.day);
  const end = new Date(endParts.year, endParts.month - 1, endParts.day);

  const headers: DateHeader[] = [];
  const cursor = new Date(start);

  const labelFmt = new Intl.DateTimeFormat(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
  });

  while (cursor <= end) {
    const year = cursor.getFullYear();
    const month = cursor.getMonth() + 1;
    const day = cursor.getDate();

    const key =
      year +
      "-" +
      String(month).padStart(2, "0") +
      "-" +
      String(day).padStart(2, "0");

    const label = labelFmt.format(cursor);

    headers.push({ key, label });
    cursor.setDate(cursor.getDate() + 1);
  }

  return headers;
}

export function getLocalDateKeyForGame(dateStr: string): string {
  const { year, month, day } = getLocalYMD(dateStr);
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

export function formatLocalTime(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  if (Number.isNaN(date.getTime())) return null;
  return localTimeFormatter.format(date);
}
