<script lang="ts">
  // ด่านก่อนส่งออก + ยืนยันปีงบ + คำนวณรอบใหม่ — เซิร์ฟเวอร์ตรวจด่านใหม่เองทุกครั้งที่ส่งออก หน้านี้แสดงสถานะและพาไปแก้
  import { tick } from "svelte";
  import { go, link } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import { confirmYear, loadPreflight, loadRun, peekRun, rangeFull, rerun, type AB, type PPreflight, type PRun } from "../lib/pair";

  let { rid }: { rid: string } = $props();
  const SIDES = ["A", "B"] as const;

  let pf = $state<PPreflight | null>(null);
  let r = $state<PRun | null>(peekRun(rid) ?? null);
  let err = $state("");
  let busy = $state<"" | AB | "rerun">("");
  let form = $state<Record<AB, { year: string; note: string; seen: boolean; err: string }>>({
    A: { year: "", note: "", seen: false, err: "" }, B: { year: "", note: "", seen: false, err: "" } });
  let pages = $state<Record<AB, boolean>>({ A: false, B: false });

  /** รับสถานะด่านใหม่ — รีเซ็ตฟอร์มเฉพาะฉบับที่ระบุ (ไม่ล้างสิ่งที่พิมพ์ค้างไว้ในอีกฉบับ) */
  function fill(x: PPreflight, sides: readonly AB[] = SIDES) {
    pf = x;
    for (const s of sides) {
      const y = x.years[s];
      form[s] = { year: String(y.confirmed?.year ?? y.detected ?? ""), note: y.confirmed?.note ?? "", seen: false, err: "" };
      pages[s] = y.status_state !== "ok";
    }
  }
  // มาจากปุ่ม "ยืนยันปีงบก่อน"/"ส่งออก" (#years · #export) → เลื่อนไปส่วนนั้นเมื่อข้อมูลขึ้นแล้ว
  const hash = location.hash.slice(1);
  loadPreflight(rid).then((x) => {
    fill(x);
    if (hash) tick().then(() => jump(hash));
  }).catch((e) => (err = (e as Error).message));
  loadRun(rid, 30000).then((x) => (r = x)).catch(() => {});

  async function confirm(s: AB) {
    const f = form[s];
    busy = s; f.err = "";
    try {
      fill(await confirmYear(rid, s, f.year.trim(), f.note.trim(), f.seen), [s]);
      toast(`บันทึกการยืนยันปีงบของฉบับ ${s} แล้ว`);
      loadRun(rid).then((x) => (r = x)).catch(() => {});
    } catch (e) {
      f.err = (e as Error).message;
    } finally { busy = ""; }
  }

  async function doRerun() {
    busy = "rerun";
    try {
      const x = await rerun(rid);
      toast("สร้างรอบใหม่ด้วยปีที่ยืนยันแล้ว — คำตัดสินของรอบเดิมไม่ถูกคัดลอกมา ตัดสินรอบใหม่นี้");
      go(`/r/p/${x.rid}`);
    } catch (e) {
      toast((e as Error).message, true);
      loadPreflight(rid).then((x) => fill(x)).catch(() => {});
    } finally { busy = ""; }
  }

  const label = (k: string) => r?.decisions.find((d) => d.key === k)?.label ?? "";
  const when = (s: string) => s.slice(0, 16).replace("T", " ");
  const png = (tpl: string, n: number) => tpl.replace("{n}", String(n));
  function jump(id: string) { document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }
</script>

