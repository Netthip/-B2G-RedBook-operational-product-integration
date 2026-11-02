// เส้นทางในแอป (ไม่โหลดหน้าใหม่) — /r · /r/s/<sid> · /r/s/<sid>/result · /survey · /dashboard
// คลังเล่มงบประมาณ: /r/lib (หน้าแรกของสายเทียบเล่ม) · สมุดของระบบ: /r/book (เปิดจากส่วนผู้พัฒนา)
// สายเทียบเล่ม PDF: /r/p (รายการรอบ) · /r/p/new (เริ่มรอบจากชั้นเล่ม) · /r/p/<rid> (ภาพรวม) · /r/p/<rid>/f/<fid> (หลักฐาน A | B + บันทึกผล)
//                  /r/p/<rid>/preflight (ด่านก่อนส่งออก + ยืนยันปีงบ + คำนวณรอบใหม่) · /r/p/<rid>/audit · /r/p/<rid>/summary (สรุปพิมพ์ได้)
// เปลี่ยนหน้าด้วย View Transitions ถ้าเบราว์เซอร์มี (ลดการเคลื่อนไหวตามค่าระบบ)

export type Route =
  | { name: "home" }
  | { name: "review"; sid: string }
  | { name: "result"; sid: string }
  | { name: "survey"; sid: string }
  | { name: "dashboard"; sid: string }
  | { name: "lib" }
  | { name: "about" }
  | { name: "dev" }
  | { name: "book" }
  | { name: "pairs" }
  | { name: "pairNew" }
  | { name: "pair"; rid: string }
  | { name: "pairFinding"; rid: string; fid: string }
  | { name: "pairPreflight"; rid: string }
  | { name: "pairAudit"; rid: string }
  | { name: "pairSummary"; rid: string }
  | { name: "missing" };

function parse(path: string): Route {
  if (/^\/r\/lib\/?$/.test(path)) return { name: "lib" };
  if (/^\/r\/about\/?$/.test(path)) return { name: "about" };
  if (/^\/r\/dev\/?$/.test(path)) return { name: "dev" };
  if (/^\/r\/book\/?$/.test(path)) return { name: "book" };
  const pp = path.replace(/\/+$/, "").match(/^\/r\/p(?:\/([\w-]+)(?:\/f\/([\w-]+)|\/(preflight|audit|summary))?)?$/);
  if (pp) {
    if (!pp[1]) return { name: "pairs" };
    if (pp[1] === "new" && !pp[2] && !pp[3]) return { name: "pairNew" };
    if (pp[2]) return { name: "pairFinding", rid: pp[1], fid: pp[2] };
    if (pp[3] === "preflight") return { name: "pairPreflight", rid: pp[1] };
    if (pp[3] === "summary") return { name: "pairSummary", rid: pp[1] };
    return pp[3] === "audit" ? { name: "pairAudit", rid: pp[1] } : { name: "pair", rid: pp[1] };
  }
  const m = path.replace(/\/+$/, "").match(/^\/r(?:\/s\/([\w-]+)(?:\/(result|survey|dashboard))?)?$/);
  if (!m) return { name: "missing" };
  if (!m[1]) return { name: "home" };
  return { name: (m[2] ?? "review") as "review" | "result" | "survey" | "dashboard", sid: m[1] };
}

export const nav = $state({ route: parse(location.pathname) as Route, query: new URLSearchParams(location.search) });

const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;

export function go(path: string, replace = false) {
  const apply = () => {
    if (replace) history.replaceState(null, "", path); else history.pushState(null, "", path);
    const u = new URL(path, location.origin);
    nav.route = parse(u.pathname);
    nav.query = u.searchParams;
    window.scrollTo({ top: 0 });
  };
  const doc = document as Document & { startViewTransition?: (cb: () => void) => Record<"finished" | "ready" | "updateCallbackDone", Promise<void>> };
  if (!doc.startViewTransition || reduce || document.hidden) { apply(); return; }
  // ภาพเคลื่อนไหวรอให้จอวาดก่อน — ถ้าไม่เริ่มใน 300 ms (หน้าต่างถูกซ่อน/เครื่องช้า) เปลี่ยนหน้าเลย ไม่ค้าง
  let done = false;
  const once = () => { if (!done) { done = true; apply(); } };
  // เปลี่ยนหน้าซ้อนกันเร็ว ๆ → ภาพเคลื่อนไหวรอบก่อนถูกข้าม (ไม่ใช่ข้อผิดพลาด) — กลืนไว้ไม่ให้ขึ้นใน console
  const vt = doc.startViewTransition(once);
  for (const p of [vt.finished, vt.ready, vt.updateCallbackDone]) p?.catch(() => {});
  setTimeout(once, 300);
}

addEventListener("popstate", () => {
  nav.route = parse(location.pathname);
  nav.query = new URLSearchParams(location.search);
});

/** ลิงก์ภายในแอป: <a href="/r/..." onclick={link}> */
export function link(e: MouseEvent) {
  const a = e.currentTarget as HTMLAnchorElement;
  if (e.metaKey || e.ctrlKey || e.shiftKey || a.target) return;
  e.preventDefault();
  go(a.getAttribute("href") ?? "/r");
}
