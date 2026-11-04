<script lang="ts" module>
  // ร่างคำตัดสินที่ยังไม่บันทึก (ต่อข้อ) — เปลี่ยนข้อแล้วกลับมายังอยู่ · หายเมื่อปิดแท็บ ไม่บันทึกที่ใด
  const drafts = new Map<string, { choice: string; note: string }>();
</script>

<script lang="ts">
  // หลักฐาน A | B + บันทึกผล · ← → เลื่อนดูอย่างเดียว ไม่บันทึก · เลือกผลแล้วต้องกดบันทึก (หรือ Ctrl+Enter) เอง
  // ทวนรอบ 2 (U2): ด้านบนเหลือ ความคืบหน้า · จุดนี้ · ภาพสองฝั่ง · ตัวเลือก — รายละเอียดพับไว้ท้ายหน้า · รายการจุดด้านซ้ายแทนปุ่มก่อนหน้า/ถัดไป
  import { onDestroy } from "svelte";
  import { go, link } from "../lib/router.svelte";
  import { ApiError } from "../lib/api";
  import { toast } from "../lib/notify.svelte";
  import PagePeek from "./PagePeek.svelte";
  import DevBadge from "../lib/DevBadge.svelte";
  import { TREND_MARK, TREND_SAY, absDelta, trend, backTo, clip, decide, fitSrc, hasValues, loadList, loadRun, loadView, offsetsOf, pageFull, printedOf, peekList, peekRun, peekView, prefetch,
           type AB, type PFinding, type PRun, type PView } from "../lib/pair";

  let { rid, fid }: { rid: string; fid: string } = $props();
  // props ของ Svelte 5 อ่านค่าสด — ตอนหน้านี้ถูกแทน fid จะเป็นของข้อใหม่แล้ว จึงจำที่อยู่ของข้อนี้ไว้ตั้งแต่ต้น
  const key = `${rid}/${fid}`;
  const here = `/r/p/${rid}/f/${fid}`;

  let v = $state<PView | null>(null);
  let r = $state<PRun | null>(peekRun(rid) ?? null);
  let err = $state("");
  let choice = $state("");
  let note = $state("");
  let saved = $state({ choice: "", note: "" });
  let restored = $state(false);
  let busy = $state(false);
  let formErr = $state("");
  let writable = $state(true);
  let list = $state<PFinding[] | null>(peekList(rid) ?? null);
  // ค่าตั้งต้น = ลำดับในเล่ม · เรียงตามขนาดผลต่างเป็นตัวเลือก (เรียงแบบนี้ข้อผลต่างน้อยอาจถูกทวนน้อยลง — รอ Bo D3)
  let order = $state<"book" | "delta">("book");
  const wide = typeof matchMedia === "function" && matchMedia("(min-width: 1600px)").matches;
  let noteOpen = $state(false);
  // Bo 6463792323: รายการจุดพับได้ (จอแคบเริ่มพับ) แต่ยังเห็นจำนวน/สถานะ · ปุ่มดูความหมายก่อนเลือก (คีย์บอร์ด/สัมผัสได้) · ขยายภาพเห็นชัด
  let listOpen = $state(wide);
  // จอต่ำกว่า 1600px (รวมโน้ตบุ๊ก 1366) รายการจุดเลื่อนออกมาทับจากซ้าย ให้ภาพ A|B คู่กันได้ความกว้างเต็ม (กิ๊ฟ 30 ต.ค.) · ย่อจอ = พับเอง
  let narrow = $state(!wide);
  $effect(() => {
    if (typeof matchMedia !== "function") return;
    const m = matchMedia("(min-width: 1600px)");
    const on = () => { narrow = !m.matches; listOpen = m.matches; };
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  });
  const pickPoint = (e: MouseEvent) => { link(e); if (narrow) listOpen = false; };
  // จัดหน้าแบบแผงขวา + แถบบันทึกล่างจอ — เลือกจาก 3 แบบที่ลองบนจอโน้ตบุ๊ก (กิ๊ฟ 29 ต.ค.): แถบล่างเต็มบังภาพ · ตัวเลือกใต้ภาพต้องเลื่อนจอทุกข้อ
  let peek = $state("");
  let zoom = $state<HTMLDialogElement>();
  // หน้าที่กำลังดูของแต่ละฝั่ง · null = ภาพตัดตรงจุดที่ระบบชี้
  let at = $state<Record<AB, number | null>>({ A: null, B: null });
  // ภาพตัดจากหลังบ้านกว้างเต็มหน้ากระดาษ (zoom 1.6) — ตัดขอบกระดาษว่างซ้ายขวาออกให้ตัวเลขใหญ่ขึ้นเมื่อวาง A|B คู่กัน
  // เก็บช่วงกว้างอย่างน้อย 60% ของหน้า (บรรทัดสั้นไม่ซูมจนเสียบริบท) · ไม่รู้ขนาดภาพ/ไม่มีกรอบ = แสดงเต็มกว้างเหมือนเดิม
  // ขอบขวาเก็บถึงสุดหน้าเสมอ — กรอบบางจุดครอบแค่ชื่อรายการ ส่วนจำนวนเงินอยู่คอลัมน์ขวา (ทดลองคณะทำงาน 4 พ.ย.: เห็นชื่อแต่ไม่เห็นเลข)
  const EV_ZOOM = 1.6, PAD = 24, MIN_SPAN = 0.6;
  let natW = $state<Record<AB, number>>({ A: 0, B: 0 });
  const trim = (b: number[] | null, w: number) => {
    const page = w / EV_ZOOM;
    if (!b || !page) return null;
    let l = Math.max(0, b[0] - PAD), r = page;
    const need = page * MIN_SPAN - (r - l);
    if (need > 0) { l = Math.max(0, l - need / 2); r = Math.min(page, l + page * MIN_SPAN); l = Math.max(0, r - page * MIN_SPAN); }
    const span = r - l;
    return span >= page * 0.98 ? null : { width: `${(page / span) * 100}%`, ml: `${(-l / span) * 100}%` };
  };
  const pageSrc = (s: AB, n: number) => `/pdfpair/runs/${encodeURIComponent(rid)}/page/${s}/${n}.png`;
  function step(s: AB, n: number, rs: { first: number; last: number }) { at[s] = Math.min(rs.last, Math.max(rs.first, n)); }
  // ภาพ A|B สูงเต็มพื้นที่ที่เหลือของจอ แทนแถบตัดสั้นที่เหลือที่ว่างครึ่งล่าง (กิ๊ฟ 2 พ.ย. · จอ 14" 1366×768 และ 27" 2560×1440)
  // ภาพทั้งหน้าเลื่อนให้กรอบเน้นอยู่ราวหนึ่งในสามจากบน — เห็นบรรทัดก่อน/หลังเป็นบริบท · ต่ำสุด 280px
  let evsEl = $state<HTMLDivElement>();
  let evh = $state(0);
  function fit() {
    const shot = evsEl?.querySelector<HTMLElement>(".shot");
    if (!shot) return;
    const foot = document.querySelector<HTMLElement>(".foot-s")?.offsetHeight ?? 0;
    evh = Math.max(280, Math.floor(innerHeight - (shot.getBoundingClientRect().top + scrollY) - foot - 16));
  }
  function toBox(img: HTMLImageElement, bbox: number[] | null) {
    fit();
    const box = img.closest<HTMLElement>(".shot");
    if (!box || !bbox || !img.naturalWidth) return;
    requestAnimationFrame(() => { box.scrollTop = Math.max(0, bbox[1] * EV_ZOOM * (img.clientWidth / img.naturalWidth) - box.clientHeight * 0.35); });
  }
  let noteEl = $state<HTMLTextAreaElement>();
  let touched = false;

  function adopt(x: PView) {
    v = x;
    writable = x.writable;
    const d = x.finding.decision;
    saved = { choice: d?.choice ?? "", note: d?.note ?? "" };
    if (!touched) {
      const dr = drafts.get(key);
      restored = !!dr;
      ({ choice, note } = dr ?? saved);
    }
  }
  const cached = peekView(rid, fid);
  if (cached) adopt(cached);
  // ข้อนี้ก่อน แล้วค่อยเตรียมข้อที่น่าจะไปต่อ (ภาพเฉพาะข้อถัดไปที่ยังไม่ตัดสิน) — เซิร์ฟเวอร์ตอบทีละคำขอ
  loadView(rid, fid).then((x) => {
    adopt(x);
    prefetch(rid, x.next_pending_id);
    if (x.next_id !== x.next_pending_id) prefetch(rid, x.next_id, false);
  }).catch((e) => { if (v) toast((e as Error).message, true); else err = (e as Error).message; });
  // ภาพรวม/รายการใช้แค่ป้ายและลำดับ — มีในแคชแล้วไม่ดึงซ้ำ (บันทึกผลแก้ค่าในแคชให้เอง)
  if (!r) loadRun(rid, 30000).then((x) => (r = x)).catch(() => {});
  if (!list) loadList(rid, 60000).then((x) => (list = x)).catch(() => {});

  const todo = $derived((list ?? []).filter((f) => !f.info));
  const pos = $derived(todo.findIndex((f) => f.id === fid));
  const doneN = $derived(todo.filter((f) => f.decision).length);
  const mag = (f: PFinding) => { const n = Math.abs(parseFloat(f.delta)); return Number.isFinite(n) ? n : -1; };
  // เรียงตามผลต่างเป็นตัวเลือกเท่านั้น (Bo) — แสดงผลต่างพร้อมหน่วย · ข้อที่ไม่มีตัวเลขแยกไว้ท้าย ไม่ปนในลำดับ
  const shown = $derived(order === "delta" ? todo.filter((x) => mag(x) >= 0).sort((x, y) => mag(y) - mag(x)) : todo);
  const nonum = $derived(order === "delta" ? todo.filter((x) => mag(x) < 0) : []);
  // ป้ายฉบับจริงแทน "A/B" (ป้ายมาจากเซิร์ฟเวอร์ · ตัดคำนำ "ฉบับ A · ")
  const short = (s: AB) => r?.run.sides[s].label.replace(/^ฉบับ [AB] · /, "") ?? `ฉบับ ${s}`;

  const dirty = $derived(!!v && (choice !== saved.choice || note !== saved.note));
  // การปรับลดครั้งเดียวไหลไปทุกตารางรวม ⇒ หลายจุดยอดต่างเท่ากัน (ทดลองคณะทำงาน 4 พ.ย.: 25 จาก 28 จุด · กิ๊ฟให้แก้ · แจ้ง Bo #44)
  // เสนอจุดที่ยังไม่ได้ตัดสินและยอดต่าง+หน่วยเท่ากัน ให้ผู้ตรวจเลือกเอง · ระบบบันทึกแยกทีละจุดพร้อมหมายเหตุ ไม่รวมจุด ไม่เปลี่ยนตัวนับ
  // ใช้ได้เฉพาะความเห็นครั้งแรกของข้อนี้ — แก้ความเห็นเดิมยังต้องใส่เหตุผลทีละจุดตามเดิม
  // ยอดเดียวกันพิมพ์ต่างหน่วยได้ (ตารางรวมเป็นล้านบาท ทศนิยม 4 ตำแหน่ง) ⇒ เทียบเป็นบาท โดยยอมคลาดไม่เกินครึ่งหลักสุดท้ายที่พิมพ์
  const PER: Record<string, number> = { "บาท": 1, "พันบาท": 1e3, "ล้านบาท": 1e6 };
  const baht = (x: PFinding) => {
    const n = parseFloat(x.delta), k = PER[x.unit];
    if (!Number.isFinite(n) || !n || !k) return null;
    return { v: n * k, tol: 0.5 * 10 ** -((x.delta.split(".")[1] ?? "").length) * k };
  };
  const same = (x: PFinding, y: PFinding) => {
    const p = baht(x), q = baht(y);
    if (p && q) return Math.abs(p.v - q.v) <= Math.max(p.tol, q.tol);
    return !p && !q && !!(parseFloat(x.delta) || 0) && x.delta === y.delta && x.unit === y.unit;
  };
  const twins = $derived(!v || v.finding.info || saved.choice ? []
    : todo.filter((x) => x.id !== fid && !x.decision && same(x, v!.finding)));
  let alsoOn = $state(false);
  let also = $state<Record<string, boolean>>({});
  $effect(() => { for (const x of twins) if (!(x.id in also)) also[x.id] = true; });
  const alsoIds = $derived(alsoOn ? twins.filter((x) => also[x.id]).map((x) => x.id) : []);
  const picked = $derived(r?.decisions.find((d) => d.key === choice));
  const backUrl = $derived(`${backTo.get(rid) ?? `/r/p/${rid}`}#f-${fid}`);

  function pick(k: string) {
    if (!writable || busy || v?.finding.info) return;
    choice = k; touched = true; formErr = "";
  }
  // หมายเหตุพับไว้ — เปิดเองเมื่อกด หรือเมื่อมีข้อความ/จำเป็นต้องระบุ (เปลี่ยนผลเดิม)
  // ป้ายสั้นของผลต่อการใช้ผล (ตัดจาก use_label ของเซิร์ฟเวอร์) — ติดตัวเลือกที่ไม่ปิดข้อ
  const useShort = (l?: string) => (l ?? "").split(" — ")[0].split(" (")[0];
  const showNote = $derived(noteOpen || !!note || !!saved.choice || !!formErr || !!choice);

  function goNext(nextPending: string) {
    if (nextPending && nextPending !== fid) go(`/r/p/${rid}/f/${nextPending}`);
    else { toast("บันทึกครบทุกจุดในรอบนี้แล้ว — นี่คือสรุปของรอบ"); go(`/r/p/${rid}/summary`); }
  }

  async function save() {
    if (!v || busy || !writable || v.finding.info || !choice || !dirty) return;
    busy = true; formErr = "";
    const ids = alsoIds;   // จับไว้ก่อน — บันทึกข้อนี้แล้ว twins ว่าง (saved.choice มีค่า)
    try {
      const res = await decide(rid, fid, choice, note);
      const d = res.finding.decision;
      saved = { choice: d?.choice ?? choice, note: d?.note ?? note };
      ({ choice, note } = saved);
      drafts.delete(key);
      restored = false;
      v = { ...v, finding: res.finding, next_pending_id: res.next_pending_id };
      let next = res.next_pending_id, ok = 0;
      const fail: string[] = [];
      const with_ = `บันทึกพร้อมกับจุด “${clip(v.finding.subject, 60)}${v.finding.column ? ` · ${v.finding.column}` : ""}” (ยอดต่างเท่ากัน)`;
      for (const id of ids) {
        try {
          const x = await decide(rid, id, choice, note.trim() ? `${note.trim()} · ${with_}` : with_);
          next = x.next_pending_id; ok++;
        } catch (e) {
          fail.push((e as Error).message);
          if (e instanceof ApiError && e.code === "superseded") break;
        }
      }
      if (fail.length) toast(`บันทึกข้อนี้ + อีก ${ok} จุดแล้ว · อีก ${fail.length} จุดบันทึกไม่ได้ (${clip(fail[0], 60)}) — เปิดจุดนั้นแล้วบันทึกเอง`, true);
      else toast(`บันทึกความเห็นข้อนี้แล้ว (${d?.choice_label ?? ""})${ok ? ` พร้อมอีก ${ok} จุดที่ยอดต่างเท่ากัน` : ""} — ไปจุดถัดไปได้`);
      goNext(next);
    } catch (e) {
      if (e instanceof ApiError && e.code === "superseded") { writable = false; formErr = e.message; }
      else if (e instanceof ApiError && e.code === "invalid") { formErr = e.message; noteEl?.focus(); }
      else toast((e as Error).message, true);
    } finally { busy = false; }
  }

  // ออกจากข้อนี้ทั้งที่ยังไม่บันทึก → เก็บร่างไว้ + บอกให้รู้ (กลับมาได้)
  onDestroy(() => {
    if (dirty && v && !v.finding.info) {
      drafts.set(key, { choice, note });
      const subject = v.finding.subject;
      toast(`ยังไม่ได้บันทึกผลของ “${clip(subject, 40)}” — เก็บร่างไว้ให้แล้ว`, false,
            { label: "กลับไปบันทึก", run: () => go(here) });
    } else drafts.delete(key);
  });

  function onkey(e: KeyboardEvent) {
    if (e.altKey || e.metaKey || !v) return;
    if (e.key === "Enter" && e.ctrlKey) { e.preventDefault(); save(); return; }
    const t = e.target;
    if (e.ctrlKey || (t instanceof Element && t.closest("input, textarea, select"))) return;
    if (e.key === "ArrowLeft" && v.prev_id) { e.preventDefault(); go(`/r/p/${rid}/f/${v.prev_id}`); }
    else if (e.key === "ArrowRight" && v.next_id) { e.preventDefault(); go(`/r/p/${rid}/f/${v.next_id}`); }
    else if (/^[1-9]$/.test(e.key) && r) {
      const d = r.decisions[Number(e.key) - 1];
      if (d) { e.preventDefault(); pick(d.key); }
    }
  }
