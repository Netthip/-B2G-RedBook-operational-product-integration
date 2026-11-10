// การเคลื่อนไหวของหน้าจอ (ใบงาน #44 9 พ.ย. — แถบเลื่อนตามแท็บ · Fade Content) — แสดงผลเท่านั้น ไม่แตะข้อมูลหรือการนับ
// ไม่ใช้ svelte/transition (ฉีด <style> ขัด CSP) · ตั้งค่าผ่าน CSSOM (style.setProperty) และ element.animate() ซึ่ง CSP ไม่บล็อก
// ระบบตั้งลดการเคลื่อนไหว = ไม่เคลื่อนไหวเลย ย้าย/แสดงทันที

const rm = matchMedia("(prefers-reduced-motion: reduce)");
export const reduced = () => rm.matches;

const SEL = ':scope > [aria-selected="true"], :scope > [aria-checked="true"], :scope > [aria-current="page"]';

/** แถบของแท็บที่เลือกอยู่ เลื่อนไปแท็บใหม่ ~0.2 วิ — ใส่ที่กล่อง tablist/radiogroup: <div role="tablist" use:slide>
 *  คำนวณตำแหน่งจริงทุกครั้งที่กล่อง/แท็บเปลี่ยนขนาด (จอแคบที่แท็บขึ้นสองบรรทัด แถบอยู่ใต้แท็บที่เลือกจริง) */
export function slide(node: HTMLElement) {
  node.classList.add("slide");
  // วางทันทีใน callback ของ observer (ไม่รอ requestAnimationFrame — แท็บที่อยู่เบื้องหลังเบราว์เซอร์หน่วงเฟรม แถบจะค้างที่เดิม)
  const place = () => {
    const on = node.querySelector<HTMLElement>(SEL);
    if (!on) { node.style.setProperty("--sl-o", "0"); return; }
    node.style.setProperty("--sl-x", `${on.offsetLeft}px`);
    node.style.setProperty("--sl-y", `${on.offsetTop}px`);
    node.style.setProperty("--sl-w", `${on.offsetWidth}px`);
    node.style.setProperty("--sl-h", `${on.offsetHeight}px`);
    node.style.setProperty("--sl-o", "1");
    // ครั้งแรกวางที่เดิมโดยไม่เลื่อน แล้วจึงเปิดการเลื่อน (ไม่ให้แถบวิ่งมาจากมุมซ้ายตอนเปิดหน้า)
    if (!node.classList.contains("slide-on")) {
      node.classList.add("slide-on");
      getComputedStyle(node, "::before").transform;   // ให้ตำแหน่งแรกถูกคำนวณก่อนเปิดการเลื่อน
      node.classList.add("slide-ready");
    }
  };
  const ro = new ResizeObserver(place);
  const watch = () => { ro.disconnect(); ro.observe(node); for (const c of node.children) ro.observe(c); };
  const mo = new MutationObserver((ms) => { if (ms.some((m) => m.type === "childList")) watch(); place(); });
  mo.observe(node, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ["aria-selected", "aria-checked", "aria-current", "class"] });
  watch();
  place();
  document.fonts?.ready.then(place);
  return { destroy() { ro.disconnect(); mo.disconnect(); } };
}

/** เนื้อหาจางเข้า ~0.15 วิ ทุกครั้งที่ค่า key เปลี่ยน (สลับแท็บ/ตัวกรอง) — ไม่สร้างเนื้อหาใหม่ จึงไม่เสียตำแหน่งเลื่อน
 *  <div use:fadeOn={show}> · ไม่ใช้กับภาพหลักฐาน */
export function fadeOn(node: HTMLElement, key: unknown) {
  let last = key;
  return {
    update(k: unknown) {
      if (k === last) return;
      last = k;
      if (!reduced()) node.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150, easing: "ease-out" });
    },
  };
}
