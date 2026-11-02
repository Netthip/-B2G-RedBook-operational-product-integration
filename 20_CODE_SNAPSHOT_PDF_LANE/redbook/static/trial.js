/* ทดลองตรวจเล่ม (#43 · วิธีวัดผลฉบับ 0.2) — การ์ดเลือกเล่ม · วงจุดบนภาพหน้า (ทาง ร2) · แถบแดชบอร์ด
 * ไม่มีสคริปต์ฝังในหน้า (CSP script-src 'self') · ตำแหน่งจุดเก็บเป็นสัดส่วนของภาพ (0–1)
 * ทุกการบันทึกส่ง CSRF ไปกับฟอร์ม · ไม่ใช้ที่เก็บของเบราว์เซอร์
 * กันเห็นผลก่อนล็อก: หน้าที่กลับมาจากแคชย้อนหลัง (ปุ่มย้อนกลับ) โหลดใหม่ · แท็บที่ส่งไปแล้วจากแท็บอื่น โหลดใหม่เป็นแบบดูอย่างเดียว */
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
      if (e.target && e.target.closest && e.target.closest("input, select, textarea")) return;
      if (e.key === "ArrowRight") { e.preventDefault(); set(cur + 1); }
      if (e.key === "ArrowLeft") { e.preventDefault(); set(cur - 1); }
    });
    lay();
  }

  // ── หน้าตรวจ: วงจุด (ร2) · เปลี่ยนหน้าแยกแต่ละฝั่ง · ตัวช่วย "ตรวจหน้านี้แล้ว" ทั้งสองฉบับ ───────────
  function review(data) {
    var pen = "red", base = "/trial/s/" + data.sid, tpl = document.getElementById("tr-pop"), pop = null;
    var counter = document.querySelector("[data-tr-count]");
    var canMark = !data.locked && data.path === "r2";
    document.querySelectorAll(".tr-pen[data-pen]").forEach(function (b) {
      b.addEventListener("click", function () {
        pen = b.dataset.pen;
        document.querySelectorAll(".tr-pen[data-pen]").forEach(function (x) {
          x.classList.toggle("is-on", x === b); x.setAttribute("aria-pressed", x === b ? "true" : "false");
        });
      });
    });
    function gaps(m) {
      var out = [];
      if (!m.topic) out.push("หัวข้อ");
      if (!m.part) out.push("ส่วน");
      if (!m.cause) out.push("ต/ล");
      if (m.level !== "red" && m.level !== "brown") out.push("ระดับ");
      if (m.pen === "pin" && !(m.searched || "").trim()) out.push("ขอบเขตที่ค้น");
      if (data.xkind === "cross_year" && !m.xtype) out.push("ชนิดประเด็น");
      return out;
    }
    function canvasOf(m) {
      return document.querySelector('.tr-page[data-side="' + m.side + '"][data-page="' + m.page + '"] .tr-marks');
    }
    function count() {
      if (!counter) return;
      if (data.path !== "r2") { counter.textContent = ""; return; }
      var c = { red: 0, brown: 0, pin: 0 }, todo = 0;
      data.marks.forEach(function (m) {
        if (m.deleted) return;
        if (m.el) c[m.pen] += 1;                              // เฉพาะหน้าที่เปิดอยู่
        if (gaps(m).length) todo += 1;
      });
      counter.textContent = "จุดที่วงบนหน้าที่เปิด: แดง " + c.red + " · น้ำตาล " + c.brown + " · หมุด " + c.pin +
        (todo ? " · ทั้งรอบยังกรอกรายละเอียดไม่ครบ " + todo + " จุด" : "");
    }
    function label(m) {
      var t = data.pens[m.pen];
      if (m.pen === "pin" && m.level) t += " · ระดับ" + (data.levels[m.level] || "").split(" — ")[0];
      if (m.topic) t += " · " + m.topic + " " + (data.topics[m.topic] || "");
      if (m.part) t += " · ส่วน " + m.part;
      if (m.cause) t += " · " + (data.causes[m.cause] || "").split(" — ")[0];
      if (m.note) t += " · " + m.note;
      var g = gaps(m);
      return t + (g.length ? " · ยังขาด " + g.join(", ") : "");
    }
    function draw(m) {
      var host = canvasOf(m);
      if (!host) return;
      var el = m.el || document.createElement("button");
      el.type = "button";
      el.className = "tr-mark tr-mark-" + m.pen + (gaps(m).length ? " is-incomplete" : "");
      el.style.left = (m.fx * 100) + "%";
      el.style.top = (m.fy * 100) + "%";
      el.setAttribute("aria-label", label(m));
      el.title = el.getAttribute("aria-label");
      if (!m.el) {
        el.addEventListener("click", function (e) { e.stopPropagation(); if (canMark) open(m); });
        host.appendChild(el);
        m.el = el;
      }
    }
    function close() { if (pop) { pop.remove(); pop = null; } }
    function open(m) {
      close();
      pop = tpl.content.firstElementChild.cloneNode(true);
      var st = { pen: m.pen, level: m.level || (m.pen === "pin" ? "" : m.pen), topic: m.topic || "", part: m.part || "",
                 cause: m.cause || "", xtype: m.xtype || "" };
      var note = pop.querySelector("[data-note]"), searched = pop.querySelector("[data-searched]");
      var tlabel = pop.querySelector("[data-topic-label]");
      note.value = m.note || "";
      searched.value = m.searched || "";
      function paint() {
        pop.querySelectorAll("[data-set-pen]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.setPen === st.pen); });
        pop.querySelectorAll("[data-level]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.level === st.level); });
        pop.querySelectorAll("[data-topic]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.topic === st.topic); });
        pop.querySelectorAll("[data-part]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.part === st.part); });
        pop.querySelectorAll("[data-cause]").forEach(function (b) { b.classList.toggle("is-on", b.dataset.cause === st.cause); });
        var allowed = (data.xtype_by_topic || {})[st.topic] || [];
        if (st.xtype && allowed.indexOf(st.xtype) < 0) st.xtype = "";
        pop.querySelectorAll("[data-xtype]").forEach(function (b) {
          b.hidden = allowed.indexOf(b.dataset.xtype) < 0;
          b.classList.toggle("is-on", b.dataset.xtype === st.xtype);
        });
        pop.querySelector('[data-row="level"]').hidden = st.pen !== "pin";
        searched.hidden = st.pen !== "pin";
        tlabel.textContent = [st.topic ? st.topic + " " + (data.topics[st.topic] || "") : "",
                              st.part ? "ส่วน " + st.part + " " + (data.parts[st.part] || "") : ""].filter(Boolean).join(" · ");
      }
      function pick(sel, key) {
        pop.querySelectorAll("[" + sel + "]").forEach(function (b) {
          b.addEventListener("click", function () {
            var v = b.getAttribute(sel);
            st[key] = (key === "pen" || key === "level") ? v : (st[key] === v ? "" : v);
            if (key === "pen" && v !== "pin") st.level = v;
            paint();
          });
        });
      }
      pick("data-set-pen", "pen"); pick("data-level", "level"); pick("data-topic", "topic");
      pick("data-part", "part"); pick("data-cause", "cause"); pick("data-xtype", "xtype");
      pop.querySelector("[data-save]").addEventListener("click", function () {
        var body = { pen: st.pen, topic: st.topic, part: st.part, cause: st.cause, note: note.value };
        if (data.xkind === "cross_year") body.xtype = st.xtype;
        if (st.pen === "pin") { body.level = st.level; body.searched = searched.value; }
        post(base + "/marks/" + m.id, body).then(function () {
          m.pen = st.pen; m.topic = st.topic; m.part = st.part; m.cause = st.cause; m.note = note.value; m.xtype = st.xtype;
          m.level = st.pen === "pin" ? st.level : st.pen;
          if (st.pen === "pin") m.searched = searched.value;
          draw(m); count(); close();
        }).catch(function (e) { alert(e.message); });
      });
      pop.querySelector("[data-del]").addEventListener("click", function () {
        post(base + "/marks/" + m.id, { delete: "1" }).then(function () {
          m.deleted = 1; if (m.el) m.el.remove(); count(); close();
        }).catch(function (e) { alert(e.message); });
      });
      paint();
      canvasOf(m).parentElement.appendChild(pop);
      pop.style.left = Math.min(m.fx * 100, 58) + "%";
      pop.style.top = (m.fy * 100) + "%";
      var first = pop.querySelector("[data-topic]");
      if (first) first.focus({ preventScroll: true });
    }
    document.querySelectorAll(".tr-page").forEach(function (fig) {
      var img = fig.querySelector("img");
      fig.querySelector(".tr-canvas").addEventListener("click", function (e) {
        if (!canMark || e.target !== img && !e.target.classList.contains("tr-marks")) return;
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
    function syncForms() {
      ["cur", "prev"].forEach(function (side) {
        var box = document.querySelector('[data-donebox="' + side + '"]');
        if (!box) return;
        var list = data.pages[side], p = pageOf(side), i = list.indexOf(p), done = data.done[side].indexOf(p) >= 0;
        var chip = box.querySelector("[data-done-chip]");
        if (chip) chip.hidden = !done;
        box.querySelectorAll("form").forEach(function (form) {
          var undo = form.hasAttribute("data-undo-form");
          form.hidden = undo ? !done : done;
          var set = function (name, v) { var x = form.querySelector('input[name="' + name + '"]'); if (x) x.value = v; };
          set("page_no", p);
          set("go", i + 1 < list.length ? list[i + 1] : "");
          set("pp", pageOf("prev") || "");
          set("cur", pageOf("cur"));
          var btn = form.querySelector('button[type="submit"]');
          if (btn && !undo) btn.textContent = "ตรวจหน้านี้แล้ว" + (i + 1 < list.length ? " →" : "");
        });
      });
    }
    function syncUrl() {
      var q = "?page_no=" + pageOf("cur") + "&prev=" + (data.two ? 1 : 0) + (data.two ? "&pp=" + pageOf("prev") : "");
      if (window.history && history.replaceState) history.replaceState(null, "", base + q);
      syncForms();
    }
    function show(side, page) {
      var f = fig(side), list = data.pages[side];
      if (!f || list.indexOf(page) < 0 || page === pageOf(side)) return;
      close();
      data.marks.forEach(function (m) { if (m.side === side && m.el) { m.el.remove(); m.el = null; } });
      f.dataset.page = page;
      var img = f.querySelector("img");
      img.src = base + "/page/" + side + "/" + page + ".png";
      img.alt = (data.labels[side] || "") + " หน้า " + page;
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
        document.querySelectorAll(".tr-pagelist a").forEach(function (a) {
          var on = parseInt(a.textContent, 10) === page;
          a.classList.toggle("is-on", on);
          if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
        });
      }
      if (list[i + 1]) { var im = new Image(); im.src = base + "/page/" + side + "/" + list[i + 1] + ".png"; }
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
    syncForms();
    (data.preload || []).forEach(function (u) {
      var go = function () { var im = new Image(); im.src = u; };
      if (window.requestIdleCallback) requestIdleCallback(go); else setTimeout(go, 400);
    });
    // แท็บอื่นส่งใบประกาศไปแล้ว → กลับมาที่แท็บนี้ = โหลดใหม่เป็นแบบดูอย่างเดียว (เซิร์ฟเวอร์ไม่รับการแก้อยู่แล้ว)
    if (!data.locked) {
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState !== "visible") return;
        fetch("/api/trial/s/" + data.sid, { credentials: "same-origin" }).then(function (r) { return r.json(); })
          .then(function (j) { if (j && (j.locked || j.status)) location.reload(); }).catch(function () {});
      });
    }
  }

  function waiting() {
    document.querySelectorAll("form").forEach(function (f) {
      f.addEventListener("submit", function (e) {
        var b = e.submitter || f.querySelector("[data-pp-wait]");
        if (b && b.dataset.ppWait) { setTimeout(function () { b.disabled = true; b.textContent = b.dataset.ppWait; }, 0); }
      });
    });
  }

  // หน้าที่กลับมาจากแคชย้อนหลัง (ปุ่มย้อนกลับ/ไปข้างหน้า) อาจเป็นสภาพก่อนส่ง — โหลดใหม่จากเซิร์ฟเวอร์เสมอ
  window.addEventListener("pageshow", function (e) { if (e.persisted) location.reload(); });

  document.addEventListener("DOMContentLoaded", function () {
    var f = document.querySelector("[data-tr-fan]");
    if (f) fan(f);
    var d = document.getElementById("tr-data");
    if (d) review(JSON.parse(d.textContent));
    document.querySelectorAll(".tr-bar-fill[data-w]").forEach(function (b) { b.style.width = b.dataset.w + "%"; });
    waiting();
  });
})();
