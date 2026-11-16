# API migration baseline

These files preserve the API implementations from commit `30a1675b96c38a30f5adb00536c436962dd2f388`
(before the safe-error migration). `allApiErrors.test.ts` compares their successful
transport arguments and response shapes with the current implementations.

Keep this baseline fixed when changing the current APIs. These committed fixtures
allow the comparison to run in shallow checkouts and source archives without Git history.
