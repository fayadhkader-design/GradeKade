"use client";
import { ocrLabel, ocrDescription } from "@/lib/ocr";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  LayoutDashboard,
  ScanLine,
  Files,
  Inbox,
  ArrowUpRight,
  Plus,
  RefreshCw,
  Check,
  GraduationCap,
  Download,
  ArrowRight,
} from "lucide-react";
import { api, post, Metrics, Student, Submission, Template } from "@/lib/api";
import TemplateEditor from "@/components/TemplateEditor";
import ReviewDesk from "@/components/ReviewDesk";
import Results, { GradeBadge } from "@/components/Results";

type View = "dashboard" | "templates" | "upload" | "review" | "results";
const navigation = [
  { view: "dashboard", label: "Overview", icon: LayoutDashboard },
  { view: "templates", label: "Templates", icon: Files },
  { view: "upload", label: "Upload worksheet", icon: ScanLine },
  { view: "review", label: "Review queue", icon: Inbox },
] as const;
const headings: Record<View, [string, string]> = {
  dashboard: [
    "A clearer grading day.",
    "Keep paper practice moving. Spend your time on the answers that need you.",
  ],
  templates: [
    "Configure once. Reuse every scan.",
    "Give each worksheet its answer regions and an exact answer key.",
  ],
  upload: [
    "Paper in. Answers out.",
    "Choose a student and template, then upload one completed worksheet page.",
  ],
  review: [
    "Your judgment, where it matters.",
    "Resolve uncertain answers in a few keystrokes. We’ll handle the next one.",
  ],
  results: [
    "Worksheet results",
    "A clear record of automated decisions and human review.",
  ],
};

