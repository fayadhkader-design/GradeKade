"use client";
import { useEffect, useState } from "react";
import { api, Submission } from "@/lib/api";
export function GradeBadge({status}: {status: string}) {
  return <span className={`badge ${status === "needs_review" || status === "uncertain" ? "review" : status === "correct" || status === "completed" ? "correct" : status === "incorrect" || status === "failed" ? "incorrect" : "neutral"}`}>{status.replaceAll("_", " ")}</span>;
}
export default function Results({id, review, refreshKey}: {id: string; review: () => void; refreshKey: number}) {
  const [submission, setSubmission] = useState<Submission | null>(null);
  const [error, setError] = useState("");
  const [aligned, setAligned] = useState(true);
  useEffect(() => {let active = true; setSubmission(null); api<Submission>(`/submissions/${id}`).then(s => {if(active) {setSubmission(s); setError("");}}).catch(e => {if(active) setError(e.message);}); return () => {active = false;};}, [id, refreshKey]);
  if (error) return <p role="alert" className="error">{error}</p>;
  if (!submission) return <p role="status">Loading worksheet…</p>;
  return <section>
    <div className="section-bar result-heading"><div><h2>{submission.template_name}</h2><p>{submission.student_name} · <GradeBadge status={submission.status}/></p></div><div className="score"><strong>{submission.score_percent === null ? "Pending" : `${submission.correct} / ${submission.total}`}</strong><span>{submission.score_percent === null ? `${submission.waiting} answers need review` : `${submission.score_percent}% · final score`}</span></div></div>
    {submission.error && <p className="error">{submission.error}</p>}
    {submission.processing && <p className="notice">OCR: {submission.processing.ocr_provider === "synthetic_fixture" ? "Synthetic fixture (simulated, not handwriting recognition)" : submission.processing.ocr_provider} · Auto-grade threshold: {(submission.processing.threshold * 100).toFixed(1)}%. Confidence is not calibrated.</p>}
    {submission.alignment && !submission.alignment.verified && <p className="notice warning">Alignment could not be verified. Inspect the full page before deciding; every answer requires human review.</p>}
    <div className="results-layout"><div className="page-preview"><div className="segmented"><button className={aligned ? "active" : ""} onClick={() => setAligned(true)} disabled={!submission.aligned_url}>Aligned page</button><button className={!aligned ? "active" : ""} onClick={() => setAligned(false)}>Original page</button></div><img src={aligned && submission.aligned_url ? submission.aligned_url : submission.original_url} alt={aligned ? "Aligned worksheet page" : "Original worksheet page"}/><p className="muted">{submission.alignment?.verified ? "Page registration verified" : "Registration not verified"}</p></div>
      <div><div className="section-bar"><h2>Answer results</h2>{submission.waiting > 0 && <button className="primary" onClick={review}>Review {submission.waiting} answers</button>}</div><div className="table-scroll"><table className="answers-table"><thead><tr><th>Q.</th><th>Answer crop</th><th>Expected / OCR</th><th>Confidence</th><th>Decision</th></tr></thead><tbody>{submission.answers.map(a => <tr key={a.id}><td>{a.question_number}</td><td><img src={a.crop_url} alt={`Answer ${a.question_number}`} className="answer-thumbnail"/></td><td><strong>{a.expected_answer}</strong><small>OCR: {a.raw_ocr_text || "—"}</small>{a.reviewed_answer !== null && <small>Edited: {a.reviewed_answer || "(blank)"}</small>}</td><td>{(a.grading_confidence * 100).toFixed(1)}%</td><td><GradeBadge status={a.review_status === "needs_review" ? "needs_review" : a.final_grade || a.system_grade}/><small>{a.review_status === "auto_accepted" ? "Auto-graded" : a.review_status === "human_reviewed" ? "Human reviewed" : a.routing_reason.replaceAll("_", " ")}</small></td></tr>)}</tbody></table></div></div>
    </div>
  </section>;
}
