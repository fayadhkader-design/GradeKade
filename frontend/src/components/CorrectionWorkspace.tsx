"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { api, post, CorrectionRound, Submission } from "@/lib/api";
import ReviewDesk from "./ReviewDesk";
import { GradeBadge } from "./Results";

export default function CorrectionWorkspace({ id }: { id: string }) {
  const [round, setRound] = useState<CorrectionRound | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [reviewing, setReviewing] = useState(false);
  const processing = round?.pages.some(
    (slot) => slot.submission?.status === "processing",
  );
  const load = useCallback(async () => {
    try {
      setRound(await api<CorrectionRound>(`/correction-rounds/${id}`));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);
  useEffect(() => {
    void load();
  }, [load]);
  useEffect(() => {
    // Processing continues on the server if this screen is reloaded or reopened.
    if (!busy && !processing) return;
    const timer = setInterval(() => void load(), 1500);
    return () => clearInterval(timer);
  }, [busy, processing, load]);
  async function upload(source: string, file: File) {
    if (busy) return;
    setBusy("Uploading corrected page");
    setError("");
    try {
      const body = new FormData();
      body.set("file", file);
      await api<Submission>(`/correction-rounds/${id}/pages/${source}`, {
        method: "POST",
        body,
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function process(page: Submission) {
    if (busy) return;
    setBusy("Processing corrections");
    setError("");
    try {
      await api(`/submissions/${page.id}/process`, post());
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  return (
    <div className={`booklet-app ${reviewing ? "review-mode" : ""}`}>
      <header className="scan-header">
        <Link
          href={round ? `/booklets/${round.booklet_id}` : "/booklets"}
          aria-label="Back to booklet"
        >
          <ArrowLeft size={20} />
        </Link>
        <span className="scan-wordmark">GradeKade</span>
        <span className="badge neutral">
          Correction round {round?.round_number ?? ""}
        </span>
      </header>
      <main className="booklet-shell">
        {error && (
          <p className="error" role="alert">
            {error}
            <button className="text-button" onClick={() => void load()}>
              Refresh round
            </button>
          </p>
        )}
        {!round ? (
          <p role="status">Loading correction round…</p>
        ) : reviewing ? (
          <ReviewDesk
            correctionRoundId={id}
            finishedLabel="Back to correction round"
            changed={() => void load()}
            openSubmission={(pageId) => {
              const page = round.pages.find(
                (p) => p.submission?.id === pageId,
              )?.submission;
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
        ) : (
          <>
            <h1>Correction round {round.round_number}</h1>
            <p>
              {round.unresolved_before} questions to check · {round.corrected}{" "}
              correct so far
            </p>
            <p className="muted">
              Scan the same corrected pages. Only the question numbers listed
              below will be evaluated.
            </p>
            {(busy || processing) && (
              <p role="status" className="notice">
                {busy || "Processing corrections"}…
              </p>
            )}
            <section className="correction-pages">
              {round.pages.map((slot) => (
                <section
                  key={slot.source_submission_id}
                  className="correction-page"
                >
                  <h2>Page {slot.page_number}</h2>
                  <p>
                    Check questions:{" "}
                    <strong>{slot.question_numbers.join(", ")}</strong>
                  </p>
                  {slot.submission && (
                    <>
                      <a
                        href={slot.submission.original_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        <img
                          className="correction-preview"
                          src={slot.submission.original_url}
                          alt={`Corrected page ${slot.page_number}`}
                        />
                      </a>
                      <GradeBadge
                        status={
                          slot.submission.processing?.stage ??
                          slot.submission.status
                        }
                      />
                      {slot.submission.error && (
                        <p className="error">{slot.submission.error}</p>
                      )}
                      <p>
                        {slot.submission.total} answers evaluated ·{" "}
                        {slot.submission.waiting} need review
                      </p>
                    </>
                  )}
                  {!round.completed_at &&
                    (!slot.submission ||
                      ["failed", "uploaded"].includes(
                        slot.submission.status,
                      )) && (
                      <label className="field-stack">
                        {slot.submission
                          ? "Retake or replace this ungraded page"
                          : "Scan corrected page"}
                        <input
                          aria-label={`Corrected page ${slot.page_number}`}
                          type="file"
                          accept="image/jpeg,image/png,application/pdf"
                          capture="environment"
                          disabled={!!busy}
                          onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file)
                              void upload(slot.source_submission_id, file);
                            e.target.value = "";
                          }}
                        />
                        <small>
                          PNG/JPG or first PDF page · 10 MB maximum. Phone photo
                          capture is available where supported.
                        </small>
                      </label>
                    )}
                  {slot.submission &&
                    !round.completed_at &&
                    ["uploaded", "failed"].includes(slot.submission.status) && (
                      <button
                        className="primary"
                        disabled={!!busy}
                        onClick={() => void process(slot.submission!)}
                      >
                        Process page {slot.page_number}
                      </button>
                    )}
                </section>
              ))}
            </section>
            {round.waiting > 0 && (
              <button
                className="primary"
                disabled={!!busy}
                onClick={() => setReviewing(true)}
              >
                Review {round.waiting} corrections <ArrowRight size={18} />
              </button>
            )}
            {round.status === "ready_to_finalize" && (
              <button
                className="primary"
                disabled={!!busy}
                onClick={async () => {
                  setBusy("Finalizing correction round");
                  try {
                    setRound(
                      await api<CorrectionRound>(
                        `/correction-rounds/${id}/finalize`,
                        post(),
                      ),
                    );
                    setError("");
                  } catch (e) {
                    setError((e as Error).message);
                  } finally {
                    setBusy("");
                  }
                }}
              >
                Finalize correction round
              </button>
            )}
            {round.completed_at && (
              <p className="notice">
                Round finalized: {round.corrected} of {round.unresolved_before}{" "}
                corrected · {round.unresolved_after} remaining.
              </p>
            )}
            <p>
              <Link
                className="text-button"
                href={`/booklets/${round.booklet_id}`}
              >
                Back to booklet summary <ArrowRight size={17} />
              </Link>
            </p>
          </>
        )}
      </main>
    </div>
  );
}
