"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Check, X, Pencil, ArrowRight, CheckCheck } from "lucide-react";
import { api, post, Answer } from "@/lib/api";
import { mayUseShortcut } from "@/lib/regions";

export default function ReviewDesk({changed, openSubmission}: {changed: () => void; openSubmission: (id: string) => void}) {
  const [queue, setQueue] = useState<Answer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [editing, setEditing] = useState(false);
  const [recognized, setRecognized] = useState("");
  const [done, setDone] = useState(0);
  const [lastSubmission, setLastSubmission] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  const current = queue[0];
  const load = useCallback(async () => {setLoading(true); try {setQueue(await api<Answer[]>("/review-queue")); setError("");} catch(e) {setError((e as Error).message);} finally {setLoading(false);}}, []);
  useEffect(() => {void load();}, [load]);
  useEffect(() => {if (editing) input.current?.focus();}, [editing]);
  const decide = useCallback(async (grade: "correct" | "incorrect") => {
    if (!current || submitting.current) return;
    submitting.current = true; setBusy(true); setError("");
    try {
      await api(`/question-submissions/${current.id}/review`, post({grade, recognized_answer: editing ? recognized : null}));
      setQueue(q => q.filter(a => a.id !== current.id)); setDone(n => n + 1); setLastSubmission(current.submission_id);
      setEditing(false); setRecognized(""); changed();
      if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    } catch(e) {setError((e as Error).message);}
    finally {submitting.current = false; setBusy(false);}
  }, [current, editing, recognized, changed]);
  useEffect(() => {
    function key(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey || event.repeat || !mayUseShortcut(event.target)) return;
      if (event.key.toLowerCase() === "c") {event.preventDefault(); void decide("correct");}
      if (event.key.toLowerCase() === "i") {event.preventDefault(); void decide("incorrect");}
      if (event.key.toLowerCase() === "e" && current) {event.preventDefault(); setRecognized(current.raw_ocr_text); setEditing(true);}
    }
    window.addEventListener("keydown", key); return () => window.removeEventListener("keydown", key);
  }, [decide, current]);
  if (loading) return <p role="status">Loading review queue…</p>;
  if (!current) return <section className="empty-state"><CheckCheck size={42}/><h2>{done ? "Review complete" : "You’re all caught up"}</h2><p>{done ? `${done} answers reviewed in this session. Each worksheet finalizes when all its answers have a decision.` : "Answers that need your judgment will appear here after processing."}</p>{lastSubmission && <button className="primary" onClick={() => openSubmission(lastSubmission)}>View worksheet result <ArrowRight size={16}/></button>}{error && <p role="alert" className="error">{error}</p>}<button className="text-button" onClick={load}>Refresh queue</button></section>;
  return <section>
    <div className="section-bar"><p><strong>{queue.length}</strong> waiting <span className="muted">· {done} reviewed this session</span></p><span className="badge review">Human judgment needed</span></div>
    <div className="review-layout">
      <div className="crop-desk"><div className="section-bar"><h2>Question {current.question_number}</h2><span>{current.student_name}</span></div><div className="crop-stage"><img src={current.crop_url} alt={`Handwritten answer to question ${current.question_number}`}/></div><p className="muted">{current.routing_reason.replaceAll("_", " ")} · {current.ocr_provider === "synthetic_fixture" ? "Synthetic demo interpretation" : current.ocr_provider}</p><button className="text-button" onClick={() => openSubmission(current.submission_id)}>Open full worksheet <ArrowRight size={16}/></button></div>
      <div className="decision-panel"><h2>Make the call</h2><dl className="answer-facts"><div><dt>Expected answer</dt><dd>{current.expected_answer}</dd></div><div><dt>OCR interpretation</dt><dd>{current.raw_ocr_text || "No answer recognized"}</dd></div><div><dt>Grading confidence</dt><dd>{(current.grading_confidence * 100).toFixed(1)}% <small>Uncalibrated</small></dd></div></dl>
        <p className="muted">Judge the handwriting against the answer key. Your decision is final.</p>
        <div className="decision-buttons"><button className="primary correct-button" disabled={busy} onClick={() => decide("correct")}><Check size={23}/> Correct <kbd>C</kbd></button><button className="incorrect-button" disabled={busy} onClick={() => decide("incorrect")}><X size={23}/> Incorrect <kbd>I</kbd></button></div>
        <button className="text-button" disabled={busy} onClick={() => {setRecognized(current.raw_ocr_text); setEditing(!editing);}}><Pencil size={16}/> {editing ? "Cancel edit" : "Edit recognized answer"} <kbd>E</kbd></button>
        {editing && <label className="edit-answer">Recognized answer<input ref={input} value={recognized} onChange={e => setRecognized(e.target.value)} maxLength={100}/><small>Saved with your next decision. Original OCR is retained.</small></label>}
        <p aria-live="polite" className="muted">{busy ? "Saving decision…" : "After each decision, the next answer appears automatically."}</p>
        {error && <div role="alert" className="error">{error}<button className="text-button" onClick={load}>Refresh queue</button></div>}
      </div>
    </div>
  </section>;
}
