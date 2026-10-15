"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { ocrLabel, ocrDescription } from "@/lib/ocr";
export default function OCRMode() {
  const [mode, setMode] = useState<{
    ocr_provider: string;
    ocr_fallback: boolean;
    ocr_available?: boolean;
    ocr_diagnostic?: string | null;
    experimental_auto_grade?: boolean;
  } | null>(null);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => {
    api<NonNullable<typeof mode>>("/health")
      .then(setMode)
      .catch(() => setUnavailable(true));
  }, []);
  return (
    <div className="ocr-mode-banner" role="status">
      {mode
        ? mode.ocr_available === false
          ? `${ocrLabel(mode.ocr_provider)} · UNAVAILABLE. ${mode.ocr_diagnostic ?? "Check the local OCR installation."}`
          : mode.ocr_provider === "mock"
            ? `MOCK OCR · No handwriting recognition.${mode.ocr_fallback ? " Mathpix credentials are missing; fallback is active." : ""}`
            : `${ocrLabel(mode.ocr_provider)} · ${ocrDescription(mode.ocr_provider)}${mode.ocr_provider === "paddle" ? (mode.experimental_auto_grade ? " Experimental agreement-based auto-grading is enabled." : " Automatic grading is off; OCR suggestions require human review.") : ""}`
        : unavailable
          ? "OCR provider unavailable. Check that the backend is running."
          : "Checking OCR provider…"}{" "}
      Synthetic demo pages always use simulated predictions.
    </div>
  );
}
