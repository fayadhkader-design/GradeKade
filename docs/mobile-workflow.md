# Mobile scanning milestone (local preview)

Mobile scanning is a core employee workflow: select the student/default worksheet once, capture successive pages, check readability, submit an ordered booklet and review exceptions on the same phone. Desktop retains template setup and bulk operations. No native app has been introduced.

## Try it locally

Run migrations (`cd backend && uv run alembic upgrade head`) before starting the updated backend. Open `http://localhost:3000/scan`. For a no-key demo, choose **Set up sample student & template**, then **Add original demo page** twice, and **Submit booklet**. The two-page synthetic booklet has 40 answers: 30 auto-accepted and 10 reviewed. Review Q2/Q7/Q15 as correct and Q12/Q20 as incorrect on each page; final score is 34/40.

`/booklets` lists saved batches. Each booklet detail offers page results, failed-page retry, scoped review and observed timings. The dashboard links to scanning and saved booklets.

## Capture and recovery

- Live rear-camera preference, full-page framing guide, PNG/JPG photo picker fallback, thumbnail preview, retake, delete and reorder; a page may override the default worksheet template.
- Camera captures use JPEG to keep files manageable. At most 30 pages per booklet, 10 MB per page. PDF multi-page import and HEIC decoding are not included; use JPEG/PNG for this flow.
- Every draft (including image blobs) is stored in IndexedDB on the capturing browser. Only one draft is active. Browser storage can be denied, cleared or evicted; visible save errors must be resolved before leaving. This is a demo-only recovery aid, not an encrypted backup.
- Booklet/page UUIDs are stable idempotency keys. Retries return the existing matching page; mismatched images/slots are rejected. Upload progress and synchronous per-page processing are separate. Failed processing can be retried from booklet results without capturing again.
- Frozen uploads cannot be reordered/replaced. **Create editable copy** preserves the photos under a new booklet ID for correcting a bad capture or settings. Already uploaded pages stay in the original batch; no automatic record deletion.
- Camera tracks stop on close, submission and component exit. No microphone is requested. Synthetic OCR is turned off when opening the camera: it is not handwriting recognition.
- No automatic edge detection or perspective correction at capture time. Framing checks remain manual. The backend now measures severe blur/darkness/empty photos and alignment; clearly unusable pages require a retake. Moderate glare and handwriting ambiguity still need real-world validation.

## Phone/device boundary

Live `getUserMedia` requires a secure browser context (HTTPS, with localhost treated specially). A phone's localhost is the phone itself, not this computer. The local preview stays bound to loopback; no public tunnel or unauthenticated LAN deployment has been enabled. A trusted HTTPS device-test setup is needed for actual iPhone/Android camera validation. A photo-picker fallback is provided when live camera is unavailable.

The web manifest supports a home-screen entry on compatible browsers. No service worker caches educational images, no offline grading is promised, and an initial app load still needs the server. Draft persistence and upload retries are not a background upload service.

## Review and measurement

Booklet-specific review uses large crops and fixed thumb-friendly Correct/Incorrect controls on mobile; keyboard shortcuts remain available on desktop. Each decision records observed seconds from crop load to decision, capped at one hour. Review batches refetch as needed beyond the 200-item response limit. Original OCR remains intact when recognized text is edited.

Capture elapsed time, server processing duration, timed review total/average and elapsed completion time are shown separately. Timers include interruptions, are client-reported where applicable and are not verified labor telemetry. An optional measured manual-grading baseline provides a comparison only after the booklet is final and every human decision has timing. No savings claim is generated from automation coverage alone.

Real OCR uses the existing Mathpix adapter when `OCR_PROVIDER=mathpix`, `MATHPIX_APP_ID` and `MATHPIX_APP_KEY` are configured. Missing credentials use empty mock OCR; arbitrary phone captures then require human review. Live paid OCR and actual handwriting accuracy have not been evaluated in this milestone. The existing evaluation CLI accepts separately annotated, permissioned adult handwriting datasets.

## Local checks

Backend tests cover ordered/idempotent uploads, booklet scope, timing comparison safeguards, cross-organization resource isolation and migration of existing grades. Browser tests cover reload recovery, an interrupted upload, subsequent upload deduplication, paged exception review through finalization, a simulated camera stream and permission-denied fallback, alongside the original desktop workflow. Camera tests do not access the physical webcam.
