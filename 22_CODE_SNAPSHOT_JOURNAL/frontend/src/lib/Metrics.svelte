<script lang="ts">
  import type { Meta, Metrics } from "./api";
  import Count from "./Count.svelte";

  let { m, meta, extrasTotal, big = false }: { m: Metrics; meta: Meta; extrasTotal: number; big?: boolean } = $props();
  const missed = $derived(m.pens.red.missed + m.pens.brown.missed + m.pens.pin.missed);
</script>

<div class="metrics" class:big>
  {#each ["red", "brown", "pin"] as const as k (k)}
    {@const c = m.pens[k]}
    <div class="card metric m-{k}">
      <span class="lbl">{k === "red" ? "จุดสำคัญ (แดง) ที่ระบบจับได้" : k === "brown" ? "จุดสังเกต (น้ำตาล)" : "ของที่หายไป (หมุด)"}</span>
      <b><Count to={c.exact} /> / {c.total}</b>
      <small>บางส่วน {c.partial} · พลาด {c.missed}{c.pending ? ` · รอยืนยัน ${c.pending}` : ""}</small>
      <span class="track"><span class="fill" style:width="{c.total ? (100 * c.exact) / c.total : 0}%"></span></span>
    </div>
  {/each}
  <div class="card metric"><span class="lbl">ระบบพลาด (ทุกปากกา)</span><b><Count to={missed} /></b>
    <small>จุดที่คุณวงแต่ระบบไม่ได้ยก</small></div>
  <div class="card metric"><span class="lbl">ระบบยกเพิ่ม</span><b><Count to={extrasTotal} /></b>
    <small>{meta.extra_verdicts.real_unnoted.split(" ")[0]} {m.extras.real_unnoted} · ไม่ใช่ความต่าง {m.extras.not_diff} ·
      ยังตัดสินไม่ได้ {m.extras.undecided}{m.extras.pending ? ` · รอดู ${m.extras.pending}` : ""}</small></div>
  <div class="card metric"><span class="lbl">ส่วนที่ระบบอ่านไม่ได้</span><b><Count to={m.unread} /></b><small>ประเด็นในส่วนนี้นับเป็นพลาด</small></div>
</div>

<style>
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
  .metric { padding: 14px; display: flex; flex-direction: column; gap: 2px; }
  .lbl { color: var(--muted); font-size: .9em; }
  b { font-size: 1.8em; line-height: 1.2; }
  .big b { font-size: 2.3em; }
  small { color: var(--muted); }
  .m-red { border-left: 5px solid var(--red); } .m-brown { border-left: 5px solid var(--brown); } .m-pin { border-left: 5px solid var(--pin); }
  .track { display: block; height: 8px; border-radius: 999px; background: #eef0f3; overflow: hidden; margin-top: 6px; }
  .fill { display: block; height: 100%; background: var(--red); transition: width .9s cubic-bezier(.22, 1, .36, 1); }
  .m-brown .fill { background: var(--brown); } .m-pin .fill { background: var(--pin); }
</style>
