<script lang="ts">
  // สรุปของรอบ (อ่าน/พิมพ์ได้) — ข้อค้างและข้อยกเว้นขึ้นก่อน · CSV เป็นไฟล์เก็บหลักฐาน ไม่ใช่ปลายทางเดียว (Bo #44 6459501871)
  import { link } from "../lib/router.svelte";
  import { clip, loadList, loadRun, peekList, peekRun, NO_VALUES, offsetsOf, pagesOf, trend, TREND_MARK, TREND_SAY, absDelta,
    type PFinding, type PRun } from "../lib/pair";

  let { rid }: { rid: string } = $props();
  let r = $state<PRun | null>(peekRun(rid) ?? null);
  let list = $state<PFinding[] | null>(peekList(rid) ?? null);
  let err = $state("");
  loadRun(rid).then((x) => (r = x)).catch((e) => (err = (e as Error).message));
  loadList(rid).then((x) => (list = x)).catch((e) => (err = (e as Error).message));

  const by = (u: string) => (list ?? []).filter((f) => f.use === u);
  // ลำดับ: ยังไม่บันทึก → ยังไม่ปิด → ไม่นับ → ปิดแล้ว (ชื่อหมวดตาม use_breakdown ของเซิร์ฟเวอร์)
  const SECTIONS = [
    ["pending", "ยังไม่ได้บันทึกความเห็น", "กลับไปตรวจก่อนใช้สรุปนี้"],
    ["open", "ยังไม่ปิด", "ต้องตรวจเพิ่ม หรือระบบจับคู่ผิด — ยังใช้ผลไม่ได้"],
    ["excluded", "ไม่นับ", "ผู้ตรวจระบุว่าไม่เกี่ยวข้อง"],
    ["usable", "ปิดแล้ว", "ใช้ผลได้"],
  ] as const;
  const printed = new Date().toLocaleString("th-TH", { dateStyle: "long", timeStyle: "short" });
  const when = (s: string) => s.slice(0, 16).replace("T", " ");
</script>

