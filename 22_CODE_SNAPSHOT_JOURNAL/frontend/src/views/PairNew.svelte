<script lang="ts">
  // เริ่มรอบเทียบจากชั้นเล่ม — เลือกเล่ม A → หน่วยงาน + เล่ม B → ระบบแนบเล่ม หาหน้าของหน่วยงานจากสารบัญ แล้วเทียบ
  // ระบบอ่านเฉพาะสารบัญต้นเล่ม แถบเลขหน้า และหน้าของหน่วยงานที่เลือก · หน่วยงานที่กันไว้ไม่อยู่ในรายชื่อ (เซิร์ฟเวอร์กันเอง)
  // อัปโหลด PDF จากเครื่องเป็นอีกทางหนึ่ง (?src=upload) — แยกไว้ใน PairUpload
  import { go, link, nav } from "../lib/router.svelte";
  import PairUpload from "./PairUpload.svelte";
  let { kind = "" }: { kind?: string } = $props();
  // ข้ามปี: เล่ม พ.ร.บ. ปีก่อน → ปีใหม่ (ปีใหม่มักยังไม่อยู่บนชั้น ⇒ เริ่มที่อัปโหลด) · ปีเดียวกัน: ร่าง พ.ร.บ. → พ.ร.บ. ปีเดียวกัน
  const TITLE: Record<string, string> = { cross: "ตรวจเล่มงบประมาณข้ามปี", same: "ตรวจเล่มงบประมาณในปีเดียวกัน" };
  import { toast } from "../lib/notify.svelte";
  import { loadShelf, startRun, type PShelf, type PVolume } from "../lib/pair";
  import { get } from "../lib/api";
  import { tick } from "svelte";

  let mode = $state<"shelf" | "upload">(nav.query.get("src") === "upload" || (kind === "cross" && nav.query.get("src") !== "shelf") ? "upload" : "shelf");
  $effect(() => {
    const p = new URLSearchParams();
    if (kind) p.set("kind", kind);
    p.set("src", mode);
    history.replaceState(null, "", `/r/p/new?${p}`);
  });
  let shelf = $state<PShelf | null>(null);
  let err = $state("");
  let a = $state("");
  let pick = $state<PShelf | null>(null);
  let agency = $state("");
  let q = $state("");
  let b = $state("");
  let busy = $state(false);
  let secs = $state(0);

  loadShelf().then((x) => (shelf = x)).catch((e) => (err = (e as Error).message));

  const byYear = $derived.by(() => {
    const m = new Map<number, PVolume[]>();
    for (const v of shelf?.volumes ?? []) {
      if (kind === "same" && v.stage !== "draft") continue;     // ปีเดียวกัน: ฉบับตั้งต้น = ร่าง พ.ร.บ.
      if (kind === "cross" && v.stage === "draft") continue;    // ข้ามปี: เทียบเล่ม พ.ร.บ.
      m.set(v.fiscal_year, [...(m.get(v.fiscal_year) ?? []), v]);
    }
    return [...m.entries()].sort((x, y) => y[0] - x[0]);
  });
  // คณะทำงาน 29 ต.ค.: บอกว่าในระบบมีกี่เล่ม — ไม่ให้คนตรวจคิดว่าระบบมีแค่กระทรวงที่เห็น · ไม่เจอ → ไฟล์ในเครื่อง
  const nVol = $derived(byYear.reduce((n, [, vs]) => n + vs.length, 0));
  const vol = (k: string) => shelf?.volumes.find((v) => v.key === k);
  // ชื่อเล่มบนปุ่ม: ตัดวงเล็บขั้นเอกสารท้ายชื่อที่ซ้ำกับหัวข้อ (คณะทำงาน UI 29 ต.ค.)
  const nice = (k: string) => (vol(k)?.title ?? k).replace(/\s*\((ร่าง )?พ\.ร\.บ\.\)\s*$/, "");
  // คนตรวจรู้ชื่อหน่วยงานของตัวเอง แต่ไม่รู้ว่าอยู่เล่มไหน ⇒ โหลดรายชื่อหน่วยงานของทุกเล่มที่เลือกได้ (สารบัญ ~0.1 วิ/เล่ม)
  // แล้วให้ค้นชื่อข้ามทุกเล่ม หรือไล่ดูตามกระทรวง (ชื่อกระทรวงจากคลังเล่ม) · หน่วยงานที่กันไว้เซิร์ฟเวอร์ไม่ส่งมาอยู่แล้ว
  let ags = $state<Record<string, string[]>>({});
  $effect(() => {
    for (const [, vs] of byYear) for (const v of vs) {
      if (v.key in ags) continue;
      ags[v.key] = [];
      loadShelf(v.key).then((x) => (ags[v.key] = x.agencies)).catch(() => {});
    }
  });
  let heads = $state<Record<string, string>>({});
  const volNo = (k: string) => k.match(/เล่มที่\s*(\d+)/)?.[1] ?? "";
  get<{ books: { fiscal_year: number; stage: string; type_group: string; kicker: string; headline: string }[] }>("/api/books")
    .then((c) => { for (const x of c.books) if (x.type_group === "by_ministry") heads[`${x.fiscal_year}|${x.stage}|${volNo(x.kicker)}`] ??= x.headline; })
    .catch(() => {});
  const head = (v: PVolume) => heads[`${v.fiscal_year}|${v.stage === "draft" ? "draft" : "act"}|${v.volume_no}`] ?? "";
  const flat = (t: string) => t.replace(/\s+/g, "");
  const hits = $derived.by(() => {
    const w = flat(q.trim());
    if (!w) return [];
    return byYear.flatMap(([, vs]) => vs.flatMap((v) => (ags[v.key] ?? []).filter((g) => flat(g).includes(w)).map((g) => [v, g] as const)));
  });

  async function pickAgency(k: string, g: string) {
    if (a !== k || !pick) await chooseA(k);
    agency = g; q = "";
    await tick();
    document.getElementById("step2")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  // ฉบับที่นำมาเทียบที่เข้ากับชนิดงาน — ปีเดียวกัน: พ.ร.บ. ปีเดียวกัน · ข้ามปี: ปีที่ใหม่กว่า
  function fitB(keys: string[]) {
    const av = vol(a);
    return keys.filter((k) => {
      const v = vol(k);
      if (!v || !av || !kind) return true;
      return kind === "same" ? v.stage !== "draft" && v.fiscal_year === av.fiscal_year : v.stage !== "draft" && v.fiscal_year > av.fiscal_year;
    });
  }

  async function chooseA(k: string) {
    a = k; pick = null; agency = ""; b = ""; q = "";
    try {
      pick = await loadShelf(k);
      b = fitB(pick.suggest.map((s) => s.key))[0] ?? fitB(pick.others)[0] ?? "";
    } catch (e) { toast((e as Error).message, true); }
  }

  // ขั้นปัจจุบันของแถบ 1-2-3 (อัปโหลดรายงานขั้นของตัวเองผ่าน onstep)
  let upStep = $state(1);
  const step = $derived(mode === "upload" ? upStep : busy ? 3 : a && agency ? (b ? 3 : 2) : 1);
  const STEPS = $derived(mode === "upload" ? ["เลือกไฟล์", "เลือกหน่วยงาน", "เทียบ"] : ["เลือกหน่วยงาน", "เลือกเล่มที่จะเทียบ", "เทียบ"]);

  async function start() {
    if (!a || !b || !agency || busy) return;
    busy = true; secs = 0;
    const t = setInterval(() => secs++, 1000);
    try {
      const r = await startRun(a, b, agency);
      toast("เทียบเสร็จแล้ว");
      go(`/r/p/${r.rid}`);
    } catch (e) {
      toast((e as Error).message, true);
    } finally { clearInterval(t); busy = false; }
  }
</script>

<div class="bar">
  <a class="btn small ghost" href="/r/lib" onclick={link}>← กลับ</a>
  <h1>{TITLE[kind] ?? "เริ่มรอบเทียบใหม่"}</h1>
</div>
<ol class="stepper" aria-label="ขั้นตอน">
  {#each STEPS as t, i (t)}
    <li class:on={step === i + 1} class:done={step > i + 1}><span>{step > i + 1 ? "✓" : i + 1}</span>{t}</li>
  {/each}
</ol>
<div class="modes" role="tablist" aria-label="ที่มาของเอกสาร">
  <button role="tab" aria-selected={mode === "shelf"} class:on={mode === "shelf"} onclick={() => (mode = "shelf")}>เล่มที่มีในระบบ</button>
  <button role="tab" aria-selected={mode === "upload"} class:on={mode === "upload"} onclick={() => (mode = "upload")}>ไฟล์ในเครื่อง</button>
</div>

{#if mode === "upload"}
  <PairUpload {kind} onstep={(n: number) => (upStep = n)} />
{:else if err}
  <div class="card msg">{err}</div>
{:else if !shelf}
  <div class="card skeleton sk"></div>
{:else if !shelf.volumes.length}
  <div class="note warn"><b>ยังไม่มีเล่มบนชั้นเล่มในเครื่องนี้</b> — ระบบไม่ออกอินเทอร์เน็ต เล่มต้องดาวน์โหลดไว้ก่อนด้วยคำสั่ง
    <code>python scripts/shelf_add.py --book &lt;รหัสเล่มในคลังเล่ม&gt;</code> · ชั้นเล่ม: {shelf.shelf_label}</div>
{:else}
  <section class="card step">
    <h2>หน่วยงานของคุณ</h2>
    <input class="search big" type="search" placeholder="พิมพ์ชื่อหน่วยงาน เช่น กรมการแพทย์" bind:value={q} aria-label="ค้นชื่อหน่วยงาน" />
    <p class="have"><span>ตอนนี้มีในระบบ <b>{nVol}</b> เล่ม</span><span class="hint">ไม่เจอหน่วยงานของคุณ?</span>
      <button class="btn small ghost" onclick={() => (mode = "upload")}>ใช้ไฟล์ในเครื่อง →</button></p>
    {#if q.trim()}
      <div class="hits" role="list">
        {#each hits as [v, g] (v.key + g)}
          <button class="hit" class:on={a === v.key && agency === g} onclick={() => pickAgency(v.key, g)}>
            <b>{g}</b><span class="hint">{head(v) || nice(v.key)}{head(v) ? ` · ${nice(v.key)}` : ""}</span></button>
        {/each}
        {#if !hits.length}<p class="hint">ไม่พบชื่อนี้ในเล่มที่มีในระบบ — ลองพิมพ์สั้นลง หรือกด "ใช้ไฟล์ในเครื่อง" ด้านบน</p>{/if}
      </div>
    {:else}
      <p class="hint or">หรือเลือกจากกระทรวง</p>
      {#each byYear as [fy, vs] (fy)}
        <p class="fy">ปีงบประมาณ {fy}</p>
        <div class="mins">
          {#each vs as v (v.key)}
            <details class="min" open={a === v.key}>
              <summary><b>{head(v) || nice(v.key)}</b>
                <span class="hint">{head(v) ? `${nice(v.key)} · ` : ""}{ags[v.key]?.length ? `${ags[v.key].length} หน่วยงาน` : "กำลังโหลด…"}</span></summary>
              <div class="agl">
                {#each ags[v.key] ?? [] as g (g)}
                  <button class="ag" class:on={a === v.key && agency === g} onclick={() => pickAgency(v.key, g)}>{g}</button>
                {/each}
              </div>
            </details>
          {/each}
        </div>
      {/each}
    {/if}
  </section>

  {#if a && agency}
    <section class="card step" id="step2">
      <h2>{kind === "same" ? "เทียบกับ พ.ร.บ. เล่มไหน" : kind === "cross" ? "เทียบกับเล่มปีใหม่เล่มไหน" : "เลือกเล่ม B"}</h2>
      <p class="chosen"><span class="tick" aria-hidden="true">✓</span><b>{agency}</b><span class="hint">{nice(a)}</span>
        <button class="btn small ghost" onclick={() => (agency = "")}>เปลี่ยน</button></p>
      {#if !pick}
        <div class="skeleton sk2"></div>
      {:else}
        {#if pick.agency_error}<p class="note danger">{pick.agency_error}</p>{/if}
        <div class="bs" role="radiogroup" aria-label="เล่มที่จะเทียบ">
          {#each pick.suggest.filter((x) => fitB([x.key]).length) as x (x.key)}
            <button role="radio" aria-checked={b === x.key} class="vol" class:on={b === x.key} onclick={() => (b = x.key)}>
              <span class="chip ok">แนะนำ</span><span>{nice(x.key)}<small class="hint">{x.why}</small></span></button>
          {/each}
          {#if fitB(pick.others).length}
            {@const rec = pick.suggest.some((x) => fitB([x.key]).length)}
            <details class="others" open={!rec || fitB(pick.others).includes(b)}>
              <summary>{rec ? `เล่มอื่น (${fitB(pick.others).length})` : "เลือกเล่ม"}</summary>
              <div class="bs">
                {#each fitB(pick.others) as k (k)}
                  <button role="radio" aria-checked={b === k} class="vol" class:on={b === k} onclick={() => (b = k)}>
                    <span>{nice(k)}</span></button>
                {/each}
              </div>
            </details>
          {/if}
        </div>
        <div class="go">
          <p class="sum">{#if b}{nice(a)} เทียบกับ {nice(b)}{:else}<span class="hint">เลือกเล่มที่จะเทียบ</span>{/if}</p>
          <button class="btn" disabled={!b || busy} onclick={start}>{busy ? `กำลังเทียบ… ${secs} วินาที` : "เริ่มเทียบ →"}</button>
        </div>
      {/if}
    </section>
  {/if}
{/if}

<style>
  .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-bottom: 4px; }
  .bar h1 { margin: 0; font-size: 1.5em; }
  .lead { margin: 0 0 12px; }
  .stepper { list-style: none; display: flex; gap: 6px; padding: 0; margin: 4px 0 12px; flex-wrap: wrap; }
  .stepper li { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px 6px 6px; border-radius: 999px; background: #eef0f3;
    color: var(--muted); font-weight: 600; }
  .stepper li span { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: #fff; color: var(--muted); }
  .stepper li.on { background: var(--accent); color: #fff; } .stepper li.on span { color: var(--accent); }
  .stepper li.done { background: var(--ok-bg); color: var(--ok); } .stepper li.done span { background: var(--ok); color: #fff; }
  .modes { display: inline-flex; gap: 4px; padding: 4px; margin: 8px 0 8px; border-radius: 14px; background: #e9ecf1; }
  .modes button { border: 0; background: transparent; border-radius: 10px; padding: 7px 16px; cursor: pointer; color: #344054; }
  .modes button.on { background: #fff; color: var(--ink); font-weight: 600; box-shadow: 0 1px 4px rgba(16, 24, 40, .12); }
  .msg { padding: 16px; }
  .sk { height: 40vh; } .sk2 { height: 200px; border-radius: 12px; }
  .step { padding: 14px 18px; margin-bottom: 12px; }
  .step h2 { display: flex; align-items: center; gap: 10px; margin: 0 0 8px; font-size: 1.1em; }
  .fy { margin: 10px 0 6px; color: var(--muted); font-weight: 600; }
  .bs { display: flex; flex-direction: column; gap: 8px; max-width: 640px; }
  .others summary { cursor: pointer; color: var(--muted); padding: 4px 2px; }
  .others .bs { margin-top: 6px; }
  .vol { display: flex; align-items: center; gap: 8px; text-align: left; padding: 10px 14px; border-radius: 14px; border: 1px solid #cfd4dc;
    background: #fff; cursor: pointer; color: inherit; font: inherit; transition: border-color .15s, box-shadow .15s; }
  .vol span:last-child { display: flex; flex-direction: column; }
  .vol:hover { border-color: var(--accent); }
  .vol.on, .ag.on { border-color: var(--accent); background: var(--accent-bg); box-shadow: inset 0 0 0 1px var(--accent); }
  .search { width: 100%; padding: 8px 12px; border-radius: 12px; border: 1px solid #cfd4dc; font: inherit; margin-bottom: 6px; }
  .search.big { max-width: 640px; padding: 12px 16px; font-size: 1.05em; border-radius: 14px; border-width: 2px; border-color: #b9c3d6; }
  .search.big:focus { border-color: var(--accent); outline: none; }
  .or { margin: 10px 0 0; }
  .have { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; margin: 8px 0 0; }
  .hits { display: flex; flex-direction: column; gap: 6px; max-width: 640px; }
  .hit { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; text-align: left; padding: 10px 14px; border-radius: 14px;
    border: 1px solid #cfd4dc; background: #fff; cursor: pointer; color: inherit; font: inherit; }
  .hit:hover { border-color: var(--accent); }
  .hit.on { border-color: var(--accent); background: var(--accent-bg); }
  .mins { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 8px; align-items: start; }
  .min { border: 1px solid #cfd4dc; border-radius: 14px; background: #fff; }
  .min[open] { border-color: var(--accent); }
  .min summary { display: flex; flex-direction: column; gap: 2px; padding: 10px 14px; cursor: pointer; list-style: none; }
  .min summary::-webkit-details-marker { display: none; }
  .min summary b::before { content: "▸ "; color: var(--muted); } .min[open] summary b::before { content: "▾ "; }
  .agl { display: flex; flex-direction: column; gap: 4px; max-height: 300px; overflow: auto; padding: 0 10px 10px; }
  .chosen { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 10px; margin: 0 0 10px; padding: 10px 14px; border-radius: 14px;
    background: var(--ok-bg); }
  .tick { display: inline-grid; place-items: center; width: 24px; height: 24px; border-radius: 50%; background: var(--ok); color: #fff; font-weight: 700; }
  .ag { text-align: left; padding: 7px 12px; border-radius: 10px; border: 1px solid transparent; background: #f7f8fa; cursor: pointer;
    color: inherit; font: inherit; }
  .ag:hover { border-color: #cfd4dc; }
  .go { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; justify-content: space-between; margin: 14px 0 6px;
    padding-top: 12px; border-top: 1px dashed var(--line); }
  .sum { margin: 0; }
</style>
