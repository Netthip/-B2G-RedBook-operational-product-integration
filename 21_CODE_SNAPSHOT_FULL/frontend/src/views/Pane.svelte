<script lang="ts">
  // หนึ่งฉบับของเอกสาร — สองฉบับวางข้างกันเท่ากัน (ฉบับ A/ปีก่อน ซ้าย · ฉบับ B/ปีนี้ ขวา) · วงจุดได้ทั้งสองฉบับ (ทาง ร2)
  import { markGaps as gapsOf, pageImage, short, xtypesFor, type Mark, type Meta, type Pen, type Side } from "../lib/api";

  let {
    sid, side, label, pages, page, marks, done = [], open_, canMark, meta, open = $bindable(), dkey = "",
    onmove, onadd, onsave, ondone, onundo,
  }: {
    sid: string; side: Side; label: string; pages: number[]; page: number; marks: Mark[];
    done?: number[]; open_: boolean; canMark: boolean; meta: Meta; open: string | null; dkey?: string;
    onmove: (page: number) => void;                 // เปลี่ยนหน้า — หน้าหลักตัดสินว่าอีกฉบับเลื่อนตามหรือไม่
    onadd: (side: Side, fx: number, fy: number) => void;
    onsave: (m: Mark, patch: Partial<Mark> & { delete?: boolean }) => void;
    ondone: (side: Side) => void;
    onundo: (side: Side, page: number) => void;
  } = $props();

  let loaded = $state(false);
  let scroller: HTMLDivElement | undefined = $state();
  let img: HTMLImageElement | undefined = $state();
  const idx = $derived(pages.indexOf(page));
  const here = $derived(marks.filter((m) => m.side === side && m.page === page));
  const isDone = $derived(done.includes(page));
  const editing = $derived(here.find((m) => m.id === open) ?? null);

  // ร่างของกล่องรายละเอียด (แก้แล้วกดบันทึก)
  let dPen = $state<Pen>("red"), dLevel = $state(""), dTopic = $state(""), dPart = $state(""), dCause = $state("");
  let dXtype = $state("");
  const cross = $derived(meta.xkind === "cross_year");
  let dNote = $state(""), dSearched = $state("");
  $effect(() => {
    if (editing) {
      dPen = (editing.pen || "red") as Pen; dLevel = editing.level || (editing.pen === "pin" ? "" : editing.pen);
      dTopic = editing.topic; dPart = editing.part; dCause = editing.cause; dNote = editing.note; dSearched = editing.searched;
      dXtype = editing.xtype ?? "";
    }
  });

  function save() {
    if (!editing) return;
    const patch: Partial<Mark> = { pen: dPen, topic: dTopic, part: dPart, cause: dCause, note: dNote };
    if (cross) patch.xtype = xtypesFor(meta, dTopic).includes(dXtype) ? dXtype : "";
    if (dPen === "pin") { patch.level = dLevel; patch.searched = dSearched; }
    onsave(editing, patch);
  }

  let lastPage = 0;
  $effect(() => {
    if (page !== lastPage) { lastPage = page; loaded = !!img?.complete && img?.src.endsWith(`/${page}.png`); scroller?.scrollTo({ top: 0 }); }
  });

  function move(d: number) {
    const j = idx + d;
    if (j >= 0 && j < pages.length) { open = null; onmove(pages[j]); }
  }

  function click(e: MouseEvent) {
    if (!canMark || !img) return;
    if (open) { open = null; return; }
    const r = img.getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
    onadd(side, +fx.toFixed(5), +fy.toFixed(5));
  }

  function title(m: Mark): string {
    const g = gapsOf(m, meta.xkind);
    return [meta.pens[m.pen as Pen], m.pen === "pin" && m.level ? `ระดับ${short(meta.levels[m.level])}` : "",
            m.topic ? `หัวข้อ ${m.topic}` : "", m.part ? `ส่วน ${m.part}` : "", m.cause ? short(meta.causes[m.cause]) : "",
            m.note, g.length ? `ยังขาด ${g.join(", ")}` : ""].filter(Boolean).join(" · ");
  }
</script>

