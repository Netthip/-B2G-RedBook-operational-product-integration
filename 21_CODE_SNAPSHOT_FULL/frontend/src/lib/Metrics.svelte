<script lang="ts">
  // ตัวนับตามวิธีวัดผลฉบับ 0.2 — แสดงตัวตั้ง/ตัวหารเสมอ (ร้อยละเฉพาะตัวหาร ≥ 10 ตามที่เซิร์ฟเวอร์คำนวณ)
  import type { Meta, Metrics } from "./api";
  import Count from "./Count.svelte";

  let { m, meta, big = false }: { m: Metrics; meta: Meta; big?: boolean } = $props();
  const a1 = $derived(m.A1);
  const led = $derived(m.A3);
  const fill = $derived(a1.N ? (100 * a1.exact) / a1.N : 0);
</script>

{#if m.scope.pair_kind === "cross_year"}
  {@const sc = m.scope}
  <div class="card note xyear">
    <b>คู่ข้ามปี — {sc.label}</b> (หัวข้อ {meta.xyear.topics.join(" ")}) · ข้อสังเกตที่ไม่ใช่เชิงโครงสร้าง {m.findings.descriptive} ข้อ
    ไม่ต้องจับคู่หรือจัดกลุ่ม ไม่นับใน F — นับจำนวนแยกตามชนิดเท่านั้น{Object.keys(sc.descriptive_by_kind).length ? ": " : ""}
    {Object.entries(sc.descriptive_by_kind).map(([k, n]) => `${meta.kind_labels[k] ?? k} ${n}`).join(" · ")}
    <span class="hint">· กติกา {sc.rule}</span>
  </div>
{/if}
{#if m.v03}
  {@const v = m.v03}
  <div class="metrics v03" class:big>
    <div class="card metric m-red">
      <span class="lbl">H1 อัตราการพบหลัก (พบตรง ÷ N₀)</span><b>{v.issues ? v.issues.H1.text : `ยังตัดสินไม่ครบ ${v.pending.issues}`}</b>
      {#if v.issues}<small>ผลเสริม พบตรง ÷ N {v.issues.supplement.text} · รวมพบบางส่วน ÷ N₀ {v.issues.incl_partial.text} · ตัดสินไม่ได้ {v.issues.undecidable}</small>{/if}
    </div>
    <div class="card metric">
      <span class="lbl">H2 ตำแหน่งถูกทุกฝั่ง ในประเด็นที่พบและตัดสินตำแหน่งได้</span>
      <b>{v.location ? v.location.H2.text : `ยังไม่ครบ ${v.pending.location}`}</b>
      {#if v.location}<small>P {v.location.P} · ตัดสินไม่ได้ {v.location.undecidable} · ถูกทุกฝั่ง ÷ P {v.location.all_over_P.text}</small>{/if}
    </div>
    <div class="card metric">
      <span class="lbl">A3-อ ความตรงของสิ่งที่อ่านได้ · A3-ข ความถูกของข้อสรุป</span>
      <b>{v.obs ? `${v.obs.A3_fidelity.text} · ${v.obs.A3_assertion.text}` : `ยังไม่ครบ ${v.pending.obs}`}</b>
      {#if v.obs}<small>ตัดสินไม่ได้ A3-อ {v.obs.fidelity.undecidable} · A3-ข {v.obs.assertion.undecidable} ·
        อ่านตรงครบแต่ข้อสรุปไม่ถูก {v.obs.read_ok_assertion_wrong} · แจ้งเกิน ส3 ÷ (F − ส4) {v.obs.overflag.text} (ไม่ใช่ precision)</small>{/if}
    </div>
  </div>
{/if}
<div class="metrics" class:big>
  <div class="card metric m-red">
    <span class="lbl">อัตราการพบแบบเข้ม (พบตรง ÷ N)</span>
    <b>{a1.strict.text}</b>
    <small>N0 = {a1.N0} ที่ล็อกในขอบเขต · N = {a1.N} (ไม่รวมตัดสินไม่ได้){a1.pending ? ` · ยังไม่ครบ ${a1.pending}` : ""}</small>
    <span class="track"><span class="fill" style:width="{fill}%"></span></span>
  </div>
  <div class="card metric">
    <span class="lbl">รวมพบบางส่วน</span><b>{a1.with_partial.text}</b>
    <small>พบตรง {a1.exact} · บางส่วน {a1.partial} · พลาด {a1.missed} · ตัดสินไม่ได้ {a1.undecidable}</small>
  </div>
  <div class="card metric">
    <span class="lbl">ข้อสังเกตต้องตรวจในส่วนที่ตรวจครบ (F){m.scope.pair_kind === "cross_year" ? ` — ${meta.xyear.label}` : ""}</span><b><Count to={led.F} /></b>
    <small>จับคู่ {led.matched} · ส1 {led.s1} · ส2 {led.s2} · ส3 {led.s3} · ส4 {led.s4}{led.pending ? ` · รอจัด ${led.pending}` : ""}</small>
  </div>
  <div class="card metric" class:ok={led.closed}>
    <span class="lbl">บัญชี F = จ + ส1 + ส2 + ส3 + ส4</span><b>{led.closed ? "ปิดแล้ว" : "ยังไม่ปิด"}</b>
    <small>นอกส่วนที่ตรวจครบ {led.outside} · {meta.finding_levels.info} {m.findings.info} · {meta.finding_levels.unread} {m.findings.unread}</small>
  </div>
  {#if big}
    <div class="card metric">
      <span class="lbl">หลักฐานชี้ตำแหน่งถูกทุกฉบับ (A2)</span><b>{m.A2.rate.text}</b>
      <small>ถูกบางฉบับ {m.A2.some} · ไม่ถูก {m.A2.none}</small>
    </div>
    <div class="card metric">
      <span class="lbl">สัดส่วนแจ้งเกิน ส3 ÷ (F − ส4)</span><b>{led.false_alarm.text}</b>
      <small>{Object.entries(meta.s3_reasons).map(([k, l]) => `${l} ${led.s3_reasons[k] ?? 0}`).join(" · ")}</small>
    </div>
    <div class="card metric">
      <span class="lbl">บัญชีข้อสังเกตต้องตรวจ (จำนวน)</span><b>จ {led.matched} · ส1 {led.s1} · ส2 {led.s2}</b>
      <small>สัดส่วน "ความต่างจริง" ระงับไว้จนกว่าจะนิยามแยกความถูกของข้อสังเกตจากการจับคู่ — จ รวมข้อที่จับคู่แบบบางส่วน
        จึงยังไม่ใช่จำนวนข้อสังเกตที่ถูก · ส1 ไม่เพิ่มเข้า N</small>
    </div>
    <div class="card metric">
      <span class="lbl">ฐานการวินิจฉัยรายข้อ (ด้าน B)</span><b><Count to={m.B1_basis.total} /> ข้อ</b>
      <small>{Object.entries(meta.basis).map(([k, l]) => `${l} ${m.B1_basis[k] ?? 0}`).join(" · ")}</small>
    </div>
  {/if}
</div>

<style>
  .metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }
  .metric { padding: 14px; display: flex; flex-direction: column; gap: 2px; }
  .metric.ok { border-color: #b9e0c4; }
  .lbl { color: var(--muted); font-size: .9em; }
  b { font-size: 1.5em; line-height: 1.25; }
  .big b { font-size: 1.8em; }
  small { color: var(--muted); }
  .m-red { border-left: 5px solid var(--red); }
  .track { display: block; height: 8px; border-radius: 999px; background: #eef0f3; overflow: hidden; margin-top: 6px; }
  .fill { display: block; height: 100%; background: var(--red); transition: width .9s cubic-bezier(.22, 1, .36, 1); }
</style>
