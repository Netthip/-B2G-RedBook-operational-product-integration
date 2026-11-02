<script lang="ts">
  import { ApiError, get, post, pageImage, preload, type Meta, type Mark, type Pen, type Session, type Side } from "../lib/api";
  import { go, link, nav } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import Pane from "./Pane.svelte";

  let { sid, meta }: { sid: string; meta: Meta } = $props();

  let s = $state<Session | null>(null);
  let pen = $state<Pen>("red");
  let two = $state(nav.query.get("two") !== "0");
  let linked = $state(true);                         // เลื่อนฉบับปัจจุบันแล้วฉบับก่อนเลื่อนตาม (รักษาคู่หน้าที่จัดไว้)
  let page = $state<Record<Side, number>>({ cur: 0, prev: 0 });
  let open = $state<string | null>(null);          // จุดที่เปิดกล่องรายละเอียด
  let brief = $state(false);
  let lockAsk = $state(false);
  let lockOk = $state(false);
  let locking = $state(false);

  get<Session>(`/api/trial/s/${sid}`).then((r) => {
    s = r;
    const q = (k: string) => Number(nav.query.get(k)) || 0;
    const firstTodo = r.pages.cur.find((p) => !r.done.includes(p)) ?? r.pages.cur[0];
    page.cur = r.pages.cur.includes(q("p")) ? q("p") : firstTodo;
    const i = r.pages.cur.indexOf(page.cur);
    page.prev = r.pages.prev.includes(q("pp")) ? q("pp") : r.pages.prev[Math.min(i, r.pages.prev.length - 1)];
    brief = !r.locked && !r.marks.length && !r.done.length;
  }).catch((e) => toast(e.message, true));

  const pending = $derived(s ? s.pages.cur.filter((p) => !s!.done.includes(p)) : []);
  const counts = $derived.by(() => {
    const c = { red: 0, brown: 0, pin: 0 };
    s?.marks.forEach((m) => { if ((m.side === "cur" && m.page === page.cur) || (two && m.side === "prev" && m.page === page.prev)) c[m.pen]++; });
    return c;
  });

  // URL + บันทึกคู่หน้าที่เปิดเทียบ (รอให้หยุดเปลี่ยนหน้าก่อน) + โหลดหน้าถัดไปรอไว้
  let logTimer: ReturnType<typeof setTimeout>;
  $effect(() => {
    if (!s || !page.cur) return;
    const q = `?p=${page.cur}${two ? `&pp=${page.prev}` : "&two=0"}`;
    history.replaceState(null, "", `/r/s/${sid}${q}`);
    const nxt = (side: Side) => s!.pages[side][s!.pages[side].indexOf(page[side]) + 1];
    preload([nxt("cur"), ...(two ? [nxt("prev")] : [])].filter(Boolean).map((p, k) => pageImage(sid, k ? "prev" : "cur", p!)));
    if (s.locked) return;
    const pair = { cur: page.cur, prev: two ? page.prev : 0 };
    clearTimeout(logTimer);
    logTimer = setTimeout(() => post(`/api/trial/s/${sid}/view`, pair).catch(() => {}), 600);
  });

  async function addMark(side: Side, fx: number, fy: number) {
    if (!s || s.locked) return;
    const temp: Mark = { id: `tmp${Math.random()}`, side, page: page[side], fx, fy, pen, topic: "", note: "" };
    s.marks.push(temp);                                   // ขึ้นทันที — ไม่รอเซิร์ฟเวอร์
    open = temp.id;
    try {
      const m = await post<Mark>(`/api/trial/s/${sid}/marks`, { side, page: temp.page, fx, fy, pen });
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
    else Object.assign(m, patch);
    open = null;
    try {
      await post(`/api/trial/s/${sid}/marks/${m.id}`, patch);
      toast(patch.delete ? "ลบจุดแล้ว" : "บันทึกแล้ว");
    } catch (e) {
      if (patch.delete) s.marks.push(before); else Object.assign(m, before);
      failed(e);
    }
  }

  /** เปลี่ยนหน้า — เลื่อนฉบับปัจจุบันเมื่อ "เลื่อนคู่กัน" เปิดอยู่ ฉบับก่อนเลื่อนตามเท่ากัน (รักษาคู่หน้าที่ผู้ตรวจจัดไว้)
   *  · เลื่อนฉบับก่อนเอง = ปรับคู่หน้า (ฉบับปัจจุบันไม่ขยับ) */
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

  /** "ตรวจหน้านี้แล้ว" (D) = นับว่าดูหน้านี้ครบแล้ว (ไม่ได้แปลว่าหน้าถูกต้อง) แล้วไปหน้าถัดไป */
  async function markDone() {
    if (!s || s.locked) return;
    const p = page.cur;
    if (!s.done.includes(p)) s.done.push(p);
    const list = s.pages.cur, nx = list[list.indexOf(p) + 1];
    if (nx) moveTo("cur", nx);
    toast(`นับหน้า ${p} ว่าตรวจแล้ว`, false, { label: "ยกเลิก", run: () => undo(p) });
    try {
      await post(`/api/trial/s/${sid}/done`, { page: p });
    } catch (e) {
      s.done = s.done.filter((x) => x !== p);
      failed(e);
    }
  }

  /** ยกเลิก "ตรวจหน้านี้แล้ว" (กดพลาด) — ก่อนส่งผลเท่านั้น */
  async function undo(p: number) {
    if (!s || s.locked || !s.done.includes(p)) return;
    s.done = s.done.filter((x) => x !== p);
    try {
      await post(`/api/trial/s/${sid}/undone`, { page: p });
      toast(`ยกเลิกเครื่องหมายตรวจของหน้า ${p} แล้ว`);
    } catch (e) {
      if (!s.done.includes(p)) s.done.push(p);
      failed(e);
    }
  }

  /** ข้อผิดพลาด — ถ้าส่งผลไปแล้ว (เช่น จากอีกแท็บ) เปลี่ยนเป็นแบบดูอย่างเดียว */
  function failed(e: unknown) {
    toast((e as Error).message, true);
    if (e instanceof ApiError && e.code === "locked" && s) s.locked = true;
  }

  async function lock() {
    if (!lockOk || locking) return;
    locking = true;
    try {
      await post(`/api/trial/s/${sid}/lock`, { confirm: true });
      go(`/r/s/${sid}/result`);
    } catch (e) {
      toast((e as Error).message, true);
      locking = false;
    }
  }

  function keys(e: KeyboardEvent) {
    const t = e.target instanceof Element ? e.target : null;
    if (t?.closest("input, textarea, select") || e.ctrlKey || e.metaKey || e.altKey || !s) return;
    if (e.key === "1") pen = "red";
    else if (e.key === "2") pen = "brown";
    else if (e.key === "3") pen = "pin";
    else if (e.key === "Escape") open = null;
    else if (e.key.toLowerCase() === "d") markDone();
    else if (e.key === "ArrowRight") step(1);
    else if (e.key === "ArrowLeft") step(-1);
    else return;
    e.preventDefault();
  }
</script>

<svelte:window onkeydown={keys} />

{#if !s}
  <div class="bar"><span class="skeleton sk-line"></span></div>
  <div class="panes two"><div class="card skeleton sk-page"></div><div class="card skeleton sk-page"></div></div>
{:else}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>{s.book.title}</b> · {s.book.agency} · {s.book.pair}</div>
    <span class="chip">{s.pages.cur.length - pending.length}/{s.pages.cur.length} หน้า</span>
    <span class="progress" aria-hidden="true"><span style:width="{(100 * (s.pages.cur.length - pending.length)) / s.pages.cur.length}%"></span></span>
  </div>

  {#if s.locked}
    <div class="card note ok">ส่งผลตรวจแล้ว — หน้านี้ดูได้อย่างเดียว · <a href="/r/s/{sid}/result" onclick={link}>ไปดูว่าระบบเจออะไร →</a></div>
  {:else}
    <details class="card brief" bind:open={brief}>
      <summary>คำชี้แจงก่อนตรวจ</summary>
      <ul>
        <li><b>ปีปัจจุบันต้องถูกต้องเป็นหลัก</b> — ตรวจ {s.book.cur.title} เป็นหลัก · ฉบับก่อน ({s.book.prev.title}) วางไว้ด้านซ้ายให้เทียบ</li>
        <li>รบกวนดู<b>ตัวชี้วัด วิสัยทัศน์ พันธกิจ</b> ด้วยว่าอะไรหายไป เพิ่มเข้ามา หรือไม่ใช้แล้ว</li>
        <li>เจอจุดที่ไม่ตรง เลือกปากกาแล้วแตะบนภาพตรงจุดนั้น — เลือกหัวข้อและพิมพ์สั้น ๆ ได้ (ไม่บังคับ)</li>
        <li>ปากกา<b class="r">แดง</b> = สำคัญ · ปากกา<b class="b">น้ำตาล</b> = สังเกตเห็นแต่สำคัญน้อยกว่า · <b>หมุด</b> = ของที่ควรมีแต่หายไป</li>
        <li><b>เลื่อนดูเฉย ๆ</b> ใช้ปุ่มลูกศร ← → หรือ ‹ › — ยังไม่นับว่าตรวจ · <b>ดูหน้านี้ครบแล้ว</b> กด "ตรวจหน้านี้แล้ว" (หรือ D)
          ซึ่งไม่ได้แปลว่าหน้านั้นถูกต้อง จุดที่ไม่ตรงให้วงไว้ · ปุ่มลัดปากกา 1 · 2 · 3</li>
      </ul>
    </details>
  {/if}

  <div class="tools" role="toolbar" aria-label="ปากกา">
    {#if !s.locked}
      {#each Object.entries(meta.pens) as [k, label], i (k)}
        <button class="pen pen-{k}" class:on={pen === k} aria-pressed={pen === k} onclick={() => (pen = k as Pen)}>
          <span class="dot" aria-hidden="true"></span>{label}<kbd>{i + 1}</kbd></button>
      {/each}
    {/if}
    <button class="pen" onclick={() => (two = !two)}>{two ? "ดูฉบับปัจจุบันอย่างเดียว" : "วางสองฉบับข้างกัน"}</button>
    {#if two}
      <button class="pen" class:on={linked} aria-pressed={linked} onclick={() => (linked = !linked)}
              title="เปิด = เลื่อนฉบับปัจจุบันแล้วฉบับก่อนเลื่อนตาม · เลื่อนฉบับก่อนเองได้เสมอเพื่อจัดคู่หน้า">
        เลื่อนสองฉบับคู่กัน: {linked ? "เปิด" : "ปิด"}</button>
    {/if}
    <span class="hint counts"><kbd>←</kbd><kbd>→</kbd> เลื่อนดู · <kbd>D</kbd> ตรวจหน้านี้แล้ว ·
      บนหน้าที่เปิด: แดง {counts.red} · น้ำตาล {counts.brown} · หมุด {counts.pin}</span>
  </div>

  <div class="panes" class:two>
    {#if two}
      <Pane {sid} side="prev" label="ฉบับก่อน" pages={s.pages.prev} page={page.prev} marks={s.marks}
            locked={s.locked} {meta} bind:open onmove={(p) => moveTo("prev", p)} onadd={addMark} onsave={saveMark} />
    {/if}
    <Pane {sid} side="cur" label="ฉบับปัจจุบัน" main pages={s.pages.cur} page={page.cur} marks={s.marks}
          done={s.done} locked={s.locked} {meta} bind:open onmove={(p) => moveTo("cur", p)} onadd={addMark}
          onsave={saveMark} ondone={markDone} onundo={undo} />
  </div>

  {#if !s.locked}
    <div class="card lockbox">
      <div><b>ส่งผลตรวจ</b> · วงไว้ {s.marks.length} จุด ·
        {#if pending.length}<span class="hint">ยังไม่กด "ตรวจหน้านี้แล้ว" {pending.length} หน้า
          ({pending.slice(0, 8).join(", ")}{pending.length > 8 ? " …" : ""})</span>{:else}<span class="chip ok">ตรวจครบทุกหน้าแล้ว</span>{/if}</div>
      {#if !lockAsk}
        <button class="btn" disabled={pending.length > 0} onclick={() => (lockAsk = true)}>ส่งผลตรวจ</button>
      {:else}
        <label class="confirm"><input type="checkbox" bind:checked={lockOk}> ฉันตรวจเสร็จแล้ว ส่งแล้วแก้จุดที่วงไม่ได้</label>
        <button class="btn" disabled={!lockOk || locking} onclick={lock}>
          {#if locking}<span class="spin sm"></span> ระบบกำลังเทียบเล่ม…{:else}ยืนยันส่งผล{/if}</button>
        <button class="btn ghost small" onclick={() => { lockAsk = false; lockOk = false; }}>ยังไม่ส่ง</button>
      {/if}
    </div>
  {/if}
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 10px; }
  .title { flex: 1; min-width: 240px; }
  .progress { width: 140px; height: 8px; background: #e4e7ec; border-radius: 999px; overflow: hidden; }
  .progress span { display: block; height: 100%; background: var(--ok); transition: width .4s ease; }
  .note { padding: 12px 16px; margin-bottom: 10px; }
  .note.ok { background: var(--ok-bg); border-color: #b9e0c4; }
  .brief { padding: 8px 18px; margin-bottom: 10px; background: #fff8e6; border-color: #f1d58a; box-shadow: none; }
  .brief summary { cursor: pointer; font-weight: 600; }
  .r { color: #c8322f; } .b { color: var(--brown); }
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
  .lockbox { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; padding: 14px 18px; margin-top: 16px; }
  .lockbox > div { flex: 1; min-width: 260px; }
  .confirm { display: inline-flex; gap: 6px; align-items: center; }
  .sk-line { display: block; height: 22px; width: 50%; border-radius: 8px; }
  .sk-page { height: 70vh; }
  .spin.sm { width: 14px; height: 14px; border-width: 2px; border-color: rgba(255,255,255,.4); border-top-color: #fff; }
  @media (max-width: 900px) { .panes.two { grid-template-columns: minmax(0, 1fr); } .counts { margin-left: 0; } }
</style>
