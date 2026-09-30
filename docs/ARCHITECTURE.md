# Architecture
Django renders HTML forms with CSRF. Sessions are database-backed; the client receives only a secure HttpOnly session cookie. Every application query is filtered by the signed-in owner. Resume text is stored in the owner's profile. An application stores an immutable random UUID plus mutable user-entered fields.

New form submissions accept a random UUID and store a canonical payload fingerprint. A locked owner row serializes creation and enforces the 100-record quota. Replaying the same nonce/payload returns the existing record; changed payload is rejected. PostgreSQL owner/nonce uniqueness is an additional invariant. Concurrent edits remain last-write-wins; this personal workspace does not implement team editing.

Matching is synchronous and bounded by 20,000-character inputs, a fixed small dictionary or 30 custom phrases. It performs Unicode-normalized phrase-boundary matching and returns original evidence. No network model calls, paid dependencies or unbounded job queue are involved.

The service stores password hashes, salted recovery hashes and application records in an isolated database project separate from ReturnReady and OrderOps. Operators retain database administrative access; there is no end-to-end encryption. Do not upload financial, identity or medical records.

Deployment is one free Render Python service plus a separate Neon Free project. It has no redundant replicas and no uptime SLA. `/livez` checks the process; `/healthz` checks the application table. Operational logs contain only allowlisted route/status/timing/request IDs, never resume text or submitted values.
