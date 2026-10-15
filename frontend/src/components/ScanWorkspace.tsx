"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  Camera,
  Check,
  CheckCheck,
  ChevronLeft,
  ChevronRight,
  Files,
  ImagePlus,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { api, post, Student, Template, Submission, Booklet } from "@/lib/api";
import {
  newId,
  CapturedPage,
  ScanDraft,
  emptyDraft,
  loadDraft,
  saveDraft,
  deleteDraft,
} from "@/lib/scan-draft";

function PageImage({ blob, label }: { blob: Blob; label: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const u = URL.createObjectURL(blob);
    setUrl(u);
    return () => URL.revokeObjectURL(u);
  }, [blob]);
  return url ? <img src={url} alt={label} /> : null;
}
export default function ScanWorkspace() {
  const [draft, setDraft] = useState<ScanDraft | null>(null);
  const current = useRef<ScanDraft | null>(null);
  const saving = useRef<Promise<unknown>>(Promise.resolve());
  const [students, setStudents] = useState<Student[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [provider, setProvider] = useState("mock");
  const [selected, setSelected] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [progress, setProgress] = useState("");
  const [live, setLive] = useState(false);
  const [cameraBusy, setCameraBusy] = useState(false);
  const [showPreview, setShowPreview] = useState(true);
  const [retake, setRetake] = useState<string | null>(null);
  const [discarding, setDiscarding] = useState(false);
  const [booklet, setBooklet] = useState<Booklet | null>(null);
  const stage = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const mounted = useRef(true);
  const cameraGeneration = useRef(0);
  const picker = useRef<HTMLInputElement>(null);
  const retakePicker = useRef<HTMLInputElement>(null);
  const working = useRef(false);
  useEffect(() => {
    if ((live || draft?.pages.length) && window.innerWidth <= 700)
      requestAnimationFrame(() =>
        stage.current?.scrollIntoView({ block: "start" }),
      );
  }, [live, showPreview, selected, draft?.pages.length]);
  useEffect(() => {
    mounted.current = true;
    Promise.all([
      loadDraft(),
      api<Student[]>("/students"),
      api<Template[]>("/templates"),
      api<{ ocr_provider: string }>("/health"),
    ])
      .then(([stored, s, t, h]) => {
        if (!mounted.current) return;
        const value = stored || emptyDraft();
        current.current = value;
        setDraft(value);
        setSelected(Math.max(0, value.pages.length - 1));
        setStudents(s);
        setTemplates(t.filter((item) => item.questions.length));
        setProvider(h.ocr_provider);
        setSaved(!!stored);
      })
      .catch((e) => setError(e.message));
    return () => {
      mounted.current = false;
      cameraGeneration.current++;
      stream.current?.getTracks().forEach((t) => t.stop());
    };
  }, []);
  function update(value: ScanDraft) {
    current.current = value;
    setDraft(value);
    setSaved(false);
    saving.current = saving.current
      .catch(() => {})
      .then(() => saveDraft(value))
      .then(() => {
        if (mounted.current && current.current === value) setSaved(true);
      })
      .catch((e) => {
        if (mounted.current) setError(e.message);
        throw e;
      });
    // Handle rejection even when the user is not submitting yet.
    void saving.current.catch(() => {});
  }
  function stopCamera() {
    cameraGeneration.current++;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    setLive(false);
    setCameraBusy(false);
  }
  async function openCamera(replacement: string | null = null) {
    setError("");
    setRetake(replacement);
    setShowPreview(false);
    if (current.current?.synthetic)
      update({ ...current.current, synthetic: false });
    if (stream.current) {
      setLive(true);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        "Live camera needs HTTPS on a phone. Use Choose photos / camera, or try localhost on this computer.",
      );
      return;
    }
    const generation = ++cameraGeneration.current;
    setCameraBusy(true);
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 2400 },
          height: { ideal: 3200 },
        },
      });
      if (!mounted.current || generation !== cameraGeneration.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = media;
      setLive(true);
      if (video.current) {
        video.current.srcObject = media;
        await video.current.play();
      }
    } catch {
      if (mounted.current && generation === cameraGeneration.current) {
        setError(
          "Camera couldn’t start. Allow camera access, or use Choose photos / camera.",
        );
        setShowPreview(true);
      }
    } finally {
      if (mounted.current && generation === cameraGeneration.current)
        setCameraBusy(false);
    }
  }
  async function addFiles(
    files: File[] | Blob[],
    replacement: string | null = null,
  ) {
    const value = current.current;
    if (!value || value.submitted || working.current) return;
    setError("");
    if (
      files.some(
        (f) =>
          !["image/jpeg", "image/png"].includes(f.type) ||
          f.size > 10 * 1024 * 1024,
      )
    ) {
      setError(
        "Use JPG or PNG images up to 10 MB each. Export HEIC photos as JPG first.",
      );
      return;
    }
    if (value.pages.length + files.length - (replacement ? 1 : 0) > 30) {
      setError("A booklet can contain up to 30 pages.");
      return;
    }
    const pages = files.map((blob, i): CapturedPage => ({
      id: newId(),
      blob,
      templateId: value.templateId,
      name:
        blob instanceof File
          ? blob.name
          : `Camera page ${value.pages.length + i + 1}`,
    }));
    const next = replacement
      ? value.pages.map((p) =>
          p.id === replacement ? { ...pages[0], templateId: p.templateId } : p,
        )
      : [...value.pages, ...pages];
    setSelected(
      replacement
        ? Math.max(
            0,
            value.pages.findIndex((p) => p.id === replacement),
          )
        : next.length - 1,
    );
    update({ ...value, pages: next, startedAt: value.startedAt ?? Date.now() });
    setRetake(null);
    setShowPreview(true);
  }
  async function capture() {
    if (!video.current?.videoWidth || !current.current || working.current)
      return;
    setBusy(true);
    try {
      const canvas = document.createElement("canvas");
      canvas.width = video.current.videoWidth;
      canvas.height = video.current.videoHeight;
      canvas.getContext("2d")!.drawImage(video.current, 0, 0);
      const blob = await new Promise<Blob | null>((resolve) =>
        canvas.toBlob(resolve, "image/jpeg", 0.92),
      );
      if (blob) await addFiles([blob], retake);
    } catch {
      setError("Could not capture the page. Try again or choose a photo.");
    } finally {
      setBusy(false);
    }
  }
  async function setupDemo() {
    setBusy(true);
    setError("");
    try {
      const ids = await api<{ student_id: string; template_id: string }>(
        "/demo/setup",
        post(),
      );
      const [s, t] = await Promise.all([
        api<Student[]>("/students"),
        api<Template[]>("/templates"),
      ]);
      setStudents(s);
      setTemplates(t.filter((x) => x.questions.length));
      update({
        ...current.current!,
        studentId: ids.student_id,
        templateId: ids.template_id,
        synthetic: true,
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function addSample() {
    try {
      const response = await fetch("/api/samples/completed.png");
      if (!response.ok) throw new Error("Sample download failed");
      await addFiles([
        new File([await response.blob()], "Original demo page.png", {
          type: "image/png",
        }),
      ]);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function submit() {
    const value = current.current;
    if (!value || working.current || !value.pages.length) return;
    working.current = true;
    setBusy(true);
    setError("");
    stopCamera();
    setBooklet(null);
    try {
      await saving.current;
      const frozen = {
        ...value,
        submitted: true,
        captureSeconds:
          value.captureSeconds ??
          Math.min(
            86400,
            (Date.now() - (value.startedAt || Date.now())) / 1000,
          ),
      };
      update(frozen);
      await saving.current;
      await api<Booklet>(
        "/booklets",
        post({
          id: frozen.id,
          student_id: frozen.studentId,
          page_count: frozen.pages.length,
          capture_seconds: frozen.captureSeconds,
          synthetic_demo: frozen.synthetic,
        }),
      );
      for (let i = 0; i < frozen.pages.length; i++) {
        const page = frozen.pages[i];
        setProgress(`Uploading page ${i + 1} of ${frozen.pages.length}`);
        const data = new FormData();
        data.set("file", page.blob, page.name);
        data.set("template_id", page.templateId);
        data.set("page_number", String(i + 1));
        await api<Submission>(`/booklets/${frozen.id}/pages/${page.id}`, {
          method: "POST",
          body: data,
        });
      }
      for (let i = 0; i < frozen.pages.length; i++) {
        setProgress(`Processing page ${i + 1} of ${frozen.pages.length}`);
        let polling = false;
        const stageTimer = setInterval(async () => {
          if (polling) return;
          polling = true;
          try {
            const page = await api<Submission>(
              `/submissions/${frozen.pages[i].id}`,
            );
            const labels: Record<string, string> = {
              aligning: "Aligning",
              cropping: "Cropping",
              recognizing: "Recognizing handwriting",
              grading: "Grading",
              needs_review: "Needs review",
              completed: "Completed",
              failed: "Failed",
            };
            const stage = page.processing?.stage ?? page.status;
            setProgress(
              `${labels[stage] ?? "Processing"} · page ${i + 1} of ${frozen.pages.length}${stage === "recognizing" ? ` · ${page.processing?.questions_recognized ?? 0}/${page.processing?.questions_total ?? "?"} answers` : ""}`,
            );
          } catch {
            /* The process response remains authoritative. */
          } finally {
            polling = false;
          }
        }, 1000);
        try {
          await api<Submission>(
            `/submissions/${frozen.pages[i].id}/process`,
            post(),
          );
        } catch {
          /* Continue other pages. Persisted results expose retry per page. */
        } finally {
          clearInterval(stageTimer);
        }
      }
      const result = await api<Booklet>(`/booklets/${frozen.id}`);
      setBooklet(result);
      setProgress("");
      // Every upload is acknowledged; retries and results now live on the server.
      await deleteDraft();
      setSaved(false);
    } catch (e) {
      setError(
        `${(e as Error).message} Your pages are kept on this device. Resume safely below.`,
      );
      setProgress("");
    } finally {
      working.current = false;
      setBusy(false);
    }
  }
  if (!draft)
    return (
      <main className="scan-shell">
        <h1>Scan a booklet</h1>
        {error ? (
          <p role="alert" className="error">
            {error}
          </p>
        ) : (
          <p role="status">Loading your scanning desk…</p>
        )}
      </main>
    );
  const page = draft.pages[selected];
  const configured = !!draft.studentId && !!draft.templateId;
  return (
    <div className="scan-app">
      <header className="scan-header">
        <Link href="/" aria-label="Back to workspace">
          <ArrowLeft size={20} />
        </Link>
        <Link href="/scan" className="scan-wordmark">
          GradeKade
        </Link>
        <span className="badge neutral">
          {draft.synthetic
            ? "Synthetic demo"
            : provider === "mathpix"
              ? "Mathpix OCR"
              : "Mock OCR"}
        </span>
      </header>
      <main className="scan-shell">
        <div className="scan-title">
          <div>
            <h1>Scan a booklet</h1>
            <p>One student. All their pages. Review only what needs you.</p>
          </div>
          <span className="page-counter">
            {draft.pages.length}
            <small>pages</small>
          </span>
        </div>
        <p className="scan-privacy">
          Demo only · use fictional students and original practice sheets.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {booklet ? (
          <section className="scan-finished">
            <CheckCheck size={35} />
            <h2>
              {booklet.processed_pages === booklet.page_count
                ? "Booklet processed"
                : "Pages saved. Some need another try."}
            </h2>
            <p>
              {booklet.auto_graded} of {booklet.answers_total} answers
              auto-graded · {booklet.waiting} need review.
            </p>
            <Link className="primary" href={`/booklets/${booklet.id}`}>
              Open booklet & review <ArrowRight size={18} />
            </Link>
            <button
              className="secondary"
              onClick={() => {
                const next = {
                  ...emptyDraft(),
                  studentId: draft.studentId,
                  templateId: draft.templateId,
                  synthetic: draft.synthetic,
                };
                update(next);
                setBooklet(null);
                setSelected(0);
              }}
            >
              Start another booklet
            </button>
          </section>
        ) : (
          <>
            <section className="scan-settings">
              <label>
                Student
                <select
                  aria-label="Scan student"
                  value={draft.studentId}
                  disabled={busy || draft.submitted}
                  onChange={(e) =>
                    update({ ...draft, studentId: e.target.value })
                  }
                >
                  <option value="">Choose a student</option>
                  {students.map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.first_name} {s.last_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Default worksheet
                <select
                  aria-label="Scan worksheet"
                  value={draft.templateId}
                  disabled={busy || draft.submitted}
                  onChange={(e) =>
                    update({ ...draft, templateId: e.target.value })
                  }
                >
                  <option value="">Choose a configured template</option>
                  {templates.map((t) => (
                    <option value={t.id} key={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              </label>
            </section>
            {!configured && (
              <div className="scan-setup">
                <p>
                  Choose a student and worksheet above, or try the original
                  arithmetic demo.
                </p>
                <button
                  className="secondary"
                  disabled={busy || draft.submitted}
                  onClick={setupDemo}
                >
                  Set up sample student & template
                </button>
                <Link href="/">Manage students and templates</Link>
              </div>
            )}
            <div className="capture-layout">
              <section className="capture-desk">
                <div
                  ref={stage}
                  className={`camera-stage ${page && showPreview ? "has-page" : ""}`}
                >
                  <video
                    ref={video}
                    autoPlay
                    muted
                    playsInline
                    hidden={!live || showPreview}
                    onLoadedMetadata={() =>
                      video.current?.play().catch(() => {})
                    }
                  />
                  {live && !showPreview && (
                    <div className="camera-guide">
                      <span>Keep all four edges inside the frame</span>
                    </div>
                  )}
                  {page && showPreview ? (
                    <PageImage
                      blob={page.blob}
                      label={`Captured page ${selected + 1}`}
                    />
                  ) : (
                    !live && (
                      <div className="capture-empty">
                        <Camera size={42} />
                        <h2>
                          {cameraBusy
                            ? "Waiting for camera…"
                            : "Ready for the first page"}
                        </h2>
                        <p>
                          Lay the page flat. Keep the full sheet in view and
                          check that every answer is readable.
                        </p>
                      </div>
                    )
                  )}
                </div>
                {live && !showPreview ? (
                  <div className="capture-actions">
                    <button
                      className="primary shutter"
                      disabled={busy || cameraBusy || draft.submitted}
                      onClick={capture}
                    >
                      <Camera size={23} />
                      {retake ? "Replace page" : "Capture page"}
                    </button>
                    <button
                      className="secondary"
                      onClick={() => {
                        stopCamera();
                        setShowPreview(true);
                      }}
                    >
                      Close camera
                    </button>
                  </div>
                ) : (
                  <div className="capture-actions">
                    <button
                      className="primary"
                      disabled={!configured || busy || draft.submitted}
                      onClick={() => openCamera()}
                    >
                      <Camera size={21} />
                      {page ? "Capture next page" : "Open camera"}
                    </button>
                    <button
                      className="secondary"
                      disabled={!configured || busy || draft.submitted}
                      onClick={() => picker.current?.click()}
                    >
                      <ImagePlus size={19} />
                      Choose photos / camera
                    </button>
                  </div>
                )}
                <input
                  ref={picker}
                  type="file"
                  className="sr-only"
                  aria-label="Add worksheet photos"
                  accept="image/jpeg,image/png"
                  multiple
                  onChange={(e) => {
                    void addFiles(Array.from(e.target.files || []));
                    e.target.value = "";
                  }}
                />
                <input
                  ref={retakePicker}
                  type="file"
                  className="sr-only"
                  aria-label="Replace worksheet photo"
                  accept="image/jpeg,image/png"
                  capture="environment"
                  onChange={(e) => {
                    if (e.target.files?.[0])
                      void addFiles([e.target.files[0]], page?.id);
                    e.target.value = "";
                  }}
                />
                {page && (
                  <div className="page-check">
                    <Check size={17} />
                    <span>
                      Check sharpness, glare and page edges before continuing.
                    </span>
                    <button
                      disabled={busy || draft.submitted}
                      className="text-button"
                      onClick={() => retakePicker.current?.click()}
                    >
                      <RotateCcw size={16} />
                      Retake
                    </button>
                  </div>
                )}
              </section>
              <section className="scan-pages">
                <div className="section-bar">
                  <h2>Pages in this booklet</h2>
                  <span className="muted">{draft.pages.length} / 30</span>
                </div>
                {!draft.pages.length && (
                  <p className="muted">
                    Each capture appears here in order. You can retake, reorder,
                    or choose a different template for a page.
                  </p>
                )}
                <div className="page-strip">
                  {draft.pages.map((p, i) => (
                    <button
                      key={p.id}
                      className={`page-tile ${i === selected ? "active" : ""}`}
                      aria-label={`Preview page ${i + 1}`}
                      onClick={() => {
                        setSelected(i);
                        setShowPreview(true);
                      }}
                    >
                      <PageImage
                        blob={p.blob}
                        label={`Page ${i + 1} thumbnail`}
                      />
                      <span>Page {i + 1}</span>
                    </button>
                  ))}
                </div>
                {page && (
                  <div className="page-options">
                    <label>
                      Template for page {selected + 1}
                      <select
                        aria-label="Page worksheet template"
                        value={page.templateId}
                        disabled={busy || draft.submitted}
                        onChange={(e) =>
                          update({
                            ...draft,
                            pages: draft.pages.map((p) =>
                              p.id === page.id
                                ? { ...p, templateId: e.target.value }
                                : p,
                            ),
                          })
                        }
                      >
                        {templates.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <div className="page-tools">
                      <button
                        className="secondary"
                        aria-label="Move page earlier"
                        disabled={selected === 0 || busy || draft.submitted}
                        onClick={() => {
                          const pages = [...draft.pages];
                          [pages[selected - 1], pages[selected]] = [
                            pages[selected],
                            pages[selected - 1],
                          ];
                          update({ ...draft, pages });
                          setSelected(selected - 1);
                        }}
                      >
                        <ChevronLeft size={18} />
                      </button>
                      <button
                        className="secondary"
                        aria-label="Move page later"
                        disabled={
                          selected === draft.pages.length - 1 ||
                          busy ||
                          draft.submitted
                        }
                        onClick={() => {
                          const pages = [...draft.pages];
                          [pages[selected + 1], pages[selected]] = [
                            pages[selected],
                            pages[selected + 1],
                          ];
                          update({ ...draft, pages });
                          setSelected(selected + 1);
                        }}
                      >
                        <ChevronRight size={18} />
                      </button>
                      <button
                        className="text-button danger-text"
                        disabled={busy || draft.submitted}
                        onClick={() => {
                          update({
                            ...draft,
                            pages: draft.pages.filter((p) => p.id !== page.id),
                          });
                          setSelected(Math.max(0, selected - 1));
                        }}
                      >
                        <Trash2 size={16} />
                        Remove page
                      </button>
                    </div>
                  </div>
                )}
                <div className="ocr-choice">
                  <label className="check-label">
                    <input
                      type="checkbox"
                      disabled={busy || draft.submitted}
                      checked={draft.synthetic}
                      onChange={(e) =>
                        update({ ...draft, synthetic: e.target.checked })
                      }
                    />
                    Synthetic OCR for original sample pages only
                  </label>
                  <p>
                    {draft.synthetic
                      ? "Simulated predictions. Camera photos must use this option off."
                      : provider === "mathpix"
                        ? "Answer crops will be sent to Mathpix."
                        : "Mock OCR is active. All photographed answers will need human review."}
                  </p>
                  {draft.synthetic && configured && !draft.submitted && (
                    <button
                      className="text-button"
                      disabled={busy}
                      onClick={addSample}
                    >
                      <Files size={17} />
                      Add original demo page
                    </button>
                  )}
                </div>
              </section>
            </div>
            <div className="scan-submit">
              <div>
                <strong>
                  {busy
                    ? progress || "Saving booklet…"
                    : `${draft.pages.length} ${draft.pages.length === 1 ? "page" : "pages"} ready`}
                </strong>
                <span role="status">
                  {saved
                    ? "Draft saved on this device"
                    : busy
                      ? "Keep this tab open while submitting"
                      : draft.pages.length
                        ? "Saving locally…"
                        : "No pages captured yet"}
                </span>
              </div>
              <button
                className="primary"
                disabled={busy || !configured || !draft.pages.length}
                onClick={submit}
              >
                {draft.submitted
                  ? "Resume upload & processing"
                  : "Submit booklet"}
                <ArrowRight size={18} />
              </button>
            </div>
            <div className="scan-bottom">
              {draft.submitted && !busy && (
                <button
                  className="secondary"
                  onClick={() => {
                    update({
                      ...draft,
                      id: newId(),
                      submitted: false,
                      pages: draft.pages.map((p) => ({
                        ...p,
                        id: newId(),
                      })),
                    });
                    setError("");
                  }}
                >
                  Create editable copy to fix a page
                </button>
              )}
              <p>
                Draft photos stay in this browser until submitted. Browser
                storage can be cleared; this is not a backup.
              </p>
              <button
                className="text-button danger-text"
                disabled={busy}
                onClick={() => setDiscarding(true)}
              >
                Discard local draft
              </button>
              {discarding && (
                <div className="discard-confirm">
                  <p>
                    Discard these local photos? Uploaded pages remain available
                    in Booklets.
                  </p>
                  <button
                    className="secondary"
                    onClick={() => setDiscarding(false)}
                  >
                    Keep draft
                  </button>
                  <button
                    className="incorrect-button"
                    onClick={async () => {
                      stopCamera();
                      await saving.current.catch(() => {});
                      await deleteDraft();
                      const next = emptyDraft();
                      current.current = next;
                      setDraft(next);
                      setSelected(0);
                      setDiscarding(false);
                      setSaved(false);
                      setError("");
                    }}
                  >
                    Discard draft
                  </button>
                </div>
              )}
            </div>
          </>
        )}
        <Link className="text-button" href="/booklets">
          Open saved booklets <ArrowRight size={16} />
        </Link>
      </main>
    </div>
  );
}
