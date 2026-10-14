"use client";
import { useRef, useState } from "react";
import { Plus, Trash2, Save, LockKeyhole } from "lucide-react";
import { api, post, Question, Template, AnswerType } from "@/lib/api";
import { pagePoint, rectangle, Point } from "@/lib/regions";

export default function TemplateEditor({template, saved}: {template: Template; saved: (template: Template) => void}) {
  const [questions, setQuestions] = useState<Question[]>(template.questions);
  const [selected, setSelected] = useState(0);
  const [draft, setDraft] = useState<ReturnType<typeof rectangle> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const start = useRef<Point | null>(null);
  const canvas = useRef<HTMLDivElement>(null);
  const locked = template.locked;
  function add(region = {x: .1, y: .2, width: .18, height: .05}) {
    setSelected(questions.length);
    setQuestions([...questions, {question_number: Math.max(0, ...questions.map(q => q.question_number)) + 1, ...region, expected_answer: "", answer_type: "integer", auto_grade_enabled: true}]);
    setMessage("");
  }
  function update(patch: Partial<Question>) {
    setQuestions(questions.map((q, i) => i === selected ? {...q, ...patch} : q)); setMessage("");
  }
  async function save() {
    setBusy(true); setError("");
    try {
      const updated = await api<Template>(`/templates/${template.id}/questions`, post({questions}));
      setQuestions(updated.questions); saved(updated); setMessage(`${updated.questions.length} answer boxes saved.`);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  const q = questions[selected];
  return <section className="editor-layout">
    <div>
      <div className="section-bar"><div><h2>{template.name}</h2><p>{locked ? "Template in use · answer key locked" : "Drag around the answer area only. Leave the printed question outside."}</p></div><span className="badge neutral">{questions.length} boxes</span></div>
      <div className={`worksheet-canvas ${locked ? "locked" : ""}`} ref={canvas}
        onPointerDown={e => { if (locked || !canvas.current) return; e.preventDefault(); start.current = pagePoint(e.clientX, e.clientY, canvas.current.getBoundingClientRect()); e.currentTarget.setPointerCapture(e.pointerId); }}
        onPointerMove={e => {if (start.current && canvas.current) setDraft(rectangle(start.current, pagePoint(e.clientX, e.clientY, canvas.current.getBoundingClientRect())));}}
        onPointerUp={e => {if (!start.current || !canvas.current) return; const region = rectangle(start.current, pagePoint(e.clientX, e.clientY, canvas.current.getBoundingClientRect())); start.current = null; setDraft(null); if (region.width * template.width >= 8 && region.height * template.height >= 8) add(region);}}
        onPointerCancel={() => {start.current = null; setDraft(null);}}>
        {/* Native image preserves the exact page coordinate surface. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={template.image_url} width={template.width} height={template.height} alt={`Blank worksheet: ${template.name}`} draggable={false}/>
        {questions.map((region, i) => <button key={i} className={`answer-region ${i === selected ? "selected" : ""}`} aria-label={`Select question ${region.question_number}`} style={{left: `${region.x * 100}%`, top: `${region.y * 100}%`, width: `${region.width * 100}%`, height: `${region.height * 100}%`}} onPointerDown={e => e.stopPropagation()} onClick={() => setSelected(i)}><span>{region.question_number}</span></button>)}
        {draft && <div className="answer-region draft" style={{left:`${draft.x*100}%`, top:`${draft.y*100}%`, width:`${draft.width*100}%`, height:`${draft.height*100}%`}}/>}
      </div>
    </div>
    <div className="editor-panel">
      <h2>Answer key</h2><p className="muted">Select a box to edit it. Coordinates are fractions of the page.</p>
      {locked && <p className="notice"><LockKeyhole size={16}/> Create a new template to change a used answer key.</p>}
      <div className="question-picker">{questions.map((q, i) => <button key={i} className={i === selected ? "active" : ""} onClick={() => setSelected(i)} aria-label={`Edit question ${q.question_number}`}>{q.question_number}</button>)}</div>
      {q ? <fieldset disabled={locked || busy} className="field-stack">
        <label>Question number<input type="number" min="1" max="200" value={q.question_number} onChange={e => update({question_number: Number(e.target.value)})}/></label>
        <label>Correct answer<input aria-label="Correct answer" value={q.expected_answer} placeholder="e.g. 42, 0.5, 1/2" onChange={e => update({expected_answer: e.target.value})}/></label>
        <label>Answer type<select value={q.answer_type} onChange={e => update({answer_type: e.target.value as AnswerType})}><option value="integer">Integer</option><option value="decimal">Decimal</option><option value="fraction">Fraction</option></select></label>
        <div className="coordinates">{(["x", "y", "width", "height"] as const).map(key => <label key={key}>{key}<input aria-label={`Box ${key}`} type="number" step="0.001" min="0" max="1" value={Number(q[key].toFixed(4))} onChange={e => update({[key]: Number(e.target.value)})}/></label>)}</div>
        <label className="check-label"><input type="checkbox" checked={q.auto_grade_enabled} onChange={e => update({auto_grade_enabled: e.target.checked})}/> Allow high-confidence auto-grading</label>
        <button className="text-button danger-text" onClick={() => {setQuestions(questions.filter((_, i) => i !== selected)); setSelected(Math.max(0, selected - 1)); setMessage("");}}><Trash2 size={16}/> Remove box</button>
      </fieldset> : <div className="empty-inline">Draw your first answer box, or add one using the keyboard and adjust its coordinates.</div>}
      {!locked && <div className="field-stack"><button className="secondary" onClick={() => add()} disabled={busy}><Plus size={17}/> Add box with coordinates</button><button className="primary" disabled={busy || !questions.length} onClick={save}><Save size={17}/>{busy ? "Saving…" : "Save answer key"}</button></div>}
      {error && <p role="alert" className="error">{error}</p>}{message && <p role="status" className="success-text">{message}</p>}
    </div>
  </section>;
}
