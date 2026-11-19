import { useEffect, useState } from "react";
import { getTeamSearchCatalog } from "../api/teamSearch";
import { buildTeamSearchIndex } from "../utils/teamSearch";

const empty = buildTeamSearchIndex([]);

export function useTeamSearchCatalog() {
  const [index, setIndex] = useState(empty);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let cancelled = false;
    setError(false);
    getTeamSearchCatalog(revision > 0).then(data => {
      if (!cancelled) setIndex(buildTeamSearchIndex(data.teams));
    }).catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [revision]);
  return { index, error, retry: () => setRevision(value => value + 1) };
}
