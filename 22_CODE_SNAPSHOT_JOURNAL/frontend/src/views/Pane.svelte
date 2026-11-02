<script lang="ts">
  import { pageImage, type Mark, type Meta, type Pen, type Side } from "../lib/api";

  let {
    sid, side, label, main = false, pages, page, marks, done = [], locked, meta, open = $bindable(),
    onmove, onadd, onsave, ondone, onundo,
  }: {
    sid: string; side: Side; label: string; main?: boolean; pages: number[]; page: number; marks: Mark[];
    done?: number[]; locked: boolean; meta: Meta; open: string | null;
    onmove: (page: number) => void;                 // เปลี่ยนหน้า — หน้าหลักตัดสินว่าอีกฉบับเลื่อนตามหรือไม่
    onadd: (side: Side, fx: number, fy: number) => void;
    onsave: (m: Mark, patch: Partial<Mark> & { delete?: boolean }) => void;
    ondone?: () => void;
    onundo?: (page: number) => void;
  } = $props();

  let loaded = $state(false);
  let scroller: HTMLDivElement | undefined = $state();
  let img: HTMLImageElement | undefined = $state();
  const idx = $derived(pages.indexOf(page));
  const here = $derived(marks.filter((m) => m.side === side && m.page === page));
  const isDone = $derived(done.includes(page));
  const editing = $derived(here.find((m) => m.id === open) ?? null);

  // ร่างของกล่องรายละเอียด (แก้แล้วกดบันทึก)
  let dTopic = $state(""), dNote = $state(""), dPen = $state<Pen>("red");
  $effect(() => { if (editing) { dTopic = editing.topic; dNote = editing.note; dPen = editing.pen; } });

  let lastPage = 0;
  $effect(() => {
    if (page !== lastPage) { lastPage = page; loaded = !!img?.complete && img?.src.endsWith(`/${page}.png`); scroller?.scrollTo({ top: 0 }); }
  });

  function move(d: number) {
    const j = idx + d;
    if (j >= 0 && j < pages.length) { open = null; onmove(pages[j]); }
  }

  function click(e: MouseEvent) {
    if (locked || !img) return;
    if (open) { open = null; return; }
    const r = img.getBoundingClientRect();
    const fx = (e.clientX - r.left) / r.width, fy = (e.clientY - r.top) / r.height;
    if (fx < 0 || fx > 1 || fy < 0 || fy > 1) return;
    onadd(side, +fx.toFixed(5), +fy.toFixed(5));
  }
</script>