</script>

<svelte:window onkeydown={onkey} onresize={fit} />

{#if err}
  <div class="card msg">{err} · <a href="/r/p/{rid}" onclick={link}>กลับไปภาพรวม</a></div>
{:else if !v}
  <div class="card skeleton sk"></div>
{:else}
  {@const f = v.finding}
  {@const t = trend(f)}
  <div class="bar">
    <a class="btn small ghost" href={backUrl} onclick={link}>← ภาพรวม</a>
    <!-- จอต่ำกว่า 1600px: ปุ่มเปิดรายการจุดอยู่แถวบนนี้ ไม่กินแถวของตัวเอง (คณะทำงาน UI 30 ต.ค.) -->
    {#if narrow}<button class="btn small ghost" aria-expanded={listOpen} onclick={() => (listOpen = !listOpen)}>☰ รายการจุด <span class="pt-n">{`✓ ${doneN}/${todo.length}`}</span></button>{/if}
    {#if r}<span class="ctx"><b>{r.run.agency}</b><span class="hint">{` · ${short("A")} → ${short("B")}`}</span></span>
      <span class="grow"></span><DevBadge text={r.run.profile_status_label} />{/if}
  </div>

  {#if r?.run.superseded_by}
    <div class="note danger" role="alert"><b>รอบนี้ถูกแทนแล้ว</b> — ผลและความเห็นเดิมเก็บไว้ดูย้อนหลังเท่านั้น บันทึกเพิ่มไม่ได้
      <a class="btn small" href="/r/p/{r.run.superseded_by}" onclick={link}>ไปรอบใหม่ →</a></div>
  {/if}

  <div class="layout" class:folded={!listOpen}>
    <nav class="plist" aria-label="รายการจุด">
      <button class="ptoggle" aria-expanded={listOpen} onclick={() => (listOpen = !listOpen)} title={listOpen ? "พับรายการจุด" : "เปิดรายการจุด"}>
        <span class="pt-t">{listOpen ? "รายการจุด" : "☰"}</span>
        <span class="pt-n">{`✓ ${doneN}/${todo.length}`}</span><span class="pt-c" aria-hidden="true">{listOpen ? "‹" : "›"}</span>
      </button>
      {#if listOpen}
      <div class="sorter" role="radiogroup" aria-label="เรียงรายการ">
        <button role="radio" aria-checked={order === "book"} class:on={order === "book"} onclick={() => (order = "book")}>ตามลำดับในเล่ม</button>
        <button role="radio" aria-checked={order === "delta"} class:on={order === "delta"} onclick={() => (order = "delta")}>ผลต่างมาก → น้อย</button>
      </div>
      {#snippet item(x: PFinding)}
        <li><a href="/r/p/{rid}/f/{x.id}" onclick={pickPoint} class:cur={x.id === fid} class:done={!!x.decision}
               aria-current={x.id === fid ? "page" : undefined}>
          <span class="mk" aria-hidden="true">{x.decision ? "✓" : ""}</span>
          <span class="pt">{clip(x.subject, 70)}{#if order === "delta" && x.delta_text}{@const t = trend(x)}<small class="dt {t}">{`${TREND_MARK[t]} ${t ? absDelta(x) : x.delta_text}`}</small>{/if}
            <small>{x.decision ? x.decision.choice_label : x.topic_label}</small></span>
        </a></li>
      {/snippet}
      <ol class="pl">{#each shown as x (x.id)}{@render item(x)}{/each}</ol>
      {#if nonum.length}
        <p class="plh">ไม่มีตัวเลขให้เทียบ ({nonum.length})</p>
        <ol class="pl">{#each nonum as x (x.id)}{@render item(x)}{/each}</ol>
      {/if}
      {/if}
    </nav>
    {#if listOpen && narrow}<button class="scrim" aria-label="ปิดรายการจุด" onclick={() => (listOpen = false)}></button>{/if}

    <div class="main">
      <!-- หัวสั้น: ภาพหลักฐานคือพระเอกของหน้า (กิ๊ฟ 30 ต.ค.) — ลำดับจุดย้ายมาข้างชื่อ · ตัดคำนำ "ระบบพบ:" -->
      <header class="head">
        <div class="hrow"><h1>{f.subject}</h1>
          {#if pos >= 0}<span class="pos" aria-label="จุดที่ {pos + 1} จาก {todo.length} · บันทึกแล้ว {doneN}">{pos + 1}/{todo.length}</span>{/if}</div>
        <p class="what">{f.info ? "ข้อมูลเพิ่มเติม (ไม่ต้องตอบ)" : f.kind_label}{#if f.column}{` · ช่อง ${f.column}`}{/if}
          {#if f.within}{` · ภายใน${short(f.within)}`}{/if}</p>
        {#if hasValues(f)}
          <p class="vline">
            <span><small>{short("A")}</small><b class="va" class:gone-v={t === "gone"}>{f.a.amount_text || "—"}</b></span>
            <span class="arr" aria-hidden="true">→</span>
            <span><small>{short("B")}</small><b class="vb" class:added-v={t === "added"}>{f.b.amount_text || "—"}</b></span>
            {#if t === "gone" || t === "added"}<span class="dl {t}"><b>{TREND_MARK[t]} {TREND_SAY[t]}</b></span>
            {:else if f.delta_text}<span class="dl {t}" title={TREND_SAY[t]}><b>{#if t}{`${TREND_MARK[t]} `}{/if}{t ? absDelta(f) : f.delta_text}</b></span>{/if}
          </p>
        {/if}
      </header>
      {#if f.caveats.length}<p class="note warn" role="alert"><b>ต้องให้คนยืนยันก่อนใช้:</b> {f.caveats.join(" · ")}</p>{/if}

      <div class="evs" bind:this={evsEl}>
        {#each ["A", "B"] as const as s, si (s)}
          {@const sd = s === "A" ? f.a : f.b}
          {@const o = s === "A" ? "B" : "A"}
          {@const od = s === "A" ? f.b : f.a}
          {@const rs = r?.run.sides[s]}
          <section class="card ev ev-{s.toLowerCase()}" aria-labelledby="ev-{s}">
            <h2 id="ev-{s}">{#if si}<span class="arr" aria-hidden="true">→</span>{/if}{short(s)} <small class="code">ฉบับ {s}</small></h2>
            {#if sd.page && sd.evidence_png}
              {@const cur = at[s] ?? sd.page}
              {@const tr = at[s] === null ? trim(sd.bbox, natW[s]) : null}
              <div class="evbar">
                <span title="หน้าพิมพ์ = เลขบนหัวกระดาษของเล่ม">หน้าพิมพ์ {printedOf(cur, rs?.printed_offset)}<small class="pdfno" title="ลำดับหน้าในไฟล์ PDF (นับปกและสารบัญด้วย)"> · หน้า PDF {cur}</small></span>
                <span class="grow"></span>
                {#if at[s] === null}<button class="btn small ghost" onclick={() => (at[s] = sd.page)}>ดูทั้งหน้า</button>{/if}
                {#if rs}
                  <button class="btn small ghost" disabled={cur <= rs.first} onclick={() => step(s, cur - 1, rs)} aria-label="หน้าก่อน">‹</button>
                  <button class="btn small ghost" disabled={cur >= rs.last} onclick={() => step(s, cur + 1, rs)} aria-label="หน้าถัดไป">›</button>
                {/if}
                {#if at[s] !== null}<button class="btn small" onclick={() => (at[s] = null)} title="กลับไปจุดที่ระบบชี้">↺ กลับ</button>{/if}
              </div>
              <figure>
                <!-- ไม่มีคำอธิบายใต้ภาพ: กรอบเน้นบอกเองว่าเทียบตรงไหน (กิ๊ฟ 28 ต.ค.) · กดภาพ = เปิดภาพใหญ่ -->
                <button class="shot" class:full={at[s] !== null} style:height={at[s] === null && evh ? `${evh}px` : undefined}
                        title="ขยายภาพสองฉบับ" onclick={() => zoom?.showModal()}>
                  <img src={at[s] === null ? fitSrc(sd) : at[s] === sd.page ? `${sd.evidence_png}?full=1` : pageSrc(s, at[s])}
                       style:width={tr?.width} style:max-width={tr ? "none" : undefined} style:margin-left={tr?.ml}
                       onload={(e) => { const im = e.currentTarget as HTMLImageElement; if (at[s] === null) { natW[s] = im.naturalWidth; toBox(im, sd.bbox); } }}
                       alt="ภาพจาก {short(s)} {pageFull(cur, rs?.printed_offset)}{at[s] === null || cur === sd.page ? ' — กรอบเน้น = บรรทัดที่ระบบอ่านค่านี้' : ''}" />
                </button>
                {#if at[s] === null}<span class="zhint" aria-hidden="true">⤢ กดเพื่อขยาย</span>{/if}
              </figure>
            {:else if f.within && f.within !== s}
              <p class="empty-ev">จุดนี้อยู่ใน{short(f.within)}เท่านั้น</p>
            {:else}
              <p class="absent">ระบบหาไม่เจอ — <b>อาจมีอยู่</b> ลองเลื่อนหาด้านล่าง</p>
              {#if rs}
                {@const ors = r?.run.sides[o]}
                {@const guess = !!(od.page && ors)}
                <PagePeek {rid} side={s} first={rs.first} last={rs.last} off={rs.printed_offset}
                  start={guess && od.page && ors ? rs.first + (od.page - ors.first) : rs.first}
                  note={guess ? `เริ่มที่หน้าตำแหน่งเดียวกับ${short(o)} (ประมาณ — เลื่อนหาเอง)` : ""} />
              {/if}
            {/if}
          </section>
        {/each}
      </div>

      <!-- ขยาย: สองฉบับเคียงกันเต็มจอ · Esc หรือปุ่มปิด -->
      <dialog class="zoom" bind:this={zoom} onclick={(e) => { if (e.target === zoom) zoom?.close(); }}>
        <div class="zhead"><b>{f.subject}</b><span class="grow"></span>
          <button class="btn small" onclick={() => zoom?.close()}>ปิด (Esc)</button></div>
        <div class="zgrid">
          {#each ["A", "B"] as const as s, si (s)}
            {@const sd = s === "A" ? f.a : f.b}
            {@const zsrc = at[s] === null || at[s] === sd.page ? `${sd.evidence_png}?full=1` : pageSrc(s, at[s] ?? 1)}
            <section class="zcol ev-{s.toLowerCase()}">
              <h2>{#if si}<span class="arr" aria-hidden="true">→</span>{/if}{short(s)} <small class="code">{sd.page ? pageFull(at[s] ?? sd.page, offsetsOf(r)[s]) : ""}</small></h2>
              {#if sd.page && sd.evidence_png}
                <img src={zsrc} alt="ภาพเต็มหน้าจาก {short(s)}" />
                <a class="hint" href={zsrc} target="_blank" rel="noopener">เปิดในแท็บใหม่ ↗</a>
              {:else}<p class="hint">ไม่มีภาพของฉบับนี้</p>{/if}
            </section>
          {/each}
        </div>
      </dialog>

      <details class="more">
        <summary>รายละเอียดเพิ่มเติมของจุดนี้</summary>
        {#if f.note}<p class="why">{f.note}</p>{/if}
        {#if hasValues(f)}
          <div class="card vals">
            {#each ["A", "B"] as const as s (s)}
              {@const sd = s === "A" ? f.a : f.b}
              <div class="cell"><span class="lbl">{short(s)}</span><b>{sd.amount_text || "—"}</b>
                {#if sd.unit_note || sd.raw_note}<small>{[sd.unit_note, sd.raw_note].filter(Boolean).join(" · ")}</small>{/if}</div>
            {/each}
            <div class="cell cell-d"><span class="lbl">ผลต่าง</span><b>{f.delta_text || "—"}</b>
              {#if f.tolerance_text && !f.parts.length}<small>เกณฑ์ปัดเศษ {f.tolerance_text}</small>{/if}</div>
          </div>
        {/if}
        {#if f.parts.length}
          <div class="card parts">
            <h3>องค์ประกอบที่ใช้คำนวณ {f.parts.length} ค่า{#if f.tolerance_text}{` · เกณฑ์ปัดเศษ ${f.tolerance_text}`}{/if}</h3>
            <div class="tbl"><table>
              <thead><tr><th scope="col">รายการ</th><th scope="col">ค่าที่พิมพ์</th><th scope="col">หน้า PDF</th><th scope="col">ต้องยืนยัน</th></tr></thead>
              <tbody>{#each f.parts as p, i (i)}<tr><td>{p.label}</td><td class="mono">{p.raw || p.value} {p.unit}</td>
                <td>{p.page ?? "—"}</td><td>{p.flag_labels.join(" · ") || "—"}</td></tr>{/each}</tbody>
            </table></div>
            {#if v.rounding_policy || r?.rounding_policy}<p class="hint">{v.rounding_policy || r?.rounding_policy}</p>{/if}
          </div>
        {/if}
        {#if v.diff.a.length || v.diff.b.length}
          <section class="card diff" aria-label="ส่วนที่ข้อความต่างกัน">
            <h3>ส่วนที่ข้อความต่างกัน</h3>
            <p><small>{short("A")}</small> {#each v.diff.a as [k, t], i (i)}{#if k === "same"}{t}{:else}<del>{t}</del>{/if}{/each}</p>
            <p><small>{short("B")}</small> {#each v.diff.b as [k, t], i (i)}{#if k === "same"}{t}{:else}<ins>{t}</ins>{/if}{/each}</p>
          </section>
        {/if}
        {#each ["A", "B"] as const as s (s)}
          {@const sd = s === "A" ? f.a : f.b}
          {#if sd.text}<p class="excerpt"><small>ข้อความที่ระบบอ่านได้จาก{short(s)}</small> “{sd.text.slice(0, 300)}”</p>{/if}
        {/each}
        <p class="hint">ตำแหน่งและค่าที่แสดงได้จากการอ่านชั้นข้อความของ PDF · <kbd>←</kbd> <kbd>→</kbd> เลื่อนจุด ·
          <kbd>1</kbd>–<kbd>{r?.decisions.length ?? 6}</kbd> เลือกความเห็น · <kbd>Ctrl</kbd>+<kbd>Enter</kbd> บันทึก</p>
      </details>
    </div>

    <aside class="card decide" aria-labelledby="dec-h">
      {#if f.info}
        <h2 id="dec-h">ข้อมูลเพิ่มเติม</h2>
        <p class="hint">จุดนี้เป็นข้อมูลเพิ่มเติม (เช่น การเปลี่ยนแปลงระหว่างปี) ไม่ต้องบันทึกความเห็น</p>
      {:else}
        <h2 id="dec-h">ความเห็นของคุณ</h2>
        {#if f.decision || restored}
          <p class="status">
            {#if f.decision}<span class="chip ok-c">✓ บันทึกแล้ว: {f.decision.choice_label}</span>{/if}
            {#if f.decision?.after && !dirty}<span class="after-s">{f.decision.after}</span>{/if}
            {#if restored}<span class="chip warn">ร่างที่ยังไม่บันทึก</span>{/if}
          </p>
        {/if}
        {#if !writable}<p class="note danger">รอบนี้ถูกแทนแล้ว — บันทึกเพิ่มไม่ได้</p>{/if}
        <div class="choices" role="radiogroup" aria-label="เลือกความเห็น">
          {#if !r}{#each [0, 1, 2, 3, 4, 5] as i (i)}<span class="choice skeleton"></span>{/each}{/if}
          {#each r?.decisions ?? [] as d (d.key)}
            {@const open = !!d.when && (choice === d.key || peek === d.key)}
            {@const cond = d.use && d.use !== "usable" ? useShort(d.use_label) : ""}
            <div class="crow">
              <button role="radio" aria-checked={choice === d.key} class="choice" class:on={choice === d.key}
                      class:was={saved.choice === d.key && choice !== d.key} disabled={!writable || busy} onclick={() => pick(d.key)}>
                <span class="radio" aria-hidden="true"></span>
                <span class="cl">{d.label}{#if cond}<small class="cond">{cond}</small>{/if}</span></button>
              {#if d.when}<button class="mean" aria-expanded={open} aria-label="ความหมายของ {d.label}"
                      onclick={() => (peek = peek === d.key ? "" : d.key)}>ⓘ</button>{/if}
              {#if open}<p class="when">{d.when}</p>{/if}
            </div>
          {/each}
        </div>
        {#if showNote}
          <label for="dec-note">หมายเหตุ{#if saved.choice} — <b>ต้องระบุ</b>เมื่อเปลี่ยนความเห็นเดิม{/if}</label>
          <textarea id="dec-note" bind:this={noteEl} bind:value={note} maxlength="1800" rows="3" disabled={!writable}
                    oninput={() => { touched = true; formErr = ""; }}></textarea>
        {:else}
          <button class="linkish" onclick={() => { noteOpen = true; queueMicrotask(() => noteEl?.focus()); }}>＋ เพิ่มหมายเหตุ</button>
        {/if}
        {#if twins.length && writable}
          <div class="twins">
            <label class="tw-on"><input type="checkbox" bind:checked={alsoOn} disabled={busy} />
              <span>ใช้ความเห็นนี้กับอีก <b>{twins.length}</b> จุดที่ยอดต่างเท่ากัน ({f.delta_text})</span></label>
            {#if alsoOn}
              <p class="hint">ระบบบันทึกแยกทีละจุด พร้อมหมายเหตุว่าบันทึกพร้อมกับจุดนี้ · เอาเครื่องหมายออกได้ถ้าจุดไหนไม่ใช่เรื่องเดียวกัน</p>
              <ul class="tw-list">
                {#each twins as x (x.id)}
                  <li><label><input type="checkbox" bind:checked={also[x.id]} disabled={busy} />
                    <span>{clip(x.subject, 70)}<small class="hint">{x.column ? ` · ${x.column}` : ""} · {x.delta_text}</small></span></label>
                    <a href="/r/p/{rid}/f/{x.id}" onclick={link} title="เปิดดูหลักฐานของจุดนี้">ดู</a></li>
                {/each}
              </ul>
            {/if}
          </div>
        {/if}
        {#if formErr}<p class="err" role="alert">{formErr}</p>{/if}
        <div class="foot-s">
          <p class="after" role="status">{#if picked && dirty}<small>{picked.label}</small>{picked.after || picked.use_label}
            {:else if f.decision && !dirty}<small>บันทึกแล้ว</small>{f.decision.choice_label}{:else}<small>ยังไม่ได้เลือก</small>เลือกความเห็นด้านขวา{/if}</p>
          <button class="btn save" disabled={!writable || busy || !choice || !dirty} onclick={save}>
            {!writable ? "บันทึกไม่ได้ — รอบนี้อ่านอย่างเดียว" : busy ? "กำลังบันทึก…" : !choice ? "เลือกความเห็นก่อน"
              : dirty ? (alsoIds.length ? `บันทึก ${alsoIds.length + 1} จุด แล้วไปต่อ` : "บันทึก แล้วไปต่อ") : "บันทึกแล้ว"}</button>
        </div>
      {/if}
    </aside>
  </div>
{/if}

<style>
  .msg { padding: 16px; }
  .sk { height: 70vh; }
  .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; padding: 0 0 10px; }
  .ctx { display: inline-flex; align-items: baseline; gap: 2px; max-width: 80ch; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
  .grow { flex: 1; }

  .layout { display: grid; grid-template-columns: 208px minmax(0, 1fr) 248px; gap: 16px; align-items: start; }
  /* จอ 27" (กว้าง ≥ 2000px): รายการจุดกว้างขึ้น ชื่อจุดไม่ตกบรรทัดถี่ (กิ๊ฟ 2 พ.ย.) */
  @media (min-width: 2000px) { .layout { grid-template-columns: 320px minmax(0, 1fr) 300px; } }

  .plist { position: sticky; top: 64px; max-height: calc(100vh - 80px); overflow: auto; background: #fff; border: 1px solid var(--line);
    border-radius: var(--radius); padding: 10px 8px; }
  .ptoggle { width: 100%; display: flex; align-items: center; gap: 6px; border: 0; background: transparent; cursor: pointer; padding: 2px 6px 8px;
    font: inherit; color: inherit; text-align: left; }
  .pt-t { font-weight: 600; flex: 1; } .pt-n { color: var(--ok); font-size: .85em; font-variant-numeric: tabular-nums; }
  .pt-c { color: var(--muted); font-size: 1.2em; line-height: 1; }
  .layout.folded { grid-template-columns: 64px minmax(0, 1fr) 248px; }
  .folded .plist { padding: 8px 4px; }
  .folded .ptoggle { flex-direction: column; gap: 4px; padding: 4px 0; text-align: center; }
  .folded .pt-t { font-size: 1.2em; flex: none; }
  button.shot { width: 100%; padding: 0; font: inherit; }
  .zoom { width: 96vw; max-width: 96vw; height: 92vh; max-height: 92vh; padding: 0; border: 0; border-radius: 14px; }
  .zoom::backdrop { background: rgba(16, 24, 40, .6); }
  .zhead { position: sticky; top: 0; display: flex; align-items: center; gap: 8px; padding: 10px 16px; background: #fff;
    border-bottom: 1px solid var(--line); z-index: 1; }
  .zgrid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; padding: 14px 16px; }
  .zcol { min-width: 0; border-top: 4px solid var(--line); padding-top: 6px; }
  .zcol.ev-a { border-top-color: var(--a); } .zcol.ev-b { border-top-color: var(--b); }
  .zcol h2 { font-size: 1em; margin: 0 0 6px; display: flex; gap: 8px; align-items: center; }
  .zcol.ev-a h2 { color: var(--a); } .zcol.ev-b h2 { color: var(--b); }
  .zcol img { display: block; width: 100%; height: auto; border: 1px solid var(--line); border-radius: 8px; }
  .sorter { display: flex; gap: 4px; padding: 3px; margin: 0 4px 8px; border-radius: 10px; background: #eef0f3; }
  .sorter button { flex: 1; border: 0; background: transparent; border-radius: 8px; padding: 4px 6px; font-size: .8em; cursor: pointer; color: #344054; }
  .sorter button.on { background: #fff; color: var(--ink); font-weight: 600; box-shadow: 0 1px 3px rgba(16, 24, 40, .12); }
  .pl { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; }
  .pl a { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 6px; padding: 5px 6px; border-radius: 10px;
    color: inherit; text-decoration: none; font-size: .84em; line-height: 1.4; }
  .pl a:hover { background: #f4f6f9; }
  .pl a.cur { background: var(--accent-bg); box-shadow: inset 3px 0 0 var(--accent); font-weight: 600; }
  .pl .mk { display: inline-grid; place-items: center; width: 18px; height: 18px; margin-top: 2px; border-radius: 50%;
    border: 1.5px solid #b7bec9; font-size: .75em; color: #fff; }
  .pl a.done .mk { background: var(--ok); border-color: var(--ok); }
  .pt { display: flex; flex-direction: column; overflow-wrap: anywhere; }
  .pt small { color: var(--muted); font-weight: 400; }
  .pl a.done small { color: var(--ok); }

  .head h1 { margin: 2px 0 2px; font-size: 1.15em; line-height: 1.35; overflow-wrap: anywhere; flex: 1; }
  .hrow { display: flex; align-items: baseline; gap: 12px; }
  .pos { color: var(--muted); font-size: .9em; font-variant-numeric: tabular-nums; white-space: nowrap; }
  .what { margin: 0 0 6px; color: var(--muted); font-size: .9em; }
  .vline { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 6px 14px; margin: 0 0 10px; }
  .vline > span { display: flex; flex-direction: column; }
  .vline small { color: var(--muted); font-size: .8em; }
  .vline b { font-size: 1.2em; font-variant-numeric: tabular-nums; }
  .va { color: var(--a); } .vb { color: var(--b); }
  .vline .arr { font-size: 1.3em; color: var(--muted); align-self: center; }
  .dl { padding-left: 14px; border-left: 1px solid var(--line); align-self: center; }
  .dl b { font-size: 1.2em; }

  /* ภาพหลักฐาน A ซ้าย · B ขวา — ไล่ตาข้ามเทียบแถวเดียวกันได้ง่ายกว่าเรียงบนล่าง (กิ๊ฟ 30 ต.ค. ลองบนล่างแล้วกลับ) */
  .evs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-items: start; }
  .ev { padding: 10px 12px; min-width: 0; box-shadow: 0 8px 24px rgba(16, 24, 40, .1); }
  .ev h2 { display: flex; align-items: center; gap: 8px; font-size: 1.02em; margin: 0 0 6px; white-space: nowrap; }
  .ev h2 .arr { color: var(--muted); font-weight: 400; }
  .code { color: var(--muted); font-weight: 400; font-size: .78em; }
  .ev-a { border-top: 4px solid var(--a); } .ev-b { border-top: 4px solid var(--b); }
  .ev-a h2 { color: var(--a); } .ev-b h2 { color: var(--b); }
  .evbar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 0 0 6px; color: #344054; }
  figure { margin: 0; }
  figure { position: relative; }
  .shot { position: relative; display: block; border: 1px solid var(--line); border-radius: 12px; overflow: hidden auto; background: #fafbfc; cursor: zoom-in; }
  .shot.full { max-height: 75vh; overflow: auto; }
  .zhint { position: absolute; right: 18px; bottom: 8px; padding: 2px 8px; border-radius: 999px; font-size: .78em;
    background: rgba(16, 42, 84, .82); color: #fff; pointer-events: none; }
  .shot img { display: block; width: 100%; height: auto; }
  .absent { margin: 0; padding: 10px 12px; border-radius: 12px; background: var(--warn-bg); border: 1px solid var(--warn-line); }
  .empty-ev { color: var(--muted); }

  .more { margin-top: 16px; border-top: 1px solid var(--line); padding-top: 8px; }
  .more summary { cursor: pointer; color: #344054; font-weight: 600; padding: 4px 2px 8px; }
  .why { margin: 0 0 10px; padding: 8px 12px; border-left: 4px solid #98a2b3; background: #fff; border-radius: 0 10px 10px 0; }
  .vals { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin-bottom: 12px; overflow: hidden; }
  .cell { display: flex; flex-direction: column; gap: 2px; padding: 10px 14px; }
  .cell + .cell { border-left: 1px solid var(--line); }
  .cell .lbl { color: var(--muted); font-size: .88em; }
  .cell b { font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
  .cell small { color: var(--muted); }
  .cell-d { background: #f8f9fb; }
  .parts, .diff { margin-bottom: 12px; padding: 10px 14px; overflow: hidden; }
  .parts h3, .diff h3 { margin: 0 0 6px; font-size: .98em; }
  .tbl { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: .9em; }
  th, td { text-align: left; padding: 6px 10px; border-top: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; }
  .diff p { margin: 6px 0; }
  .diff small, .excerpt small { display: block; color: var(--muted); }
  del { background: var(--danger-bg); text-decoration: line-through; }
  ins { background: var(--ok-bg); text-decoration: none; }
  .excerpt { margin: 0 0 8px; color: #344054; font-size: .92em; overflow-wrap: anywhere; }

  /* แผงความเห็นเล็กและเบากว่าหลักฐาน — ไม่มีเงา พื้นอ่อน อักษรเล็กลง */
  .decide { position: sticky; top: 64px; max-height: calc(100vh - 140px); overflow: auto; padding: 12px 12px 0; display: flex; flex-direction: column;
    gap: 8px; font-size: .9em; box-shadow: none; background: #fbfcfd; }
  .decide h2 { margin: 0; font-size: 1em; }
  .status { margin: 0; display: flex; flex-wrap: wrap; gap: 6px; }
  .ok-c { background: var(--ok-bg); color: var(--ok); font-weight: 600; }
  .choices { display: flex; flex-direction: column; gap: 5px; }
  .crow { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0 4px; align-items: start; }
  .crow .when { grid-column: 1 / -1; margin: 4px 2px 2px 30px; font-size: .9em; line-height: 1.45; color: #344054; }
  .mean { width: 30px; height: 30px; margin-top: 2px; border: 1px solid transparent; border-radius: 8px; background: transparent;
    color: var(--muted); cursor: pointer; font-size: 1.05em; }
  .mean:hover, .mean[aria-expanded="true"] { border-color: #d5dae1; background: #fff; color: var(--ink); }
  .cond { display: block; color: var(--warn); font-weight: 600; font-size: .85em; }
  .choice { display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: 8px; align-items: start; text-align: left;
    padding: 6px 10px; border-radius: 10px; border: 1px solid #d5dae1; background: #fff; cursor: pointer; color: inherit;
    transition: border-color .15s, background .15s; }
  .choice:hover:not(:disabled) { border-color: var(--accent); }
  .radio { width: 16px; height: 16px; margin-top: 3px; border-radius: 50%; border: 2px solid #98a2b3; background: #fff; }
  .choice.on { border-color: var(--accent); background: var(--accent-bg); font-weight: 600; }
  .choice.on .radio { border: 4px solid var(--accent); }
  .choice.was { border-style: dashed; }
  .cl { display: flex; flex-direction: column; }
  .choice:disabled { opacity: .55; cursor: not-allowed; }
  span.choice { height: 44px; border: 0; }
  label { font-size: .92em; }
  textarea { width: 100%; padding: 8px 10px; border-radius: 10px; border: 1px solid #cfd4dc; font: inherit; resize: vertical; }
  .linkish { align-self: flex-start; border: 0; background: none; padding: 0; color: #2950c8; cursor: pointer; font: inherit; font-size: .92em; }
  .err { margin: 0; color: var(--danger); font-weight: 600; }
  .twins { padding: 8px 10px; border-radius: 10px; border: 1px solid #d5dae1; background: #fff; }
  .twins .hint { margin: 6px 0 4px; font-size: .88em; }
  .tw-on { display: flex; gap: 8px; align-items: flex-start; cursor: pointer; }
  .tw-on input { margin-top: 4px; }
  .tw-list { list-style: none; margin: 0; padding: 0; max-height: 220px; overflow: auto; display: flex; flex-direction: column; gap: 2px; }
  .tw-list li { display: flex; gap: 6px; align-items: flex-start; justify-content: space-between; font-size: .88em; }
  .tw-list label { display: flex; gap: 6px; align-items: flex-start; cursor: pointer; min-width: 0; }
  .tw-list input { margin-top: 3px; }
  .tw-list a { flex: none; color: #2950c8; }
  /* แถบล่างจอแบบแอปธนาคาร — เห็นเสมอว่าเลือกอะไร บันทึกแล้วเป็นอย่างไร และปุ่มบันทึก */
  .foot-s { position: fixed; left: 0; right: 0; bottom: 0; z-index: 45; display: flex; align-items: center; justify-content: flex-end;
    gap: 14px; padding: 10px max(24px, calc((100vw - 2560px) / 2 + 24px)); background: #fff; border-top: 1px solid var(--line);
    box-shadow: 0 -8px 24px rgba(16, 24, 40, .08); font-size: 1rem; }
  .foot-s .after { flex: 0 1 auto; max-width: 60ch; background: transparent; border: 0; padding: 0; text-align: right; }
  .foot-s .save { min-width: 220px; min-height: 48px; font-size: 1.02em; }
  .layout { padding-bottom: 84px; }
  .save { justify-content: center; padding: 9px 14px; }
  .after { margin: 0; padding: 8px 12px; border-radius: 10px; background: #f2f4f7; border: 1px solid var(--line); font-weight: 600; }
  .after small { display: block; color: var(--muted); font-weight: 400; }
  .after-s { flex-basis: 100%; font-size: .88em; color: #344054; }
  .plh { margin: 10px 8px 4px; font-size: .82em; color: var(--muted); font-weight: 600; }
  .pt .dt { color: #344054; font-variant-numeric: tabular-nums; }
  kbd { display: inline-block; min-width: 1.6em; padding: 0 5px; border: 1px solid #cfd4dc; border-bottom-width: 2px;
    border-radius: 6px; background: #fff; font: .85em ui-monospace, Consolas, monospace; text-align: center; }

  @media (max-width: 1599px) {
    .layout { grid-template-columns: minmax(0, 1fr) 248px; }
    .plist { grid-column: 1 / -1; position: static; max-height: none; }
    .layout:not(.folded) .plist { position: fixed; z-index: 61; top: 0; left: 0; bottom: 0; width: min(360px, 88vw);
      border-radius: 0 var(--radius) var(--radius) 0; box-shadow: 0 12px 32px rgba(16, 24, 40, .22); }
    .scrim { position: fixed; inset: 0; z-index: 60; border: 0; padding: 0; background: rgba(16, 24, 40, .35); cursor: pointer; }
    .layout.folded { grid-template-columns: minmax(0, 1fr) 248px; }
    .folded .ptoggle { flex-direction: row; text-align: left; }
    .layout.folded .plist { display: none; }
  }
  @media (max-width: 1000px) {
    .layout { grid-template-columns: 1fr; }
    .decide { position: static; max-height: none; }
  }
  @media (max-width: 760px) {
    .evs, .vals { grid-template-columns: 1fr; }
    .cell + .cell { border-left: 0; border-top: 1px solid var(--line); }
  }
  /* เลขหน้าในไฟล์ PDF = ข้อมูลรอง — เลขที่พิมพ์บนหัวกระดาษเด่นกว่า */
  .pdfno { color: #667085; font-size: .85em; }
</style>
