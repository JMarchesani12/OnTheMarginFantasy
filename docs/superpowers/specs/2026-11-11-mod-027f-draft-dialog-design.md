# MOD-027F: draft-completion dialog focus

## Intent and selected approach

Make automatic draft completion keyboard accessible without changing draft lifecycle, summary contents or page layout. The user selected in-place dismissal: Escape and Close dismiss the summary rather than navigate to the league page. Restore focus safely in Draft Center afterward.

Use a native HTML dialog opened with showModal(), retaining the existing card/summary styles and accessible title. Native modal behavior supplies background isolation and keyboard focus containment. A custom focus trap/inert manager would duplicate browser behavior and require more lifecycle code; retaining navigation on Close would require destination-page focus policy instead of the selected in-place restoration. No dialog dependency or polyfill is introduced. Supported browser/runtime checks remain explicit rather than assuming a test double proves native behavior.

## Opening and interaction

Keep the existing completion transition trigger, including initial observation of a completed draft. Bind visible completion state to the current league/account draft scope so a previous summary cannot remain visible after context replacement. Dismissal must not reopen the same completion on unrelated renders or snapshots; a distinct draft context/completion can open its own summary.

Open through showModal() after the dialog mounts, not merely an open attribute or CSS display. Keep aria-labelledby pointing to the summary heading. Initially focus the heading with tabIndex=-1 so a long summary begins at its title; normal Tab reaches Close. Tab and Shift-Tab stay in the modal, background controls remain inert, and Escape/cancel follows the same dismissal path as Close. Do not add backdrop dismissal or automatic navigation. Existing Back to League remains available after dismissal.

A small focused dialog component or hook may own refs and showModal/close lifecycle; preserve summary rendering and avoid refactoring draft controller/state beyond scoping the completion presentation. Native dialog CSS must hide closed dialogs and preserve the current overlay/card appearance, using ::backdrop as needed. Do not override native closed-state visibility accidentally with display:flex.

## Focus restoration and lifecycle

Capture the focused element before opening. After explicit Close or Escape in the same mounted draft context, restore it only if still connected, visible, enabled and outside hidden/inert content. Automatic completion can remove/disable the previous pick/finalize control; use the visible Draft Center league heading with tabIndex=-1 as the fallback. Do not focus body, disconnected controls or disabled controls.

On route/account context replacement, unmount, access loss or a programmatic draft-view reset, close/clean up the dialog without explicitly moving focus back into the obsolete page. Disposal and effect cleanup/setup must be safe and idempotent, with no late focus work after teardown. Avoid deferred timers when synchronous post-close focus suffices. Native close/cancel events must not double-dismiss or navigate.

## Scope and verification

No API/schema/dependency changes, draft allocation/timing/realtime redesign, summary-content rewrite or global modal framework. Preserve existing uncommitted/committed user work as found, and leave this change uncommitted/undeployed.

Use actual component/hook tests with controlled DOM operations where existing tools allow: showModal called, title focused, Close/Escape share dismissal, still-usable previous focus restored, removed/disabled/hidden prior control falls back, context replacement/unmount avoids explicit stale restoration, and cleanup/setup is safe. Integration tests should confirm completion opens once, dismissal stays in Draft Center, and old scope cannot show its modal in a new league/account. Existing draft regression suites remain intact.

Run full frontend tests, production build, import graph and diff checks; obtain a fresh final code review and record exact evidence. Real browser verification should cover title announcement, Tab/Shift-Tab containment, inert background and native cancel/restoration when practical existing tooling is available. If unavailable, explicitly leave native browser/assistive-technology behavior unverified; a controlled dialog double does not establish it. No dependency installation or live services are required for the bounded implementation.
