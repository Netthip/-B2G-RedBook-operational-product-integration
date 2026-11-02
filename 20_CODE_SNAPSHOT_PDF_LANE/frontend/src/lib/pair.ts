// สายเทียบเล่ม PDF ↔ PDF — ชนิดข้อมูลตามสัญญา docs/API_CONTRACT_R.md ข้อ 2 และ 4 + แคชเล็ก ๆ ในหน่วยความจำ
// ป้ายของโดเมน (หัวข้อ · ชนิดข้อสังเกต · ผลการตรวจ · การใช้ผล) มาจากเซิร์ฟเวอร์เสมอ — ไฟล์นี้ไม่มีป้ายของตัวเอง
// ฟิลด์ที่มี ? = หลังบ้านยังไม่ส่ง (รุ่นเก่า) — หน้าจอซ่อนส่วนนั้น ไม่เดาค่าเอง

import { get, post, postForm, preload } from "./api";

export type AB = "A" | "B";

export interface PSide {
  value: string; raw: string; unit: string; unit_origin: string; unit_note: string;
  status: "read" | "dash" | "blank" | ""; amount_text: string; page: number | null;
  bbox: number[] | null; text: string; evidence_png: string | null; raw_note?: string;
}
export interface PPart { label: string; value: string; raw: string; unit: string; page: number | null;
  flags: string[]; flag_labels: string[] }
export interface PDecision { choice: string; choice_label: string; note: string; decided_at: string; after?: string }
export interface PFinding {
  id: string; topic: string; topic_label: string; kind: string; kind_label: string; subject: string; column: string;
  within: AB | ""; info: boolean; a: PSide; b: PSide; delta: string; delta_text: string; unit: string; note: string;
  caveats: string[]; parts: PPart[]; tolerance: string; tolerance_text: string; tolerance_basis: string;
  evidence: string; decision: PDecision | null; use: string; use_label: string;
}
export interface PRunSide {
  label: string; file: string; sha256: string; fiscal_year: number | null; year_status: string; year_status_label?: string;
  year_origin_label: string; stage: string; stage_status: string; stage_origin: string;
  first: number; last: number; method_label: string; pages_in_file?: number;
  printed_offset?: number | null;   // หน้า PDF − เลขที่พิมพ์บนหัวกระดาษ · null = ระบบไม่รู้ (ไม่เดา)
  coverage?: { sections_found: number; repaired_words: number; pages_no_text: number[] };
}
export interface PGroup { key: string; label: string; total: number; decided: number; pending: number; info: number }
export interface PUse {
  ok: boolean; use_status: string; use_status_label: string; use_status_scope: string; use_reasons: string[];
  use_counts: Record<string, number>; actionable: number; use_breakdown: string; failing: string[];
  export_url: string; failing_checks?: { key: string; label: string }[];
}
export interface PRun {
  run: { id: string; created_at: string; mode: string; mode_label: string; agency: string;
    versions: Record<string, string>; profile_status_label: string; superseded_by: string; supersedes: string;
    sides: Record<AB, PRunSide> };
  groups: PGroup[]; counts: { actionable: number; pending: number; info: number };
  use_counts: Record<string, number>; next_pending_id: string;
  year_warnings: { side: AB; text: string }[]; stage_warnings: { side: AB; text: string }[];
  decisions: { key: string; label: string; use?: string; use_label?: string; when?: string; after?: string }[]; preflight: PUse; item_change_ids?: string[]; rounding_policy?: string;
}
export interface PView {
  finding: PFinding; prev_id: string; next_id: string; next_pending_id: string;
  diff: { a: [string, string][]; b: [string, string][] }; writable: boolean; rounding_policy?: string;
}
export interface PRunRow { id: string; created_at: string; mode: string; mode_label: string; agency: string; superseded_by: string;
  sides?: Record<AB, { label: string; file: string }>; counts?: { actionable: number; pending: number } }

// ด่านก่อนส่งออก — action.code บอกหน้าบ้านว่าพาไปไหน (ป้ายปุ่มมาจากเซิร์ฟเวอร์)
export interface PCheck { key: string; label: string; ok: boolean; detail: string;
  action: { code: "open_finding" | "confirm_year" | "rerun" | "open_run" | "reattach"; label: string; href: string;
            finding_id?: string; run_id?: string } | null }