<section class="pane card" class:main aria-label="{label} หน้า {page}">
  <header>
    <span class="chip" class:dark={main}>{label}</span>
    <span class="pager">
      <button class="pg" disabled={idx <= 0} onclick={() => move(-1)} aria-label="{label} หน้าก่อน">‹</button>
      <select aria-label="{label} เลือกหน้า" value={page} onchange={(e) => { open = null; onmove(+e.currentTarget.value); }}>
        {#each pages as p (p)}<option value={p}>หน้า {p}{main && done.includes(p) ? " ✓" : ""}</option>{/each}
      </select>
      <button class="pg" disabled={idx >= pages.length - 1} onclick={() => move(1)} aria-label="{label} หน้าถัดไป">›</button>
    </span>
    {#if main}
      {#if isDone}<span class="chip ok">ตรวจหน้านี้แล้ว ✓
        {#if !locked}<button class="undo" onclick={() => onundo?.(page)} title="กดพลาด — ยกเลิกเครื่องหมายตรวจของหน้านี้">ยกเลิก</button>{/if}</span>{/if}
      {#if !locked}
        <button class="btn small donebtn" onclick={() => ondone?.()}
                title="นับว่าดูหน้านี้ครบแล้ว (ไม่ได้แปลว่าหน้านี้ถูกต้อง) แล้วไปหน้าถัดไป · ถ้าแค่อยากเลื่อนดู ใช้ ‹ › หรือปุ่มลูกศร ← →"
          >ตรวจหน้านี้แล้ว{idx < pages.length - 1 ? " →" : ""} <kbd>D</kbd></button>
      {/if}
    {/if}
  </header>

  <div class="scroll" bind:this={scroller}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="canvas" class:locked onclick={click}>
      {#if !loaded}<div class="ph skeleton"></div>{/if}
      {#key page}
        <img bind:this={img} src={pageImage(sid, side, page)} alt="{label} หน้า {page}" class:show={loaded}
             onload={() => (loaded = true)} draggable="false">
      {/key}
      {#each here as m (m.id)}
        <button class="mk mk-{m.pen}" class:sel={open === m.id} style:left="{m.fx * 100}%" style:top="{m.fy * 100}%"
                title={`${meta.pens[m.pen]}${m.topic ? ` · ${m.topic}` : ""}${m.note ? ` · ${m.note}` : ""}`}
                aria-label={`${meta.pens[m.pen]}${m.topic ? ` หัวข้อ ${m.topic}` : ""}${m.note ? ` ${m.note}` : ""}`}
                onclick={(e) => { e.stopPropagation(); if (!locked) open = open === m.id ? null : m.id; }}></button>
      {/each}
      {#if editing}
        <!-- svelte-ignore a11y_click_events_have_key_events -->
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="pop card" role="dialog" aria-label="รายละเอียดจุดที่วง" tabindex="-1"
             style:left="{Math.min(editing.fx * 100, 58)}%" style:top="{editing.fy * 100}%" onclick={(e) => e.stopPropagation()}>
          <div class="row">
            {#each Object.entries(meta.pens) as [k, l] (k)}
              <button class="mini pen-{k}" class:on={dPen === k} onclick={() => (dPen = k as Pen)}>{l.split(" — ")[0]}</button>
            {/each}
          </div>
          <div class="row">
            {#each meta.topics as t (t.code)}
              <button class="mini" class:on={dTopic === t.code} title={t.label}
                      onclick={() => (dTopic = dTopic === t.code ? "" : t.code)}>{t.code} {t.label}</button>
            {/each}
          </div>
          <!-- svelte-ignore a11y_autofocus -->
          <input type="text" maxlength="200" placeholder="หมายเหตุสั้น ๆ (ไม่บังคับ) · Enter = บันทึก" bind:value={dNote} autofocus
                 onkeydown={(e) => { if (e.key === "Enter") onsave(editing!, { topic: dTopic, note: dNote, pen: dPen }); }}>
          <div class="row">
            <button class="btn small" onclick={() => onsave(editing!, { topic: dTopic, note: dNote, pen: dPen })}>บันทึก</button>
            <button class="btn ghost small" onclick={() => onsave(editing!, { delete: true })}>ลบจุดนี้</button>
          </div>
        </div>
      {/if}
    </div>
  </div>
</section>

<style>
  .pane { padding: 10px; display: flex; flex-direction: column; min-width: 0; }
  .pane.main { border-color: #b8bec9; }
  header { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; }
  .pager { display: inline-flex; align-items: center; gap: 4px; }
  .pg { width: 32px; height: 32px; border-radius: 10px; border: 1px solid #cfd4dc; background: #fff; font-size: 1.2em;
    cursor: pointer; line-height: 1; }
  .pg:disabled { opacity: .3; cursor: default; }
  select { padding: 5px 8px; border-radius: 10px; border: 1px solid #cfd4dc; font: inherit; background: #fff; }
  .donebtn { margin-left: auto; }
  .undo { margin-left: 4px; border: 0; background: transparent; color: inherit; text-decoration: underline; cursor: pointer;
    font: inherit; font-size: .95em; padding: 0 2px; }
  kbd { font: inherit; font-size: .72em; opacity: .7; border: 1px solid rgba(255,255,255,.4); border-radius: 5px; padding: 0 4px; }
  .scroll { height: calc(100vh - 190px); min-height: 440px; overflow: auto; overscroll-behavior: contain; border-radius: 10px;
    background: #fafbfc; }
  .canvas { position: relative; cursor: crosshair; }
  .canvas.locked { cursor: default; }
  img { display: block; width: 100%; height: auto; user-select: none; opacity: 0; transition: opacity .18s; }
  img.show { opacity: 1; }
  .ph { position: absolute; inset: 0; min-height: 600px; border-radius: 8px; }
  .mk { position: absolute; width: 48px; height: 28px; margin: -14px 0 0 -24px; border-radius: 50%; border: 3px solid var(--pin);
    background: transparent; cursor: pointer; padding: 0; animation: drop .22s ease-out; }
  .mk-red { border-color: var(--red); } .mk-brown { border-color: var(--brown); }
  .mk-pin { width: 16px; height: 16px; margin: -8px 0 0 -8px; background: var(--pin); border-color: #fff; box-shadow: 0 0 0 2px var(--pin); }
  .mk.sel { box-shadow: 0 0 0 4px rgba(83, 74, 183, .25); }
  @keyframes drop { from { transform: scale(1.6); opacity: 0; } to { transform: scale(1); opacity: 1; } }
  .pop { position: absolute; z-index: 20; width: 340px; margin-top: 20px; padding: 10px; cursor: default; animation: up .18s ease-out; }
  @keyframes up { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
  .row { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }
  .mini { font-size: .82em; padding: 3px 9px; border-radius: 999px; border: 1px solid #cfd4dc; background: #fff; cursor: pointer; }
  .mini.on { background: var(--dark); color: #fff; border-color: var(--dark); }
  .pop input { width: 100%; padding: 7px 9px; border: 1px solid #cfd4dc; border-radius: 10px; font: inherit; margin-bottom: 6px; }
</style>
