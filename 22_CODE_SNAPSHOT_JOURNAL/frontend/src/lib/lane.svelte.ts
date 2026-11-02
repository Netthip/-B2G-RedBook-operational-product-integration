// เซิร์ฟเวอร์สาย PDF เท่านั้น (redbook.pdf_lane_app) ตอบ GET /api/lane · แอปเต็มตอบ 404 = เปิดทุกสาย
// สาย PDF ซ่อนลิงก์ไปหน้าสาย Excel (โต๊ะตรวจเต็ม · Audit ทั้งระบบ) ที่เซิร์ฟเวอร์จะตอบ 404
// evalGuard = สถานะด่านชุดประเมิน (จำนวน + ล็อกไหม · เซิร์ฟเวอร์ไม่ส่งรายชื่อ) — หน้าส่วนผู้พัฒนา
export type EvalGuard = { configured: boolean; agencies: number; unlocked: boolean; pdfbook: string };
export const lane = $state<{ pdfOnly: boolean; known: boolean; evalGuard: EvalGuard | null }>({ pdfOnly: false, known: false, evalGuard: null });

fetch("/api/lane", { credentials: "same-origin" })
  .then((r) => (r.ok ? r.json() : null))
  .then((j: { lane?: string; eval_guard?: EvalGuard } | null) => {
    lane.pdfOnly = j?.lane === "pdf_only";
    lane.evalGuard = j?.eval_guard ?? null;
  })
  .catch(() => {})
  .finally(() => { lane.known = true; });
