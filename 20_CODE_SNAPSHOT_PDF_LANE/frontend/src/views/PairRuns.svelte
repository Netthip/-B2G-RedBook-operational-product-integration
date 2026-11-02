<script lang="ts">
  import { link } from "../lib/router.svelte";
  import { listRuns, type PRunRow } from "../lib/pair";

  let rows = $state<PRunRow[] | null>(null);
  let err = $state("");
  listRuns().then((x) => (rows = x)).catch((e) => (err = (e as Error).message));

  const when = (s: string) => s.slice(0, 16).replace("T", " ");
  const short = (l: string) => l.replace(/^ฉบับ [AB] · /, "");
</script>

<div class="head">
  <h1 class="h1">รอบตรวจเทียบ</h1>
  <a class="btn" href="/r/p/new" onclick={link}>＋ เริ่มรอบใหม่</a>
</div>

{#if err}
  <div class="card msg">{err}</div>
{:else if !rows}
  <div class="list">{#each [0, 1, 2] as i (i)}<div class="card skeleton sk"></div>{/each}</div>
{:else if !rows.length}
  <p class="empty">ยังไม่มีรอบ · <a href="/r/p/new" onclick={link}>เริ่มรอบใหม่</a></p>
{:else}
  <div class="list">
    {#each rows as r (r.id)}
      {@const done = r.counts ? r.counts.actionable - r.counts.pending : 0}
      {@const frac = r.counts?.actionable ? done / r.counts.actionable : 1}
      <a class="card run" class:old={!!r.superseded_by} href="/r/p/{r.id}" onclick={link}>
        <span class="mini" role="img" aria-label={r.counts ? `บันทึกความเห็นแล้ว ${done} จาก ${r.counts.actionable} จุด` : "ไม่ทราบความคืบหน้า"}>
          <svg viewBox="0 0 44 44" aria-hidden="true"><circle class="mb" cx="22" cy="22" r="18" />
            {#if r.counts && done > 0}<circle class="mf" class:full={frac >= 1} cx="22" cy="22" r="18" style:stroke-dasharray="{113.1 * frac}px 113.1px" />{/if}</svg>
          <span>{r.counts ? (r.counts.actionable ? `${Math.round(frac * 100)}%` : "—") : ""}</span></span>
        <span class="who"><b>{r.agency || "ไม่ระบุหน่วยงาน"}</b>
          <span class="chip">{r.mode_label.split(" (")[0]}</span>
          {#if r.superseded_by}<span class="chip warn">ถูกแทนแล้ว — อ่านอย่างเดียว</span>{/if}</span>
        {#if r.sides}<span class="files"><span class="sa">{short(r.sides.A.label)}</span>
          <span class="arrow" aria-hidden="true">→</span> <span class="sb">{short(r.sides.B.label)}</span></span>{/if}
        <span class="hint">{when(r.created_at)}{#if r.counts}{r.counts.actionable ? ` · ตรวจแล้ว ${r.counts.actionable - r.counts.pending}/${r.counts.actionable} จุด` : " · ไม่พบจุดต่าง"}{/if}</span>
        <span class="go" aria-hidden="true">→</span>
      </a>
    {/each}
  </div>
{/if}

<style>
  .head { display: flex; align-items: center; justify-content: space-between; gap: 12px; max-width: 980px; margin: 0 auto 14px; }
  .head .h1 { margin: 0; }
  .sa { color: var(--a); font-weight: 600; } .sb { color: var(--b); font-weight: 600; }
  .h2 { max-width: 980px; margin: 0 auto 8px; font-size: 1.05em; }
  .msg { padding: 16px; }
  .list { display: flex; flex-direction: column; gap: 10px; max-width: 980px; margin: 0 auto; }
  .sk { height: 74px; }
  .run { display: grid; grid-template-columns: 52px 1fr auto; gap: 2px 12px; padding: 14px 18px; color: inherit; text-decoration: none;
    transition: transform .15s, box-shadow .2s; }
  .run:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(16, 24, 40, .12); }
  .run.old { opacity: .75; }
  .who { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .files { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-size: .92em; }
  .files .tag { width: 22px; height: 22px; font-size: 12px; }
  .arrow { color: var(--muted); }
  .run > :not(.mini):not(.go) { grid-column: 2; }
  .go { grid-row: 1 / span 3; grid-column: 3; align-self: center; font-size: 1.4em; color: var(--muted); }
  .mini { grid-row: 1 / span 3; grid-column: 1; align-self: center; position: relative; width: 44px; height: 44px;
    display: grid; place-items: center; font-size: .72em; font-weight: 700; }
  .mini svg { position: absolute; inset: 0; transform: rotate(-90deg); }
  .mb, .mf { fill: none; stroke-width: 5; }
  .mb { stroke: #eef0f3; }
  .mf { stroke: var(--accent); stroke-linecap: round; }
  .mf.full { stroke: var(--ok); }
  .mono { font-family: ui-monospace, Consolas, monospace; font-size: .9em; }
</style>
