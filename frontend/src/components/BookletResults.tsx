"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  RefreshCw,
  CheckCheck,
  Clock3,
} from "lucide-react";
import { api, post, Booklet } from "@/lib/api";
import ReviewDesk from "@/components/ReviewDesk";
import { GradeBadge } from "@/components/Results";

function seconds(value: number) {
  return value < 60
    ? `${value.toFixed(1)}s`
    : `${Math.floor(value / 60)}m ${Math.round(value % 60)}s`;
}
export default function BookletResults({ id }: { id: string }) {
  const [booklet, setBooklet] = useState<Booklet | null>(null);
  const [error, setError] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [baseline, setBaseline] = useState("");
  const load = useCallback(async () => {
    try {
      setBooklet(await api<Booklet>(`/booklets/${id}`));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    if (!booklet?.pages.some((p) => p.status === "processing")) return;
    const timer = setInterval(() => void load(), 2000);
    return () => clearInterval(timer);
  }, [booklet, load]);
  async function retry(pageId: string) {
    setBusy(true);
    try {
      await api(`/submissions/${pageId}/process`, post());
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={`booklet-app ${reviewing ? "review-mode" : ""}`}>
      <header className="scan-header">
        <Link href="/scan" aria-label="Back to scanning">
          <ArrowLeft size={20} />
        </Link>
        <Link href="/scan" className="scan-wordmark">
          GradeKade
        </Link>
        <Link href="/booklets" className="text-button">
          Booklets
        </Link>
      </header>
      <main className="booklet-shell">
        {error && (
          <p role="alert" className="error">
            {error}
            <button className="text-button" onClick={load}>
              Retry loading
            </button>
          </p>
        )}
        {!booklet ? (
          <p role="status">Loading booklet…</p>
        ) : reviewing ? (
          <>
            <div className="mobile-review-heading">
              <button
                className="text-button"
                onClick={() => {
                  setReviewing(false);
                  void load();
                }}
              >
                <ArrowLeft size={16} />
                Booklet summary
              </button>
              <span>{booklet.student_name}</span>
            </div>
            <ReviewDesk
              bookletId={id}
              changed={load}
              openSubmission={(pageId) => {
                const page = booklet.pages.find((p) => p.id === pageId);
                if (page)
                  window.open(
                    page.aligned_url || page.original_url,
                    "_blank",
                    "noopener,noreferrer",
                  );
              }}
              finished={() => {
                setReviewing(false);
                void load();
              }}
            />
          </>
        ) : (
          <>
            <div className="booklet-title">
              <div>
                <h1>
                  {booklet.status === "completed"
                    ? "Booklet complete"
                    : "Your booklet, at a glance"}
                </h1>
                <p>
                  {booklet.student_name} · {booklet.page_count} pages ·{" "}
                  {new Date(booklet.created_at).toLocaleDateString()}
                </p>
              </div>
              <button
                className="icon-button"
                aria-label="Refresh booklet"
                onClick={load}
              >
                <RefreshCw size={20} />
              </button>
            </div>
            <section className="booklet-outcome">
              <span className="badge neutral">
                {booklet.synthetic_demo
                  ? "Synthetic OCR demo"
                  : "Grading results"}
              </span>
              <h2>
                {booklet.auto_graded}{" "}
                <span>of {booklet.answers_total} answers auto-graded</span>
              </h2>
              {booklet.waiting ? (
                <>
                  <p>
                    <strong>{booklet.waiting} need your review.</strong> The
                    handwriting crop and answer key are ready for each one.
                  </p>
                  <button
                    className="primary"
                    onClick={() => setReviewing(true)}
                  >
                    Review {booklet.waiting} answers <ArrowRight size={19} />
                  </button>
                </>
              ) : booklet.status === "completed" ? (
                <p className="booklet-score">
                  <CheckCheck size={23} />
                  Final score: {booklet.correct} / {booklet.answers_total} (
                  {booklet.score_percent}%)
                </p>
              ) : (
                <p>
                  {booklet.processed_pages} of {booklet.page_count} pages
                  processed. Check the page list below.
                </p>
              )}
              {booklet.synthetic_demo && (
                <small>
                  Simulated predictions for original sample pages. This does not
                  measure handwriting accuracy.
                </small>
              )}
            </section>
            {booklet.uploaded_pages < booklet.page_count && (
              <p className="notice warning">
                {booklet.page_count - booklet.uploaded_pages} pages haven’t
                uploaded yet.{" "}
                <Link href="/scan">
                  Resume the saved draft on the capturing device.
                </Link>
              </p>
            )}
            <section className="booklet-page-list">
              <h2>Page results</h2>
              {booklet.pages.map((p, i) => (
                <article key={p.id}>
                  <a
                    href={p.aligned_url || p.original_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    <img
                      src={p.original_url}
                      alt={`Full worksheet page ${p.page_number || i + 1}`}
                    />
                  </a>
                  <div>
                    <strong>Page {p.page_number || i + 1}</strong>
                    <span>{p.template_name}</span>
                    <GradeBadge status={p.status} />
                    <small>
                      {p.total} answers · {p.waiting} waiting
                    </small>
                    {p.alignment && !p.alignment.verified && (
                      <p className="warning-text">
                        Alignment unverified. Open the full page before judging
                        crops.
                      </p>
                    )}
                  </div>
                  {["uploaded", "failed"].includes(p.status) && (
                    <button
                      className="secondary"
                      disabled={busy}
                      onClick={() => retry(p.id)}
                    >
                      Retry page
                    </button>
                  )}
                </article>
              ))}
            </section>
            <section className="workflow-timing">
              <h2>
                <Clock3 size={19} />
                Observed workflow time
              </h2>
              <dl>
                <div>
                  <dt>Capture elapsed</dt>
                  <dd>{seconds(booklet.timing.capture_seconds)}</dd>
                </div>
                <div>
                  <dt>Processing</dt>
                  <dd>{seconds(booklet.timing.processing_seconds)}</dd>
                </div>
                <div>
                  <dt>Human review</dt>
                  <dd>{seconds(booklet.timing.review_seconds)}</dd>
                </div>
                <div>
                  <dt>Average timed review</dt>
                  <dd>
                    {booklet.timing.mean_review_seconds === null
                      ? "—"
                      : seconds(booklet.timing.mean_review_seconds)}
                  </dd>
                </div>
              </dl>
              {booklet.timing.end_to_end_seconds != null && (
                <p>
                  Elapsed from first capture to final decision:{" "}
                  {seconds(booklet.timing.end_to_end_seconds)}.
                </p>
              )}
              <p>
                Elapsed timers include pauses and interruptions. Processing time
                is separate. These observations are not a claim of labor
                savings.
              </p>
              <form
                className="baseline-form"
                onSubmit={async (e) => {
                  e.preventDefault();
                  setBusy(true);
                  try {
                    setBooklet(
                      await api<Booklet>(
                        `/booklets/${id}/baseline`,
                        post({ seconds: Number(baseline) }),
                      ),
                    );
                    setBaseline("");
                  } catch (err) {
                    setError((err as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label>
                  Manual grading baseline (seconds)
                  <input
                    aria-label="Manual grading baseline"
                    type="number"
                    min="1"
                    max="86400"
                    step="1"
                    placeholder="Time the same work manually"
                    value={baseline}
                    onChange={(e) => setBaseline(e.target.value)}
                    required
                  />
                </label>
                <button className="secondary" disabled={busy}>
                  Save comparison
                </button>
              </form>
              {booklet.timing.manual_baseline_seconds !== null && (
                <p>
                  Manual baseline:{" "}
                  {seconds(booklet.timing.manual_baseline_seconds)}.{" "}
                  {booklet.timing.comparable
                    ? `Observed capture + review was ${seconds(Math.abs(booklet.timing.difference_seconds!))} ${booklet.timing.difference_seconds! >= 0 ? "shorter" : "longer"}.`
                    : "Comparison appears after all answers are final and every human review has a timing."}
                </p>
              )}
            </section>
            <Link className="primary" href="/scan">
              Scan another booklet <ArrowRight size={18} />
            </Link>
          </>
        )}
      </main>
    </div>
  );
}
