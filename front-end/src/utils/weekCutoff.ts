type WeekCutoffInput = {
  currentWeekNumber: number | null | undefined;
  currentWeekStartDate: string | Date | null | undefined;
  cutoffHourLocal?: number;
  timeZone?: string | null;
};

const DEFAULT_CUTOFF_HOUR_LOCAL = 2;

const getTimeZoneOffset = (date: Date, timeZone: string) => {
  const dtf = new Intl.DateTimeFormat("en-US", {
    timeZone,
    hour12: false,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const parts = dtf.formatToParts(date);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const asUtc = Date.UTC(
    Number(values.year),
    Number(values.month) - 1,
    Number(values.day),
    Number(values.hour),
    Number(values.minute),
    Number(values.second)
  );
  return asUtc - date.getTime();
};

const toUtcFromTimeZone = (
  year: number,
  month: number,
  day: number,
  hour: number,
  minute: number,
  second: number,
  timeZone: string
) => {
  const utcGuess = Date.UTC(year, month - 1, day, hour, minute, second);
  const offset = getTimeZoneOffset(new Date(utcGuess), timeZone);
  return utcGuess - offset;
};

export const getEffectiveWeekNumber = ({
  currentWeekNumber,
  currentWeekStartDate,
  cutoffHourLocal = DEFAULT_CUTOFF_HOUR_LOCAL,
  timeZone,
}: WeekCutoffInput): number | null => {
  if (!currentWeekNumber || currentWeekNumber < 1) {
    return currentWeekNumber ?? null;
  }

  if (!currentWeekStartDate) {
    return currentWeekNumber;
  }

  const startDate =
    typeof currentWeekStartDate === "string"
      ? new Date(currentWeekStartDate)
      : currentWeekStartDate;

  if (Number.isNaN(startDate.getTime())) {
    return currentWeekNumber;
  }

  let cutoffMs = startDate.getTime() + cutoffHourLocal * 60 * 60 * 1000;
  if (timeZone) {
    const dtf = new Intl.DateTimeFormat("en-US", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
    const parts = dtf.formatToParts(startDate);
    const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    const year = Number(values.year);
    const month = Number(values.month);
    const day = Number(values.day);
    if (
      !Number.isNaN(year) &&
      !Number.isNaN(month) &&
      !Number.isNaN(day)
    ) {
      cutoffMs = toUtcFromTimeZone(
        year,
        month,
        day,
        cutoffHourLocal,
        0,
        0,
        timeZone
      );
    }
  }
  if (Date.now() < cutoffMs && currentWeekNumber > 1) {
    return currentWeekNumber - 1;
  }

  return currentWeekNumber;
};
