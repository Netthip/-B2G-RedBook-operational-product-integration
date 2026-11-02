<script lang="ts">
  // เริ่มรอบเทียบจาก PDF ในเครื่อง — อัปโหลดสองฉบับ → เลือกหน่วยงาน → เทียบ (สัญญาส่วนที่ 4 · ไม่ดึงไฟล์จากลิงก์)
  // ตรวจชนิดไฟล์/ไฟล์เสีย/รหัสผ่าน/จำนวนหน้าที่เซิร์ฟเวอร์ · หน้าบ้านเช็กแค่นามสกุลและขนาดเพื่อบอกเร็ว · หน่วยงานที่กันไว้ไม่อยู่ในรายชื่อ
  import { go } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import { startUploaded, uploadPdf, type AB, type PUpload } from "../lib/pair";

  const MAX_MB = 80;                 // เท่ากับ REDBOOK_MAX_UPLOAD_MB ค่าเริ่มของเซิร์ฟเวอร์ — เซิร์ฟเวอร์ตัดสินจริง
  let { kind = "", onstep }: { kind?: string; onstep?: (n: number) => void } = $props();
  // ชื่อช่องตามชนิดงาน (ข้ามปี: ปีใหม่ที่ระบบยังไม่เคยเห็น เทียบกับเล่มปีก่อน เช่น พ.ร.บ. 2570)
  const SIDES = (kind === "cross"
    ? [["A", "เล่มปีก่อน", "เช่น พ.ร.บ. 2570"], ["B", "เล่มปีใหม่", "ปีที่ยังไม่เคยตรวจ"]]
    : kind === "same"
      ? [["A", "ร่าง พ.ร.บ.", "ฉบับร่าง"], ["B", "พ.ร.บ.", "ปีเดียวกับร่าง"]]
      : [["A", "ฉบับตั้งต้น", "เช่น เล่มปีก่อน หรือร่าง พ.ร.บ."], ["B", "ฉบับที่นำมาเทียบ", "เช่น เล่มปีนี้ หรือ พ.ร.บ."]]) as [AB, string, string][];

  let pid = $state("");
  let got = $state<Partial<Record<AB, PUpload>>>({});
  let busy = $state<Partial<Record<AB, string>>>({});
  let errs = $state<Partial<Record<AB, string>>>({});
  let urls = $state<Record<AB, string>>({ A: "", B: "" });
  let over = $state<AB | "">("");
  let agency = $state("");
  let q = $state("");
  let starting = $state(false);
  let secs = $state(0);

  // อัปโหลดทีละไฟล์ — ไฟล์แรกได้ project_id แล้วไฟล์ต่อไปใช้งานตรวจเดียวกัน (กันได้สองงานตรวจเมื่อเลือกพร้อมกัน)
  let queue: Promise<unknown> = Promise.resolve();
  function send(side: AB, file: File | undefined | null) {
    if (!file) return;
    errs[side] = "";
    if (!/\.pdf$/i.test(file.name)) { errs[side] = "เลือกได้เฉพาะไฟล์ PDF"; return; }
    if (file.size > MAX_MB * 1024 * 1024) { errs[side] = `ไฟล์ใหญ่เกิน ${MAX_MB} MB`; return; }
    busy[side] = file.name;
    queue = queue.then(async () => {
      try {
        const r = await uploadPdf(side, file, pid, urls[side]);
        pid = r.project_id;
        got[side] = r;
        if (agency && !choices.includes(agency)) agency = "";
      } catch (e) {
        errs[side] = (e as Error).message;
      } finally { busy[side] = ""; }
    });
  }

  // หน่วยงานที่อยู่ในสารบัญของทั้งสองไฟล์ · ไม่มีชื่อร่วมเลย = แสดงรวมพร้อมเตือน (ชื่ออาจเปลี่ยนระหว่างปี)
  // เทียบแบบโครงอักษร (ตัดช่องว่าง สระบน/ล่าง วรรณยุกต์ อักขระเสีย · ำ→า) แบบเดียวกับ pdfbook.text.skeleton — ชื่อข้ามปีสะกดต่างเล็กน้อยได้
  const key = (g: string) => g.replace(/[\s\u0E31\u0E34-\u0E3A\u0E47-\u0E4E\uFFFD]/g, "").replace(/\u0E33/g, "\u0E32");
  const common = $derived.by(() => {
    if (!got.A || !got.B) return [];
    const inB = new Set(got.B.agencies.map(key));
    return got.A.agencies.filter((g) => inB.has(key(g)));
  });
  const both = $derived(!!(got.A && got.B));
  const choices = $derived(both ? (common.length ? common : [...new Set([...got.A!.agencies, ...got.B!.agencies])]) : []);
  const shown = $derived(choices.filter((g) => !q.trim() || g.includes(q.trim())));
  const working = $derived(!!(busy.A || busy.B));

  $effect(() => { onstep?.(starting ? 3 : both ? (agency ? 3 : 2) : 1); });

  async function start() {
    if (!pid || !both || !agency || starting || working) return;
    starting = true; secs = 0;
    const t = setInterval(() => secs++, 1000);
    try {
      const r = await startUploaded(pid, agency);
      toast("เทียบเสร็จแล้ว");
      go(`/r/p/${r.rid}`);
    } catch (e) {
      toast((e as Error).message, true);
    } finally { clearInterval(t); starting = false; }
  }
