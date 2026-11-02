/* เทียบเล่ม PDF ↔ PDF — ตรวจไล่ทีละข้อให้ลื่น (เสริมจากหน้าเดิม · ไม่มี JS = ลิงก์/ฟอร์มปกติทำงานครบ)

   (1) เปลี่ยนข้อ/เปิดข้อจากรายการ โดยสลับเฉพาะเนื้อหาใน <main> + ภาพเคลื่อนไหว (View Transitions)
   (2) โหลดข้อถัดไปและภาพหลักฐานรอไว้ล่วงหน้า (ภาพเก็บที่เซิร์ฟเวอร์ในเครื่อง — เบราว์เซอร์ไม่เก็บ)
   (3) บันทึกผลการตรวจแบบไม่โหลดหน้าใหม่ แล้วไปข้อถัดไปทันที — คำตัดสินยังบันทึกที่เซิร์ฟเวอร์เหมือนเดิม
       (CSRF · Audit · เหตุผลบังคับเมื่อเปลี่ยนผล) · ข้อสุดท้าย = ส่งฟอร์มแบบปกติ
   (4) ปุ่มลัด: ← → เปลี่ยนข้อ · 1–6 เลือกผล · Ctrl+Enter บันทึก
   (5) กรอบรอภาพ (skeleton) ระหว่างภาพหลักฐานกำลังโหลด

   ไม่โหลดอะไรจากภายนอก (CSP 'self') · ไม่เก็บข้อมูลในที่เก็บของเบราว์เซอร์ */
