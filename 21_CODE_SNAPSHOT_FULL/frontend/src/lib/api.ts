// เรียก JSON API ของแอปเดิม — CSRF แบบ double-submit (ขอโทเคนครั้งเดียว ส่งในหัว X-CSRF-Token)
// รูปข้อมูลตามวิธีวัดผลฉบับ 0.2 (หน้าทดลอง trial-0.2.0) · ป้ายภาษาไทยทุกชุดมาจาก /api/trial/meta

export type Pen = "red" | "brown" | "pin";
export type Side = "cur" | "prev";
export type Path = "r1" | "r2";
export type Level = "must" | "info" | "unread" | "descriptive" | "review";

export interface Mark {
  id: string; side: Side | ""; page: number; fx: number; fy: number; pen: Pen | ""; topic: string; note: string;
  level: string; cause: string; part: string; searched: string; found_in: string; origin: "mark" | "row";
  seq: number; ref: string; row_source?: string; xtype?: string;
}
export interface Book { id: string; title: string; agency: string; pair: string; pair_kind: "same_year" | "cross_year";
  status: { sid: string; state: "draft" | "locked" | "stopped" | "withdrawn" | "legacy"; legacy: boolean } | null }
export interface Defaults { made_on: string; source: string; edition_first: string; edition_second: string;
  topics_marked: string[] }
export interface Session {
  sid: string; locked: boolean; locked_at: string; reviewer: string; path: Path; protocol: string;
  legacy: boolean; read_only_legacy: boolean; status: "" | "stopped" | "withdrawn"; active: boolean;
  pair_kind: "same_year" | "cross_year"; labels: Record<Side, string>;
  book: { id: string; title: string; agency: string; pair: string;
          cur: { title: string; fy: number }; prev: { title: string; fy: number } };
  pages: Record<Side, number[]>; done: Record<Side, number[]>; marks: Mark[]; gaps: Record<string, string[]>;
  run: { done: boolean; error: string; failures: number }; use_done: boolean; survey_state: string; consented: boolean;
  topics: string[];   // หัวข้อที่ใช้กับชนิดคู่นี้ (คู่ข้ามปี = ค ช ซ จ)
  xkind: "same_year" | "cross_year";   // ชนิดคู่สำหรับกติกา (รอบก่อน 0.2.1 = same_year)
  v03: boolean;                        // รอบตามวิธีวัดผลฉบับ 0.3
  defaults?: Defaults;
}
export interface Part { label: string; value: string; raw: string; unit: string; page: number | null; flag_labels: string[] }
export interface Finding { id: string; subject: string; kind: string; column: string; topic: string; topic_code: string;
  level: Level; within: string; page_cur: number | null; page_prev: number | null; a: string; b: string; evidence: string;
  kind_code?: string; info?: boolean; caveats?: string[]; delta_text?: string; tolerance_text?: string; parts?: Part[];
  obs_kind: string }
export interface Decision { verdict: string; reason: string; evidence: string; basis: string; decided_at: string;
  location: string; relevant_sides: string; search_scope: string }
export interface ObsEval { fidelity: string; fidelity_reason: string; dims: Record<string, string>; assertion: string;
  basis: string; decided_at: string }
export interface Rate3 { num: number; den: number; value: number | null; pct: number | null; reason: string; text: string }
export interface V03 {
  counts: { issues: Record<string, unknown>; location: Record<string, { exact: number; partial: number }>;
            obs: { F: number; groups: Record<string, number> } };
  pending: { issues: number; location: number; obs: number };
  issues: { N0: number; N: number; undecidable: number; exact: number; partial: number; miss: number;
            H1: Rate3; supplement: Rate3; incl_partial: Rate3; P: number } | null;
  location: { P: number; undecidable: number; H2: Rate3; all_over_P: Rate3; H2_exact: Rate3; H2_partial: Rate3;
              grid: Record<string, { exact: number; partial: number }> } | null;
  obs: { F: number; overflag: Rate3; A3_fidelity: Rate3; A3_assertion: Rate3; read_ok_assertion_wrong: number;
         fidelity: Record<string, number>; assertion: Record<string, number>;
         crosstab: Record<string, Record<string, number>> } | null;
}
export interface HistoryRow { at: string; before: Record<string, unknown> | null; after: Record<string, unknown>; reason: string }
export interface Issue extends Mark { in_scope: boolean; proposal: string; links: string[]; decision: Decision | null;
  gaps: string[]; history: HistoryRow[] }