export interface PYearEvidence { page: number; line: string; kind: string; kind_label?: string; cue: string; direct: boolean;
  year: number; end?: number; bbox?: number[] | null }
export interface PYear {
  used: number | null; known: number | null; detected: number | null; status: string; status_label?: string;
  status_state?: "ok" | "warn" | "fail"; confirmable?: boolean; origin_label: string; candidates: string[];
  evidence: PYearEvidence[]; confirmed: { year: number; note: string; confirmed_at: string } | null;
  pages_allowed: number[]; page_png: string;
}
export interface PPreflight extends PUse {
  checks: PCheck[]; years: Record<AB, PYear>; needs_rerun: boolean; mode_for_years: string;
  stage_warnings: { side: AB; text: string }[];
}
// Audit ของรอบ — chain = ผลตรวจสายโซ่แฮชของทั้งระบบ
export interface PAuditEntry { seq: number; at: string; action: string; action_label: string; object_id: string;
  summary: string; detail: Record<string, unknown>; entry_hash: string }
export interface PAudit { entries: PAuditEntry[]; chain: { ok: boolean; checked: number; broken_at_seq: number | null } }
export const loadAudit = (rid: string) => get<PAudit>(`${base(rid)}/audit`);
export const loadPreflight = (rid: string) => get<PPreflight>(`${base(rid)}/preflight`);
/** ยืนยันปีงบ — ``seen`` = ผู้ตรวจติ๊กว่าดูปีจากภาพหน้าเอกสารแล้ว (เซิร์ฟเวอร์ปฏิเสธถ้าไม่ติ๊ก) */
export function confirmYear(rid: string, side: AB, year: string, note: string, seen: boolean) {
  const run = runs.get(rid);
  if (run) run.at = 0;
  return post<PPreflight>(`${base(rid)}/year`, { side, year, note, seen });
}
export function rerun(rid: string) {
  const run = runs.get(rid);
  if (run) run.at = 0;
  return post<{ rid: string }>(`${base(rid)}/rerun`, {});
}

// ── แคช: แสดงของเดิมทันที แล้วค่อยดึงใหม่ (ข้อมูลเปลี่ยนได้จากแท็บหน้าเดิมด้วย) ─────────────────
interface Entry<T> { at: number; val?: T; p?: Promise<T> }
const runs = new Map<string, Entry<PRun>>();
const lists = new Map<string, Entry<PFinding[]>>();
const views = new Map<string, Entry<PView>>();

function load<T>(m: Map<string, Entry<T>>, key: string, fetcher: () => Promise<T>, maxAge: number): Promise<T> {
  const e = m.get(key);
  if (e?.p) return e.p;
  if (e?.val !== undefined && Date.now() - e.at < maxAge) return Promise.resolve(e.val);
  const p = fetcher().then(
    (val) => { m.set(key, { at: Date.now(), val }); return val; },
    (err) => { m.set(key, { at: e?.at ?? 0, val: e?.val }); throw err; },
  );
  m.set(key, { at: e?.at ?? 0, val: e?.val, p });
  return p;
}

const base = (rid: string) => `/api/pdfpair/runs/${encodeURIComponent(rid)}`;

export const peekRun = (rid: string) => runs.get(rid)?.val;
export const peekList = (rid: string) => lists.get(rid)?.val;
export const peekView = (rid: string, fid: string) => views.get(`${rid}/${fid}`)?.val;

export const loadRun = (rid: string, maxAge = 0) => load(runs, rid, () => get<PRun>(base(rid)), maxAge);
export const loadList = (rid: string, maxAge = 0) =>
  load(lists, rid, () => get<{ findings: PFinding[] }>(`${base(rid)}/findings`).then((j) => j.findings), maxAge);
export const loadView = (rid: string, fid: string, maxAge = 15000) =>
  load(views, `${rid}/${fid}`, () => get<PView>(`${base(rid)}/f/${encodeURIComponent(fid)}`), maxAge);
// ชั้นเล่ม + เริ่มรอบ — หน่วยงานที่กันไว้ไม่อยู่ในรายชื่อ (เซิร์ฟเวอร์กันเอง)
export interface PVolume { key: string; title: string; fiscal_year: number; stage: string; stage_label: string; volume_no: string }
export interface PShelf { shelf_label: string; volumes: PVolume[]; a: PVolume | null; agency: string; agencies: string[];
  suggest: { key: string; why: string }[]; others: string[]; agency_error?: string }
