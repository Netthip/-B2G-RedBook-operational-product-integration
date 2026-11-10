<script lang="ts">
  // หน้าแรกของสายเทียบเล่ม: คลังเล่มงบประมาณ (กิ๊ฟ 29 ต.ค.) — ข้อมูลจากทะเบียนเล่มทางการ (/api/books · อ่านอย่างเดียว)
  // ลิงก์ออกไปหน้าเผยแพร่ของสำนักงบประมาณ/ไฟล์ PDF ตามทะเบียน · ทางเข้างานตรวจสองแบบอยู่ด้านบน
  import { link, nav } from "../lib/router.svelte";
  import { get } from "../lib/api";
  import { slide, fadeOn } from "../lib/motion";

  interface LBook { id: string; fiscal_year: number; headline: string; kicker: string; stage: string; stage_label: string;
    type_group: string; type_group_label: string; stripe_color: string; source_page: string; pdf_url: string; synthetic: boolean }
  interface LCat { years: number[]; books: LBook[]; synthetic: boolean }

  let cat = $state<LCat | null>(null);
  let err = $state("");
  get<LCat>("/api/books").then((x) => { cat = x; if (!year) year = Math.max(...x.years); }).catch((e) => (err = (e as Error).message));

  const q0 = nav.query;
  let year = $state(Number(q0.get("y")) || 0);
  let stage = $state(q0.get("s") ?? "act");
  let group = $state(q0.get("g") ?? "by_ministry");
  let q = $state("");
  $effect(() => {
    const p = new URLSearchParams();
    if (year) p.set("y", String(year));
    if (stage !== "act") p.set("s", stage);
    if (group !== "by_ministry") p.set("g", group);
    history.replaceState(null, "", `/r/lib${p.toString() ? `?${p}` : ""}`);
  });

  const groups = $derived(cat ? [...new Map(cat.books.map((b) => [b.type_group, b.type_group_label])).entries()] : []);
  const shown = $derived((cat?.books ?? []).filter((b) => b.fiscal_year === year && (!stage || b.stage === stage)
    && (!group || b.type_group === group) && (!q.trim() || `${b.headline} ${b.kicker}`.includes(q.trim()))));
  const vol = (k: string) => k.match(/เล่มที่\s*(\d+)/)?.[1] ?? "";
  // ปกขาวคาดแดงแบบเล่มงบประมาณจริง (กิ๊ฟ 29 ต.ค.) · ถ้าทะเบียนระบุสีคาดอื่นตามชื่อไฟล์ทางการ ใช้สีนั้น
  const STRIPE: Record<string, string> = { "แดง": "red", "เหลือง": "yellow", "ม่วง": "purple", "น้ำเงิน": "navy",
    "ชมพู": "pink", "เขียว": "green", "ส้ม": "orange", "ฟ้า": "sky" };
</script>

<section class="go2">
  <a class="act" href="/r/p/new?kind=cross" onclick={link}>
    <b>ตรวจเล่มงบประมาณข้ามปี</b><span>เล่มปีใหม่ เทียบกับปีก่อน</span><i>เริ่มตรวจ →</i></a>
  <a class="act" href="/r/p/new?kind=same" onclick={link}>
    <b>ตรวจเล่มงบประมาณในปีเดียวกัน</b><span>ร่าง พ.ร.บ. เทียบกับ พ.ร.บ.</span><i>เริ่มตรวจ →</i></a>
</section>

