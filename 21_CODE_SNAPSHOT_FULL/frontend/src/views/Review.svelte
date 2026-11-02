<script lang="ts">
  // ทำรายการอ้างอิง → ส่งใบประกาศก่อนเห็นผล (= ล็อก) — วิธีวัดผลฉบับ 0.2
  // ร1 = ใช้รายการเดิมของผู้ตรวจ (ใบประกาศจำนวน) · ร2 = วงจุดบนภาพหน้า (ทุกจุดต้องมีหัวข้อ/ส่วน/ต-ล/ระดับ)
  // ไม่บังคับกด "ตรวจหน้านี้แล้ว" ครบทุกหน้า (เป็นตัวช่วยของผู้ตรวจ) · ก่อนส่งไม่มีผลระบบให้โหลด
  import { onMount } from "svelte";
  import { ApiError, get, markGaps, post, pageImage, preload, reloadOnRestore, scoped, short,
           type Meta, type Mark, type Pen, type Session, type Side } from "../lib/api";
  import { go, link, nav } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import Pane from "./Pane.svelte";

  let { sid, meta }: { sid: string; meta: Meta } = $props();
  // svelte-ignore state_referenced_locally
  const SID = sid;                                   // props อ่านค่าสด — เก็บรหัสรอบของหน้านี้ไว้

  let s = $state<Session | null>(null);
  const tmeta = $derived(scoped(meta, s));      // หัวข้อของชนิดคู่นี้ (คู่ข้ามปี = ค ช ซ จ)
  let pen = $state<Pen>("red");
  let two = $state(nav.query.get("two") !== "0");
  let linked = $state(true);                         // เลื่อนฉบับ B แล้วฉบับ A เลื่อนตาม (รักษาคู่หน้าที่จัดไว้)
  let page = $state<Record<Side, number>>({ cur: 0, prev: 0 });
  let open = $state<string | null>(null);
  let brief = $state(false);
  let docs = $state(false);                          // ทาง ร1: เปิดดูเอกสาร (ไม่บังคับ)
  let decl = $state<Record<string, string>>({});
  let confirmOk = $state(false);
  let locking = $state(false);
  let lockErr = $state("");
  let stOpen = $state(false), stStatus = $state(""), stReason = $state(""), stNoUse = $state(false), stConfirm = $state(false);
  let consent = $state<Record<string, boolean>>({});

  function init(r: Session) {
    s = r;
    const q = (k: string) => Number(nav.query.get(k)) || 0;
    if (!page.cur) {
      page.cur = r.pages.cur.includes(q("p")) ? q("p") : (r.pages.cur.find((p) => !r.done.cur.includes(p)) ?? r.pages.cur[0]);
      const i = r.pages.cur.indexOf(page.cur);
      page.prev = r.pages.prev.includes(q("pp")) ? q("pp") : r.pages.prev[Math.min(i, r.pages.prev.length - 1)];
    }
    brief = !r.locked && r.active && !r.marks.length && !r.done.cur.length && !r.done.prev.length;
    if (r.defaults && !decl.made_on) {
      decl = { made_on: r.defaults.made_on, source: r.defaults.source === "web" ? "" : r.defaults.source,
               edition_first: r.defaults.edition_first, edition_second: r.defaults.edition_second,
               made: "", seen: "", seen_note: "" };
    }
  }
  get<Session>(`/api/trial/s/${SID}`).then(init).catch((e) => toast(e.message, true));

  const open_ = $derived(!!s && s.active && !s.locked && !s.legacy);
  const ready = $derived(open_ && !!s?.consented);                 // ยินยอมแล้วจึงเริ่มทำรายการได้
  const canMark = $derived(ready && s?.path === "r2");
  const gaps = $derived(s ? s.marks.map((m) => ({ m, g: markGaps(m, s!.xkind) })).filter((x) => x.g.length) : []);
  const counts = $derived.by(() => {
    const c = { red: 0, brown: 0, pin: 0 };
    s?.marks.forEach((m) => { if (m.pen && ((m.side === "cur" && m.page === page.cur) || (two && m.side === "prev" && m.page === page.prev))) c[m.pen]++; });
    return c;
  });
  const marked = $derived(new Set((s?.marks ?? []).map((m) => m.topic).filter(Boolean)));

  // URL + บันทึกคู่หน้าที่เปิดเทียบ (รอให้หยุดเปลี่ยนหน้าก่อน) + โหลดภาพหน้าถัดไปของเอกสารรอไว้
  let logTimer: ReturnType<typeof setTimeout>;
  $effect(() => {
    if (!s || !page.cur) return;
    const q = `?p=${page.cur}${two ? `&pp=${page.prev}` : "&two=0"}`;
    history.replaceState(null, "", `/r/s/${SID}${q}`);
    const nxt = (side: Side) => s!.pages[side][s!.pages[side].indexOf(page[side]) + 1];
    preload([nxt("cur"), ...(two ? [nxt("prev")] : [])].filter(Boolean).map((p, k) => pageImage(SID, k ? "prev" : "cur", p!)));
    if (s.locked || !s.active) return;
    const pair = { cur: page.cur, prev: two ? page.prev : 0 };
    clearTimeout(logTimer);
    logTimer = setTimeout(() => post(`/api/trial/s/${SID}/view`, pair).catch(() => {}), 600);
  });

  // กลับมาที่แท็บนี้: ถ้าแท็บอื่นส่งไปแล้วหรือหยุดรอบ → เปลี่ยนเป็นแบบดูอย่างเดียว
  function refresh() {
    if (document.visibilityState !== "visible" || !s || s.locked || !s.active) return;
    get<Session>(`/api/trial/s/${SID}`).then((r) => { if (r.locked || !r.active) { s = r; toast("รอบนี้ส่งใบประกาศหรือหยุดไปแล้วจากอีกแท็บ — ดูได้อย่างเดียว"); } })
      .catch(() => {});
  }
  onMount(() => {
    const off = reloadOnRestore();
    document.addEventListener("visibilitychange", refresh);
    return () => { off(); document.removeEventListener("visibilitychange", refresh); };
  });

  async function addMark(side: Side, fx: number, fy: number) {
    if (!s || !canMark) return;
    const temp: Mark = { id: `tmp${Math.random()}`, side, page: page[side], fx, fy, pen, topic: "", note: "",
                         level: pen === "pin" ? "" : pen, cause: "", part: "", searched: "", found_in: pen === "pin" ? side : "",
                         origin: "mark", seq: 0, ref: "" };
    s.marks.push(temp);                                   // ขึ้นทันที — ไม่รอเซิร์ฟเวอร์
    open = temp.id;
    try {
      const m = await post<Mark>(`/api/trial/s/${SID}/marks`, { side, page: temp.page, fx, fy, pen });
      const i = s.marks.findIndex((x) => x.id === temp.id);
      if (i >= 0) s.marks[i] = { ...m, topic: s.marks[i].topic, note: s.marks[i].note };
      if (open === temp.id) open = m.id;
    } catch (e) {
      s.marks = s.marks.filter((x) => x.id !== temp.id);
      open = null;
      failed(e);
    }
  }

  async function saveMark(m: Mark, patch: Partial<Mark> & { delete?: boolean }) {
    if (!s) return;
    const before = { ...m };
    if (patch.delete) s.marks = s.marks.filter((x) => x.id !== m.id);
    else Object.assign(m, patch, patch.pen && patch.pen !== "pin" ? { level: patch.pen } : {});
    open = null;
    try {
      await post(`/api/trial/s/${SID}/marks/${m.id}`, patch);
      toast(patch.delete ? "ลบจุดแล้ว" : "บันทึกแล้ว");
    } catch (e) {
      if (patch.delete) s.marks.push(before); else Object.assign(m, before);
      failed(e);
    }
  }

  /** เปลี่ยนหน้า — เลื่อนฉบับ B เมื่อ "เลื่อนคู่กัน" เปิดอยู่ ฉบับ A เลื่อนตามเท่ากัน · เลื่อนฉบับ A เอง = ปรับคู่หน้า */
  function moveTo(side: Side, p: number) {
    if (!s || !s.pages[side].includes(p)) return;
    if (side === "cur" && linked) {
      const cl = s.pages.cur, pl = s.pages.prev;
      const d = cl.indexOf(p) - cl.indexOf(page.cur), j = pl.indexOf(page.prev);
      if (d && j >= 0) page.prev = pl[Math.max(0, Math.min(pl.length - 1, j + d))];
    }
    page[side] = p;
    open = null;
  }

  /** เลื่อนดูอย่างเดียว (ปุ่มลูกศร ← →) — ไม่นับว่าตรวจ */
  function step(d: number) {
    if (!s) return;
    const list = s.pages.cur, p = list[list.indexOf(page.cur) + d];
    if (p) moveTo("cur", p);
  }

  /** "ตรวจหน้านี้แล้ว" = ดูหน้านี้ครบ (ไม่ได้แปลว่าถูกต้อง) แล้วไปหน้าถัดไปของฉบับนั้น — ตัวช่วย ไม่บังคับ */
  async function markDone(side: Side) {
    if (!s || !open_) return;
    const p = page[side];
    if (!s.done[side].includes(p)) s.done[side].push(p);
    const list = s.pages[side], nx = list[list.indexOf(p) + 1];
    if (nx) moveTo(side, nx);
    toast(`นับ${s.labels[side]} หน้า ${p} ว่าตรวจแล้ว`, false, { label: "ยกเลิก", run: () => undo(side, p) });
    try {
      await post(`/api/trial/s/${SID}/done`, { page: p, side });
    } catch (e) {
      s.done[side] = s.done[side].filter((x) => x !== p);
      failed(e);
    }
  }

  /** ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งเท่านั้น */
  async function undo(side: Side, p: number) {
    if (!s || !open_ || !s.done[side].includes(p)) return;
    s.done[side] = s.done[side].filter((x) => x !== p);
    try {
      await post(`/api/trial/s/${SID}/undone`, { page: p, side });
      toast(`ยกเลิกเครื่องหมายตรวจของ${s.labels[side]} หน้า ${p} แล้ว`);
    } catch (e) {
      if (!s.done[side].includes(p)) s.done[side].push(p);
      failed(e);
    }
  }

  /** ข้อผิดพลาด — ถ้าส่งไปแล้ว/หยุดแล้ว (เช่น จากอีกแท็บ) เปลี่ยนเป็นแบบดูอย่างเดียว */
  function failed(e: unknown) {
    toast((e as Error).message, true);
    if (e instanceof ApiError && e.code === "locked") get<Session>(`/api/trial/s/${SID}`).then((r) => (s = r)).catch(() => {});
  }

  async function giveConsent() {
    try { s = await post<Session>(`/api/trial/s/${SID}/consent`, consent); toast("บันทึกความยินยอมแล้ว"); }
    catch (e) { failed(e); }
  }

  async function setPath(p: string) {
    try { s = await post<Session>(`/api/trial/s/${SID}/path`, { path: p }); decl.source = p === "r1" ? "routine" : ""; }
    catch (e) { failed(e); }
  }

  async function lock() {
    if (!confirmOk || locking || !s) return;
    locking = true;
    lockErr = "";
    try {
      const r = await post<{ ok: boolean; run: boolean; run_error: string }>(`/api/trial/s/${SID}/lock`, { ...decl, confirm: true });
      if (!r.run) toast(`ส่งใบประกาศแล้ว แต่ระบบเทียบไม่สำเร็จ — ${r.run_error}`, true);
      go(`/r/s/${SID}/result`);
    } catch (e) {
      lockErr = (e as Error).message;
      locking = false;
      if (e instanceof ApiError && e.code === "locked") failed(e);
    }
  }

  async function setStatus() {
    if (!stConfirm || !stStatus) return;
    try {
      s = await post<Session>(`/api/trial/s/${SID}/status`, { status: stStatus, reason: stReason, no_data_use: stNoUse, confirm: true });
      stOpen = false;
      toast(`บันทึกสถานะแล้ว — ${meta.statuses[stStatus]}`);
    } catch (e) { toast((e as Error).message, true); }
  }

  function keys(e: KeyboardEvent) {
    const t = e.target instanceof Element ? e.target : null;
    if (t?.closest("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey || !s) return;
    if (canMark && e.key === "1") pen = "red";
    else if (canMark && e.key === "2") pen = "brown";
    else if (canMark && e.key === "3") pen = "pin";
    else if (e.key === "Escape") open = null;
    else if (e.key.toLowerCase() === "d") markDone("cur");
    else if (e.key === "ArrowRight") step(1);
    else if (e.key === "ArrowLeft") step(-1);
    else return;
    e.preventDefault();
  }
</script>

<svelte:window onkeydown={keys} />

{#snippet panes()}
  <div class="tools" role="toolbar" aria-label="ปากกา">
    {#if canMark}
      {#each Object.entries(meta.pens) as [k, label], i (k)}
        <button class="pen pen-{k}" class:on={pen === k} aria-pressed={pen === k} onclick={() => (pen = k as Pen)}>
          <span class="dot" aria-hidden="true"></span>{label}<kbd>{i + 1}</kbd></button>
      {/each}
    {/if}
    <button class="pen" onclick={() => (two = !two)}>{two ? `ดู${s!.labels.cur} อย่างเดียว` : "วางสองฉบับข้างกัน"}</button>
    {#if two}
      <button class="pen" class:on={linked} aria-pressed={linked} onclick={() => (linked = !linked)}
              title="เปิด = เลื่อน{s!.labels.cur} แล้ว{s!.labels.prev} เลื่อนตาม · เลื่อน{s!.labels.prev} เองได้เสมอเพื่อจัดคู่หน้า">
        เลื่อนสองฉบับคู่กัน: {linked ? "เปิด" : "ปิด"}</button>
    {/if}
    <span class="hint counts"><kbd>←</kbd><kbd>→</kbd> เลื่อนดู · <kbd>D</kbd> ตรวจหน้านี้แล้ว ({s!.labels.cur}){#if canMark}{` · บนหน้าที่เปิด: แดง ${counts.red} · น้ำตาล ${counts.brown} · หมุด ${counts.pin}`}{/if}</span>
  </div>
  <div class="panes" class:two>
    {#if two}
      <Pane sid={SID} side="prev" label={s!.labels.prev} pages={s!.pages.prev} page={page.prev} marks={s!.marks}
            done={s!.done.prev} {open_} {canMark} meta={tmeta} bind:open onmove={(p) => moveTo("prev", p)} onadd={addMark}
            onsave={saveMark} ondone={markDone} onundo={undo} />
    {/if}
    <Pane sid={SID} side="cur" label={s!.labels.cur} pages={s!.pages.cur} page={page.cur} marks={s!.marks}
          done={s!.done.cur} {open_} {canMark} meta={tmeta} bind:open dkey="D" onmove={(p) => moveTo("cur", p)} onadd={addMark}
          onsave={saveMark} ondone={markDone} onundo={undo} />
  </div>
{/snippet}

{#snippet declaration()}
  <section class="card lockbox" aria-labelledby="h-decl">
    <h2 id="h-decl">ใบประกาศก่อนเห็นผล <span class="hint">(แบบ ๐๒ ส่วนที่ ๑ · จำนวนเท่านั้น) — ส่งแล้ว = ล็อก</span></h2>
    {#if lockErr}<div class="err" role="alert">{lockErr}</div>{/if}
    <div class="grid2">
      <label>วันที่จัดทำรายการอ้างอิง <input type="date" bind:value={decl.made_on}></label>
      {#if s!.path === "r1"}
        <fieldset class="radios"><legend>ที่มาของรายการ</legend>
          {#each ["routine", "form01"] as k (k)}<label><input type="radio" bind:group={decl.source} value={k}> {meta.sources[k]}</label>{/each}
        </fieldset>
      {:else}<p>ที่มาของรายการ: {meta.sources.web}</p>{/if}
      <label>ฉบับแรกที่ใช้ <input maxlength="160" bind:value={decl.edition_first}></label>
      <label>ฉบับหลังที่ใช้ <input maxlength="160" bind:value={decl.edition_second}></label>
      <label>สำเนาลงวันที่หรือแฮชของรายการฉบับล็อกที่ท่านเก็บไว้เอง (ไม่บังคับ · ไม่ส่งเนื้อหา)
        <input maxlength="120" bind:value={decl.own_copy}></label>
    </div>
    <fieldset class="radios"><legend>รายการนี้จัดทำเมื่อไร</legend>
      {#each Object.entries(meta.made) as [k, l] (k)}<label><input type="radio" bind:group={decl.made} value={k}> {l}</label>{/each}
    </fieldset>
    <fieldset class="radios"><legend>เคยเห็นผลของระบบกับคู่นี้มาก่อนหรือไม่</legend>
      {#each Object.entries(meta.seen) as [k, l] (k)}<label><input type="radio" bind:group={decl.seen} value={k}> {l}</label>{/each}
      {#if decl.seen === "seen"}<label>ระบุสั้น ๆ <input maxlength="200" bind:value={decl.seen_note}></label>{/if}
    </fieldset>
    <table>
      <caption>ความครอบคลุมรายส่วนของเล่ม (ทุกส่วนต้องเลือก)</caption>
      <thead><tr><th scope="col">ส่วน</th><th scope="col">เนื้อหาของเล่ม</th>
        {#each Object.values(meta.coverage) as l (l)}<th scope="col">{l}</th>{/each}</tr></thead>
      <tbody>
        {#each meta.parts as p (p.code)}
          <tr><th scope="row">{p.code}</th><td class="left">{p.label}</td>
            {#each Object.entries(meta.coverage) as [k, l] (k)}
              <td><input type="radio" bind:group={decl[`part_${p.code}`]} value={k} aria-label="ส่วน {p.code} {l}"></td>
            {/each}</tr>
        {/each}
      </tbody>
    </table>
    {#if s!.path === "r1"}
      <table>
        <caption>จำนวนประเด็นรายหัวข้อ — หัวข้อที่รายการไม่ครอบคลุมเว้นว่างทั้งแถว (อย่าใส่ 0) · ตรวจแล้วไม่พบความต่างใส่ 0</caption>
        <thead><tr><th scope="col">หัวข้อ</th><th scope="col">ประเด็นทั้งหมด</th><th scope="col">ในนั้นต้นเหตุ</th><th scope="col">ในนั้นระดับแดง</th></tr></thead>
        <tbody>
          {#each tmeta.topics as t (t.code)}
            <tr><th scope="row" class="left">{t.code} <span class="hint">{t.label}</span></th>
              {#each ["total", "root", "red"] as f (f)}
                <td><input class="num" inputmode="numeric" maxlength="4" bind:value={decl[`t_${t.code}_${f}`]} aria-label="หัวข้อ {t.code} {f}"></td>
              {/each}</tr>
          {/each}
        </tbody>
      </table>
    {:else}
      <table>
        <caption>หัวข้อที่รายการครอบคลุม — หัวข้อที่มีจุดที่วงนับให้อัตโนมัติ · ตรวจแล้วไม่พบความต่างให้ติ๊กเอง</caption>
        <thead><tr><th scope="col">หัวข้อ</th><th scope="col">ครอบคลุม</th><th scope="col">จุดที่วง</th><th scope="col">ต้นเหตุ</th><th scope="col">แดง</th></tr></thead>
        <tbody>
          {#each tmeta.topics as t (t.code)}
            {@const mine = s!.marks.filter((m) => m.topic === t.code)}
            <tr><th scope="row" class="left">{t.code} <span class="hint">{t.label}</span></th>
              <td>{#if marked.has(t.code)}✓{:else}<input type="checkbox" aria-label="หัวข้อ {t.code} ครอบคลุม"
                  checked={decl[`t_${t.code}_covered`] === "1"}
                  onchange={(e) => (decl[`t_${t.code}_covered`] = e.currentTarget.checked ? "1" : "")}>{/if}</td>
              <td>{mine.length}</td><td>{mine.filter((m) => m.cause === "t").length}</td><td>{mine.filter((m) => m.level === "red").length}</td></tr>
          {/each}
        </tbody>
      </table>
      {#if gaps.length}
        <div class="warnbox"><b>ยังกรอกรายละเอียดจุดที่วงไม่ครบ {gaps.length} จุด</b> — ส่งไม่ได้จนกว่าจะครบ
          <ul>{#each gaps.slice(0, 12) as x (x.m.id)}
            <li><button class="linkish" onclick={() => { moveTo(x.m.side as Side, x.m.page); if (x.m.side === "prev") two = true; open = x.m.id; }}>
              {s!.labels[x.m.side as Side]} หน้า {x.m.page}</button> — ขาด {x.g.join(", ")}</li>{/each}</ul></div>
      {/if}
    {/if}
    <label class="confirm"><input type="checkbox" bind:checked={confirmOk}> ข้อมูลข้างบนถูกต้อง · ส่งแล้วแก้รายการและใบประกาศไม่ได้</label>
    <div><button class="btn" disabled={!confirmOk || locking} onclick={lock}>
      {#if locking}<span class="spin sm"></span> ระบบกำลังเทียบเล่ม…{:else}ส่งใบประกาศ{/if}</button></div>
    <p class="hint">ไม่ต้องกด "ตรวจหน้านี้แล้ว" ครบทุกหน้า · ส่งแล้วระบบจึงเริ่มเทียบ (ครั้งเดียวต่อรอบ) · ประเด็นที่เห็นเพิ่มหลังส่ง
      จดเป็น "ข้อสังเกตหลังล็อก" ได้ในหน้าผล (ไม่เพิ่มเข้ารายการที่ล็อก)</p>
  </section>
{/snippet}

{#if !s}
  <div class="bar"><span class="skeleton sk-line"></span></div>
  <div class="panes two"><div class="card skeleton sk-page"></div><div class="card skeleton sk-page"></div></div>
{:else}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>{s.book.title}</b> · {s.book.agency} · {meta.pair_kinds[s.pair_kind]}</div>
    <span class="chip">{meta.paths[s.path]}</span>
  </div>

  {#if s.legacy}
    <div class="card note warn"><b>รอบกติกา 0.1 — อ่านได้อย่างเดียว</b> · รอบนี้เริ่มก่อนเปลี่ยนเป็นวิธีวัดผลฉบับ 0.2 จึงอ่าน/นับตามรุ่นเดิมเท่านั้น
      (ไม่เปลี่ยนรุ่นอัตโนมัติ) · จุดที่วงไว้เก็บไว้ครบ · งานตามฉบับ 0.2 ให้<a href="/r" onclick={link}>เริ่มรอบใหม่จากหน้าเลือกเล่ม</a>
      {#if s.locked}{" · "}<a href="/r/s/{SID}/result" onclick={link}>ดูผลของรอบนี้</a>{/if}</div>
  {:else if !s.active}
    <div class="card note">รอบนี้{meta.statuses[s.status]}แล้ว — ดูได้อย่างเดียว ข้อมูลเดิมเก็บไว้ตามเดิม</div>
  {:else if s.locked}
    <div class="card note ok">ส่งใบประกาศแล้ว — หน้านี้ดูได้อย่างเดียว · <a href="/r/s/{SID}/result" onclick={link}>ไปดูว่าระบบเจออะไร →</a></div>
  {:else}
    <details class="card brief" bind:open={brief}>
      <summary>คำชี้แจงก่อนตรวจ</summary>
      <ul>
        <li>เปิดได้ทั้งสองฉบับเท่ากัน — <b>{s.labels.prev}</b> ({s.book.prev.title}) อยู่ซ้าย · <b>{s.labels.cur}</b> ({s.book.cur.title}) อยู่ขวา ·
          {s.pair_kind === "cross_year" ? "คู่ข้ามปีใช้ชื่อ ฉบับปีก่อน / ฉบับปีนี้" : "ปีเดียวกัน: ฉบับ A = ฉบับประกอบร่าง พ.ร.บ. · ฉบับ B = ฉบับตาม พ.ร.บ."}</li>
        <li>{#if s.pair_kind === "cross_year"}คู่ข้ามปีนับ<b>{meta.xyear.label}</b> — ตัวเลขที่เปลี่ยนตามปีไม่ต้องจด ·
          หัวข้อ: {tmeta.topics.map((t) => `${t.code} ${t.label}`).join(" · ")}{:else}ตรวจทุกหัวข้อในขอบเขตตามวิธีปกติของท่าน (ก–ญ):
          {tmeta.topics.map((t) => `${t.code} ${t.label}`).join(" · ")}{/if}</li>
        <li>หนึ่งประเด็น = ความต่าง ๑ จุด ใน ๑ ช่อง — ค่าของรายการ ๑ รายการในคอลัมน์ ๑ คอลัมน์ · ข้อความ ๑ ช่อง · หรือโครงสร้าง ๑ จุด
          (เพิ่ม หาย เปลี่ยนชื่อ ย้ายแผนงาน)</li>
        {#if s.pair_kind === "cross_year"}
          <li>คู่ข้ามปี นับเป็นประเด็นเฉพาะ: ตัวเลขของปีเดียวกันที่ปรากฏในทั้งสองเล่ม · โครงสร้างที่เพิ่ม หาย เปลี่ยนชื่อ หรือย้ายแผนงาน ·
            ตัวชี้วัดและค่าเป้าหมายของปีที่ทับกัน · รายการผูกพัน "ผูกพันปีถัดไป" ในเล่มปีก่อนกับ "ปีนั้นตั้งงบ" ในเล่มปีนี้ ·
            ยอดที่เปลี่ยนระหว่างปีตามปกติไม่ต้องจด</li>
        {/if}
        {#if s.path === "r2"}
          <li>เจอจุดที่ต่าง เลือกปากกาแล้วแตะบนภาพตรงจุดนั้น (วางได้ทั้งสองฉบับ) — ปากกา<b class="r">แดง</b> = สำคัญ ·
            ปากกา<b class="b">น้ำตาล</b> = สังเกตเห็นแต่สำคัญน้อยกว่า (ตามดุลพินิจของท่าน) · <b>หมุด</b> = ของที่หายไป วางบนฉบับที่พบ
            แล้วจดขอบเขตที่ค้นในอีกฉบับ</li>
          <li>ทุกจุดต้องระบุ หัวข้อ ก–ญ · ส่วนของเล่ม ๑–๘ · ต (ต้นเหตุ) หรือ ล (ผลที่ตามมา) ก่อนส่ง · ปุ่มลัดปากกา 1 · 2 · 3</li>
        {:else}
          <li>ทาง ร1 ใช้รายการที่ท่านจดไว้แล้ว — กรอกใบประกาศจำนวนด้านล่าง (ไม่ต้องส่งเนื้อหาของประเด็น) · เปิดดูเอกสารได้แต่ไม่บังคับ</li>
        {/if}
        <li><b>เลื่อนดูเฉย ๆ</b> ใช้ปุ่มลูกศร ← → หรือ ‹ › — ยังไม่นับว่าตรวจ · "ตรวจหน้านี้แล้ว" (หรือ D) = ดูหน้านี้ครบ ไม่ได้แปลว่าถูกต้อง
          และ<b>ไม่ต้องกดครบทุกหน้า</b> · ระบบยังไม่เทียบจนกว่าท่านจะส่งใบประกาศ</li>
      </ul>
    </details>
    {#if !s.consented}
      <section class="card lockbox" aria-labelledby="h-consent">
        <h2 id="h-consent">คำชี้แจงและความยินยอม <span class="hint">— ก่อนเริ่มทำรายการ (ติ๊ก ไม่ลงชื่อ)</span></h2>
        <p>รอบทดลองนี้ใช้ประกอบการศึกษาค้นคว้าอิสระเรื่องระบบเทียบเล่มเอกสารงบประมาณ PDF ที่เผยแพร่แล้ว · ไม่ต้องลงชื่อ ใช้รหัสผู้ตรวจแทน ·
          ข้อมูลเก็บในเครื่องนี้ ผู้ศึกษารับเฉพาะสรุปจำนวนและแบบสอบถาม · ถอนตัวได้ทุกเมื่อ</p>
        {#each meta.consent as c (c.key)}<label class="line"><input type="checkbox" bind:checked={consent[c.key]}> {c.text}</label>{/each}
        <div><button class="btn" disabled={!meta.consent.every((c) => consent[c.key])} onclick={giveConsent}>ยืนยัน แล้วเริ่มทำรายการ</button></div>
      </section>
    {/if}
    <div class="pathline">
      {#if s.path === "r1"}
        <button class="btn ghost small" onclick={() => setPath("r2")}>เปลี่ยนเป็นทาง ร2 (วงจุดบนภาพหน้า)</button>
      {:else}
        <button class="btn ghost small" disabled={s.marks.length > 0} title={s.marks.length ? "ลบจุดที่วงก่อน" : ""}
                onclick={() => setPath("r1")}>เปลี่ยนเป็นทาง ร1 (ใช้รายการเดิมของฉัน)</button>
      {/if}
    </div>
  {/if}

  {#if s.path === "r1" && ready}
    {@render declaration()}
    <details class="card docs" bind:open={docs}><summary>เปิดดูเอกสารทั้งสองฉบับ (ไม่บังคับ)</summary>
      {#if docs}{@render panes()}{/if}
    </details>
  {:else}
    {@render panes()}
    {#if ready}{@render declaration()}{/if}
  {/if}

  {#if s.active && !s.legacy}
    <details class="card status" bind:open={stOpen}><summary>หยุดรอบนี้ / ถอนตัว</summary>
      <div class="stack">
        {#each Object.entries(meta.statuses) as [k, l] (k)}<label><input type="radio" bind:group={stStatus} value={k}> {l}</label>{/each}
        <label>เหตุ (หยุดรอบนี้ต้องระบุ · ไม่ต้องระบุตัวเลขจริง) <input maxlength="300" bind:value={stReason}></label>
        <label><input type="checkbox" bind:checked={stNoUse}> ถอนตัวและขอไม่ให้ใช้ข้อมูลที่ทำไว้</label>
        <label><input type="checkbox" bind:checked={stConfirm}> ยืนยัน — หลังจากนี้บันทึกเพิ่มในรอบนี้ไม่ได้</label>
        <div><button class="btn ghost small" disabled={!stConfirm || !stStatus} onclick={setStatus}>บันทึกสถานะ</button></div>
      </div>
    </details>
  {/if}
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .title { flex: 1; min-width: 240px; }
  .note { padding: 12px 16px; margin-bottom: 10px; }
  .note.ok { background: var(--ok-bg); border-color: #b9e0c4; }
  .note.warn, .warnbox { background: #fff8e6; border-color: #f1d58a; }
  .warnbox { border: 1px solid #f1d58a; border-radius: 10px; padding: 8px 12px; margin: 8px 0; }
  .brief { padding: 8px 18px; margin-bottom: 10px; background: #fff8e6; border-color: #f1d58a; box-shadow: none; }
  .brief summary, .docs summary, .status summary { cursor: pointer; font-weight: 600; }
  .r { color: #c8322f; } .b { color: var(--brown); }
  .pathline { margin: 0 0 8px; }
  .tools { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; position: sticky; top: 52px; z-index: 30;
    background: var(--bg); padding: 8px 0; }
  .pen { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; border-radius: 999px; background: #fff;
    border: 1px solid #cfd4dc; cursor: pointer; transition: border-color .15s, transform .12s; }
  .pen:active { transform: scale(.97); }
  .pen.on { border: 2px solid var(--ink); font-weight: 700; }
  .dot { width: 13px; height: 13px; border-radius: 50%; border: 3px solid var(--pin); }
  .pen-red .dot { border-color: var(--red); } .pen-brown .dot { border-color: var(--brown); }
  .pen-pin .dot { background: var(--pin); }
  kbd { font: inherit; font-size: .72em; color: var(--muted); border: 1px solid #d0d5dd; border-radius: 5px; padding: 0 5px; }
  .counts { margin-left: auto; }
  .panes { display: grid; grid-template-columns: minmax(0, 1fr); gap: 14px; }
  .panes.two { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); }
  .lockbox, .docs, .status { padding: 14px 18px; margin-top: 16px; }
  .lockbox h2 { font-size: 1.15em; margin: 0 0 10px; }
  .err { background: #fdecea; border: 1px solid #f3b9b4; border-radius: 10px; padding: 8px 12px; margin-bottom: 8px; }
  .grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 8px 16px; margin-bottom: 8px; }
  .grid2 label { display: flex; flex-direction: column; gap: 2px; }
  .grid2 input, .radios input:not([type]), .stack input:not([type]) { padding: 6px 8px; border: 1px solid #cfd4dc; border-radius: 8px; font: inherit; }
  .radios { border: 0; padding: 4px 0; margin: 6px 0; display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; }
  .radios legend { font-weight: 600; padding: 0; width: 100%; }
  table { border-collapse: collapse; width: 100%; margin: 10px 0; }
  caption { text-align: left; font-weight: 600; padding: 4px 0; }
  th, td { border: 1px solid var(--line); padding: 4px 8px; text-align: center; }
  .left { text-align: left; }
  .num { width: 5em; padding: 4px 6px; border: 1px solid #cfd4dc; border-radius: 6px; font: inherit; }
  .confirm { display: inline-flex; gap: 6px; align-items: center; margin: 8px 0; }
  .linkish { border: 0; background: none; padding: 0; color: var(--link, #1d4ed8); text-decoration: underline; cursor: pointer; font: inherit; }
  .line { display: block; margin: 4px 0; }
  .stack { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; margin-top: 8px; }
  .sk-line { display: block; height: 22px; width: 50%; border-radius: 8px; }
  .sk-page { height: 70vh; }
  .spin.sm { width: 14px; height: 14px; border-width: 2px; border-color: rgba(255,255,255,.4); border-top-color: #fff; }
  @media (max-width: 900px) { .panes.two { grid-template-columns: minmax(0, 1fr); } .counts { margin-left: 0; } }
</style>
