<script lang="ts">
  import { get, post, type Book, type Meta, type Path } from "../lib/api";
  import { go } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";

  let meta = $state<Meta | null>(null);       // App.svelte ไม่ส่ง meta ให้หน้านี้ — ขอป้ายจากเซิร์ฟเวอร์เอง
  get<Meta>("/api/trial/meta").then((m) => (meta = m));
  let books = $state<Book[] | null>(null);
  let cur = $state(0);
  let reviewer = $state("");
  let path = $state<Path>("r1");
  let busy = $state(false);
  let sparks = $state<{ id: number; x: number; y: number; d: number; red: boolean }[]>([]);
  let fanEl: HTMLDivElement | undefined = $state();

  get<{ books: Book[] }>("/api/trial/books").then((r) => {
    books = r.books;
    const i = r.books.findIndex((b) => b.status?.state !== "locked");
    cur = i < 0 ? 0 : i;
  });

  const done = $derived(books ? books.filter((b) => b.status?.state === "locked").length : 0);

  function stateText(b: Book): string {
    const st = b.status?.state;
    if (st === "locked") return "ส่งใบประกาศแล้ว";
    if (st === "draft") return "กำลังทำ";
    if (st === "legacy") return "มีรอบกติกา 0.1 (อ่านอย่างเดียว)";
    if (st) return `${meta?.statuses[st] ?? ""}แล้ว`;
    return "ยังไม่เริ่ม";
  }

  function pose(i: number) {
    const d = i - cur, a = Math.abs(d);
    if (d === 0) return { t: "translateX(0) translateY(0) rotate(0deg) scale(1)", z: 50 };
    if (d < 0) return { t: `translateX(${-160 + (d + 1) * 58}px) translateY(${6 * a}px) rotate(${-3 + d * 0.6}deg) scale(${0.86 + d * 0.02})`, z: 20 + i };
    return { t: `translateX(${160 + (d - 1) * 50}px) translateY(${8 * a}px) rotate(${2 + d * 0.4}deg) scale(${0.84 - d * 0.02})`, z: 20 - d };
  }

  let sid = 0;
  function pick(i: number, el?: HTMLElement) {
    if (!books || i < 0 || i >= books.length || i === cur) return;
    cur = i;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || !fanEl) return;
    setTimeout(() => {
      const card = fanEl!.querySelector<HTMLElement>(`[data-i="${i}"]`);
      if (!card) return;
      const box = fanEl!.getBoundingClientRect(), r = card.getBoundingClientRect();
      const add = Array.from({ length: 9 }, (_, k) => ({
        id: ++sid, x: r.left - box.left + 18 + Math.random() * (r.width - 36),
        y: r.top - box.top + 26 + Math.random() * r.height * 0.6, d: k * 65, red: k % 3 === 0 }));
      sparks.push(...add);
      setTimeout(() => { sparks = sparks.filter((s) => !add.includes(s)); }, 1600);
    }, 220);
    el?.focus({ preventScroll: true });
  }

  function key(e: KeyboardEvent) {
    if (e.key === "ArrowRight") { e.preventDefault(); pick(cur + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); pick(cur - 1); }
  }

  async function start(again = false, book = books?.[cur]) {
    if (!book || busy) return;
    busy = true;
    try {
      const r = await post<{ sid: string; locked: boolean; result: boolean }>("/api/trial/start",
        { book_id: book.id, reviewer, again, path });
      go(`/r/s/${r.sid}${r.result ? "/result" : ""}`);
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      busy = false;
    }
  }
</script>