</script>

<section class="card step">
  <h2><span class="n">๑</span> เลือกไฟล์ PDF ทั้งสองฉบับ</h2>
  <div class="drops">
    {#each SIDES as [s, title, eg], i (s)}
      {#if i}<span class="arr" aria-hidden="true">→</span>{/if}
      <div class="side">
        <label class="drop" class:over={over === s} class:ok={!!got[s] && !busy[s]}
               ondragover={(e) => { e.preventDefault(); over = s; }} ondragleave={() => (over = "")}
               ondrop={(e) => { e.preventDefault(); over = ""; send(s, e.dataTransfer?.files[0]); }}>
          <input type="file" accept="application/pdf,.pdf" disabled={!!busy[s] || starting}
                 onchange={(e) => { const el = e.currentTarget; send(s, el.files?.[0]); el.value = ""; }} />
          <b class="t">{title}</b>
          {#if busy[s]}
            <span class="spin" aria-hidden="true"></span><span>กำลังอัปโหลดและตรวจไฟล์…</span><small class="hint">{busy[s]}</small>
          {:else if got[s]}
            <span class="okmark" aria-hidden="true">✓</span><span class="fn">{got[s]!.file}</span>
            <small class="hint">{got[s]!.pages.toLocaleString("th-TH")} หน้า</small>
          {:else}
            <span class="plus" aria-hidden="true">＋</span><span>เลือกไฟล์ หรือลากมาวาง</span><small class="hint">{eg}</small>
          {/if}
        </label>
        {#if errs[s]}<p class="err" role="alert">{errs[s]}</p>{/if}
        <details class="src">
          <summary>ลิงก์ที่มาของไฟล์ (ถ้ามี)</summary>
          <input type="url" maxlength="1000" placeholder="วางลิงก์หน้าที่ดาวน์โหลดไฟล์มา" bind:value={urls[s]} aria-label="ลิงก์ที่มาของ{title}" />
          <small class="hint">เก็บไว้อ้างอิง ระบบไม่ดาวน์โหลด</small>
        </details>
      </div>
    {/each}
  </div>
</section>

{#if both}
  <section class="card step">
    <h2><span class="n">๒</span> เลือกหน่วยงาน</h2>
    {#if !choices.length}
      <p class="note warn">ไม่พบรายชื่อหน่วยงานจากสารบัญของไฟล์ — ไฟล์อาจไม่ใช่เล่มงบประมาณ หรือสารบัญอ่านไม่ได้</p>
    {:else}
      {#if !common.length}<p class="note warn">ไม่พบชื่อหน่วยงานที่ตรงกันในสองไฟล์ — แสดงรายชื่อรวม ตรวจให้แน่ใจว่าเลือกถูกหน่วยงาน</p>{/if}
      <input class="search" type="search" placeholder="ค้นชื่อหน่วยงาน" bind:value={q} aria-label="ค้นชื่อหน่วยงาน" />
      <div class="agencies" role="radiogroup" aria-label="หน่วยงาน">
        {#each shown as g (g)}
          <button role="radio" aria-checked={agency === g} class="ag" class:on={agency === g} onclick={() => (agency = g)}>{g}</button>
        {/each}
        {#if !shown.length}<p class="hint">ไม่พบชื่อที่ค้น</p>{/if}
      </div>
    {/if}
    <div class="go">
      <p class="sum">{#if agency}<b>{agency}</b>{` · ${got.A!.file} → ${got.B!.file}`}{:else}<span class="hint">เลือกหน่วยงาน</span>{/if}</p>
      <button class="btn" disabled={!agency || starting || working} onclick={start}>
        {starting ? `กำลังเทียบ… ${secs} วินาที` : "เทียบ →"}</button>
    </div>
  </section>
{/if}

<style>
  .step { padding: 14px 18px; margin-bottom: 12px; }
  .step h2 { display: flex; align-items: center; gap: 10px; margin: 0 0 10px; font-size: 1.1em; }
  .n { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--dark); color: #fff; font-size: .9em; }
  .drops { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: 12px; align-items: start; }
  .arr { align-self: center; font-size: 1.6em; color: var(--muted); }
  .drop { position: relative; display: flex; flex-direction: column; align-items: center; gap: 4px; text-align: center; padding: 22px 16px;
    min-height: 150px; justify-content: center; border: 2px dashed #b7bec9; border-radius: 16px; background: #fafbfc; cursor: pointer;
    transition: border-color .15s, background .15s; }
  .drop:hover, .drop.over { border-color: var(--accent); background: var(--accent-bg); }
  .drop.ok { border-style: solid; border-color: var(--ok); background: var(--ok-bg); }
  .drop input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
  .drop input:focus-visible + .t { outline: 3px solid #534ab7; outline-offset: 4px; border-radius: 4px; }
  .t { font-size: 1.05em; }
  .plus { font-size: 1.6em; line-height: 1; color: var(--muted); }
  .okmark { display: inline-grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--ok); color: #fff; }
  .fn { font-weight: 600; overflow-wrap: anywhere; }
  .spin { width: 22px; height: 22px; border-radius: 50%; border: 3px solid var(--line); border-top-color: var(--ink); animation: spin 1s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .err { margin: 6px 0 0; color: var(--danger); font-weight: 600; }
  .src { margin-top: 6px; font-size: .9em; }
  .src summary { cursor: pointer; color: #344054; }
  .src input { width: 100%; margin: 6px 0 2px; padding: 6px 10px; border-radius: 10px; border: 1px solid #cfd4dc; font: inherit; }
  .search { width: 100%; max-width: 480px; padding: 8px 12px; border-radius: 12px; border: 1px solid #cfd4dc; font: inherit; margin-bottom: 6px; }
  .agencies { display: flex; flex-direction: column; gap: 4px; max-height: 340px; overflow: auto; padding-right: 4px; }
  .ag { text-align: left; padding: 7px 12px; border-radius: 10px; border: 1px solid transparent; background: #f7f8fa; cursor: pointer; color: inherit; font: inherit; }
  .ag:hover { border-color: #cfd4dc; }
  .ag.on { border-color: var(--accent); background: var(--accent-bg); box-shadow: inset 0 0 0 1px var(--accent); }
  .go { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; margin: 14px 0 6px;
    padding-top: 12px; border-top: 1px dashed var(--line); }
  .sum { margin: 0; overflow-wrap: anywhere; }
  @media (max-width: 760px) { .drops { grid-template-columns: 1fr; } .arr { transform: rotate(90deg); justify-self: center; } }
</style>
