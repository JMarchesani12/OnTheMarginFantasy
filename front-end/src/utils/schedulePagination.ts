import type { DateHeader } from "./scheduleTable";

export function buildSchedulePages(headers: DateHeader[]): DateHeader[][] {
  // Keep a single scoring week intact, including football's Tuesday–Monday window.
  // Only longer periods need calendar-week pagination.
  if (headers.length <= 7) return headers.length ? [headers] : [];

  const pages: DateHeader[][] = [];
  for (const header of headers) {
    const isMonday = new Date(`${header.key}T00:00:00Z`).getUTCDay() === 1;
    if (!pages.length || isMonday || pages[pages.length - 1].length === 7) {
      pages.push([]);
    }
    pages[pages.length - 1].push(header);
  }
  return pages;
}

export function getSchedulePageIndex(
  pages: DateHeader[][], requested: number | null, today: string,
): number {
  if (requested === -1) return Math.max(0, pages.length - 1);
  if (requested != null) return Math.max(0, Math.min(requested, pages.length - 1));
  const current = pages.findIndex(page => page[0].key <= today && page[page.length - 1].key >= today);
  return Math.max(0, current);
}

export function moveSchedulePage(
  weekNumber: number, pageIndex: number, pageCount: number,
  direction: -1 | 1, minWeek: number, maxWeek?: number,
): { weekNumber: number; pageIndex: number } {
  const nextPage = pageIndex + direction;
  if (nextPage >= 0 && nextPage < pageCount) return { weekNumber, pageIndex: nextPage };
  const nextWeek = weekNumber + direction;
  if (nextWeek < minWeek || (maxWeek != null && nextWeek > maxWeek)) {
    return { weekNumber, pageIndex };
  }
  return { weekNumber: nextWeek, pageIndex: direction === -1 ? -1 : 0 };
}
