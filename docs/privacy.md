# Development privacy boundary

Development/demo use only. Do not upload identifiable student educational records until production privacy/security controls are completed.

This version uses a fixed local demo organization and demo admin. UUID resource lookups, including page/crop routes, check organization ownership. Organization access is **not authentication**: anyone reaching the local API acts as the demo user. Role fields are stored but not an authorization system. This application must not be exposed publicly in its current form. It makes no FERPA/COPPA claims.

## Implemented foundations

- Minimal student display identifier and optional external ID; no DOB, addresses or contacts.
- UUID records and storage keys, validated numeric keys/normalized bounds, locked used templates.
- Decoded JPEG/PNG/PDF validation, 10 MB request/file limit, 20 MP raster cap, first PDF page only, EXIF orientation corrected and metadata removed from stored PNGs.
- Same-origin Next.js proxy bounds streamed request bodies before forwarding. Direct backend uploads also enforce declared length and decoded file limits; deploy a real ingress limit before network exposure.
- Per-organization lookups; storage keys never appear in API responses; no static filesystem mount; no-store headers for educational images and JSON.
- Environment-only OCR credentials; no OCR text, keys or uploaded contents in application logs. Normal Uvicorn access logs contain UUID route paths and status codes.
- System predictions retained separately from final decisions and recognized-text edits. Conditional review updates reject repeat decisions.
- Mathpix is opt-in, requires credentials, and provider errors become review items. No paid API called during implementation.
- `.env`, database, uploads, test artifacts and temporary files excluded from Git.

## Required before real educational records

Authenticated sessions, organization membership and scoped role checks, tenant integrity constraints/RLS defense in depth, CSRF protections tied to session design, private object storage with controlled signed URLs, TLS, encrypted backups, secrets rotation, data deletion/retention and export policy, least-privilege database/service credentials, ingestion sandbox/resource timeouts, operational access controls and audit/incident procedures. Review vendor training/retention/residency terms and applicable student-data obligations. Use permissioned de-identified evaluation data before making any grading reliability claims.