export const loadShelf = (a = "") => get<PShelf>(`/api/pdfpair/shelf${a ? `?a=${encodeURIComponent(a)}` : ""}`);
export const startRun = (a: string, b: string, agency: string) => post<{ rid: string }>("/api/pdfpair/shelf/start", { a, b, agency });
// อัปโหลด PDF จากเครื่อง (สัญญาส่วนที่ 4) — ไม่ส่ง project_id ครั้งแรก = เซิร์ฟเวอร์สร้างงานตรวจให้
export interface PUpload { project_id: string; side: AB; pages: number; sha256: string; file: string; sides_ready: AB[]; agencies: string[] }
export function uploadPdf(side: AB, file: File, projectId: string, sourceUrl: string) {
  const f = new FormData();
  f.append("file", file); f.append("side", side);
  if (projectId) f.append("project_id", projectId);
  if (sourceUrl.trim()) f.append("source_url", sourceUrl.trim());
  return postForm<PUpload>("/api/pdfpair/uploads", f);
}
export const startUploaded = (pid: string, agency: string) =>
  post<{ rid: string }>(`/api/pdfpair/uploads/${encodeURIComponent(pid)}/run`, { agency });
export const listRuns = () => get<{ runs: PRunRow[] }>("/api/pdfpair/runs").then((j) => j.runs);

/** เตรียมข้อที่น่าจะเปิดต่อไว้ (ข้อมูล + ภาพหลักฐาน) — กดเปลี่ยนข้อแล้วขึ้นทันที
 *  เซิร์ฟเวอร์ตอบทีละคำขอ: เตรียมเฉพาะข้อที่น่าจะไปต่อ หลังข้อปัจจุบันโหลดเสร็จ ไม่ยิงตอนเลื่อนเมาส์ผ่าน */
export function prefetch(rid: string, fid: string, images = true) {
  if (!fid) return;
  loadView(rid, fid, 60000)
    .then((v) => { if (images) preload([v.finding.a.evidence_png, v.finding.b.evidence_png].filter((u): u is string => !!u)); })
    .catch(() => {});
}

/** บันทึกผลการตรวจ — คำตอบของเซิร์ฟเวอร์แทนค่าในแคชทุกที่ที่มีข้อนี้ · ภาพรวมของรอบถือว่าเก่า (ดึงใหม่ตอนเปิด) */
export async function decide(rid: string, fid: string, choice: string, note: string) {
  const r = await post<{ finding: PFinding; next_pending_id: string; preflight: PUse }>(
    `${base(rid)}/f/${encodeURIComponent(fid)}/decide`, { choice, note });
  const v = views.get(`${rid}/${fid}`);
  if (v?.val) views.set(`${rid}/${fid}`, { at: Date.now(), val: { ...v.val, finding: r.finding, next_pending_id: r.next_pending_id } });
  const l = lists.get(rid);
  if (l?.val) l.val = l.val.map((f) => (f.id === fid ? r.finding : f));
  const run = runs.get(rid);
  if (run) run.at = 0;
  return r;
}

/** ที่อยู่ภาพรวมล่าสุดของแต่ละรอบ (ตัวกรองที่เลือกไว้) — ปุ่ม "← ภาพรวม" ในหน้าหลักฐานพากลับมาที่เดิม */
export const backTo = new Map<string, string>();

// ── ตัวช่วยแสดงผล (ไม่ใช่ป้ายโดเมน) ─────────────────────────────────────────────────────────
/** หัวข้อที่ไม่มีค่าตัวเลขให้เทียบ (ข้อความ · โครงสร้าง · ปก) — แบบเดียวกับหน้าเดิม */
export const NO_VALUES = new Set(["text", "struct", "cover"]);
// ทิศของเงิน (กิ๊ฟ 28 ต.ค.: ใช้สัญลักษณ์มากกว่าตัวอักษร) — บอกแค่เพิ่ม/ลด ไม่ได้บอกว่าถูกหรือผิด
//   up = เพิ่มขึ้น ▲ · down = ลดลง ▼ · gone = มีในฉบับตั้งต้นแต่ไม่พบในฉบับที่นำมาเทียบ · added = พบเฉพาะฉบับที่นำมาเทียบ
export type Trend = "up" | "down" | "flat" | "gone" | "added" | "";
export function trend(f: PFinding): Trend {
  if (NO_VALUES.has(f.topic)) return "";
  const hasA = !!f.a.amount_text, hasB = !!f.b.amount_text;
  if (hasA && !hasB && !f.b.status) return "gone";
  if (!hasA && hasB && !f.a.status) return "added";
  const n = parseFloat(f.delta);
  return !Number.isFinite(n) ? "" : n > 0 ? "up" : n < 0 ? "down" : "flat";
}
export const TREND_MARK: Record<Trend, string> = { up: "▲", down: "▼", flat: "＝", gone: "✕", added: "＋", "": "" };
export const TREND_SAY: Record<Trend, string> = { up: "เพิ่มขึ้น", down: "ลดลง", flat: "เท่าเดิม", gone: "ไม่พบในฉบับที่นำมาเทียบ",
  added: "พบเฉพาะฉบับที่นำมาเทียบ", "": "" };
