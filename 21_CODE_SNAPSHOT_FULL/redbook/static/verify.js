/* #24 หลักฐาน A | B — (1) วางจุดชี้ (hotspot) บนภาพ PDF ตามพิกัดใน data-* (CSP ห้าม style inline
   จึงตั้งผ่าน CSSOM) · (2) "ดูหลักฐาน" จากคิว/Preflight เปิดเป็นหน้าต่างซ้อน (<dialog>)
   ไม่มี JS = ลิงก์ปกติเปิดหน้าหลักฐานเต็มหน้า (ทำงานได้ครบเหมือนกัน) */
(function () {
  "use strict";
  document.documentElement.classList.add("js");

  function placeHotspots(root) {
    root.querySelectorAll(".vx-hot").forEach(function (b) {
      b.style.left = b.dataset.x + "%";
      b.style.top = b.dataset.y + "%";
      b.style.width = Math.max(parseFloat(b.dataset.w), 2) + "%";
      b.style.height = Math.max(parseFloat(b.dataset.h), 4) + "%";
      if (parseFloat(b.dataset.x) > 55) b.classList.add("is-right");   // callout เปิดไปทางซ้าย ไม่ล้นกรอบ
    });
  }

  var dlg = null, opener = null;

  function ensureDialog() {
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.className = "vx-dialog";
    dlg.setAttribute("aria-labelledby", "vx-panel-h");
    document.body.appendChild(dlg);
    dlg.addEventListener("click", function (e) {
      var t = e.target;
      if (t === dlg || (t.closest && t.closest("[data-close]"))) { dlg.close(); return; }
      var a = t.closest && t.closest("a[data-panel]");
      if (a) { e.preventDefault(); load(a.href); }
    });
    dlg.addEventListener("close", function () {
      dlg.innerHTML = "";
      if (opener) opener.focus();
    });
    return dlg;
  }

  function load(href) {
    var d = ensureDialog();
    var url = href + (href.indexOf("?") >= 0 ? "&" : "?") + "panel=1";
    d.innerHTML = '<p class="vx-loading">กำลังเปิดหลักฐาน…</p>';
    if (!d.open) d.showModal();
    fetch(url, { credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        d.innerHTML = html;
        placeHotspots(d);
        var h = d.querySelector(".vx-ev-title");
        if (h) { h.setAttribute("tabindex", "-1"); h.focus(); }
      })
      .catch(function () { window.location.href = href; });   // เปิดไม่ได้ = ไปหน้าเต็มแทน
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest(".vx-rows a.vx-go-link");
    if (!a || e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0 || !window.HTMLDialogElement) return;
    e.preventDefault();
    opener = a;
    load(a.href);
  });

  placeHotspots(document);
})();
