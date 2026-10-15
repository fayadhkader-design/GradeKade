"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Files } from "lucide-react";
import { api, Booklet } from "@/lib/api";
import { GradeBadge } from "@/components/Results";
export default function BookletsPage() {
  const [items, setItems] = useState<Booklet[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Booklet[]>("/booklets")
      .then(setItems)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <div className="scan-app">
      <header className="scan-header">
        <Link href="/" aria-label="Back to workspace">
          <ArrowLeft size={20} />
        </Link>
        <span className="scan-wordmark">GradeKade</span>
        <Link className="primary" href="/scan">
          Scan booklet
        </Link>
      </header>
      <main className="booklet-shell">
        <h1>Saved booklets</h1>
        <p className="muted">
          Pick up review and retry processing from any device connected to this
          workspace.
        </p>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {!items && !error && <p role="status">Loading booklets…</p>}
        {items?.length === 0 && (
          <section className="empty-state">
            <Files size={35} />
            <h2>Your first booklet starts on your phone.</h2>
            <Link className="primary" href="/scan">
              Start scanning
              <ArrowRight size={18} />
            </Link>
          </section>
        )}
        <div className="booklet-links">
          {items?.map((b) => (
            <Link key={b.id} href={`/booklets/${b.id}`}>
              <div>
                <strong>{b.student_name}</strong>
                <span>
                  {b.page_count} pages · {b.waiting} answers waiting ·{" "}
                  {b.workflow.unresolved_count ?? "—"} corrections remaining
                </span>
              </div>
              <GradeBadge status={b.status} />
              <ArrowRight size={19} />
            </Link>
          ))}
        </div>
      </main>
    </div>
  );
}