{#if err}
  <div class="card msg">{err} · <a href="/r/p/{rid}" onclick={link}>กลับไปภาพรวม</a></div>
{:else if !r || !list}
  <div class="card skeleton sk"></div>
{:else}
  {@const run = r.run}
  <div class="bar no-print">
    <a class="btn small ghost" href="/r/p/{rid}" onclick={link}>← ภาพรวม</a>
    <span class="grow"></span>
    <button class="btn small" onclick={() => window.print()}>พิมพ์ / บันทึกเป็น PDF</button>
  </div>

  <article class="sheet">
    <header>
      <p class="hint">สรุปรอบตรวจเทียบ · พิมพ์เมื่อ {printed}</p>
      <h1>{run.agency || "ไม่ระบุหน่วยงาน"}</h1>
      <p>{run.sides.A.label} เทียบกับ {run.sides.B.label}</p>
    </header>

    <section class="status">
      <p class="big">บันทึกแล้ว {r.counts.actionable - r.counts.pending} / {r.counts.actionable} จุด
        {#if r.counts.info}<span class="hint">{` · ข้อมูลเพิ่มเติมอีก ${r.counts.info} รายการ (ไม่ต้องบันทึกความเห็น)`}</span>{/if}</p>
      <p><b>{r.preflight.use_status_label}</b> <span class="hint">{r.preflight.use_breakdown}</span></p>
      {#if r.counts.pending === 0 && r.counts.actionable}<p class="ok">บันทึกครบแล้ว — ไม่ได้แปลว่าเอกสารถูกต้อง</p>{/if}
    </section>

    {#if run.superseded_by || r.year_warnings.length || r.stage_warnings.length}
      <section>
        <h2>ข้อยกเว้นของรอบ</h2>
        <ul>
          {#if run.superseded_by}<li>รอบนี้ถูกแทนด้วยรอบใหม่แล้ว — ใช้สรุปของรอบใหม่</li>{/if}
          {#each r.year_warnings as w, i (i)}<li>ปีงบของฉบับ {w.side}: {w.text}</li>{/each}
          {#each r.stage_warnings as w, i (i)}<li>ขั้นเอกสารของฉบับ {w.side}: {w.text}</li>{/each}
        </ul>
      </section>
    {/if}

    {#each SECTIONS as [u, title, why] (u)}
      {@const rows = by(u)}
      <section>
        <h2>{title} <span class="n">{rows.length}</span></h2>
        <p class="hint">{why}</p>
        {#if rows.length}
          <table>
            <thead><tr><th scope="col">จุดที่ต่าง</th><th scope="col">ค่า</th><th scope="col">หน้า</th><th scope="col">ความเห็น</th></tr></thead>
            <tbody>
              {#each rows as f (f.id)}
                <tr><td><b>{f.subject}</b>{#if f.column}{` · ${f.column}`}{/if}<br /><span class="hint">{f.topic_label} · {f.kind_label}</span>
                  {#if f.caveats.length}<br /><span class="cav">{`ต้องให้คนยืนยัน: ${f.caveats.join(" · ")}`}</span>{/if}</td>
                  <td class="num">{#if NO_VALUES.has(f.topic)}—{:else}<span class="amt">{clip(f.a.amount_text || "—", 40)}</span> → <span class="amt">{clip(f.b.amount_text || "—", 40)}</span>{/if}{#if f.delta_text}{@const t = trend(f)}<br /><span class="delta {t}" title={TREND_SAY[t]}>{#if t}{`${TREND_MARK[t]} `}{/if}{t ? absDelta(f) : f.delta_text}</span>{/if}</td>
                  <td>{pagesOf(f, offsetsOf(r)) || "—"}</td>
                  <td>{f.decision ? f.decision.choice_label : "—"}{#if f.decision?.note}<br /><span class="hint">{f.decision.note}</span>{/if}</td></tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </section>
    {/each}

    <section class="files">
      <h2>ไฟล์และหลักฐาน</h2>
      <ul>
        <li><b>CSV</b> — ทุกจุดพร้อมค่าและความเห็น ไว้เก็บเป็นหลักฐาน ·
          {#if r.preflight.ok}<a class="no-print" href={r.preflight.export_url}>ดาวน์โหลด</a>{:else}ดาวน์โหลดได้เมื่อ<a href="/r/p/{rid}/preflight" onclick={link}>ตรวจก่อนส่งออกไฟล์</a>ผ่านครบ{/if}</li>
        <li><b>ประวัติการบันทึก</b> — ใคร บันทึกอะไร เมื่อไร · <a href="/r/p/{rid}/audit" onclick={link}>เปิด</a></li>
      </ul>
      <p class="hint">{r.preflight.use_status_scope} · สรุปนี้ไม่ใช่การรับรองความถูกต้องของเอกสาร</p>
      <p class="hint">รอบสร้างเมื่อ {when(run.created_at)} · รหัสรอบ {run.id} · ตัวอ่าน {run.versions.pdfbook ?? "—"}</p>
    </section>
  </article>
{/if}

<style>
  .msg { padding: 16px; }
  .sk { height: 60vh; }
  .bar { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
  .grow { flex: 1; }
  .sheet { max-width: 980px; margin: 0 auto; background: #fff; border: 1px solid var(--line); border-radius: var(--radius); padding: 22px 28px; }
  header h1 { margin: 2px 0 4px; font-size: 1.5em; }
  header p { margin: 0 0 2px; }
  .status { margin: 14px 0; padding: 12px 16px; border-radius: 12px; background: #f6f8fb; }
  .status p { margin: 2px 0; }
  .big { font-size: 1.2em; font-weight: 700; }
  .ok { color: var(--ok); font-weight: 600; }
  section h2 { margin: 18px 0 4px; font-size: 1.05em; display: flex; align-items: center; gap: 8px; }
  .n { display: inline-grid; place-items: center; min-width: 26px; height: 22px; padding: 0 6px; border-radius: 999px; background: #eef0f3; font-size: .85em; }
  section > .hint { margin: 0 0 6px; }
  table { width: 100%; border-collapse: collapse; font-size: .9em; table-layout: fixed; }
  th:nth-child(1) { width: 36%; } th:nth-child(2) { width: 32%; } th:nth-child(3) { width: 10%; } th:nth-child(4) { width: 22%; }
  th, td { text-align: left; padding: 6px 8px; border-top: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; }
  td { overflow-wrap: anywhere; }
  .num { font-variant-numeric: tabular-nums; }
  /* ตัวเลขกับหน่วยไม่แยกบรรทัด (ยอดเงินแยกจาก "บาท" บนจอ 1366 — กิ๊ฟ 2 พ.ย.) · ตัดบรรทัดได้ที่ลูกศรเท่านั้น */
  .amt, .delta { white-space: nowrap; }
  .cav { color: var(--warn); font-size: .9em; }
  .files ul { margin: 4px 0; padding-left: 20px; }
  @media print {
    .no-print { display: none !important; }
    .sheet { border: 0; padding: 0; max-width: none; }
    tr { break-inside: avoid; }
  }
</style>
