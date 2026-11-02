<script lang="ts">
  // แดชบอร์ด — ด้าน A กับด้าน B แยกกัน ไม่มีคะแนนรวม · ตัวตั้ง/ตัวหารเสมอ · ร้อยละเฉพาะตัวหาร ≥ 10
  import { get, type A1, type AnyResult, type Meta, type Result } from "../lib/api";
  import { link } from "../lib/router.svelte";
  import Metrics from "../lib/Metrics.svelte";

  let { sid }: { sid: string } = $props();
  // svelte-ignore state_referenced_locally
  const SID = sid;
  let res = $state<AnyResult | null>(null);
  let meta = $state<Meta | null>(null);
  let err = $state("");
  Promise.all([get<AnyResult>(`/api/trial/s/${SID}/result`), get<Meta>("/api/trial/meta")])
    .then(([a, b]) => { res = a; meta = b; }).catch((e) => (err = e.message));

  const r = $derived(res && !res.legacy ? (res as Result) : null);
  const rows = $derived.by(() => {
    if (!r) return [] as [string, A1][];
    const a = r.metrics.A1;
    return [["ทุกประเด็นในส่วนที่ตรวจครบ", a], ["เฉพาะต้นเหตุ (ต)", a.by_cause.t], ["ผลที่ตามมา (ล)", a.by_cause.l],
            ["ระดับแดง", a.by_level.red], ["ระดับน้ำตาล", a.by_level.brown],
            ...Object.entries(a.by_topic).map(([k, v]) => [`หัวข้อ ${k}`, v])] as [string, A1][];
  });
</script>

