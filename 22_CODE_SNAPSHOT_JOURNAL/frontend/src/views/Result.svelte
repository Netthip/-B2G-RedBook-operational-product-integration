<script lang="ts">
  import { get, post, type Meta, type Result } from "../lib/api";
  import { link } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import Metrics from "../lib/Metrics.svelte";

  let { sid, meta }: { sid: string; meta: Meta } = $props();
  let r = $state<Result | null>(null);
  let err = $state("");
  let busy = $state<string | null>(null);
  let pick = $state<Record<string, string>>({});
  let filter = $state<"todo" | "all">("todo");

  get<Result>(`/api/trial/s/${sid}/result`).then((x) => (r = x)).catch((e) => (err = e.message));

  async function link_(mid: string, verdict: string) {
    busy = mid;
    try {
      r = await post<Result>(`/api/trial/s/${sid}/link/${mid}`, { verdict, finding_id: pick[mid] ?? "" });
    } catch (e) { toast((e as Error).message, true); } finally { busy = null; }
  }
  async function extra(fid: string, verdict: string) {
    busy = fid;
    try {
      r = await post<Result>(`/api/trial/s/${sid}/extra/${fid}`, { verdict });
    } catch (e) { toast((e as Error).message, true); } finally { busy = null; }
  }

  const todoMarks = $derived(r ? r.marks.filter((m) => !m.verdict).length : 0);
  const todoExtras = $derived(r ? r.extras.filter((x) => !x.verdict).length : 0);
  const marks = $derived(r ? (filter === "todo" ? r.marks.filter((m) => !m.verdict) : r.marks) : []);
  const extras = $derived(r ? (filter === "todo" ? r.extras.filter((x) => !x.verdict) : r.extras) : []);
</script>

