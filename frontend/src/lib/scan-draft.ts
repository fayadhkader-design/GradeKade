export function newId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join(
    "",
  );
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

/** One local demo draft. Images stay in this browser until upload; never localStorage/base64. */
export type CapturedPage = {
  id: string;
  blob: Blob;
  templateId: string;
  name: string;
};
export type ScanDraft = {
  id: string;
  studentId: string;
  templateId: string;
  pages: CapturedPage[];
  startedAt: number | null;
  captureSeconds: number | null;
  synthetic: boolean;
  submitted: boolean;
};
export const emptyDraft = (): ScanDraft => ({
  id: newId(),
  studentId: "",
  templateId: "",
  pages: [],
  startedAt: null,
  captureSeconds: null,
  synthetic: false,
  submitted: false,
});
function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("gradekade-scan", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("drafts");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(
        new Error(
          "Browser storage is unavailable. Keep this tab open and enable storage to preserve captures.",
        ),
      );
  });
}
async function transact<T>(
  mode: IDBTransactionMode,
  operation: (store: IDBObjectStore) => IDBRequest<T>,
) {
  const db = await database();
  return new Promise<T>((resolve, reject) => {
    const tx = db.transaction("drafts", mode);
    const request = operation(tx.objectStore("drafts"));
    tx.oncomplete = () => {
      db.close();
      resolve(request.result);
    };
    tx.onerror = () => {
      db.close();
      reject(
        new Error(
          "Could not save the scan draft. Free browser storage before closing this tab.",
        ),
      );
    };
    tx.onabort = tx.onerror;
  });
}
export const loadDraft = () =>
  transact("readonly", (store) => store.get("active")) as Promise<
    ScanDraft | undefined
  >;
export const saveDraft = (draft: ScanDraft) =>
  transact("readwrite", (store) => store.put(draft, "active"));
export const deleteDraft = () =>
  transact("readwrite", (store) => store.delete("active"));