<section class="pane card" aria-label="{label} หน้า {page}">
  <header>
    <span class="chip dark">{label}</span>
    <span class="pager">
      <button class="pg" disabled={idx <= 0} onclick={() => move(-1)} aria-label="{label} หน้าก่อน">‹</button>
      <select aria-label="{label} เลือกหน้า" value={page} onchange={(e) => { open = null; onmove(+e.currentTarget.value); }}>
        {#each pages as p (p)}<option value={p}>หน้า {p}{done.includes(p) ? " ✓" : ""}</option>{/each}
      </select>
      <button class="pg" disabled={idx >= pages.length - 1} onclick={() => move(1)} aria-label="{label} หน้าถัดไป">›</button>
    </span>
    <span class="doneline">
      {#if isDone}<span class="chip ok">ตรวจหน้านี้แล้ว ✓
        {#if open_}<button class="undo" onclick={() => onundo(side, page)} title="กดพลาด — ยกเลิกเครื่องหมายตรวจของหน้านี้">ยกเลิก</button>{/if}</span>
      {:else if open_}
        <button class="btn small ghost" onclick={() => ondone(side)}
                title="นับว่าดูหน้านี้ครบแล้ว (ไม่ได้แปลว่าหน้านี้ถูกต้อง) · ไม่บังคับ · ถ้าแค่อยากเลื่อนดู ใช้ ‹ › หรือปุ่มลูกศร ← →"
          >ตรวจหน้านี้แล้ว{idx < pages.length - 1 ? " →" : ""}{#if dkey}{" "}<kbd>{dkey}</kbd>{/if}</button>
      {/if}
    </span>
  </header>

  <div class="scroll" bind:this={scroller}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="canvas" class:view={!canMark} onclick={click}>
      {#if !loaded}<div class="ph skeleton"></div>{/if}
      {#key page}
        <img bind:this={img} src={pageImage(sid, side, page)} alt="{label} หน้า {page}" class:show={loaded}
             onload={() => (loaded = true)} draggable="false">
      {/key}
      {#each here as m (m.id)}
        <button class="mk mk-{m.pen}" class:sel={open === m.id} class:gap={gapsOf(m, meta.xkind).length > 0}
                style:left="{m.fx * 100}%" style:top="{m.fy * 100}%" title={title(m)} aria-label={title(m)}
                onclick={(e) => { e.stopPropagation(); if (canMark) open = open === m.id ? null : m.id; }}></button>
      {/each}
      {#if editing}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="pop card" role="dialog" aria-label="รายละเอียดจุดที่วง" tabindex="-1"
             style:left="{Math.min(editing.fx * 100, 52)}%" style:top="{editing.fy * 100}%" onclick={(e) => e.stopPropagation()}>
          <div class="row">
            {#each Object.entries(meta.pens) as [k, l] (k)}
              <button class="mini pen-{k}" class:on={dPen === k}
                      onclick={() => { dPen = k as Pen; if (k !== "pin") dLevel = k; }}>{short(l)}</button>
            {/each}
          </div>
          {#if dPen === "pin"}
            <div class="row"><span class="hint">ระดับของหมุด</span>
              {#each Object.entries(meta.levels) as [k, l] (k)}
                <button class="mini" class:on={dLevel === k} onclick={() => (dLevel = k)}>{short(l)}</button>
              {/each}
            </div>
          {/if}
          <div class="row"><span class="hint">หัวข้อ</span>
            {#each meta.topics as t (t.code)}
              <button class="mini" class:on={dTopic === t.code} title={t.label}
                      onclick={() => (dTopic = dTopic === t.code ? "" : t.code)}>{t.code}</button>
            {/each}
          </div>
          {#if cross && dTopic}
            <div class="row"><span class="hint">ชนิดประเด็น</span>
              {#each xtypesFor(meta, dTopic) as k (k)}
                <button class="mini" class:on={dXtype === k} title={meta.xtypes[k]}
                        onclick={() => (dXtype = dXtype === k ? "" : k)}>{short(meta.xtypes[k])}</button>
              {/each}
            </div>
          {/if}
          <div class="row"><span class="hint">ส่วน</span>
            {#each meta.parts as p (p.code)}
              <button class="mini" class:on={dPart === p.code} title={p.label}
                      onclick={() => (dPart = dPart === p.code ? "" : p.code)}>{p.code}</button>
            {/each}
          </div>
          <div class="row"><span class="hint">ต/ล</span>
            {#each Object.entries(meta.causes) as [k, l] (k)}
              <button class="mini" class:on={dCause === k} onclick={() => (dCause = dCause === k ? "" : k)}>{l}</button>
            {/each}
          </div>
          {#if dTopic || dPart}<p class="hint small">{[dTopic && `${dTopic} ${meta.topics.find((t) => t.code === dTopic)?.label ?? ""}`,
            dPart && `ส่วน ${dPart} ${meta.parts.find((p) => p.code === dPart)?.label ?? ""}`].filter(Boolean).join(" · ")}</p>{/if}
          {#if dPen === "pin"}
            <input type="text" maxlength="200" placeholder="ขอบเขตที่ค้นในอีกฉบับ (ส่วน · หน้า)" bind:value={dSearched}>
          {/if}
          <!-- svelte-ignore a11y_autofocus -->
          <input type="text" maxlength="200" placeholder="หมายเหตุสั้น ๆ (ไม่บังคับ · อยู่ในเครื่องนี้เท่านั้น) · Enter = บันทึก"
                 bind:value={dNote} autofocus onkeydown={(e) => { if (e.key === "Enter") save(); }}>
          <div class="row">
            <button class="btn small" onclick={save}>บันทึก</button>
            <button class="btn ghost small" onclick={() => onsave(editing!, { delete: true })}>ลบจุดนี้</button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</section>

<style>
  .pane { padding: 10px; display: flex; flex-direction: column; min-width: 0; }
  header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
  .pager { display: inline-flex; align-items: center; gap: 4px; }
  .pg { width: 32px; height: 32px; border-radius: 10px; border: 1px solid #cfd4dc; background: #fff; font-size: 1.2em;
    cursor: pointer; line-height: 1; }
  .pg:disabled { opacity: .3; cursor: default; }
  select { padding: 5px 8px; border-radius: 10px; border: 1px solid #cfd4dc; font: inherit; background: #fff; }
  .doneline { margin-left: auto; }
  .undo { margin-left: 4px; border: 0; background: transparent; color: inherit; text-decoration: underline; cursor: pointer;
    font: inherit; font-size: .95em; padding: 0 2px; }
  kbd { font: inherit; font-size: .72em; opacity: .7; border: 1px solid #d0d5dd; border-radius: 5px; padding: 0 4px; }
  .scroll { height: calc(100vh - 190px); min-height: 440px; overflow: auto; overscroll-behavior: contain; border-radius: 10px;
    background: #fafbfc; }
  .canvas { position: relative; cursor: crosshair; }
  .canvas.view { cursor: default; }
  img { display: block; width: 100%; height: auto; user-select: none; opacity: 0; transition: opacity .18s; }
  img.show { opacity: 1; }
  .ph { position: absolute; inset: 0; min-height: 600px; border-radius: 8px; }
  .mk { position: absolute; width: 48px; height: 28px; margin: -14px 0 0 -24px; border-radius: 50%; border: 3px solid var(--pin);
    background: transparent; cursor: pointer; padding: 0; animation: drop .22s ease-out; }
  .mk-red { border-color: var(--red); } .mk-brown { border-color: var(--brown); }
  .mk-pin { width: 16px; height: 16px; margin: -8px 0 0 -8px; background: var(--pin); border-color: #fff; box-shadow: 0 0 0 2px var(--pin); }
  .mk.gap { border-style: dashed; }
  .mk-pin.gap { box-shadow: 0 0 0 2px var(--pin), 0 0 0 5px rgba(226, 75, 74, .35); }
  .mk.sel { box-shadow: 0 0 0 4px rgba(83, 74, 183, .25); }
  @keyframes drop { from { transform: scale(1.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  .pop { position: absolute; z-index: 20; width: 380px; margin-top: 20px; padding: 10px; cursor: default; animation: up .18s ease-out; }
  @keyframes up { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  .row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 6px; }
  .row .hint { margin-right: 4px; font-size: .85em; }
  .small { font-size: .85em; margin: 0 0 6px; }
  .mini { font-size: .82em; padding: 3px 9px; border-radius: 999px; border: 1px solid #cfd4dc; background: #fff; cursor: pointer; }
  .mini.on { background: var(--dark); color: #fff; border-color: var(--dark); }
  .pop input { width: 100%; padding: 7px 9px; border: 1px solid #cfd4dc; border-radius: 10px; font: inherit; margin-bottom: 6px; }
  @media (prefers-reduced-motion: reduce) { .mk, .pop { animation: none; } img { transition: none; } }
</style>