{#if err}
  <div class="card msg">{err} · <a href="/r/s/{sid}" onclick={link}>กลับไปหน้าตรวจ</a></div>
{:else if !r}
  <div class="card skeleton sk"></div>
{:else}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>{r.session.book.title}</b> · ระบบเจออะไร</div>
    <span class="chip ok">ส่งผลแล้ว {r.session.locked_at.slice(0, 16).replace("T", " ")}</span>
  </div>
  <p class="hint lead">จุดที่คุณวงล็อกไว้ก่อนระบบเทียบ · ระบบ<b>เสนอ</b>คู่จากหน้าและตำแหน่ง คุณเป็นผู้ยืนยันทุกข้อ ·
    ข้อมูลประกอบของระบบ {r.metrics.info} รายการ (เช่น การเปลี่ยนแปลงระหว่างปี) ไม่นับ</p>

  <Metrics m={r.metrics} {meta} extrasTotal={r.extras.length} />

  <div class="filter" role="tablist">
    <button role="tab" class:on={filter === "todo"} aria-selected={filter === "todo"} onclick={() => (filter = "todo")}>
      ยังไม่ยืนยัน <span class="chip">{todoMarks + todoExtras}</span></button>
    <button role="tab" class:on={filter === "all"} aria-selected={filter === "all"} onclick={() => (filter = "all")}>ทั้งหมด</button>
    {#if r.complete}<span class="chip ok">ยืนยันครบแล้ว</span>{/if}
  </div>

  <h2>๑. จุดที่คุณวง <span class="hint">({r.marks.length} จุด)</span></h2>
  {#if !marks.length}<p class="hint">{filter === "todo" ? "ยืนยันครบทุกจุดแล้ว" : "ไม่ได้วงจุดใดไว้"}</p>{/if}
  {#each marks as m (m.id)}
    <article class="card item item-{m.pen}" class:busy={busy === m.id}>
      <header>
        <span class="dot dot-{m.pen}" aria-hidden="true"></span>
        <b>{meta.pens[m.pen].split(" — ")[0]}</b> · {m.side === "cur" ? "ฉบับปัจจุบัน" : "ฉบับก่อน"} หน้า {m.page}
        {#if m.topic} · {m.topic} {meta.topics.find((t) => t.code === m.topic)?.label}{/if}
        {#if m.note} · “{m.note}”{/if}
        · <a href="/r/s/{sid}?{m.side === 'cur' ? `p=${m.page}` : `pp=${m.page}`}" onclick={link}>ดูจุดบนหน้า</a>
        {#if m.verdict}<span class="chip ok">{meta.link_verdicts[m.verdict]}</span>{/if}
      </header>
      {#if m.finding}
        <p>ระบบ{m.proposed && !m.verdict ? "เสนอว่าตรงกับ" : "จับคู่กับ"}: <b>{m.finding.subject}</b> · {m.finding.kind}
          {#if m.finding.column} · {m.finding.column}{/if}
          · <a href={m.finding.evidence} target="_blank" rel="noopener">ดูหลักฐาน A | B ↗</a></p>
        {#if m.finding.a || m.finding.b}<p class="mono">{m.finding.a} → {m.finding.b}</p>{/if}
        {#if m.finding.caveats?.length}<p class="caveat">⚠ ต้องให้คนยืนยันก่อนใช้: {m.finding.caveats.join(" · ")}</p>{/if}
      {:else}
        <p class="hint">ระบบไม่มีข้อสังเกตบนตำแหน่งนี้ — ถ้าคิดว่าระบบยกไว้ที่อื่น เลือกข้อด้านล่าง ถ้าไม่ใช่ กด "{meta.link_verdicts.not_same}"</p>
      {/if}
      <div class="act">
        <select bind:value={pick[m.id]} aria-label="ข้อสังเกตของระบบที่ตรงกับจุดนี้">
          <option value="">{m.finding ? "— ใช้ข้อที่ระบบเสนอ —" : "— เลือกข้อสังเกตของระบบ —"}</option>
          {#each m.candidates as c (c.id)}
            <option value={c.id}>หน้า {(m.side === "cur" ? c.page_cur : c.page_prev) ?? "—"} · {c.subject.slice(0, 60)} · {c.kind.slice(0, 36)}</option>
          {/each}
        </select>
        {#each Object.entries(meta.link_verdicts) as [k, l] (k)}
          <button class="btn small" class:ghost={k === "not_same"} class:on={m.verdict === k} disabled={busy === m.id}
                  onclick={() => link_(m.id, k)}>{l}</button>
        {/each}
      </div>
    </article>
  {/each}

  <h2>๒. ข้อที่ระบบยกเพิ่ม <span class="hint">({r.extras.length} ข้อ · ไม่นับเป็นความผิดของคุณ)</span></h2>
  {#if !extras.length}<p class="hint">{filter === "todo" ? "จัดครบทุกข้อแล้ว" : "ไม่มี"}</p>{/if}
  {#each extras as f (f.id)}
    <article class="card item" class:busy={busy === f.id}>
      <header><b>{f.subject}</b> · {f.kind}{#if f.column} · {f.column}{/if} · หน้า {f.page_cur ?? f.page_prev ?? "—"}
        {#if f.within} (ภายในฉบับ {f.within}){/if}
        · <a href={f.evidence} target="_blank" rel="noopener">ดูหลักฐาน A | B ↗</a>
        {#if f.verdict}<span class="chip ok">{meta.extra_verdicts[f.verdict]}</span>{/if}</header>
      {#if f.a || f.b}<p class="mono">{f.a} → {f.b}</p>{/if}
      {#if f.caveats?.length}<p class="caveat">⚠ ต้องให้คนยืนยันก่อนใช้: {f.caveats.join(" · ")}</p>{/if}
      <div class="act">
        {#each Object.entries(meta.extra_verdicts) as [k, l] (k)}
          <button class="btn ghost small" class:on={f.verdict === k} disabled={busy === f.id} onclick={() => extra(f.id, k)}>{l}</button>
        {/each}
      </div>
    </article>
  {/each}

  <div class="next">
    <a class="btn" href="/r/s/{sid}/survey" onclick={link}>ต่อไป: แบบสอบถามหน้าเดียว →</a>
    <a class="btn ghost" href="/r/s/{sid}/dashboard" onclick={link}>ดูแดชบอร์ด</a>
  </div>
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
  .title { flex: 1; }
  .lead { margin: 0 0 12px; }
  .msg { padding: 16px; }
  .sk { height: 60vh; }
  h2 { font-size: 1.15em; margin: 22px 0 8px; }
  .filter { display: flex; gap: 8px; align-items: center; margin: 16px 0 0; }
  .filter button { padding: 6px 14px; border-radius: 999px; border: 1px solid #cfd4dc; background: #fff; cursor: pointer; }
  .filter button.on { background: var(--dark); color: #fff; border-color: var(--dark); }
  .item { padding: 10px 14px; margin: 8px 0; transition: opacity .2s, transform .2s; }
  .item.busy { opacity: .55; }
  .item-red { border-left: 5px solid var(--red); } .item-brown { border-left: 5px solid var(--brown); } .item-pin { border-left: 5px solid var(--pin); }
  .item p { margin: 6px 0; }
  .mono { font-family: ui-monospace, Consolas, monospace; font-size: .92em; color: #344054; }
  .caveat { background: #fff8e6; border: 1px solid #f1d58a; border-radius: 10px; padding: 6px 10px; font-size: .92em; }
  .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 3px solid var(--pin); vertical-align: middle; }
  .dot-red { border-color: var(--red); } .dot-brown { border-color: var(--brown); } .dot-pin { background: var(--pin); }
  .act { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 6px; }
  .act select { max-width: 460px; padding: 6px 8px; border-radius: 10px; border: 1px solid #cfd4dc; font: inherit; }
  .next { display: flex; gap: 10px; margin-top: 22px; flex-wrap: wrap; }
</style>