<h1 class="h1">เลือกเล่มที่จะตรวจ</h1>
{#if !books || !meta}
  <div class="fan"><div class="card ghostcard skeleton"></div></div>
{:else if !books.length}
  <div class="card warn">ยังไม่มีเล่มทดสอบในเครื่องนี้ — ต้องมีเล่มบนชั้นเล่ม และไฟล์ตั้งค่า <code>trial_books.json</code></div>
{:else}
  <p class="sub">ส่งใบประกาศแล้ว {done} จาก {books.length} เล่ม · แตะป้ายของใบไหนก็ได้ หรือกด ← →</p>
  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div class="fan" bind:this={fanEl} role="radiogroup" aria-label="เล่มทดสอบ" tabindex="0" onkeydown={key}>
    {#each books as b, i (b.id)}
      {@const p = pose(i)}
      <button class="tcard" class:on={i === cur} class:left={i < cur} class:right={i > cur}
              class:done={b.status?.state === "locked"} data-i={i} role="radio" aria-checked={i === cur}
              tabindex={i === cur ? 0 : -1} style:transform={p.t} style:z-index={p.z}
              onclick={(e) => (i === cur ? start() : pick(i, e.currentTarget))}>
        <span class="tab">{b.title}{b.status?.state === "locked" ? " ✓" : ""}</span>
        <span class="art" aria-hidden="true">{i + 1}</span>
        <span class="name">{b.agency}</span>
        <span class="pair">{b.pair_kind === "cross_year" ? "ข้ามปี · ฉบับปีก่อน ↔ ฉบับปีนี้" : "ปีเดียวกัน · ฉบับ A ↔ ฉบับ B"}</span>
        <span class="chip state">{stateText(b)}</span>
      </button>
    {/each}
    {#each sparks as s (s.id)}
      <span class="spark" class:red={s.red} style:left="{s.x}px" style:top="{s.y}px" style:animation-delay="{s.d}ms"></span>
    {/each}
  </div>

  <fieldset class="card paths">
    <legend>ทางทำรายการอ้างอิง</legend>
    <label class="path"><input type="radio" bind:group={path} value="r1">
      <span><b>{meta.paths.r1}</b> · รายการที่จดไว้แล้วจากงานตรวจเล่มตามปกติ หรือจากแบบ ๐๑ · ส่งเฉพาะจำนวนก่อนเห็นผล
        ไม่ต้องตรวจใหม่ทุกหน้า</span></label>
    <label class="path"><input type="radio" bind:group={path} value="r2">
      <span><b>{meta.paths.r2}</b> · วงจุดต่างบนภาพหน้าของทั้งสองฉบับในหน้านี้</span></label>
  </fieldset>

  <div class="go">
    <label>รหัสผู้ตรวจ <span class="hint">(ไม่ต้องใส่ชื่อ เช่น R1)</span>
      <input bind:value={reviewer} maxlength="20" size="8"></label>
    <button class="btn" disabled={busy} onclick={() => start()}>
      {#if busy}<span class="spin small"></span> กำลังเปิด…{:else}
        {books[cur].status?.state === "locked" ? "ดูผลเล่มนี้" : books[cur].status?.state === "draft" ? "ทำต่อ" : "เริ่มตรวจเล่มนี้"}{/if}
    </button>
    {#if books[cur].status}
      <button class="btn ghost small" disabled={busy} onclick={() => start(true)}>เริ่มรอบใหม่ (รอบเดิมเก็บไว้)</button>
    {/if}
  </div>
  <p class="hint center">กดเริ่มที่เล่มที่เคยทำไว้ = กลับไปรอบเดิม (งานที่ทำไว้ไม่หาย) · ถ้าเคยเห็นผลระบบของเล่มนี้แล้ว
    รอบใหม่จะถูกบันทึกไว้ให้รายงาน</p>
{/if}

<section class="card steps">
  <h2>ขั้นตอน (บอกตามจริง)</h2>
  <ol>
    <li><b>เลือกเล่มและทาง</b> — ใช้งานจริงต้อง<b>อัปโหลดไฟล์ PDF</b> สองฉบับเอง · รอบทดลองนี้เตรียมเล่มไว้ให้แล้ว ·
      ทาง ร1 ใช้รายการที่ท่านมีอยู่แล้ว · ทาง ร2 วงจุดบนภาพหน้า</li>
    <li><b>ส่งใบประกาศก่อนเห็นผล</b> — วันที่จัดทำ ที่มา ส่วนของเล่มที่ตรวจครบ และจำนวนประเด็นรายหัวข้อ
      (ทาง ร2 ระบบนับจากจุดที่วง) · <b>ไม่ต้องกด "ตรวจหน้านี้แล้ว" ครบทุกหน้า</b> · ส่งแล้วแก้ไม่ได้ ·
      <b>ระบบยังไม่เทียบจนกว่าท่านจะส่ง</b></li>
    <li><b>จับคู่ประเด็นกับข้อสังเกตของระบบ</b> — ระบบเสนอคู่ ท่านเป็นผู้ยืนยัน · ระบุผล รหัสเหตุ หลักฐาน และฐานการวินิจฉัย ·
      จัดข้อสังเกตที่ไม่อยู่ในรายการของท่าน</li>
    <li><b>จบการใช้ผล</b> แล้วตอบ<b>แบบสอบถามหลังใช้ผล</b></li>
    <li><b>ดูแดชบอร์ด</b> · ดาวน์โหลดสรุปเฉพาะจำนวนส่งผู้ศึกษา (ไม่มีตำแหน่ง หมายเหตุ หรือเนื้อหาของประเด็น)</li>
  </ol>
  <p class="hint">ปิดหน้าแล้วกลับมาทำต่อได้ ทุกอย่างบันทึกทันที · หยุดรอบหรือถอนตัวได้ทุกเมื่อ · ขั้นไหนยากหรืออยากให้ปรับ บอกได้ในแบบสอบถาม</p>
</section>

<style>
  .fan { position: relative; height: 350px; max-width: 680px; margin: 0 auto; outline: none; }
  .tcard { position: absolute; bottom: 20px; left: 50%; width: 244px; height: 292px; margin-left: -122px; border-radius: 22px;
    background: #fff; border: 1px solid var(--line); box-shadow: var(--shadow); padding: 0; cursor: pointer; text-align: left;
    color: inherit; transform-origin: 50% 100%; transition: transform .55s cubic-bezier(.22, 1.2, .36, 1), box-shadow .3s; }
  .tcard.on { border: 2px solid var(--ink); box-shadow: 0 16px 34px rgba(16, 24, 40, .16); }
  .tcard:not(.on):hover { box-shadow: 0 10px 24px rgba(16, 24, 40, .12); }
  .tab { position: absolute; top: 14px; left: 14px; padding: 6px 10px; border-radius: 12px; background: #eef0f3; font-weight: 700;
    transition: background .3s, color .3s; }
  .tcard.on .tab, .tcard.right .tab { left: auto; right: 14px; }
  .tcard.on .tab { background: var(--dark); color: #fff; }
  .art { position: absolute; inset: 70px 0 92px; display: flex; align-items: center; justify-content: center; font-size: 66px;
    font-weight: 700; color: #cdd2da; transition: color .3s; }
  .tcard.on .art { color: var(--ink); }
  .tcard.done .art { color: #9fc8a9; }
  .name { position: absolute; left: 18px; right: 18px; bottom: 56px; font-weight: 700; line-height: 1.3; }
  .pair { position: absolute; left: 18px; bottom: 34px; color: var(--muted); font-size: .9em; }
  .state { position: absolute; left: 18px; bottom: 10px; }
  .tcard:not(.on) :is(.name, .pair, .state) { opacity: 0; }
  .ghostcard { width: 244px; height: 292px; margin: 20px auto; border-radius: 22px; }
  .spark { position: absolute; width: 10px; height: 10px; color: #ef9f27; pointer-events: none; z-index: 60;
    animation: tw 1s ease-out both; }
  .spark.red { color: var(--red); }
  .spark::before, .spark::after { content: ""; position: absolute; left: 4px; top: 0; width: 2px; height: 10px; background: currentColor; border-radius: 1px; }
  .spark::after { transform: rotate(90deg); }
  @keyframes tw { 0% { opacity: 0; transform: scale(.2); } 35% { opacity: 1; transform: scale(1.2) rotate(45deg); } 100% { opacity: 0; transform: scale(.3) rotate(90deg); } }
  .paths { max-width: 760px; margin: 4px auto 10px; padding: 8px 18px; border: 1px solid var(--line); }
  .paths legend { font-weight: 700; padding: 0 6px; }
  .path { display: flex; gap: 8px; align-items: flex-start; margin: 6px 0; cursor: pointer; }
  .go { display: flex; gap: 12px; align-items: center; justify-content: center; flex-wrap: wrap; margin: 6px 0 6px; }
  .go input { margin-left: 6px; padding: 8px 10px; border: 1px solid #cfd4dc; border-radius: 10px; font: inherit; }
  .center { text-align: center; margin: 0 0 18px; }
  .steps { padding: 6px 22px 12px; max-width: 980px; margin: 0 auto; }
  .steps li { margin: 6px 0; }
  .warn { padding: 16px; background: #fff8e6; }
  .spin.small { width: 14px; height: 14px; border-width: 2px; border-color: rgba(255,255,255,.4); border-top-color: #fff; }
  @media (max-width: 700px) { .fan { height: 330px; } }
</style>
