export function ocrLabel(provider?: string) {
  if (provider === "paddle") return "REAL OCR · PaddleOCR";
  if (provider === "mathpix") return "REAL OCR · Mathpix";
  if (provider === "synthetic_fixture") return "Synthetic OCR (simulated)";
  if (provider === "mock") return "MOCK OCR";
  return "Checking OCR provider";
}
export function ocrDescription(provider?: string) {
  if (provider === "paddle")
    return "PaddleOCR recognizes answer crops locally on CPU. No OCR API keys are needed.";
  if (provider === "mathpix")
    return "Answer crops will be sent to Mathpix for recognition.";
  return "Mock OCR is active. All photographed answers will need human review.";
}