/** ผลต่างไม่มีเครื่องหมาย +/− (ทิศบอกด้วยลูกศรแล้ว) */
export const absDelta = (f: PFinding) => f.delta_text.replace(/^[+\-−]\s?/, "");
export const hasValues = (f: PFinding) => !NO_VALUES.has(f.topic) && !!(f.a.value || f.b.value || f.a.status || f.b.status);
/** ตัดข้อความยาวที่ขอบคำ — ไม่ผ่ากลางคำ และไม่แยกสระ/วรรณยุกต์ออกจากพยัญชนะ */
export function clip(s: string, n: number): string {
  if (s.length <= n) return s;
  let out = "";
  for (const g of ["word", "grapheme"] as const) {
    for (const { segment } of new Intl.Segmenter("th", { granularity: g }).segment(s)) {
      if (out.length + segment.length > n) break;
      out += segment;
    }
    if (out) break;
  }
  return out.trimEnd() + "…";
}
// เลขหน้า: ผู้ใช้อ้างเลขที่พิมพ์บนหัวกระดาษ (เลขสารบรรณ) ไม่ใช่ลำดับแผ่นใน PDF ที่นับปก/สารบัญด้วย (กิ๊ฟ 30 ต.ค.)
// รู้ระยะเคลื่อน = "337" (ย่อ) / "337 (PDF 350)" (เต็ม) · ไม่รู้ = "PDF 350" บอกตรง ๆ ว่าเป็นเลขของไฟล์
export type Offsets = Partial<Record<AB, number | null | undefined>>;
export const offsetsOf = (r?: PRun | null): Offsets => r ? { A: r.run.sides.A.printed_offset, B: r.run.sides.B.printed_offset } : {};
// เลขที่พิมพ์บนหัวกระดาษ = หน้า PDF − ระยะเคลื่อน · ระยะเคลื่อน null (ระบบหาไม่ได้) = "ไม่ทราบ" ห้ามแทนด้วย 0
const printed = (p: number, off?: number | null) => (off != null && p - off > 0 ? p - off : null);
export const UNKNOWN = "ไม่ทราบ";
export const printedOf = (p: number, off?: number | null) => printed(p, off)?.toString() ?? UNKNOWN;
export const pageFull = (p: number, off?: number | null) => `หน้าพิมพ์ ${printedOf(p, off)} · หน้า PDF ${p}`;
export const rangeFull = (a: number, b: number, off?: number | null) => {
  const x = printed(a, off), y = printed(b, off);
  return `หน้าพิมพ์ ${x && y ? `${x}–${y}` : UNKNOWN} · หน้า PDF ${a}–${b}`;
};
// สองฝั่ง = "หน้าพิมพ์ 633 → 643" (ทิศเดียวกับหัวหน้า) · ฝั่งไหนไม่ทราบเลขพิมพ์ → ใช้หน้า PDF ทั้งคู่ ไม่ปนสองแบบ
export const pagesOf = (f: PFinding, off: Offsets = {}) => {
  const a = f.a.page, b = f.b.page;
  const pa = a ? printed(a, off.A) : null, pb = b ? printed(b, off.B) : null;
  const known = (!a || pa) && (!b || pb);
  const [x, y, lab] = known ? [pa, pb, "หน้าพิมพ์"] : [a, b, "หน้า PDF"];
  return a && b ? `${lab} ${x} → ${y}` : a ? `${lab} ${x} (ฉบับ A)` : b ? `${lab} ${y} (ฉบับ B)` : "";
};