(function () {
  "use strict";
  if (window.__ppInit) return;
  window.__ppInit = true;
  var main = document.getElementById("main");
  if (!main || !window.fetch || !window.DOMParser || !window.URL || !history.pushState) return;

  // ไฟล์ของสายนี้อยู่ใน <main> ของแต่ละหน้า — ย้ายไป <head> ครั้งเดียว เพื่อไม่ให้หลุดตอนสลับเนื้อหา
  var OWN = 'link[href="/static/pdfpair.css"], script[src="/static/pdfpair.js"]';
  main.querySelectorAll(OWN).forEach(function (el) { document.head.appendChild(el); });

  var reduced = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var pages = new Map();            // URL ไม่มี # → Promise<{url, html, ok}>
  var seq = 0;                      // ลำดับการเปลี่ยนหน้า — คำตอบที่มาช้ากว่าคำสั่งล่าสุดถูกทิ้ง
  var transition = null;
  var MAX_PAGES = 12;
  var live = document.createElement("div");
  live.className = "sr-only";
  live.setAttribute("aria-live", "polite");
  document.body.appendChild(live);

  function announce(t) { live.textContent = ""; setTimeout(function () { live.textContent = t; }, 30); }

  function bare(u) { var x = new URL(u, location.href); x.hash = ""; return x.href; }

  /** หน้าในสายเทียบเล่มที่สลับเนื้อหาได้: รายการผลเทียบ และหน้าหลักฐานแต่ละข้อ */
  function swappable(u) {
    var x;
    try { x = new URL(u, location.href); } catch (e) { return false; }
    return x.origin === location.origin && !x.search
      && /^\/pdfpair\/runs\/[A-Za-z0-9_]+(\/f\/[A-Za-z0-9]+)?$/.test(x.pathname);
  }

  function fetchPage(u) {
    var k = bare(u);
    if (pages.has(k)) return pages.get(k);
    var p = fetch(k, { credentials: "same-origin" }).then(function (r) {
      return r.text().then(function (t) { return { url: r.url, html: t, ok: r.ok }; });
    });
    pages.set(k, p);
    if (pages.size > MAX_PAGES) pages.delete(pages.keys().next().value);
    p.catch(function () { pages.delete(k); });
    return p;
  }

  /** อุ่นภาพหลักฐานของหน้าที่โหลดไว้ — ให้เซิร์ฟเวอร์วาดภาพรอไว้ก่อนผู้ตรวจกดไปถึง */
  function warmImages(html) {
    var doc = new DOMParser().parseFromString(html, "text/html");
    doc.querySelectorAll("#main .vx-pdf-img img").forEach(function (img) {
      var i = new Image();
      i.decoding = "async";
      i.src = img.getAttribute("src");
    });
  }

  function prefetch(u) {
    if (!swappable(u)) return;
    fetchPage(u).then(function (res) { if (res.ok) warmImages(res.html); }).catch(function () {});
  }

  function apply(res, pushUrl) {
    var doc = new DOMParser().parseFromString(res.html, "text/html");
    var next = doc.getElementById("main");
    if (!next) { location.href = pushUrl || res.url; return; }
    next.querySelectorAll(OWN).forEach(function (el) { el.remove(); });
    var run = function () {
      main.innerHTML = next.innerHTML;
      document.title = doc.title;
      if (pushUrl) history.pushState({ pp: 1 }, "", pushUrl);
      var hash = new URL(pushUrl || location.href, location.href).hash;
      var target = hash && document.getElementById(decodeURIComponent(hash.slice(1)));
      if (target) { target.scrollIntoView({ block: "center" }); }
      else { window.scrollTo(0, 0); }
      init();
      var h = (target && target.querySelector("a")) || main.querySelector("h1");
      if (h) {
        if (h.tagName === "H1") h.setAttribute("tabindex", "-1");
        h.focus({ preventScroll: true });
      }
    };
    if (transition && transition.skipTransition) transition.skipTransition();   // กดรัว ๆ = ไม่รอภาพเคลื่อนไหวเดิม
    if (document.startViewTransition && !reduced) {
      transition = document.startViewTransition(run);
      var quiet = function () {};
      transition.finished.then(function () { transition = null; }, function () { transition = null; });
      transition.ready.catch(quiet);
      transition.updateCallbackDone.catch(quiet);
    } else {
      run();
    }
  }

  function go(u, push) {
    var my = ++seq;
    main.classList.add("pp-busy");
    fetchPage(u).then(function (res) {
      if (my !== seq) return;                       // มีคำสั่งใหม่กว่าแล้ว
      main.classList.remove("pp-busy");
      if (!res.ok) { location.href = u; return; }
      apply(res, push ? u : null);
    }).catch(function () { if (my === seq) location.href = u; });
  }

  // (1) ลิงก์ภายในสายเทียบเล่ม
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("a[href]");
    if (!a || e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey
        || a.target || a.hasAttribute("download") || !swappable(a.href)) return;
    if (bare(a.href) === bare(location.href) && new URL(a.href).hash) return;   // เลื่อนในหน้าเดิม
    e.preventDefault();
    go(a.href, true);
  });
  window.addEventListener("popstate", function () {
    if (swappable(location.href)) go(location.href, false);
  });

  // (2) โหลดล่วงหน้าเมื่อชี้ที่รายการ
  var hoverTimer = null;
  function onHover(e) {
    var a = e.target.closest && e.target.closest("a.pp-f-link, a[data-pp-next], a[data-pp-prev]");
    if (!a) return;
    clearTimeout(hoverTimer);
    hoverTimer = setTimeout(function () { prefetch(a.href); }, 120);
  }
  document.addEventListener("mouseover", onHover);
  document.addEventListener("focusin", onHover);

  // ฟอร์มที่ใช้เวลานาน (แนบเล่มและเทียบ) — บอกว่ากำลังทำงาน กันกดซ้ำ · ยังส่งแบบปกติ
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!f.dataset || !f.dataset.ppWait || e.defaultPrevented) return;
    var btn = f.querySelector('button[type="submit"]');
    if (btn) { btn.disabled = true; btn.textContent = f.dataset.ppWait; }
    announce(f.dataset.ppWait);
  });

  // (3) บันทึกผลแบบไม่โหลดหน้าใหม่
  document.addEventListener("submit", function (e) {
    var f = e.target;
    if (!f.matches || !f.matches(".vx-decide form")) return;
    var nextId = f.querySelector('input[name="go_next"]');
    if (!nextId || !nextId.value) return;            // ข้อสุดท้าย — ส่งแบบปกติแล้วกลับไปรายการ
    e.preventDefault();
    var btn = f.querySelector('button[type="submit"]');
    var label = btn ? btn.textContent : "";
    if (btn) { btn.disabled = true; btn.textContent = "กำลังบันทึก…"; }
    var my = ++seq;
    fetch(f.action, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(new FormData(f)).toString()
    }).then(function (r) {
      return r.text().then(function (t) { return { url: r.url, html: t, ok: r.ok }; });
    }).then(function (res) {
      pages.clear();                                  // สถานะการตรวจเปลี่ยน — หน้าที่โหลดไว้ล้าสมัย
      if (my !== seq) return;                         // ผู้ใช้ไปหน้าอื่นแล้ว — บันทึกสำเร็จแต่ไม่ดึงกลับ
      if (res.ok) {
        announce("บันทึกผลแล้ว — ข้อถัดไป");
        apply(res, res.url);
      } else {
        announce("บันทึกไม่สำเร็จ — ดูข้อความบนหน้า");
        apply(res, null);                             // แสดงข้อความผิดพลาดของหน้าเดิม
      }
    }).catch(function () {
      if (btn) { btn.disabled = false; btn.textContent = label; }
      f.submit();                                     // ส่งแบบปกติแทน
    });
  });

  // (4) ปุ่มลัด
  document.addEventListener("keydown", function (e) {
    var form = main.querySelector(".vx-decide form");
    var t = e.target, typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
    if (form && e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (form.requestSubmit) form.requestSubmit(); else form.submit();
      return;
    }
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      var a = main.querySelector(e.key === "ArrowRight" ? "a[data-pp-next]" : "a[data-pp-prev]");
      if (a) { e.preventDefault(); a.click(); }
      return;
    }
    if (form && /^[1-9]$/.test(e.key)) {
      var radios = form.querySelectorAll('input[name="choice"]');
      var r = radios[parseInt(e.key, 10) - 1];
      if (r) { e.preventDefault(); r.checked = true; r.focus(); announce("เลือก: " + r.parentNode.textContent.trim()); }
    }
  });

  // (5) กรอบรอภาพ · ทำงานทุกครั้งที่เนื้อหาเปลี่ยน
  function init() {
    main.querySelectorAll(".vx-pdf-img img").forEach(function (img) {
      var box = img.parentNode;
      var done = function () { box.classList.add("is-loaded"); };
      if (img.complete && img.naturalWidth) done();
      else { img.addEventListener("load", done, { once: true }); img.addEventListener("error", done, { once: true }); }
    });
    var next = main.querySelector("a[data-pp-next]");
    if (next) {
      var idle = window.requestIdleCallback || function (fn) { return setTimeout(fn, 200); };
      idle(function () { prefetch(next.href); });
    }
  }
  init();
})();
