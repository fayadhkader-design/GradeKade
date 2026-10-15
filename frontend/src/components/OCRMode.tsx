"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
export default function OCRMode() {
  const [mode, setMode] = useState<{
    ocr_provider: string;
    ocr_fallback: boolean;
  } | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    api<{ ocr_provider: string; ocr_fallback: boolean }>("/health")
      .then(setMode)
      .catch(() => setUnavailable(true));
  }, []);
  return (
    <div className="ocr-mode-banner" role="status">
      {mode
        ? mode.ocr_provider === "mathpix"
          ? "REAL OCR · Mathpix · Photo uploads send answer crops to this provider."
          : `MOCK OCR · No handwriting recognition.${mode.ocr_fallback ? " Mathpix credentials are missing; fallback is active." : ""}`
        : unavailable
          ? "OCR provider unavailable. Check that the backend is running."
          : "Checking OCR provider…"}{" "}
      Synthetic demo pages always use simulated predictions.
    </div>
  );
}