export interface Group { grp: string; s3_reason: string; basis: string; issue_ref: string; part?: string; note?: string;
  decided_at: string }
export interface Rate { num: number; den: number; pct: number | null; text: string }
export interface A1 { issues: number; exact: number; partial: number; missed: number; undecidable: number; pending: number;
  N0: number; N: number; strict: Rate; with_partial: Rate }
export interface Metrics {
  A1: A1 & { partial_reasons: Record<string, number>; missed_reasons: Record<string, number>;
             matched_level: { must: number; info: number }; by_cause: Record<string, A1>; by_level: Record<string, A1>;
             by_topic: Record<string, A1>; out_of_scope: Omit<A1, "strict" | "with_partial">;
             post_result: Record<string, number>; scope_locked_only: A1 };
  A2: { all: number; some: number; none: number; found: number; rate: Rate };
  A3: { F: number; matched: number; s1: number; s2: number; s3: number; s4: number; s3_reasons: Record<string, number>;
        pending: number; closed: boolean; outside: number; outside_linked: number; must_total: number;
        superseded_groups: number; false_alarm: Rate; real_difference: null; system_extra_confirmed: number };
  A4: { parts: Record<string, number>; topics_covered: string[]; unread_pages: Record<Side, number[]>;
        unread_findings: number; read_problems: Record<string, number>; missed_unread: number; info_findings: number; info_matched: number; must_outside: number };
  B1_basis: Record<string, number> & { total: number };
  findings: { total: number; must: number; info: number; unread: number; descriptive: number };
  scope: { pair_kind: "same_year" } | { pair_kind: "cross_year"; label: string; rule: string;
                                       descriptive_by_kind: Record<string, number> };
  post_lock_notes: number;
  v03?: V03;
}
export interface Status { run: string; run_failures: number; reviewer: string; excluded_main: boolean;
  exclusions: string[]; flags: string[]; no_data_use: boolean }
export interface Result {
  session: Session; legacy: false; findings: Record<string, Finding>; issues: Issue[];
  unmatched: { id: string; group: Group | null; history: HistoryRow[] }[]; info_ids: string[]; unread_ids: string[];
  metrics: Metrics; complete: boolean; read_problem_ids: Record<string, string[]>;
  review: { id: string; reason: string }[]; u_ids: string[]; obs_eval: Record<string, ObsEval>;
  obs_history: Record<string, HistoryRow[]>; declaration: Record<string, unknown> & { parts: Record<string, string>;
  topics: Record<string, { total: number; root: number; red: number }>; received_at: string };
  declaration_check: { topic: string; declared_root: number; rows_root: number; declared_red: number; rows_red: number }[];
  status: Status; notes: number; versions: Record<string, string>; answers: Record<string, string>;
}
export interface LegacyFinding { id: string; subject: string; kind: string; evidence: string; page_cur: number | null;
  page_prev: number | null }
export interface LegacyResult {
  session: Session; legacy: true; complete: boolean; versions: Record<string, string>; answers: Record<string, string>;
  metrics: { pens: Record<Pen, { total: number; exact: number; partial: number; missed: number; pending: number }>;
             extras: Record<string, number>; info: number; actionable: number; unread: number };
  marks: (Mark & { proposed: boolean; verdict: string; finding: LegacyFinding | null })[];
  extras: (LegacyFinding & { verdict: string })[];
}
export type AnyResult = Result | LegacyResult;
type Codes = Record<string, string>;
export interface Meta {
  pens: Record<Pen, string>; levels: Codes; causes: Codes; paths: Record<Path, string>;
  topics: { code: string; label: string }[]; parts: { code: string; label: string }[]; coverage: Codes;
  sources: Codes; made: Codes; seen: Codes; verdicts: Codes; partial_reasons: Codes; miss_reasons: Codes;
  evidence: Codes; basis: Codes; groups: Codes; s3_reasons: Codes; finding_levels: Record<Level, string>; row_sources: Codes; post_dims: Codes; kind_labels: Codes; read_problems: Codes; p1_hint: string;
  xtypes: Codes; xtype_by_topic: Record<string, string[]>; xkind?: string;
  partial_reasons_v03: Codes; locations: Codes; fidelity: Codes; fidelity_reasons: Codes; assertion: Codes;
  dim_values: Codes; dims: Codes; obs_kinds: Codes; dims_by_obs_kind: Record<string, string[]>;
  likert_v03: { group: string; items: { key: string; text: string }[] }[]; likert_scale_v03: Codes;
  xyear: { topics: string[]; label: string; rule: string };
  level_definition: string; statuses: Codes; pair_kinds: Codes; survey_state_text: Codes;
  status_text: { run: Codes; reviewer: Codes; exclusions: Codes; flags: Codes };
  consent: { key: string; text: string }[]; steps: { key: string; text: string }[]; step_choices: Codes;
  likert: { group: string; items: { key: string; text: string }[] }[]; open: { key: string; text: string }[];
  general: { key: string; text: string; choices: Codes }[];
  legacy_link_verdicts: Codes; legacy_extra_verdicts: Codes; versions: Record<string, string>;
}

