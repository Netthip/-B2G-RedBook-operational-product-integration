// เรียก JSON API ของแอปเดิม — CSRF แบบ double-submit (ขอโทเคนครั้งเดียว ส่งในหัว X-CSRF-Token)

export type Pen = "red" | "brown" | "pin";
export type Side = "cur" | "prev";

export interface Mark { id: string; side: Side; page: number; fx: number; fy: number; pen: Pen; topic: string; note: string }
export interface Book { id: string; title: string; agency: string; pair: string;
  status: { sid: string; state: "draft" | "locked" } | null }
export interface Session {
  sid: string; locked: boolean; locked_at: string; reviewer: string;
  book: { id: string; title: string; agency: string; pair: string;
          cur: { title: string; fy: number }; prev: { title: string; fy: number } };
  pages: { cur: number[]; prev: number[] }; done: number[]; marks: Mark[];
}
export interface Part { label: string; value: string; raw: string; unit: string; page: number | null; flag_labels: string[] }
export interface Finding { id: string; subject: string; kind: string; column: string; topic: string; within: string;
  page_cur: number | null; page_prev: number | null; a: string; b: string; evidence: string;
  // ฟิลด์เพิ่มจาก api_common.finding_extras (รุ่นเก่าอาจไม่มี)
  kind_code?: string; info?: boolean; caveats?: string[]; delta_text?: string; tolerance_text?: string; parts?: Part[] }
export interface PenCount { total: number; exact: number; partial: number; missed: number; pending: number }
export interface Metrics { pens: Record<Pen, PenCount>;
  extras: { real_unnoted: number; not_diff: number; undecided: number; pending: number };
  info: number; actionable: number; unread: number }
export interface Result { session: Session; metrics: Metrics; complete: boolean;
  marks: (Mark & { proposed: boolean; verdict: string; finding: Finding | null; candidates: Finding[] })[];
  extras: (Finding & { verdict: string })[]; versions: Record<string, string>; answers: Record<string, string> }
export interface Meta { pens: Record<Pen, string>; topics: { code: string; label: string }[];
  link_verdicts: Record<string, string>; extra_verdicts: Record<string, string>;
  likert: { group: string; items: { key: string; text: string }[] }[]; open: { key: string; text: string }[];
  versions: Record<string, string> }

/** ข้อผิดพลาดจากเซิร์ฟเวอร์ — code ตามสัญญา: csrf · invalid · not_found · locked · not_locked · too_large · server */
export class ApiError extends Error {
  constructor(message: string, public code = "", public status = 0, public errorId = "") { super(message); }
}

let token: Promise<string> | null = null;
function csrf(): Promise<string> {
  token ??= fetch("/api/csrf", { credentials: "same-origin" }).then((r) => r.json()).then((j) => j.token as string);
  return token;
}

async function handle<T>(r: Response): Promise<T> {
  const j = (await r.json().catch(() => ({}))) as { error?: string; code?: string; error_id?: string };
  if (!r.ok) {
    const msg = (j.error ?? "ระบบตอบกลับไม่สำเร็จ ลองอีกครั้ง") + (j.error_id ? ` (รหัสเหตุการณ์ ${j.error_id})` : "");
    throw new ApiError(msg, j.code ?? "", r.status, j.error_id ?? "");
  }
  return j as T;
}

export async function get<T>(url: string): Promise<T> {
  return handle<T>(await fetch(url, { credentials: "same-origin" }));
}

export async function post<T>(url: string, body: Record<string, unknown> = {}, retried = false): Promise<T> {
  const r = await fetch(url, {
    method: "POST", credentials: "same-origin",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": await csrf() },
    body: JSON.stringify(body),
  });
  try {
    return await handle<T>(r);
  } catch (e) {
    // โทเคนหมดอายุ/คุกกี้เปลี่ยน (เช่น เปิดแท็บค้างไว้นาน) — ขอใหม่แล้วลองซ้ำครั้งเดียว
    if (e instanceof ApiError && e.code === "csrf" && !retried) { token = null; return post<T>(url, body, true); }
    throw e;
  }
}

/** ส่งไฟล์แบบ multipart — โทเคนอยู่ในหัว (เซิร์ฟเวอร์ตรวจ CSRF ก่อนอ่าน body) · ไม่ตั้ง Content-Type เอง ให้เบราว์เซอร์ใส่ boundary */
export async function postForm<T>(url: string, form: FormData, retried = false): Promise<T> {
  const r = await fetch(url, { method: "POST", credentials: "same-origin", headers: { "X-CSRF-Token": await csrf() }, body: form });
  try {
    return await handle<T>(r);
  } catch (e) {
    if (e instanceof ApiError && e.code === "csrf" && !retried) { token = null; return postForm<T>(url, form, true); }
    throw e;
  }
}

export const pageImage = (sid: string, side: Side, page: number) => `/trial/s/${sid}/page/${side}/${page}.png`;

const warmed = new Set<string>();
/** โหลดภาพหน้าเตรียมไว้ตอนเครื่องว่าง — กดเปลี่ยนหน้าแล้วขึ้นทันที */
export function preload(urls: string[]) {
  const go = () => urls.forEach((u) => { if (!warmed.has(u)) { warmed.add(u); const i = new Image(); i.src = u; } });
  if ("requestIdleCallback" in window) (window as Window).requestIdleCallback(go); else setTimeout(go, 300);
}
