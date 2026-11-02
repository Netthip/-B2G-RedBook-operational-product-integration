// คลังเล่ม — สคริปต์เสริมเท่านั้น หน้าเว็บใช้งานได้ครบเมื่อปิดสคริปต์
// โหลดจาก origin เดียวกัน — ผ่าน CSP script-src 'self' (ห้ามใช้ onerror="" ในเทมเพลต)

// 1. ส่งฟอร์มตัวกรองเมื่อเปลี่ยนตัวเลือก ประหยัดการกดหนึ่งครั้ง (ปุ่ม "ใช้ตัวกรองนี้" ยังอยู่)
document.querySelectorAll("select[data-autosubmit]").forEach(function (el) {
  el.addEventListener("change", function () { el.form.requestSubmit ? el.form.requestSubmit() : el.form.submit(); });
});

// 2. ภาพปกโหลดไม่ขึ้น → ถอดภาพออก ให้เห็นปกจำลองจาก metadata ที่อยู่ข้างใต้ (ไม่แสดงไอคอนภาพแตก)
function dropBroken(img) { img.remove(); }
document.querySelectorAll("img[data-thumb]").forEach(function (img) {
  if (img.complete && img.naturalWidth === 0) { dropBroken(img); return; }
  img.addEventListener("error", function () { dropBroken(img); });
  img.addEventListener("load", function () { img.classList.add("is-loaded"); });
  if (img.complete && img.naturalWidth > 0) { img.classList.add("is-loaded"); }
});

// 3. สถานะกำลังโหลด — ตัวกรอง/แท็บ/ค้นหา โหลดหน้าใหม่จากเซิร์ฟเวอร์ ให้ผู้ใช้รู้ว่าระบบรับคำสั่งแล้ว
var results = document.getElementById("results");
var bar = document.getElementById("loading");
function busy() {
  if (results) { results.setAttribute("aria-busy", "true"); results.classList.add("is-loading"); }
  if (bar) { bar.hidden = false; }
}
document.querySelectorAll("form[data-loading]").forEach(function (f) {
  f.addEventListener("submit", busy);
});
document.querySelectorAll(".tabs a, .year-rail a, .facet a.pill, .chips-active a, .seg a, .pager a").forEach(function (a) {
  a.addEventListener("click", function (e) {
    if (!e.ctrlKey && !e.metaKey && !e.shiftKey && e.button === 0) { busy(); }
  });
});
// กลับมาด้วยปุ่มย้อนกลับ (bfcache) — ล้างสถานะค้าง
window.addEventListener("pageshow", function () {
  if (results) { results.setAttribute("aria-busy", "false"); results.classList.remove("is-loading"); }
  if (bar) { bar.hidden = true; }
});
