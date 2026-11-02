<script lang="ts">
  // หนึ่งแถวของจุดที่ต่างในภาพรวม — ป้ายผลการตรวจ/การใช้ผลมาจากเซิร์ฟเวอร์ · "รอตรวจ" = ยังไม่มีคำตัดสิน
  import { link } from "../lib/router.svelte";
  import { NO_VALUES, TREND_MARK, TREND_SAY, absDelta, pagesOf, trend, type Offsets, type PFinding } from "../lib/pair";

  // anchor = แถวหลักของข้อนี้ (มี id ให้ลิงก์ #f-<id> เลื่อนมาหา) · แถวซ้ำในส่วนสรุปไม่มี id
  let { rid, f, flash = false, anchor = true, off = {} }: { rid: string; f: PFinding; flash?: boolean; anchor?: boolean; off?: Offsets } = $props();
  const tone = $derived(f.info ? "info" : f.decision ? f.use : "pending");
  const t = $derived(trend(f));
</script>

<a class="row" class:flash id={anchor ? `f-${f.id}` : undefined} href="/r/p/{rid}/f/{f.id}" onclick={link}>
  <span class="st st-{tone}" title={f.use_label}>{f.info ? "ข้อมูลเพิ่มเติม" : f.decision ? f.decision.choice_label : "รอตรวจ"}</span>
  <span class="main">
    <span class="subj"><b>{f.subject}</b>{#if f.column}<span class="col"> · {f.column}</span>{/if}</span>
    {#if f.within}<span class="kind">{`ภายในฉบับ ${f.within}`}</span>{/if}
    {#if f.caveats.length}<span class="cav">⚠ ต้องให้คนยืนยัน: {f.caveats.join(" · ")}</span>{/if}
  </span>
  <span class="vals">
    {#if !NO_VALUES.has(f.topic)}
      <span><span class="va" class:gone-v={t === "gone"}>{f.a.amount_text || "—"}</span> → <span class="vb" class:added-v={t === "added"}>{f.b.amount_text || "—"}</span></span>
      {#if t === "gone" || t === "added"}<span class="delta {t}" title={TREND_SAY[t]}>{TREND_MARK[t]} {TREND_SAY[t]}</span>
      {:else if f.delta_text}<span class="delta {t}" title={TREND_SAY[t]}>{#if t}<span aria-label={TREND_SAY[t]}>{TREND_MARK[t]}</span> {/if}{t ? absDelta(f) : f.delta_text}</span>{/if}
    {/if}
    <span class="pages">{pagesOf(f, off)}</span>
  </span>
</a>

<style>
  .row { display: grid; grid-template-columns: 132px minmax(0, 1fr) auto; gap: 12px; align-items: start; padding: 10px 14px;
    border-top: 1px solid var(--line); color: inherit; text-decoration: none; transition: background .15s; }
  .row:hover, .row:focus-visible { background: #f7f8fb; }
  .row.flash { animation: flash 1.6s ease-out; }
  @keyframes flash { 0%, 30% { background: #fff3c4; } 100% { background: transparent; } }
  .st { justify-self: start; padding: 2px 10px; border-radius: 999px; font-size: .82em; font-weight: 600; line-height: 1.6;
    background: #fff; border: 1px dashed #98a2b3; color: #475467; }
  .st-usable { background: var(--ok-bg); border: 1px solid #b7dfc4; color: var(--ok); }
  .st-excluded { background: #eef0f3; border: 1px solid #d0d5dd; color: #475467; }
  .st-open { background: var(--warn-bg); border: 1px solid var(--warn-line); color: var(--warn); }
  .st-info { background: #f2f4f7; border: 1px solid transparent; color: var(--muted); font-weight: 400; }
  .main { display: flex; flex-direction: column; min-width: 0; }
  .subj { overflow-wrap: anywhere; }
  .col, .kind { color: var(--muted); font-size: .9em; }
  .cav { color: var(--warn); font-size: .88em; font-weight: 600; }
  .vals { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; text-align: right; font-size: .9em;
    font-variant-numeric: tabular-nums; }
  .va { color: var(--a); } .vb { color: var(--b); }
  .delta { border-radius: 8px; padding: 0 8px; font-weight: 600; background: #f2f4f7; }
  .delta.up, .delta.added { background: #e9f6ec; } .delta.down { background: #fdeee8; } .delta.gone { background: #f2f4f7; color: var(--muted); }
  .pages { color: var(--muted); font-size: .85em; }
  @media (max-width: 760px) {
    .row { grid-template-columns: 1fr; gap: 4px; }
    .vals { align-items: flex-start; text-align: left; }
  }
</style>