{#if err}
  <div class="card msg">{err} · <a href="/r/p/{rid}" onclick={link}>กลับไปภาพรวม</a></div>
{:else if !pf}
  <div class="card skeleton sk"></div>
{:else}
  <div class="bar">
    <a class="btn small ghost" href="/r/p/{rid}" onclick={link}>← ภาพรวม</a>
    <h1>ตรวจก่อนส่งออกไฟล์</h1>
    {#if r}<span class="hint">{r.run.agency} · {r.run.mode_label}</span>{/if}
  </div>
  <p class="hint lead">ส่งออก CSV ได้เมื่อผ่านทุกข้อด้านล่าง</p>

  {#if r?.run.superseded_by}
    <div class="note danger" role="alert"><b>รอบนี้ถูกแทนแล้ว</b> — บันทึกเพิ่มหรือส่งออกไม่ได้
      <a class="btn small" href="/r/p/{r.run.superseded_by}" onclick={link}>ไปรอบใหม่ →</a></div>
  {/if}

  <section class="card status" class:ok={pf.ok} id="export">
    {#if pf.ok}
      <h2>✓ ผ่านครบ {pf.checks.length} ข้อ — ส่งออกผลการตรวจได้</h2>
    {:else}
      <h2>ยังส่งออกไม่ได้ — ติด {pf.failing.length} ข้อ</h2>
    {/if}
    <p class="use"><span class="chip use use-{pf.use_status}">{pf.use_status_label}</span> <span>{pf.use_breakdown}</span></p>
    {#if pf.use_reasons.length}<ul class="reasons">{#each pf.use_reasons as x, i (i)}<li>{x}</li>{/each}</ul>{/if}
    {#if label("needs_more") && label("mismatch") && label("not_relevant")}
      <details class="why"><summary>ทำไมตรวจครบแล้วยังส่งออกไม่ได้</summary><p class="hint">{pf.use_status_scope}</p><p class="hint">"ตรวจครบ" ≠ "ผ่านเงื่อนไขการใช้ผล": ข้อที่ตัดสินว่า "{label("needs_more")}" หรือ "{label("mismatch")}"
        ยังไม่ปิดความไม่แน่ใจ · ข้อ "{label("not_relevant")}" ไม่นับในผล และต้องรายงานจำนวนคู่กันเสมอ ·
        ระบบไม่เปลี่ยนคำตัดสินแทนผู้ตรวจ — ทุกแถวใน CSV มีคอลัมน์ "การใช้ผล"</p></details>
    {/if}
    {#if pf.ok && !r?.run.superseded_by}
      <div class="actions"><a class="btn" href={pf.export_url}>ดาวน์โหลด CSV</a></div>
      <p class="hint">ไฟล์มีทุกจุดพร้อมค่า หน่วย และความเห็น · ทุกครั้งที่ดาวน์โหลด ระบบจดไว้ในประวัติการบันทึก</p>
    {/if}
  </section>

  <ol class="checks">
    {#each pf.checks as c (c.key)}
      <li class="card gate" class:pass={c.ok}>
        <span class="mark" aria-hidden="true">{c.ok ? "✓" : "!"}</span>
        <div class="gate-body">
          <b>{c.label}</b><span class="sr-only"> — {c.ok ? "ผ่าน" : "ยังไม่ผ่าน"}</span>
          <p class="detail">{c.detail}</p>
          {#if c.action}
            <div class="actions">
              {#if c.action.code === "open_finding" && c.action.finding_id}
                <a class="btn small ghost" href="/r/p/{rid}/f/{c.action.finding_id}" onclick={link}>{c.action.label}</a>
              {:else if c.action.code === "open_run" && c.action.run_id}
                <a class="btn small" href="/r/p/{c.action.run_id}" onclick={link}>{c.action.label}</a>
              {:else if c.action.code === "confirm_year"}
                <button class="btn small ghost" onclick={() => jump("years")}>{c.action.label}</button>
              {:else if c.action.code === "rerun"}
                <button class="btn small" disabled={!!busy} onclick={doRerun}>
                  {busy === "rerun" ? "กำลังคำนวณรอบใหม่ด้วยปีที่ยืนยัน…" : c.action.label}</button>
              {:else}
                <a class="btn small ghost" href={c.action.href}>{c.action.label} (หน้าเดิม)</a>
              {/if}
            </div>
          {/if}
        </div>
      </li>
    {/each}
  </ol>

  {#if pf.stage_warnings.length}
    <div class="note warn"><b>คำเตือนที่ไม่บล็อกการส่งออก — ขั้นเอกสาร</b>
      <ul>{#each pf.stage_warnings as w, i (i)}<li>ฉบับ {w.side}: {w.text}</li>{/each}</ul></div>
  {/if}

  <section class="years" id="years" aria-labelledby="h-years">
    <h2 id="h-years">ปีงบของแต่ละฉบับ</h2>
    <p class="hint">ปีงบเป็นตัวตั้งว่าระบบเทียบแบบปีเดียวกันหรือข้ามปี และใช้จัดคอลัมน์ปีของตาราง — ถ้าอ่านผิด
      การปรับลดจริงอาจกลายเป็น "ข้อมูลเพิ่มเติม" ที่ไม่มีใครตัดสิน · การยืนยันไม่แก้ผลเทียบที่บันทึกไว้ ถ้าปีที่ยืนยันต่างจาก
      ปีที่ใช้คำนวณ ระบบให้สร้างรอบใหม่ที่คำนวณด้วยปีที่ยืนยัน และบล็อกรอบนี้ · เปลี่ยนปีที่ยืนยันไว้
      หรือยืนยันปีต่างจากที่ระบบอ่านได้ ต้องระบุเหตุผล</p>
    <div class="ycards">
      {#each SIDES as s (s)}
        {@const y = pf.years[s]}
        {@const sd = r?.run.sides[s]}
        {@const shots = sd ? [...new Set([1, sd.first])] : []}
        <section class="card ycard side-{s.toLowerCase()}" aria-labelledby="y-{s}">
          <h3 id="y-{s}"><span class="tag tag-{s.toLowerCase()}">{s}</span> {sd?.label ?? `ฉบับ ${s}`}</h3>
          <dl class="kv">
            {#if sd}<dt>ไฟล์</dt><dd>{sd.file} · {rangeFull(sd.first, sd.last, sd.printed_offset)}</dd>{/if}
            <dt>ระบบอ่านได้</dt><dd>{y.detected ? `ปี ${y.detected}` : "—"}
              <span class="chip st st-{y.status_state ?? "warn"}">{y.status_label ?? y.status}</span></dd>
            <dt>ที่มา</dt><dd>{y.origin_label || "—"}</dd>
            {#if !y.evidence.length}<dt>หลักฐานที่พบ</dt><dd class="mono">{y.candidates.join(" · ") || "—"}</dd>{/if}
            <dt>ปีที่ใช้คำนวณผลนี้</dt><dd>{y.used ?? "ไม่มีปี"}</dd>
            {#if y.confirmed}<dt>ผู้ตรวจยืนยัน</dt>
              <dd>ปี {y.confirmed.year} · {when(y.confirmed.confirmed_at)}{y.confirmed.note ? ` · ${y.confirmed.note}` : ""}</dd>{/if}
          </dl>
          {#if y.evidence.length}
            <p class="evi-h">หลักฐานที่พบ {y.evidence.length} บรรทัด</p>
            <div class="tbl"><table>
              <thead><tr><th scope="col">หน้า</th><th scope="col">ข้อความในบรรทัด</th><th scope="col">ชนิด</th><th scope="col">ที่มา</th></tr></thead>
              <tbody>{#each y.evidence as e, i (i)}<tr><td class="num">{e.page}</td><td>{e.line}</td>
                <td>{e.kind_label ?? e.kind}{#if e.cue}<span class="hint">{` (คำบอก: ${e.cue})`}</span>{/if}</td>
                <td>{e.direct ? "อ่านตรงจากข้อความ" : "อนุมาน"}{#if !e.bbox}{" · ไม่พบกรอบบนหน้า"}{/if}</td></tr>{/each}</tbody>
            </table></div>
          {/if}
          {#if shots.length}
            <details class="shots" bind:open={pages[s]}>
              <summary>ภาพหน้าที่ใช้ดูปีงบ</summary>
              <div class="thumbs">
                {#each shots as n (n)}
                  <figure><a href={png(y.page_png, n)} target="_blank" rel="noopener">
                    <img loading="lazy" src={png(y.page_png, n)} alt="ฉบับ {s} หน้า {n}" /></a>
                    <figcaption>หน้า {n} {n === sd?.first ? "(หน้าแรกของหน่วยงาน)" : "(หน้าต้นไฟล์)"}</figcaption></figure>
                {/each}
              </div>
            </details>
          {/if}
          {#if y.confirmable}
            <form class="yform" onsubmit={(e) => { e.preventDefault(); confirm(s); }}>
              <label>ปีงบตามหน้าเอกสาร (พ.ศ.)
                <input inputmode="numeric" maxlength="4" size="6" bind:value={form[s].year} required /></label>
              <label>หมายเหตุ <span class="hint">(หน้า/ข้อความที่ใช้ยืนยัน · ต้องระบุเมื่อเปลี่ยนปีหรือต่างจากที่ระบบอ่าน)</span>
                <input maxlength="300" bind:value={form[s].note} /></label>
              <label class="seen"><input type="checkbox" bind:checked={form[s].seen} /> ดูปีงบจากภาพหน้าเอกสารแล้ว</label>
              {#if form[s].err}<p class="err" role="alert">{form[s].err}</p>{/if}
              <div class="actions"><button class="btn small" type="submit" disabled={!!busy || !form[s].seen}>
                {busy === s ? "กำลังบันทึก…" : y.confirmed ? "แก้การยืนยัน" : "ยืนยันปีงบ"}</button></div>
            </form>
          {/if}
        </section>
      {/each}
    </div>
  </section>

  <p class="scope-foot">ทุกการยืนยันปีและทุกคำตัดสินบันทึกใน Audit ของรอบนี้{#if r}{` · ${r.run.profile_status_label}`}{/if}</p>
{/if}

<style>
  .why summary { cursor: pointer; color: var(--muted); font-size: .92em; }
  .msg { padding: 16px; }
  .sk { height: 60vh; }
  .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-bottom: 4px; }
  .bar h1 { margin: 0; font-size: 1.5em; }
  .lead { margin: 0 0 12px; }
  .status { padding: 14px 18px; margin-bottom: 12px; border-left: 6px solid var(--danger); }
  .status.ok { border-left-color: var(--ok); }
  .status h2 { margin: 0 0 6px; font-size: 1.15em; }
  .status p { margin: 6px 0; }
  .use { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .chip.use { font-weight: 600; }
  .use-validated { background: var(--ok-bg); color: var(--ok); }
  .use-review_complete { background: var(--warn-bg); color: var(--warn); }
  .use-blocked { background: var(--danger-bg); color: var(--danger); }
  .reasons { margin: 4px 0; padding-left: 20px; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 2px; }

  .checks { list-style: none; margin: 0 0 14px; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  .gate { display: grid; grid-template-columns: 34px minmax(0, 1fr); gap: 10px; padding: 12px 14px; }
  .mark { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; font-weight: 700;
    background: var(--danger-bg); color: var(--danger); }
  .gate.pass .mark { background: var(--ok-bg); color: var(--ok); }
  .detail { margin: 2px 0 0; color: #344054; font-size: .94em; }

  .years, .status { scroll-margin-top: 72px; }
  .years h2 { font-size: 1.15em; margin: 18px 0 4px; }
  .ycards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 8px; }
  .ycard { padding: 12px 16px; min-width: 0; }
  .ycard h3 { display: flex; align-items: center; gap: 8px; font-size: 1em; margin: 0 0 8px; }
  .side-a { border-top: 4px solid var(--a); } .side-b { border-top: 4px solid var(--b); }
  .st-ok { background: var(--ok-bg); color: var(--ok); }
  .st-warn { background: var(--warn-bg); color: var(--warn); }
  .st-fail { background: var(--danger-bg); color: var(--danger); }
  .tbl { overflow-x: auto; }
  table { border-collapse: collapse; font-size: .88em; width: 100%; }
  th, td { text-align: left; padding: 4px 8px; border-top: 1px solid var(--line); vertical-align: top; }
  th { color: var(--muted); font-weight: 600; white-space: nowrap; }
  td.num { white-space: nowrap; }
  .evi-h { margin: 10px 0 4px; color: var(--muted); font-size: .92em; }
  .shots { margin-top: 10px; }
  .shots summary { cursor: pointer; }
  .thumbs { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
  .thumbs figure { margin: 0; width: calc(50% - 5px); min-width: 180px; }
  .thumbs img { display: block; width: 100%; height: auto; border: 1px solid var(--line); border-radius: 10px; }
  .thumbs figcaption { color: var(--muted); font-size: .85em; }
  .yform { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line); }
  .yform label { display: flex; flex-direction: column; gap: 4px; font-size: .92em; }
  .yform label.seen { flex-direction: row; align-items: center; gap: 8px; }
  .yform input:not([type]) , .yform input[inputmode] { padding: 6px 10px; border-radius: 10px; border: 1px solid #cfd4dc; font: inherit; }
  .err { margin: 0; color: var(--danger); font-weight: 600; }
  .scope-foot { color: var(--muted); font-size: .88em; margin: 14px 2px; }
  @media (max-width: 900px) { .ycards { grid-template-columns: 1fr; } }
</style>
