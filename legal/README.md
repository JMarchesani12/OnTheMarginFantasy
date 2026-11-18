# Legal drafts

Prepared November 18, 2026 for On The Margin Fantasy. These files are **review drafts**, not published policies or a legal-compliance determination:

- [Privacy Policy](PRIVACY_POLICY.md)
- [Terms of Service](TERMS_OF_SERVICE.md)

They reflect the stated operating model: developed in Iowa, free participation, no prizes, accounts for ages 13+, teenagers permitted, public browsing without an account, and possible advertising later. The app currently uses Supabase Auth/PostgreSQL, Render and Vercel. No advertising/analytics implementation was identified in the reviewed source; this does not establish every deployed provider setting or outside practice.

## Resolve before publication

1. Fill in the operator's actual legal name, monitored privacy/support email(s), effective dates and any appropriate business mailing address. Do not invent a company or publish a home address by default.
2. Confirm data visibility, all providers, email/analytics/logging settings, processing regions and actual retention periods. Do not publish an unverified “no sale/sharing/advertising” promise.
3. Establish a workable account-closure/privacy-request process, including identity checks, commissioner succession, league-history handling and backup expiration. The repository review did not identify a self-service account deletion feature; the draft does not promise one.
4. Confirm the proposed parent/guardian-permission policy for ages13–17. This is a drafting proposal, not an asserted universal legal requirement or proof that a guardian has agreed. Review minors' contract rights with counsel.
5. Implement the agreed 13+ eligibility flow before sending signup details to the authentication provider. A neutral age screen must allow an honest under-13 answer, then refuse account registration; do not invite users to retry with a different age. Plan handling of existing accounts and reports of under-13 users. Policy text alone does not implement this.
6. Implement affirmative Terms acceptance and store the accepted version/timestamp for new and, where appropriate, existing accounts. A Privacy Policy acknowledgment is not blanket consent to advertising or unrelated processing. Link the published pages from signup and a persistent site location.
7. Have counsel review the drafts for the operator, intended user locations, minors, privacy-law applicability, sports-data/branding rights and the proposed Iowa governing-law clause. Iowa development alone does not limit obligations to Iowa. No arbitration/class waiver, financial liability cap or broad indemnity was selected in this draft.

Replace bracketed notes with verified text before publishing. No signup behavior, database schema, consent records, public routes or hosting settings were changed by creating these documents. No new agreement is attributed to an existing user. Future advertising, tracking, paid participation or prizes require another review before introduction.

## Sources checked

These are drafting references, not terms incorporated into a user's agreement:

- [FTC COPPA guidance](https://www.ftc.gov/business-guidance/resources/complying-coppa-frequently-asked-questions) and [the COPPA rule page](https://www.ftc.gov/legal-library/browse/rules/childrens-online-privacy-protection-rule-coppa). The FTC FAQ flags the 2025 rule amendment and directs readers to the current rule; age policies do not replace applicable duties concerning actual under-13 collection.
- [California Attorney General: privacy policies](https://oag.ca.gov/privacy/facts/online-privacy/privacy-policy), explaining disclosure of collection, sharing and other practices under CalOPPA. This is not a finding that every California privacy law applies to this app.
- [Iowa Code 2026, Chapter 599](https://www.legis.iowa.gov/docs/code/2026/599.pdf), including minority and minors' contract rules. A teen's assent is not assumed to bind a guardian.
- [Iowa Code 2026, Chapter 715D](https://www.legis.iowa.gov/docs/code/2026/715D.pdf), including scope/thresholds and controller duties. Applicability and other users' jurisdictions require separate assessment.

Before implementing the age or consent flow, review current requirements again; these drafts do not prescribe an age-verification technology or establish eligibility by a checkbox alone.
