export type AnswerType = "integer" | "decimal" | "fraction";
export type Question = {id?: string; question_number: number; x: number; y: number; width: number; height: number; expected_answer: string; answer_type: AnswerType; auto_grade_enabled: boolean};
export type Template = {id: string; name: string; version: number; width: number; height: number; image_url: string; locked: boolean; questions: Question[]};
export type Student = {id: string; first_name: string; last_name: string | null; external_id: string | null};
export type Answer = {id: string; submission_id: string; question_number: number; crop_url: string; raw_ocr_text: string; normalized_answer: string | null; expected_answer: string; ocr_confidence: number; grading_confidence: number; system_grade: string; final_grade: string | null; review_status: string; human_override: boolean; reviewed_answer: string | null; routing_reason: string; ocr_provider: string; student_name?: string};
export type Submission = {id: string; student_name: string; template_name: string; status: string; created_at: string; finalized_at: string | null; correct: number; total: number; score_percent: number | null; waiting: number; original_url: string; aligned_url: string | null; alignment: {verified: boolean; reason: string; inlier_ratio: number} | null; processing: {ocr_provider: string; threshold: number} | null; error: string | null; answers: Answer[]};
export type Metrics = {worksheets_processed: number; answers_processed: number; auto_graded_percent: number; human_review_percent: number; waiting_for_review: number; ocr_provider: string};
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try { response = await fetch(`/api${path}`, { ...options, cache: "no-store", headers: options.body instanceof FormData ? options.headers : { "Content-Type": "application/json", ...options.headers } }); }
  catch { throw new Error("Cannot reach the backend. Start FastAPI on port 8000, then retry."); }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = data?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d: {msg: string}) => d.msg).join(". ") : "Request failed. Check the backend and retry.");
  }
  return data as T;
}
export const post = (body?: unknown): RequestInit => ({method: "POST", ...(body === undefined ? {} : {body: JSON.stringify(body)})});