<div class="head">
  <h1>คลังเล่มงบประมาณ</h1>
  {#if cat}
    <div class="tabs" role="tablist" aria-label="ปีงบประมาณ" use:slide>
      {#each [...cat.years].sort((a, b) => b - a) as y (y)}
        <button role="tab" aria-selected={year === y} class:on={year === y} onclick={() => (year = y)}>{y}</button>
      {/each}
    </div>
  {/if}
</div>

{#if err}
  <div class="card msg">{err}</div>
{:else if !cat}
  <div class="grid">{#each Array(8) as _, i (i)}<div class="card skeleton sk"></div>{/each}</div>
{:else}
  <div class="tools">
    <div class="seg" role="radiogroup" aria-label="ขั้นเอกสาร" use:slide>
      {#each [["act", "พ.ร.บ."], ["draft", "ร่าง พ.ร.บ."], ["", "ทั้งหมด"]] as [k, l] (k)}
        <button role="radio" aria-checked={stage === k} class:on={stage === k} onclick={() => (stage = k)}>{l}</button>
      {/each}
    </div>
    <select bind:value={group} aria-label="ชนิดเอกสาร">
      <option value="">ทุกชนิด</option>
      {#each groups as [k, l] (k)}<option value={k}>{l}</option>{/each}
    </select>
    <input type="search" placeholder="ค้นกระทรวง" bind:value={q} aria-label="ค้นกระทรวง" />
  </div>

  {#if cat.synthetic}<p class="note warn">ข้อมูลสาธิต (สังเคราะห์)</p>{/if}
  {#if !shown.length}
    <p class="empty">ไม่มีเล่มที่ตรงเงื่อนไข</p>
  {:else}
    <div class="grid" use:fadeOn={`${year}|${stage}`}>
      {#each shown as b (b.id)}
        <article class="card book">
          <div class="cover s-{STRIPE[b.stripe_color] ?? "red"}">
            <span class="cy">{b.fiscal_year}</span>
            {#if vol(b.kicker)}<span class="cv">เล่ม {vol(b.kicker)}</span>{/if}
            <span class="cs">{b.stage_label}</span>
          </div>
          <div class="txt">
            <b class="hl" title={b.headline}>{b.headline}</b>
            <span class="hint">{b.kicker}</span>
          </div>
          <div class="links">
            {#if b.pdf_url}<a class="btn small" href={b.pdf_url} target="_blank" rel="noopener">เปิด PDF ↗</a>{/if}
            {#if b.source_page}<a class="btn small ghost" href={b.source_page} target="_blank" rel="noopener" title="หน้าเผยแพร่ของสำนักงบประมาณ">สำนักงบฯ ↗</a>{/if}
          </div>
        </article>
      {/each}
    </div>
  {/if}
{/if}

<style>
  .go2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 22px; }
  .act { position: relative; display: flex; flex-direction: column; gap: 2px; padding: 16px 150px 16px 18px; border-radius: var(--radius);
    background: linear-gradient(135deg, #0e2f6e, #1d4690); color: #fff; text-decoration: none; transition: transform .15s, box-shadow .2s; }
  .act:hover { transform: translateY(-2px); box-shadow: 0 10px 26px rgba(16, 24, 40, .2); }
  .act b { font-size: 1.1em; } .act span { opacity: .8; font-size: .92em; }
  /* ปุ่มเม็ดยาสีขาว "เริ่มตรวจ →" ให้รู้ทันทีว่ากดได้ (คณะทำงาน UI: คนใช้แอปธนาคารเป็น) */
  .act i { position: absolute; right: 16px; top: 50%; transform: translateY(-50%); font-style: normal; font-weight: 700;
    padding: 8px 16px; border-radius: 999px; background: #fff; color: #0e2f6e; }
  .head { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 10px; }
  h1 { margin: 0; font-size: 1.5em; }
  .tabs, .seg { display: inline-flex; gap: 4px; padding: 4px; border-radius: 14px; background: #e9ecf1; }
  .tabs button, .seg button { border: 0; background: transparent; border-radius: 10px; padding: 6px 14px; cursor: pointer; color: #344054; font: inherit; }
  .tabs button.on, .seg button.on { background: #fff; color: var(--ink); font-weight: 600; box-shadow: 0 1px 4px rgba(16, 24, 40, .12); }
  .tools { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 14px; }
  .tools select, .tools input { padding: 8px 12px; border-radius: 12px; border: 1px solid #cfd4dc; font: inherit; background: #fff; }
  .tools input { flex: 1; min-width: 200px; max-width: 320px; }
  .msg { padding: 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; }
  .sk { height: 190px; }
  .book { display: flex; flex-direction: column; overflow: hidden; }
  /* ปกขาว + แถบคาดแนวนอน (ค่าเริ่มต้นแดง) · เส้นเฉียงเลิกใช้: ดูเหมือนขีดฆ่า ชนกับสัญลักษณ์ "หายไป" ของงานตรวจ
     สันปกเทาอ่อนด้านซ้ายให้รู้ว่าเป็นเล่ม */
  .cover { --stripe: #c8102e; position: relative; display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto 1fr auto;
    gap: 0 8px; height: 88px; padding: 10px 14px 8px 20px; background: #fff; color: var(--ink); border-bottom: 1px solid var(--line);
    box-shadow: inset 6px 0 0 #e4e7ec; }
  .cover::after { content: ""; grid-column: 1 / -1; grid-row: 2; align-self: center; height: 10px; margin: 0 -14px 0 -14px;
    background: var(--stripe); }
  .cover.s-yellow { --stripe: #e0a800; } .cover.s-purple { --stripe: #6d28d9; } .cover.s-navy { --stripe: #0e2f6e; }
  .cover.s-pink { --stripe: #db2777; } .cover.s-green { --stripe: #1a7f37; } .cover.s-orange { --stripe: #ea580c; }
  .cover.s-sky { --stripe: #0284c7; }
  .cy { font-size: 1.5em; font-weight: 700; line-height: 1; color: #0e2f6e; } .cv { justify-self: end; font-weight: 600; }
  .cs { grid-column: 1 / -1; grid-row: 3; font-size: .82em; color: var(--muted); }
  .txt { flex: 1; display: flex; flex-direction: column; gap: 2px; padding: 10px 14px 6px; }
  .hl { display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; line-height: 1.45; }
  .links { display: flex; flex-wrap: wrap; gap: 6px; padding: 6px 14px 12px; }
  @media (max-width: 760px) { .go2 { grid-template-columns: 1fr; } }
</style>
