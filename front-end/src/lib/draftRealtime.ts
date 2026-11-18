/** Socket payloads are wakeups. Only serialized HTTP reads may publish state. */
type DraftSocket = {
  connected: boolean;
  on(event: string, handler: (...args: any[]) => void): unknown;
  off(event: string, handler: (...args: any[]) => void): unknown;
  emit(event: string, payload: {leagueId: number}): unknown;
  connect(): unknown;
  disconnect(): unknown;
};
export type DraftRealtime = { refresh(): void; join(): void; dispose(): void };

export function createDraftRealtime<T>(options: {
  socket: DraftSocket; leagueId: number;
  read(signal: AbortSignal): Promise<T>;
  apply(snapshot: T): void; clear(): void; ready(value: boolean): void;
  error(message: string | null): void; loading(value: boolean): void;
}): DraftRealtime {
  const {socket, leagueId} = options;
  let disposed = false, blocked = false, online = true, dirty = false;
  let generation = 0;
  let active: AbortController | null = null;

  function invalidate() {
    generation++;
    dirty = false;
    active?.abort();
    options.loading(false);
    options.ready(false);
  }
  function deny() {
    blocked = true;
    invalidate();
    options.clear();
    options.error('Draft access denied');
  }
  function pump() {
    if (disposed || blocked || !online || active || !dirty) return;
    dirty = false;
    const version = generation;
    const request = new AbortController();
    active = request;
    options.loading(true);
    void (async () => {
      try {
        const snapshot = await options.read(request.signal);
        if (!disposed && version === generation) {
          options.apply(snapshot);
          options.error(null);
        }
      } catch (error: any) {
        if (!disposed && version === generation) {
          if ([401,403,404].includes(error?.status)) deny();
          else {
            // Do not repeatedly retry a failed request from the same event burst.
            dirty = false;
            options.error('Failed to refresh draft. Reconnect or refresh to try again.');
          }
        }
      } finally {
        active = null;
        if (!disposed) {
          options.loading(false);
          pump();
        }
      }
    })();
  }
  function refresh() {
    if (disposed || blocked) return;
    dirty = true;
    pump();
  }
  function join() {
    if (disposed || !socket.connected) return;
    blocked = false;
    online = true;
    socket.emit('draft:join', {leagueId});
    refresh();
  }
  const handlers: Record<string, (...args: any[]) => void> = {
    connect: join,
    disconnect: () => { online = false; invalidate(); },
    'draft:snapshot': () => {
      // This event acknowledges a freshly authorized join; its embedded data is ignored.
      blocked = false;
      options.ready(true);
      refresh();
    },
    'draft:updated': refresh,
    'draft:error': deny,
    connect_error: () => { online = false; invalidate(); options.error('Failed to connect to draft'); },
  };
  options.clear();
  options.ready(false);
  for (const [event, handler] of Object.entries(handlers)) socket.on(event, handler);
  refresh(); // Initial HTTP load does not depend on the socket being available.
  if (socket.connected) join();
  else socket.connect();
  return {
    refresh, join,
    dispose() {
      if (disposed) return;
      disposed = true;
      invalidate();
      for (const [event, handler] of Object.entries(handlers)) socket.off(event, handler);
      if (socket.connected) socket.emit('draft:leave', {leagueId});
      socket.disconnect();
    },
  };
}