{#if err}
  <div class="card msg">{err}</div>
{:else if !res || !meta}
  <div class="card skeleton sk"></div>
{:else if res.legacy}
  <div class="card msg">รอบกติกา 0.1 — ไม่มีแดชบอร์ดตามฉบับ 0.2 · <a href="/r/s/{SID}/result" onclick={link}>ดูผลของรอบนี้ (อ่านได้อย่างเดียว)</a></div>
{:else if r}
  {@const st = r.status}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>แดชบอร์ด</b> · {r.session.book.title} · {r.session.book.agency}</div>
    {#if r.complete}<span class="chip ok">จับคู่และจัดกลุ่มครบ</span>{:else}<a class="chip" href="/r/s/{SID}/result" onclick={link}>ยังไม่ครบ — ไปทำต่อ</a>{/if}
    <span class="chip">การรัน: {meta.status_text.run[st.run]}</span>
    <span class="chip">ผู้ตรวจ: {meta.status_text.reviewer[st.reviewer]}</span>
  </div>
  {#if st.excluded_main}<div class="card note">ไม่นับในผลหลักของด้าน A: {st.exclusions.map((x) => meta!.status_text.exclusions[x]).join(" · ")} (รายงานแยกเชิงพรรณนา)</div>{/if}
  {#if st.flags.length}<p class="flags">{#each st.flags as f (f)}<span class="chip">{meta.status_text.flags[f]}</span>{/each}</p>{/if}

  <h2>ด้าน A — ความถูกต้องและความครบถ้วนในการหาจุดต่าง</h2>
  <p class="hint">อัตราการพบเทียบรายการอ้างอิงของผู้ตรวจ ภายในหัวข้อและส่วนของเล่มที่ผู้ตรวจประกาศว่าตรวจครบ</p>
  <Metrics m={r.metrics} {meta} big />
  {#if Object.values(r.metrics.A1.post_result).some(Boolean)}
    {@const pr = r.metrics.A1.post_result}
    <div class="card note">ร1 จัดใหม่หลังเห็นผล (ตัวประเด็นยังมาจากรายการที่ล็อก จึงอยู่ในผลรวมหลัก): ส่วนของเล่ม {pr.part} · ต/ล {pr.cause}
      (ไม่อยู่ในแถวต้นเหตุ/ผลที่ตามมา) · ระดับ {pr.level} (ไม่อยู่ในแถวแดง/น้ำตาล) · ขอบเขตตามส่วนที่ไม่ได้จัดใหม่: แบบเข้ม
      {r.metrics.A1.scope_locked_only.strict.text} · รวมบางส่วน {r.metrics.A1.scope_locked_only.with_partial.text}</div>
  {/if}
  <table>
    <caption>แยกกลุ่ม (สูตรเดียวกัน)</caption>
    <thead><tr><th scope="col">กลุ่ม</th><th scope="col">ประเด็น (N0)</th><th scope="col">พบตรง</th><th scope="col">บางส่วน</th>
      <th scope="col">พลาด</th><th scope="col">ตัดสินไม่ได้</th><th scope="col">แบบเข้ม</th><th scope="col">รวมบางส่วน</th></tr></thead>
    <tbody>
      {#each rows as [label, c] (label)}
        <tr><th scope="row">{label}</th><td>{c.issues}</td><td>{c.exact}</td><td>{c.partial}</td><td>{c.missed}</td>
          <td>{c.undecidable}</td><td>{c.strict.text}</td><td>{c.with_partial.text}</td></tr>
      {/each}
    </tbody>
  </table>
  <p class="hint">พลาดตามรหัสเหตุ: {Object.entries(meta.miss_reasons).map(([k, l]) => `${l.split(" ")[0]} ${r!.metrics.A1.missed_reasons[k] ?? 0}`).join(" · ")} ·
    พบบางส่วนตามรหัสเหตุ: {Object.entries(meta.partial_reasons).map(([k, l]) => `${l.split(" ")[0]} ${r!.metrics.A1.partial_reasons[k] ?? 0}`).join(" · ")} ·
    จับคู่ผ่าน{meta.finding_levels.info} {r.metrics.A1.matched_level.info} · ประเด็นนอกส่วนที่ตรวจครบ {r.metrics.A1.out_of_scope.issues}</p>
  <p class="hint">ความครอบคลุม: ตรวจครบ {r.metrics.A4.parts.full} ส่วน · บางส่วน {r.metrics.A4.parts.partial} · ไม่ได้ตรวจ {r.metrics.A4.parts.none} ·
    หน้าไม่มีชั้นข้อความ {r.session.labels.prev} {r.metrics.A4.unread_pages.prev.length} · {r.session.labels.cur} {r.metrics.A4.unread_pages.cur.length} ·
    สกัดไม่ได้ {r.metrics.A4.read_problems.unparsed ?? 0} · ไม่พบหัวข้อ (ต้องตรวจว่าหายจริงหรือสกัดตก) {r.metrics.A4.read_problems.not_found ?? 0} ·
    พลาดเพราะอ่าน/สกัดไม่สำเร็จ (พ1) {r.metrics.A4.missed_unread} · ต้องตรวจนอกส่วนที่ตรวจครบ {r.metrics.A4.must_outside}</p>

  <h2>ด้าน B — ประโยชน์ต่อผู้ใช้ <span class="hint">(รายงานแยกจากด้าน A · ไม่มีคะแนนรวม)</span></h2>
  <p>ฐานการวินิจฉัยรายข้อ {r.metrics.B1_basis.total} ข้อ — {Object.entries(meta.basis).map(([k, l]) => `${l} ${r!.metrics.B1_basis[k] ?? 0}`).join(" · ")} ·
    แบบสอบถาม: {Object.keys(r.answers).length ? "ตอบแล้ว" : "ยังไม่ได้ตอบ"}{#if r.session.use_done}{" · "}<a href="/r/s/{SID}/survey" onclick={link}>{Object.keys(r.answers).length ? "แก้คำตอบ" : "ไปตอบ"}</a>{/if}</p>

  <section class="card how">
    <h2>อ่านผลนี้อย่างไร</h2>
    <ul>
      <li>เป็นผลของเล่มนี้ ผู้ตรวจหนึ่งคน ระบบรุ่น {r.versions.pdfbook} เท่านั้น ภายในหัวข้อและส่วนของเล่มที่ประกาศว่าตรวจครบ —
        ไม่ใช้กับเอกสารหรือหน่วยงานอื่น และไม่ใช่ความแม่นยำของระบบ</li>
      <li>"พบ" นับเมื่อท่านยืนยันเอง · ข้อเสนอที่ยังไม่ยืนยันไม่นับ · พบบางส่วนนับแยก ไม่นับเป็นครึ่ง</li>
      <li>{meta.finding_levels.info}ที่ไม่ได้จับคู่นับจำนวนเท่านั้น ไม่นับเป็นแจ้งเกิน · ระบบพบเพิ่มที่ท่านยืนยัน (ส1) รายงานแยก ไม่เพิ่มเข้าตัวหาร</li>
      <li>ผลนี้ไม่ได้บอกว่าเอกสารถูกต้อง และไม่ได้วัดเวลาที่ใช้</li>
    </ul>
    <div class="act"><a class="btn" href="/trial/s/{SID}/summary.json">ดาวน์โหลดสรุป (เฉพาะจำนวน)</a></div>
    <p class="hint">ไฟล์สรุปมีเฉพาะจำนวน ใบประกาศ (จำนวน) รุ่นระบบ แฮชของเล่ม สถานะ และคำตอบแบบสอบถาม — ไม่มีตำแหน่ง หมายเหตุ
      เลขข้อในรายการของท่าน หรือข้อความเหตุผล · ทุกครั้งที่ดาวน์โหลด ระบบบันทึกแฮชของไฟล์ไว้</p>
  </section>
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .title { flex: 1; }
  .msg { padding: 16px; } .sk { height: 50vh; }
  .note { padding: 10px 14px; background: #fff8e6; border-color: #f1d58a; }
  .flags { display: flex; gap: 6px; flex-wrap: wrap; }
  h2 { font-size: 1.15em; margin: 20px 0 6px; }
  table { border-collapse: collapse; width: 100%; margin: 12px 0; background: #fff; }
  caption { text-align: left; font-weight: 600; padding: 4px 0; }
  th, td { border: 1px solid var(--line); padding: 4px 8px; text-align: center; }
  th[scope=row] { text-align: left; }
  .how { padding: 6px 22px 14px; margin-top: 18px; }
  .act { display: flex; gap: 10px; flex-wrap: wrap; }
  a.chip { text-decoration: none; color: inherit; }
</style>
