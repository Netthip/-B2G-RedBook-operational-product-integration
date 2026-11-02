/* ทดลองตรวจเล่ม (#43) — การ์ดเลือกเล่ม · วงจุดบนภาพหน้า · แถบแดชบอร์ด
 * ไม่มีสคริปต์ฝังในหน้า (CSP script-src 'self') · ตำแหน่งจุดเก็บเป็นสัดส่วนของภาพ (0–1)
 * ทุกการบันทึกส่ง CSRF ไปกับฟอร์ม · ไม่ใช้ที่เก็บของเบราว์เซอร์ */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function post(url, data) {
    var body = new URLSearchParams();
    Object.keys(data).forEach(function (k) { body.append(k, data[k]); });
    body.append("csrf_token", document.getElementById("tr-csrf").value);
    return fetch(url, { method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: body.toString() })
      .then(function (r) { return r.json().then(function (j) { if (!r.ok) throw new Error(j.error || "บันทึกไม่สำเร็จ"); return j; }); });
  }

  // ── การ์ดซ้อน: ใบที่เลือกขยายขึ้นมาข้างหน้า ใบอื่นเห็นแค่ป้าย ────────────────────────
  function fan(form) {
    var cards = Array.prototype.slice.call(form.querySelectorAll(".tr-card"));
    if (!cards.length) return;
    var hidden = document.createElement("input");
    hidden.type = "hidden"; hidden.name = "book_id";
    form.appendChild(hidden);
    cards.forEach(function (c) { c.dataset.value = c.value; c.removeAttribute("name"); });
    var cur = Math.max(0, cards.findIndex(function (c) { return !c.classList.contains("is-done"); }));
    form.classList.add("is-js");
    function lay() {
      cards.forEach(function (c, i) {
        var d = i - cur, x, y, r, s;
        if (d === 0) { x = 0; y = 0; r = 0; s = 1; }
        else if (d < 0) { x = -150 + (d + 1) * 56; y = 6 * -d; r = -3 + d * 0.6; s = 0.86 + d * 0.02; }
        else { x = 150 + (d - 1) * 48; y = 8 * d; r = 2 + d * 0.4; s = 0.84 - d * 0.02; }
        c.style.transform = "translateX(" + x + "px) translateY(" + y + "px) rotate(" + r + "deg) scale(" + s + ")";
        c.style.zIndex = d === 0 ? 50 : (d < 0 ? 20 + i : 20 - d);
        c.classList.toggle("is-on", d === 0);
        c.classList.toggle("is-left", d < 0);
        c.classList.toggle("is-right", d > 0);
        c.setAttribute("aria-checked", d === 0 ? "true" : "false");
        c.tabIndex = d === 0 ? 0 : -1;
      });
      hidden.value = cards[cur].dataset.value;
    }
    function sparkle(card) {
      if (reduce) return;
      var box = form.querySelector(".tr-fan").getBoundingClientRect(), r = card.getBoundingClientRect();
      for (var k = 0; k < 8; k++) {
        var s = document.createElement("span");
        s.className = "tr-spark" + (k % 3 === 0 ? " is-red" : "");
        s.style.left = (r.left - box.left + 16 + Math.random() * (r.width - 32)) + "px";
        s.style.top = (r.top - box.top + 24 + Math.random() * r.height * 0.6) + "px";
        s.style.animationDelay = (k * 70) + "ms";
        form.querySelector(".tr-fan").appendChild(s);
        setTimeout(s.remove.bind(s), 1600);
      }
    }
    function set(i) {
      if (i === cur || i < 0 || i >= cards.length) return;
      cur = i; lay(); cards[cur].focus({ preventScroll: true });
      setTimeout(function () { sparkle(cards[cur]); }, 220);
    }
    cards.forEach(function (c, i) {
      c.addEventListener("click", function (e) { if (i !== cur) { e.preventDefault(); set(i); } });
    });
    form.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); set(cur + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); set(cur - 1); }
    });
    lay();
  }

  // ── วงจุดบนภาพหน้า ───────────────────────────────────────────────────────────
  function review(data) {
    var pen = "red", base = "/trial/s/" + data.sid, tpl = document.getElementById("tr-pop"), pop = null;
    var counter = document.querySelector("[data-tr-count]");
    document.querySelectorAll(".tr-pen[data-pen]").forEach(function (b) {
      b.addEventListener("click", function () {
        pen = b.dataset.pen;
        document.querySelectorAll(".tr-pen[data-pen]").forEach(function (x) {
          x.classList.toggle("is-on", x === b); x.setAttribute("aria-pressed", x === b ? "true" : "false");
        });
      });
    });
    function canvasOf(m) {
      return document.querySelector('.tr-page[data-side="' + m.side + '"][data-page="' + m.page + '"] .tr-marks');
    }
    function count() {
      if (!counter) return;
      var c = { red: 0, brown: 0, pin: 0 };
      data.marks.forEach(function (m) { if (!m.deleted && m.el) c[m.pen] += 1; });   // เฉพาะหน้าที่เปิดอยู่
      counter.textContent = "จุดที่วงบนหน้านี้: แดง " + c.red + " · น้ำตาล " + c.brown + " · หมุด " + c.pin;
    }
    function draw(m) {
      var host = canvasOf(m);
      if (!host) return;
      var el = m.el || document.createElement("button");
      el.type = "button";
      el.className = "tr-mark tr-mark-" + m.pen;
      el.style.left = (m.fx * 100) + "%";
      el.style.top = (m.fy * 100) + "%";
      el.setAttribute("aria-label", data.pens[m.pen] + (m.topic ? " · " + m.topic + " " + (data.topics[m.topic] || "") : "") +
        (m.note ? " · " + m.note : ""));
      el.title = el.getAttribute("aria-label");
      if (!m.el) {
        el.addEventListener("click", function (e) { e.stopPropagation(); if (!data.locked) open(m); });
        host.appendChild(el);
        m.el = el;
      }
    }
    function close() { if (pop) { pop.remove(); pop = null; } }
    function open(m) {
      close();
      pop = tpl.content.firstElementChild.cloneNode(true);
      var note = pop.querySelector("[data-note]"), topic = m.topic, pp = m.pen;
      note.value = m.note || "";
      function mark() {
        pop.querySelectorAll("[data-topic]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.topic === topic); });
        pop.querySelectorAll("[data-set-pen]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.setPen === pp); });
      }
      pop.querySelectorAll("[data-topic]").forEach(function (b) {
        b.addEventListener("click", function () { topic = topic === b.dataset.topic ? "" : b.dataset.topic; mark(); });
      });
      pop.querySelectorAll("[data-set-pen]").forEach(function (b) {
        b.addEventListener("click", function () { pp = b.dataset.setPen; mark(); });
      });
      pop.querySelector("[data-save]").addEventListener("click", function () {
        post(base + "/marks/" + m.id, { topic: topic || "", note: note.value, pen: pp }).then(function () {
          m.topic = topic; m.note = note.value; m.pen = pp; draw(m); count(); close();
        }).catch(function (e) { alert(e.message); });
      });
      pop.querySelector("[data-del]").addEventListener("click", function () {
        post(base + "/marks/" + m.id, { delete: "1" }).then(function () {
          m.deleted = 1; if (m.el) m.el.remove(); count(); close();
        }).catch(function (e) { alert(e.message); });
      });
      mark();
      canvasOf(m).parentElement.appendChild(pop);
      pop.style.left = Math.min(m.fx * 100, 62) + "%";
      pop.style.top = (m.fy * 100) + "%";
      note.focus({ preventScroll: true });
    }
    document.querySelectorAll(".tr-page").forEach(function (fig) {
      var img = fig.querySelector("img");
      fig.querySelector(".tr-canvas").addEventListener("click", function (e) {
        if (data.locked || e.target !== img && !e.target.classList.contains("tr-marks")) return;
        if (pop) { close(); return; }
        var r = img.getBoundingClientRect();
        var fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
        if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
        post(base + "/marks", { side: fig.dataset.side, page_no: fig.dataset.page, fx: fx.toFixed(5),
                                fy: fy.toFixed(5), pen: pen })
          .then(function (m) { data.marks.push(m); draw(m); count(); open(m); })
          .catch(function (err) { alert(err.message); });
      });
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") close(); });
    // ── เปลี่ยนหน้าแยกแต่ละฝั่ง (ไม่โหลดทั้งหน้าใหม่) · บันทึกคู่หน้าที่เปิดเทียบ ──────────────
    var logTimer = null;
    function fig(side) { return document.querySelector('.tr-page[data-side="' + side + '"]'); }
    function pageOf(side) { var f = fig(side); return f ? parseInt(f.dataset.page, 10) : 0; }
    function logView() {
      if (data.locked) return;
      clearTimeout(logTimer);
      logTimer = setTimeout(function () {
        post(base + "/view", { cur: pageOf("cur"), prev_page: data.two ? pageOf("prev") : 0 }).catch(function () {});
      }, 600);
    }
    function syncUrl() {
      var q = "?page_no=" + pageOf("cur") + "&prev=" + (data.two ? 1 : 0) + (data.two ? "&pp=" + pageOf("prev") : "");
      if (window.history && history.replaceState) history.replaceState(null, "", base + q);
      var form = document.querySelector('form[action$="/done"]');
      if (form) {
        var list = data.pages.cur, i = list.indexOf(pageOf("cur"));
        form.querySelector('input[name="page_no"]').value = pageOf("cur");
        form.querySelector('input[name="go"]').value = i + 1 < list.length ? list[i + 1] : "";
        var pp = form.querySelector('input[name="pp"]');
        if (pp && data.two) pp.value = pageOf("prev");
        var btn = form.querySelector('button[type="submit"]');
        if (btn) btn.textContent = "ตรวจหน้านี้แล้ว" + (i + 1 < list.length ? " → หน้าถัดไป" : "");
      }
    }
    function show(side, page) {
      var f = fig(side), list = data.pages[side];
      if (!f || list.indexOf(page) < 0 || page === pageOf(side)) return;
      close();
      data.marks.forEach(function (m) { if (m.side === side && m.el) { m.el.remove(); m.el = null; } });
      f.dataset.page = page;
      var img = f.querySelector("img");
      img.src = base + "/page/" + side + "/" + page + ".png";
      img.alt = (side === "cur" ? "ฉบับปัจจุบัน" : "ฉบับก่อน") + " หน้า " + page;
      var sc = f.querySelector(".tr-scroll");
      if (sc) sc.scrollTop = 0;
      var sel = f.querySelector("[data-pick]");
      if (sel) sel.value = String(page);
      var i = list.indexOf(page);
      f.querySelectorAll("[data-go]").forEach(function (a) {
        var j = i + parseInt(a.dataset.go, 10);
        a.classList.toggle("is-off", j < 0 || j >= list.length);
      });
      if (side === "cur") {
        var chip = f.querySelector("[data-done-chip]");
        if (chip) chip.hidden = data.done.indexOf(page) < 0;
        document.querySelectorAll(".tr-pagelist a").forEach(function (a) {
          var on = parseInt(a.textContent, 10) === page;
          a.classList.toggle("is-on", on);
          if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
        });
        var nb = list[i + 1];
        if (nb) { var im = new Image(); im.src = base + "/page/cur/" + nb + ".png"; }
      } else if (list[i + 1]) {
        var im2 = new Image(); im2.src = base + "/page/prev/" + list[i + 1] + ".png";
      }
      data.marks.forEach(draw);
      count();
      syncUrl();
      logView();
    }
    document.querySelectorAll("[data-pager]").forEach(function (p) {
      var side = p.dataset.pager;
      p.querySelectorAll("[data-go]").forEach(function (a) {
        a.addEventListener("click", function (e) {
          e.preventDefault();
          var list = data.pages[side], j = list.indexOf(pageOf(side)) + parseInt(a.dataset.go, 10);
          if (j >= 0 && j < list.length) show(side, list[j]);
        });
      });
      var sel = p.querySelector("[data-pick]");
      if (sel) sel.addEventListener("change", function () { show(side, parseInt(sel.value, 10)); });
    });
    document.querySelectorAll(".tr-pagelist a").forEach(function (a) {
      a.addEventListener("click", function (e) { e.preventDefault(); show("cur", parseInt(a.textContent, 10)); });
    });
    data.marks.forEach(draw);
    count();
    (data.preload || []).forEach(function (u) {
      var go = function () { var im = new Image(); im.src = u; };
      if (window.requestIdleCallback) requestIdleCallback(go); else setTimeout(go, 400);
    });
  }

  function waiting() {
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        var b = e.submitter || f.querySelector("[data-pp-wait]");
        if (b && b.dataset.ppWait) { setTimeout(function () { b.disabled = true; b.textContent = b.dataset.ppWait; }, 0); }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var f = document.querySelector("[data-tr-fan]");
    if (f) fan(f);
    var d = document.getElementById("tr-data");
    if (d) review(JSON.parse(d.textContent));
    document.querySelectorAll(".tr-bar-fill[data-w]").forEach(function (b) { b.style.width = b.dataset.w + "%"; });
    waiting();
  });
})();
