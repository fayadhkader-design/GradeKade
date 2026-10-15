"use client";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState, useRef } from "react";
import { ArrowLeft, ArrowRight, Download } from "lucide-react";
import { api, post, Answer } from "@/lib/api";

type RecordItem = Answer & {
  source: string;
  student_actual_answer: string | null;
  transcription_status: string;
  verified_grade: string | null;
  automated_decision_correct: boolean | null;
  original_url: string;
  aligned_url: string | null;
  alignment: Record<string, unknown> | null;
  preprocessing_variants: string[];
  variant_urls: Record<string, string>;
};
type Report = {
  verified_answers: number;
  automated_answers: number;
  verified_automated_answers: number;
  unverified_automated_answers: number;
  auto_grade_precision: number | null;
  auto_grade_coverage: number | null;
  normalized_ocr_accuracy: number | null;
  false_auto_correct_count: number;
  false_auto_incorrect_count: number;
};
type Data = { items: RecordItem[]; report: Report; total: number };
export default function Evaluation() {
  const [data, setData] = useState<Data | null>(null);
  const [source, setSource] = useState("real_handwriting");
  const [offset, setOffset] = useState(0);
  const [index, setIndex] = useState(0);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [actual, setActual] = useState("");
  const [status, setStatus] = useState("readable");
  const [grade, setGrade] = useState("incorrect");
  const [origin, setOrigin] = useState("unknown");
  const started = useRef(0);
  const loaded = useRef("");
  const load = useCallback(async () => {
    try {
      setData(
        await api<Data>(
          `/evaluation?source=${source}&offset=${offset}&limit=100`,
        ),
      );
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }, [source, offset]);
  useEffect(() => {
    setData(null);
    void load();
  }, [load]);
  const items =
    data?.items.filter((a) =>
      filter === "mistakes"
        ? a.automated_decision_correct === false
        : filter === "unverified"
          ? !a.verified_grade
          : true,
    ) ?? [];
  const current = items[index];
  useEffect(() => {
    setActual(current?.student_actual_answer ?? "");
    setStatus(
      current?.transcription_status === "blank" ||
        current?.transcription_status === "unreadable"
        ? current.transcription_status
        : "readable",
    );
    setGrade(current?.verified_grade ?? "incorrect");
    setOrigin(current?.source ?? "unknown");
    started.current = performance.now();
    loaded.current = "";
  }, [
    current?.id,
    current?.student_actual_answer,
    current?.transcription_status,
    current?.verified_grade,
    current?.source,
  ]);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (!current || loaded.current !== current.id) {
      setError("Wait for the answer crop to load before verifying.");
      return;
    }
    setBusy(true);
    setNotice("");
    try {
      await api(
        `/question-submissions/${current.id}/ground-truth`,
        post({
          actual_answer: actual,
          transcription_status: status,
          verified_grade: grade,
          source: origin,
          annotation_seconds: Math.min(
            3600,
            (performance.now() - started.current) / 1000,
          ),
        }),
      );
      setNotice("Ground truth saved. The original AI prediction is preserved.");
      await load();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const pct = (value: number | null) =>
    value === null ? "N/A" : `${(value * 100).toFixed(2)}%`;
  return (
    <div className="scan-app">
      <header className="scan-header">
        <Link href="/" aria-label="Back to workspace">
          <ArrowLeft size={20} />
        </Link>
        <span className="scan-wordmark">GradeKade</span>
        <a
          className="secondary"
          href={`/api/evaluation/export?source=${source}`}
        >
          <Download size={17} /> Export dataset
        </a>
      </header>
      <main className="evaluation-shell">
        <h1>Grading evaluation</h1>
        <p className="muted">
          Verify handwriting independently, then inspect the system prediction.
          Accuracy uses human-verified answers only.
        </p>
        <div className="evaluation-controls">
          <label>
            Dataset source
            <select
              value={source}
              onChange={(e) => {
                setSource(e.target.value);
                setOffset(0);
                setIndex(0);
              }}
            >
              <option value="real_handwriting">
                Verified real handwriting
              </option>
              <option value="unknown">Unclassified uploads</option>
              <option value="synthetic">Synthetic demo</option>
              <option value="all">All sources (mixed)</option>
            </select>
          </label>
          <label>
            Answers on this page
            <select
              value={filter}
              onChange={(e) => {
                setFilter(e.target.value);
                setIndex(0);
              }}
            >
              <option value="all">All answers</option>
              <option value="unverified">Missing human grade</option>
              <option value="mistakes">Incorrect automatic decisions</option>
            </select>
          </label>
          <button
            className="secondary"
            disabled={busy}
            onClick={() => void load()}
          >
            Refresh
          </button>
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        {!data && !error && <p role="status">Loading evaluation records…</p>}
        {data && (
          <>
            <p className="notice">
              {data.total} answers · {data.report.verified_answers} verified ·{" "}
              {data.report.verified_automated_answers} verified automated
              decisions · {data.report.unverified_automated_answers} automated
              decisions still unverified
            </p>
            <dl className="evaluation-metrics">
              <div>
                <dt>Auto-grade precision</dt>
                <dd>{pct(data.report.auto_grade_precision)}</dd>
              </div>
              <div>
                <dt>Auto-grade coverage</dt>
                <dd>{pct(data.report.auto_grade_coverage)}</dd>
              </div>
              <div>
                <dt>Normalized OCR accuracy</dt>
                <dd>{pct(data.report.normalized_ocr_accuracy)}</dd>
              </div>
              <div>
                <dt>False auto-correct / incorrect</dt>
                <dd>
                  {data.report.false_auto_correct_count} /{" "}
                  {data.report.false_auto_incorrect_count}
                </dd>
              </div>
            </dl>
            {source !== "real_handwriting" && (
              <p className="notice">
                This cohort may include mock or synthetic predictions. These
                metrics do not establish real handwriting accuracy.
              </p>
            )}
            {current ? (
              <section className="evaluation-layout">
                <div>
                  <div className="section-bar">
                    <h2>Question {current.question_number}</h2>
                    <span>
                      {index + 1} / {items.length}
                    </span>
                  </div>
                  <img
                    className="evaluation-crop"
                    src={current.crop_url}
                    alt={`Answer crop for question ${current.question_number}`}
                    onLoad={() => {
                      loaded.current = current.id;
                      started.current = performance.now();
                    }}
                    onError={() =>
                      setError("Crop failed to load. Refresh before verifying.")
                    }
                  />
                  <form className="field-stack" onSubmit={save}>
                    <label>
                      Transcription status
                      <select
                        value={status}
                        onChange={(e) => setStatus(e.target.value)}
                      >
                        <option value="readable">
                          Readable numeric answer
                        </option>
                        <option value="blank">Blank answer</option>
                        <option value="unreadable">
                          Ambiguous / unreadable
                        </option>
                      </select>
                    </label>
                    {status === "readable" && (
                      <label>
                        What was actually written
                        <input
                          value={actual}
                          onChange={(e) => setActual(e.target.value)}
                          required
                          maxLength={100}
                          autoComplete="off"
                        />
                      </label>
                    )}
                    <p>
                      Answer key: <strong>{current.expected_answer}</strong> ·{" "}
                      {current.answer_type}
                    </p>
                    <label>
                      Human-verified grade
                      <select
                        value={grade}
                        onChange={(e) => setGrade(e.target.value)}
                      >
                        <option value="incorrect">Incorrect</option>
                        <option value="correct">Correct</option>
                      </select>
                    </label>
                    <label>
                      Image source
                      <select
                        value={origin}
                        disabled={current.source === "synthetic"}
                        onChange={(e) => setOrigin(e.target.value)}
                      >
                        <option value="unknown">Unknown</option>
                        <option value="real_handwriting">
                          Real photographed handwriting
                        </option>
                        <option value="synthetic">Synthetic / rendered</option>
                      </select>
                    </label>
                    <button className="primary" disabled={busy}>
                      {busy ? "Saving…" : "Save human truth"}
                    </button>
                  </form>
                  <div className="section-bar">
                    <button
                      className="secondary"
                      disabled={busy || index === 0}
                      onClick={() => setIndex((i) => i - 1)}
                    >
                      Previous
                    </button>
                    <button
                      className="secondary"
                      disabled={busy || index + 1 >= items.length}
                      onClick={() => setIndex((i) => i + 1)}
                    >
                      Next answer <ArrowRight size={16} />
                    </button>
                  </div>
                </div>
                <div>
                  <details key={current.id}>
                    <summary>Inspect OCR and grading evidence</summary>
                    <dl className="answer-facts">
                      <div>
                        <dt>Provider</dt>
                        <dd>
                          {current.ocr_provider === "mathpix"
                            ? "REAL OCR · Mathpix"
                            : `MOCK / SYNTHETIC · ${current.ocr_provider}`}
                        </dd>
                      </div>
                      <div>
                        <dt>OCR output</dt>
                        <dd>{current.raw_ocr_text || "(none)"}</dd>
                      </div>
                      <div>
                        <dt>Provider confidence</dt>
                        <dd>{pct(current.ocr_confidence)}</dd>
                      </div>
                      <div>
                        <dt>Grading rule score (uncalibrated)</dt>
                        <dd>{pct(current.grading_confidence)}</dd>
                      </div>
                      <div>
                        <dt>Original system decision</dt>
                        <dd>{current.decision ?? current.system_grade}</dd>
                      </div>
                      <div>
                        <dt>Routing reason</dt>
                        <dd>{current.routing_reason.replaceAll("_", " ")}</dd>
                      </div>
                      <div>
                        <dt>Preprocessing</dt>
                        <dd>
                          {current.preprocessing_variants.join(", ") ||
                            "Legacy crop"}
                        </dd>
                      </div>
                    </dl>
                    {Object.entries(current.variant_urls ?? {}).map(
                      ([name, url]) => (
                        <figure key={name}>
                          <img
                            className="evaluation-crop"
                            src={url}
                            alt={`${name} OCR input`}
                          />
                          <figcaption>{name}</figcaption>
                        </figure>
                      ),
                    )}
                    <pre className="evaluation-debug">
                      {JSON.stringify(
                        {
                          alignment: current.alignment,
                          evidence: current.evidence,
                        },
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                  <details>
                    <summary>Original worksheet page</summary>
                    <img
                      className="evaluation-page"
                      src={current.original_url}
                      alt="Original worksheet page"
                    />
                  </details>
                  {current.aligned_url && (
                    <details>
                      <summary>Aligned worksheet page</summary>
                      <img
                        className="evaluation-page"
                        src={current.aligned_url}
                        alt="Aligned worksheet page"
                      />
                    </details>
                  )}
                </div>
              </section>
            ) : (
              <section className="empty-state compact">
                <h2>No matching answers</h2>
                <p>
                  Use Unclassified uploads to label photographed handwriting.
                  Synthetic records are available separately.
                </p>
              </section>
            )}
            <div className="section-bar">
              <button
                className="secondary"
                disabled={offset === 0 || busy}
                onClick={() => {
                  setOffset((o) => Math.max(0, o - 100));
                  setIndex(0);
                }}
              >
                Previous 100
              </button>
              <span>
                {data.total ? offset + 1 : 0}–
                {Math.min(offset + 100, data.total)} of {data.total}
              </span>
              <button
                className="secondary"
                disabled={offset + 100 >= data.total || busy}
                onClick={() => {
                  setOffset((o) => o + 100);
                  setIndex(0);
                }}
              >
                Next 100
              </button>
            </div>
            <details>
              <summary>Report denominators and cohorts</summary>
              <pre className="evaluation-debug">
                {JSON.stringify(data.report, null, 2)}
              </pre>
            </details>
          </>
        )}
        <p className="muted">
          Development/demo use only. Exports omit names and full pages; inspect
          crop pixels for identifiers before sharing.
        </p>
      </main>
    </div>
  );
}
