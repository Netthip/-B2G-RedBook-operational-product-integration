// เส้นทางในแอป (ไม่โหลดหน้าใหม่) — /r · /r/s/<sid> · /r/s/<sid>/result · /survey · /dashboard
// เปลี่ยนหน้าด้วย View Transitions ถ้าเบราว์เซอร์มี (ลดการเคลื่อนไหวตามค่าระบบ)

export type Route =
  | { name: "home" }
  | { name: "review"; sid: string }
  | { name: "result"; sid: string }
  | { name: "survey"; sid: string }
  | { name: "dashboard"; sid: string }
  | { name: "missing" };

function parse(path: string): Route {
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
  const doc = document as Document & { startViewTransition?: (cb: () => void) => { finished: Promise<void> } };
  if (!doc.startViewTransition || reduce || document.hidden) { apply(); return; }
  // ภาพเคลื่อนไหวรอให้จอวาดก่อน — ถ้าไม่เริ่มใน 300 ms (หน้าต่างถูกซ่อน/เครื่องช้า) เปลี่ยนหน้าเลย ไม่ค้าง
  let done = false;
  const once = () => { if (!done) { done = true; apply(); } };
  doc.startViewTransition(once).finished.catch(() => {});
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
