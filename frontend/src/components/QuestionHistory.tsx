"use client";
import { useState } from "react";
import { api, QuestionHistory as History } from "@/lib/api";
import { ocrLabel } from "@/lib/ocr";
import { GradeBadge } from "./Results";
export default function QuestionHistory({ bookletId }: { bookletId: string }) {
  const [items, setItems] = useState<History[] | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  return (
    <section className="question-history">
      <h2>Question attempt history</h2>
      <button
        className="secondary"
        disabled={loading}
        onClick={async () => {
          setLoading(true);
          try {
            setItems(
              await api<History[]>(`/booklets/${bookletId}/question-history`),
            );
            setError("");
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setLoading(false);
          }
        }}
      >
        {loading
          ? "Loading history…"
          : items
            ? "Refresh history"
            : "Show question history"}
      </button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {items?.map((q) => (
        <details key={q.initial_answer_id}>
          <summary>
            Page {q.page_number} · Question {q.question_number} ·{" "}
            {q.resolved ? "Resolved" : "Unresolved"} · {q.attempts.length}{" "}
            attempts
          </summary>
          <p>
            Expected: <strong>{q.expected_answer}</strong>
          </p>
          {q.attempts.map((a, i) => (
            <article key={a.id} className="history-attempt">
              <h3>
                Attempt {i + 1} ·{" "}
                {a.round_number ? `Correction ${a.round_number}` : "Initial"}
              </h3>
              <img
                src={a.crop_url}
                loading="lazy"
                alt={`Question ${q.question_number}, attempt ${i + 1}`}
              />
              <p>
                Detected: {a.raw_ocr_text || "(none)"} ·{" "}
                <GradeBadge status={a.final_grade ?? "needs_review"} />
              </p>
              <p>
                {ocrLabel(a.ocr_provider)} · System: {a.system_grade} · Rule
                score: {(a.grading_confidence * 100).toFixed(1)}% (uncalibrated)
              </p>
              <p>
                OCR confidence:{" "}
                {a.ocr_confidence === null
                  ? "Unknown"
                  : `${(a.ocr_confidence * 100).toFixed(1)}%`}{" "}
                · Human override: {a.human_override ? "Yes" : "No"}
              </p>
              {a.reviewed_answer !== null && (
                <p>Human transcription: {a.reviewed_answer || "(blank)"}</p>
              )}
              <p className="muted">
                Created {new Date(a.created_at).toLocaleString()}
                {a.reviewed_at
                  ? ` · Reviewed ${new Date(a.reviewed_at).toLocaleString()}`
                  : ""}
              </p>
              <a href={a.original_url} target="_blank" rel="noreferrer">
                Open attempt page
              </a>
            </article>
          ))}
        </details>
      ))}
    </section>
  );
}