export default function Workspace() {
  const [view, setView] = useState<View>("dashboard");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [activeTemplate, setActiveTemplate] = useState<Template | null>(null);
  const [activeSubmission, setActiveSubmission] = useState("");
  const [studentId, setStudentId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [synthetic, setSynthetic] = useState(false);
  const [showStudent, setShowStudent] = useState(false);
  const [pendingSubmission, setPendingSubmission] = useState("");
  const load = useCallback(async () => {
    try {
      const [m, t, s, w] = await Promise.all([
        api<Metrics>("/metrics"),
        api<Template[]>("/templates"),
        api<Student[]>("/students"),
        api<Submission[]>("/submissions"),
      ]);
      setMetrics(m);
      setTemplates(t);
      setStudents(s);
      setSubmissions(w);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);
  const changed = useCallback(() => {
    setRefreshKey((k) => k + 1);
    void load();
  }, [load]);
  function navigate(next: View) {
    setView(next);
    setNotice("");
    setError("");
  }
  function openSubmission(id: string) {
    setActiveSubmission(id);
    navigate("results");
  }
  async function action(name: string, work: () => Promise<void>) {
    setBusy(name);
    setError("");
    setNotice("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function demo() {
    await action("Preparing demo", async () => {
      const ids = await api<{ template_id: string; student_id: string }>(
        "/demo/setup",
        post(),
      );
      await load();
      setTemplateId(ids.template_id);
      setStudentId(ids.student_id);
      setSynthetic(true);
      setView("upload");
      setNotice(
        "Demo template and student are ready. Download the completed sample below, select it, and process with synthetic OCR enabled.",
      );
    });
  }
  async function createTemplate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const body = new FormData(form);
    await action("Creating template", async () => {
      const t = await api<Template>("/templates", { method: "POST", body });
      setActiveTemplate(t);
      await load();
      form.reset();
    });
  }
  async function createStudent(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    await action("Creating student", async () => {
      const student = await api<Student>(
        "/students",
        post({
          first_name: data.get("first_name"),
          external_id: data.get("external_id") || null,
        }),
      );
      await load();
      setStudentId(student.id);
      setShowStudent(false);
      form.reset();
      setNotice("Demo student created.");
    });
  }
  async function process(id: string) {
    await api<Submission>(`/submissions/${id}/process`, post());
    setPendingSubmission("");
    await load();
    openSubmission(id);
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    data.set("synthetic_demo", String(synthetic));
    await action("Processing worksheet", async () => {
      const submission = await api<Submission>("/submissions", {
        method: "POST",
        body: data,
      });
      setPendingSubmission(submission.id);
      await process(submission.id);
    });
  }
  const configured = templates.filter((t) => t.questions.length > 0);
  return (
    <div className="workspace">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("dashboard");
          }}
        >
          <span className="brand-mark">
            <GraduationCap size={23} />
          </span>
          GradeKade
        </a>
        <div className="center-name">
          Demo learning center<span>Local workspace</span>
        </div>
        <nav aria-label="Main navigation">
          <Link href="/scan" className="nav-item scan-nav">
            <ScanLine size={19} />
            Scan booklets
          </Link>
          <Link href="/booklets" className="nav-item">
            <Files size={19} />
            Saved booklets
          </Link>
          {navigation.map((item) => (
            <button
              key={item.view}
              className={view === item.view ? "nav-item active" : "nav-item"}
              aria-current={view === item.view ? "page" : undefined}
              onClick={() => navigate(item.view)}
            >
              <item.icon size={19} />
              {item.label}
              {item.view === "review" && !!metrics?.waiting_for_review && (
                <span className="nav-count">{metrics.waiting_for_review}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <span className="mode-dot" /> Development demo
          <p>Use fictional students and original sample worksheets.</p>
        </div>
      </aside>
      <main className="main-content">
        <div className="topbar">
          <span>Grading workspace</span>
          <div>
            <span className="badge neutral">
              {ocrLabel(metrics?.ocr_provider)}
            </span>
            <span className="avatar" aria-label="Local demo admin">
              GK
            </span>
          </div>
        </div>
        <div className="mobile-scan-entry">
          <Link href="/scan" className="primary">
            <ScanLine size={20} />
            Scan a booklet
            <ArrowRight size={18} />
          </Link>
        </div>
        <div className="privacy-strip">
          Development/demo use only. Do not upload identifiable student
          educational records until production privacy/security controls are
          completed.
        </div>
        <header className="page-header">
          <div>
            <h1>{headings[view][0]}</h1>
            <p>{headings[view][1]}</p>
          </div>
          {view === "dashboard" && (
            <button className="primary" onClick={() => navigate("upload")}>
              <Plus size={18} /> Upload worksheet
            </button>
          )}
          {view !== "review" && (
            <button
              className="icon-button"
              aria-label="Refresh workspace"
              disabled={loading || !!busy}
              onClick={() => {
                setLoading(true);
                void load();
              }}
            >
              <RefreshCw size={18} />
            </button>
          )}
        </header>
        {error && (
          <div role="alert" className="error">
            {error}
            {pendingSubmission && (
              <button
                className="secondary"
                disabled={!!busy}
                onClick={() =>
                  action("Retrying processing", () =>
                    process(pendingSubmission),
                  )
                }
              >
                Retry processing
              </button>
            )}
          </div>
        )}
        {notice && (
          <p role="status" className="notice">
            {notice}
          </p>
        )}
        {busy && (
          <p role="status" className="working">
            <span className="mode-dot" />
            {busy}…
          </p>
        )}
        {loading && !metrics ? (
          <p role="status">Connecting to the grading workspace…</p>
        ) : (
          <>
            {view === "dashboard" && (
              <>
                <section aria-label="Grading metrics" className="metrics-strip">
                  {[
                    [
                      metrics?.worksheets_processed ?? 0,
                      "Worksheets processed",
                    ],
                    [metrics?.answers_processed ?? 0, "Answers processed"],
                    [`${metrics?.auto_graded_percent ?? 0}%`, "Auto-graded"],
                    [
                      `${metrics?.human_review_percent ?? 0}%`,
                      "Require human review",
                    ],
                  ].map(([value, label]) => (
                    <div key={label}>
                      <span>{label}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </section>
                <section className="queue-banner">
                  <div className="queue-icon">
                    <Inbox size={25} />
                  </div>
                  <div>
                    <h2>
                      {metrics?.waiting_for_review
                        ? `${metrics.waiting_for_review} answers need a second look.`
                        : "Your review queue is clear."}
                    </h2>
                    <p>
                      {metrics?.waiting_for_review
                        ? "The confident answers are handled. These ones are ready for your judgment."
                        : "Upload a worksheet to start grading, or try the original arithmetic demo."}
                    </p>
                  </div>
                  <button
                    className="secondary"
                    onClick={() =>
                      navigate(
                        metrics?.waiting_for_review ? "review" : "upload",
                      )
                    }
                  >
                    {metrics?.waiting_for_review
                      ? "Start reviewing"
                      : "Upload a page"}
                    <ArrowRight size={17} />
                  </button>
                </section>
                <section>
                  <div className="section-bar">
                    <h2>Recent worksheets</h2>
                    <span className="muted">Latest 100 submissions</span>
                  </div>
                  {submissions.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Student</th>
                            <th>Worksheet</th>
                            <th>Status</th>
                            <th>Score</th>
                            <th>
                              <span className="sr-only">Open result</span>
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {submissions.map((s) => (
                            <tr key={s.id}>
                              <td>
                                <strong>{s.student_name}</strong>
                                <small>
                                  {new Date(s.created_at).toLocaleDateString()}
                                </small>
                              </td>
                              <td>{s.template_name}</td>
                              <td>
                                <GradeBadge status={s.status} />
                              </td>
                              <td>
                                {s.score_percent === null
                                  ? "Pending"
                                  : `${s.correct} / ${s.total}`}
                              </td>
                              <td>
                                <button
                                  className="text-button"
                                  onClick={() => openSubmission(s.id)}
                                  aria-label={`Open result for ${s.student_name}`}
                                >
                                  View <ArrowUpRight size={16} />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="empty-state compact">
                      <Files size={32} />
                      <h3>Your first worksheet starts here.</h3>
                      <p>
                        Configure a template, upload a completed page, and
                        review only the exceptions.
                      </p>
                      <button
                        className="primary"
                        disabled={!!busy}
                        onClick={demo}
                      >
                        Set up the arithmetic demo <ArrowRight size={17} />
                      </button>
                    </div>
                  )}
                </section>
                <div className="demo-footnote">
                  <p>
                    <strong>Test the workflow without an OCR account.</strong>{" "}
                    The original demo uses explicit synthetic OCR predictions;
                    it does not measure handwriting accuracy.
                  </p>
                  <button
                    className="text-button"
                    disabled={!!busy}
                    onClick={demo}
                  >
                    Prepare demo <ArrowRight size={16} />
                  </button>
                </div>
              </>
            )}
            {view === "templates" && (
              <>
                <form className="inline-form" onSubmit={createTemplate}>
                  <label>
                    Template name
                    <input
                      name="name"
                      placeholder="e.g. Arithmetic Practice A"
                      required
                      maxLength={160}
                    />
                  </label>
                  <label>
                    Blank worksheet
                    <input
                      type="file"
                      name="file"
                      accept="image/png,image/jpeg,application/pdf"
                      required
                    />
                  </label>
                  <button className="primary" disabled={!!busy}>
                    Create template
                  </button>
                </form>
                <div className="sample-links">
                  <span>Use our original sample:</span>
                  <a href="/api/samples/blank.png" download>
                    <Download size={15} /> Blank PNG
                  </a>
                  <a href="/api/samples/blank.pdf" download>
                    Blank PDF
                  </a>
                  <a href="/api/samples/answer_key.csv" download>
                    Answer key
                  </a>
                </div>
                {templates.length > 0 && (
                  <label className="template-select">
                    Open template
                    <select
                      aria-label="Open template"
                      value={activeTemplate?.id ?? ""}
                      onChange={(e) =>
                        setActiveTemplate(
                          templates.find((t) => t.id === e.target.value) ||
                            null,
                        )
                      }
                    >
                      <option value="">Choose a template…</option>
                      {templates.map((t) => (
                        <option key={t.id} value={t.id}>
                          {t.name} · {t.questions.length} boxes
                          {t.locked ? " · locked" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
                {activeTemplate ? (
                  <TemplateEditor
                    key={activeTemplate.id}
                    template={activeTemplate}
                    saved={(t) => {
                      setActiveTemplate(t);
                      void load();
                    }}
                  />
                ) : (
                  <div className="empty-state compact">
                    <Files size={32} />
                    <h2>One setup, every future scan.</h2>
                    <p>
                      Upload a blank page, draw answer boxes, and enter the key.
                      Your template will be ready to reuse.
                    </p>
                  </div>
                )}
              </>
            )}
            {view === "upload" && (
              <div className="upload-layout">
                <section>
                  <form className="field-stack upload-form" onSubmit={upload}>
                    <h2>Completed worksheet</h2>
                    <label>
                      Student
                      <select
                        aria-label="Student"
                        name="student_id"
                        value={studentId}
                        onChange={(e) => setStudentId(e.target.value)}
                        required
                      >
                        <option value="">Choose a student…</option>
                        {students.map((s) => (
                          <option key={s.id} value={s.id}>
                            {s.first_name} {s.last_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      type="button"
                      className="text-button"
                      onClick={() => setShowStudent(!showStudent)}
                    >
                      <Plus size={16} /> Add a demo student
                    </button>
                    <label>
                      Worksheet template
                      <select
                        aria-label="Worksheet template"
                        name="worksheet_template_id"
                        value={templateId}
                        onChange={(e) => setTemplateId(e.target.value)}
                        required
                      >
                        <option value="">Choose a configured template…</option>
                        {configured.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name} · {t.questions.length} questions
                          </option>
                        ))}
                      </select>
                    </label>
                    {!configured.length && (
                      <p className="notice">
                        Create and save a template first.{" "}
                        <button
                          type="button"
                          className="text-button"
                          onClick={() => navigate("templates")}
                        >
                          Open templates
                        </button>
                      </p>
                    )}
                    <label className="upload-area">
                      <ScanLine size={29} />
                      <strong>Choose a completed page</strong>
                      <span>
                        JPG, PNG or PDF · 10 MB maximum · first PDF page only
                      </span>
                      <input
                        aria-label="Completed worksheet file"
                        name="file"
                        type="file"
                        accept="image/png,image/jpeg,application/pdf"
                        required
                      />
                    </label>
                    <label className="check-label">
                      <input
                        type="checkbox"
                        checked={synthetic}
                        onChange={(e) => setSynthetic(e.target.checked)}
                      />{" "}
                      Use synthetic OCR for the supplied sample only
                    </label>
                    <p className="muted">
                      {synthetic
                        ? "Only the exact original blank and completed demo PNGs are supported. OCR predictions are simulated."
                        : ocrDescription(metrics?.ocr_provider)}
                    </p>
                    <button
                      className="primary"
                      disabled={!!busy || !studentId || !templateId}
                    >
                      Upload & process worksheet <ArrowRight size={17} />
                    </button>
                  </form>
                  {showStudent && (
                    <form
                      className="new-student field-stack"
                      onSubmit={createStudent}
                    >
                      <h3>Add a demo student</h3>
                      <label>
                        First name or display identifier
                        <input
                          name="first_name"
                          required
                          maxLength={80}
                          placeholder="Demo learner 01"
                        />
                      </label>
                      <label>
                        External ID (optional)
                        <input name="external_id" maxLength={80} />
                      </label>
                      <button className="secondary" disabled={!!busy}>
                        Save student
                      </button>
                    </form>
                  )}
                </section>
                <aside className="upload-guide">
                  <h2>A useful first scan</h2>
                  <ol>
                    <li>Use the same worksheet as the selected template.</li>
                    <li>Keep all four page edges in view.</li>
                    <li>Use a flat, well-lit page with readable answers.</li>
                    <li>Check any alignment warning before reviewing.</li>
                  </ol>
                  <div className="sample-download">
                    <h3>Try Arithmetic Practice A</h3>
                    <p>
                      20 original questions covering integers, decimals and
                      simple fractions. Includes deliberate mistakes and
                      uncertain OCR.
                    </p>
                    <button
                      className="secondary"
                      disabled={!!busy}
                      onClick={demo}
                    >
                      Prepare sample template <Check size={16} />
                    </button>
                    <a
                      className="download-link"
                      href="/api/samples/completed.png"
                      download
                    >
                      <Download size={17} /> Download completed sample
                    </a>
                  </div>
                </aside>
              </div>
            )}
            {view === "review" && (
              <ReviewDesk changed={changed} openSubmission={openSubmission} />
            )}
            {view === "results" && (
              <>
                <div className="section-bar">
                  <button
                    className="text-button"
                    onClick={() => navigate("dashboard")}
                  >
                    Back to overview
                  </button>
                  {submissions.find((s) => s.id === activeSubmission)
                    ?.status === "uploaded" ||
                  submissions.find((s) => s.id === activeSubmission)?.status ===
                    "failed" ? (
                    <button
                      className="primary"
                      disabled={!!busy}
                      onClick={() =>
                        action("Processing worksheet", () =>
                          process(activeSubmission),
                        )
                      }
                    >
                      Process worksheet
                    </button>
                  ) : null}
                </div>
                <Results
                  id={activeSubmission}
                  refreshKey={refreshKey}
                  review={() => navigate("review")}
                />
              </>
            )}
          </>
        )}
        <Link href="/evaluation">Internal grading evaluation</Link>
        <footer className="workspace-footer">
          GradeKade 0.1{" "}
          <span>Paper practice. Human judgment. Less repetition.</span>
        </footer>
      </main>
    </div>
  );
}
