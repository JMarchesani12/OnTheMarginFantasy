# Legal pages and feedback implementation plan

**Goal:** Add public Privacy and Terms pages, a site footer, and categorized feedback.
**Architecture:** Existing React Router routes; shared footer outside route content; email-based feedback without a new data store. Policy drafts remain visibly marked until owner review. Contact and copyright identity live in one configuration module.
**Tech stack:** React, TypeScript, CSS, Vite.

- [x] Create shared site contact configuration, public policy drafts, and responsive styles.
- [x] Add a feedback form that prepares email without claiming a report was sent; include copy fallback and explicit page context.
- [x] Add footer links/menu across routes and policy links at signup.
- [x] Verify build, changed-component lint, feedback formatting, and review all configured contact links.

Contact confirmed: jmarchesani.onthemarginfantasy@gmail.com. User confirmed the registered LLC name: On The Margin Fantasy LLC. Shared site configuration uses the LLC for service operator and copyright owner. Privacy and Terms remain visibly marked drafts pending confirmation of retention, full provider details, and final legal review. Build, changed new-component lint, three feedback-formatting tests, and whitespace checks pass. No deployment or messages sent.