/** ข้อผิดพลาดจากเซิร์ฟเวอร์ — code ตามสัญญา: csrf · invalid · not_found · locked · not_locked · conflict · too_large · server */
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
  return handle<T>(await fetch(url, { credentials: "same-origin", cache: "no-store" }));
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

export const pageImage = (sid: string, side: Side, page: number) => `/trial/s/${sid}/page/${side}/${page}.png`;

const warmed = new Set<string>();
/** โหลดภาพหน้าเอกสารเตรียมไว้ตอนเครื่องว่าง (ภาพหน้าเท่านั้น — ไม่โหลดผลระบบล่วงหน้า) */
export function preload(urls: string[]) {
  const go = () => urls.forEach((u) => { if (!warmed.has(u)) { warmed.add(u); const i = new Image(); i.src = u; } });
  if ("requestIdleCallback" in window) (window as Window).requestIdleCallback(go); else setTimeout(go, 300);
}

/** หน้าที่กลับมาจากแคชย้อนหลัง (ปุ่มย้อนกลับ/ไปข้างหน้า) อาจเป็นสภาพก่อนส่ง — โหลดใหม่จากเซิร์ฟเวอร์ · คืนตัวยกเลิก */
export function reloadOnRestore(): () => void {
  const h = (e: PageTransitionEvent) => { if (e.persisted) location.reload(); };
  addEventListener("pageshow", h);
  return () => removeEventListener("pageshow", h);
}

/** มิติของแถว ร1 ที่จัดใหม่หลังเห็นผล (ตรงกับ ``trial.post_dims``) */
export function postDims(src: string | undefined): string[] {
  if (src === "post_result") return ["part", "cause", "level"];
  return src?.startsWith("post:") ? src.slice(5).split(",").filter(Boolean) : [];
}

/** ป้ายชุดหัวข้อเฉพาะที่ใช้กับรอบนี้ (คู่ข้ามปี = ค ช ซ จ) */
export const scoped = (meta: Meta, s: { topics: string[]; xkind?: string } | null | undefined): Meta =>
  s ? { ...meta, topics: meta.topics.filter((t) => s.topics.includes(t.code)), xkind: s.xkind } : meta;

/** ชนิดประเด็นของคู่ข้ามปีที่ใช้ได้กับหัวข้อ */
export const xtypesFor = (meta: Meta, topic: string) => meta.xtype_by_topic?.[topic] ?? [];

/** ป้ายสั้น (ส่วนก่อน " — ") */
export const short = (label: string | undefined) => (label ?? "").split(" — ")[0];

/** ฟิลด์ที่จุดที่วง (ทาง ร2) ยังขาดก่อนส่ง — ตรงกับ ``trial.mark_gaps`` ฝั่งเซิร์ฟเวอร์ (เซิร์ฟเวอร์ตรวจซ้ำเสมอ) */
export function markGaps(m: Mark, kind = ""): string[] {
  const out: string[] = [];
  if (!m.topic) out.push("หัวข้อ");
  if (!m.part) out.push("ส่วนของเล่ม");
  if (!m.cause) out.push("ต/ล");
  if (m.level !== "red" && m.level !== "brown") out.push("ระดับ");
  if (m.pen === "pin" && !(m.searched ?? "").trim()) out.push("ขอบเขตที่ค้นในอีกฉบับ");
  if (kind === "cross_year" && !m.xtype) out.push("ชนิดประเด็น (คู่ข้ามปี)");
  return out;
}
