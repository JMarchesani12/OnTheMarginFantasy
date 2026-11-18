import { useEffect, useMemo, useRef } from "react";

const alwaysCurrent = () => true;

/** Guard async completions by mounted context and, optionally, latest resource request. */
export function useRequestScope(parentIsCurrent: () => boolean = alwaysCurrent) {
  const parent = useRef(parentIsCurrent);
  parent.current = parentIsCurrent;
  const lifecycle = useRef({ active: true, generation: 0 });
  const requests = useRef(new Map<string, number>());
  const controllers = useRef(new Map<string, AbortController>());
  useEffect(() => {
    lifecycle.current.active = true;
    return () => {
      lifecycle.current.active = false;
      lifecycle.current.generation++;
      controllers.current.forEach(controller => controller.abort());
      controllers.current.clear();
    };
  }, []);
  return useMemo(() => ({
    isCurrent: () => lifecycle.current.active && parent.current(),
    cancel(channel: string) { controllers.current.get(channel)?.abort(); },
    capture(channel?: string) {
      const generation = lifecycle.current.generation;
      const request = channel ? (requests.current.get(channel) ?? 0) + 1 : 0;
      const controller = channel ? new AbortController() : undefined;
      if (channel) {
        requests.current.set(channel, request);
        controllers.current.get(channel)?.abort();
        controllers.current.set(channel, controller!);
      }
      return Object.assign(() => !controller?.signal.aborted && lifecycle.current.active && lifecycle.current.generation === generation && parent.current() &&
        (!channel || requests.current.get(channel) === request), { signal: controller?.signal, cancel: () => controller?.abort() });
    },
  }), []);
}
