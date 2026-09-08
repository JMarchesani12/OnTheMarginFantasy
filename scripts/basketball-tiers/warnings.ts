import type { WarningCollector, WarningItem } from "./types.ts";

export function createWarningCollector(): WarningCollector {
  const warnings: WarningItem[] = [];

  return {
    add(warning) {
      warnings.push(warning);
    },
    all() {
      return [...warnings];
    },
  };
}

export function summarizeWarnings(warnings: WarningItem[]): Map<string, number> {
  const summary = new Map<string, number>();
  for (const warning of warnings) {
    summary.set(warning.code, (summary.get(warning.code) ?? 0) + 1);
  }
  return summary;
}
