<script lang="ts">
  // เปิดหน้าอื่นของฉบับ A/B ภายในช่วงหน้าที่รอบนี้อ่าน — ภาพจาก URL เดิม (เซิร์ฟเวอร์จำกัดหน้าที่เปิดได้เอง)
  import { preload } from "../lib/api";
  import { pageFull, type AB } from "../lib/pair";

  let { rid, side, first, last, start, note = "", off = null }:
    { rid: string; side: AB; first: number; last: number; start: number; note?: string; off?: number | null } = $props();
  const clamp = (n: number) => Math.min(last, Math.max(first, Math.round(n)));
  let page = $state(clamp(start));
  let loading = $state(true);
  const src = (n: number) => `/pdfpair/runs/${encodeURIComponent(rid)}/page/${side}/${n}.png`;
  const pages = $derived(Array.from({ length: last - first + 1 }, (_, i) => first + i));

  $effect(() => { preload([page - 1, page + 1].filter((n) => n >= first && n <= last).map(src)); });
  function to(n: number) { const c = clamp(n); if (c !== page) { page = c; loading = true; } }
</script>

<div class="peek">
  {#if note}<p class="hint">{note}</p>{/if}
  <div class="pager">
    <button class="btn small ghost" disabled={page <= first} onclick={() => to(page - 1)} aria-label="หน้าก่อน">‹</button>
    <label>หน้า
      <select value={page} onchange={(e) => to(Number((e.currentTarget as HTMLSelectElement).value))}>
        {#each pages as n (n)}<option value={n}>{pageFull(n, off)}</option>{/each}
      </select>
      <span class="hint">ช่วงที่รอบนี้อ่าน {first}–{last}</span></label>
    <button class="btn small ghost" disabled={page >= last} onclick={() => to(page + 1)} aria-label="หน้าถัดไป">›</button>
  </div>
  <div class="frame" class:loading>
    <img src={src(page)} alt="ฉบับ {side} {pageFull(page, off)}" onload={() => (loading = false)} onerror={() => (loading = false)} />
  </div>
</div>

<style>
  .peek { margin-top: 8px; }
  .peek .hint { margin: 0 0 6px; }
  .pager { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px; }
  .pager select { padding: 4px 8px; border-radius: 8px; border: 1px solid #cfd4dc; font: inherit; }
  .frame { max-height: 75vh; overflow: auto; border: 1px solid var(--line); border-radius: 12px; background: #fafbfc; }
  .frame img { display: block; width: 100%; height: auto; transition: opacity .2s; }
  .frame.loading img { opacity: .35; }
</style>
