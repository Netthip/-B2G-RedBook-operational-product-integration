<script lang="ts">
  import { get, post, type Book } from "../lib/api";
  import { go } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";

  let books = $state<Book[] | null>(null);
  let cur = $state(0);
  let reviewer = $state("");
  let busy = $state(false);
  let sparks = $state<{ id: number; x: number; y: number; d: number; red: boolean }[]>([]);
  let fanEl: HTMLDivElement | undefined = $state();

  get<{ books: Book[] }>("/api/trial/books").then((r) => {
    books = r.books;
    const i = r.books.findIndex((b) => b.status?.state !== "locked");
    cur = i < 0 ? 0 : i;
  });

  const done = $derived(books ? books.filter((b) => b.status?.state === "locked").length : 0);

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
      const r = await post<{ sid: string; locked: boolean }>("/api/trial/start", { book_id: book.id, reviewer, again });
      go(`/r/s/${r.sid}${r.locked ? "/result" : ""}`);
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      busy = false;
    }
  }
</script>

<h1 class="h1">เลือกเล่มที่จะตรวจ</h1>
{#if !books}
  <div class="fan"><div class="card ghostcard skeleton"></div></div>
{:else if !books.length}
  <div class="card warn">ยังไม่มีเล่มทดสอบในเครื่องนี้ — ต้องมีเล่มบนชั้นเล่ม และไฟล์ตั้งค่า <code>trial_books.json</code></div>
{:else}
  <p class="sub">ตรวจแล้ว {done} จาก {books.length} เล่ม · แตะป้ายของใบไหนก็ได้ หรือกด ← →</p>
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
        <span class="pair">{b.pair}</span>
        <span class="chip state">{b.status?.state === "locked" ? "ส่งผลแล้ว" : b.status ? "กำลังตรวจ" : "ยังไม่เริ่ม"}</span>
      </button>
    {/each}
    {#each sparks as s (s.id)}
      <span class="spark" class:red={s.red} style:left="{s.x}px" style:top="{s.y}px" style:animation-delay="{s.d}ms"></span>
    {/each}
  </div>

  <div class="go">
    <label>รหัสผู้ตรวจ <span class="hint">(ไม่ต้องใส่ชื่อ เช่น R1)</span>
      <input bind:value={reviewer} maxlength="20" size="8"></label>
    <button class="btn" disabled={busy} onclick={() => start()}>
      {#if busy}<span class="spin small"></span> กำลังเปิด…{:else}
        {books[cur].status?.state === "locked" ? "ดูผลเล่มนี้" : books[cur].status ? "ตรวจต่อ" : "เริ่มตรวจเล่มนี้"}{/if}
    </button>
    {#if books[cur].status}
      <button class="btn ghost small" disabled={busy} onclick={() => start(true)}>เริ่มรอบใหม่ (รอบเดิมเก็บไว้)</button>
    {/if}
  </div>
{/if}

<section class="card steps">
  <h2>ขั้นตอน (บอกตามจริง)</h2>
  <ol>
    <li><b>เลือกเล่ม</b> — ใช้งานจริงต้อง<b>อัปโหลดไฟล์ PDF</b> สองฉบับเอง · รอบทดลองนี้เตรียมเล่มไว้ให้แล้ว จะได้ไม่ต้องหาไฟล์</li>
    <li><b>อ่านคำชี้แจง</b> — ปีปัจจุบันต้องถูกต้องเป็นหลัก · ช่วยดูตัวชี้วัด วิสัยทัศน์ พันธกิจ ว่าอะไรหาย เพิ่ม หรือไม่ใช้แล้ว</li>
    <li><b>วงจุดบนภาพหน้า</b> — สองฉบับวางข้างกัน เลื่อนและเปลี่ยนหน้าแยกกันได้ · ปากกาแดง = สำคัญ · น้ำตาล = สังเกตเห็น · หมุด = ของที่หายไป</li>
    <li><b>ส่งผลตรวจ</b> — ล็อกจุดที่วง · <b>ระบบยังไม่เทียบจนกว่าคุณจะส่ง</b> จะได้ไม่เห็นคำตอบของระบบก่อน</li>
    <li><b>ดูว่าระบบเจออะไร</b> — ยืนยันคู่ทีละข้อ แล้วจัดข้อที่ระบบยกเพิ่ม</li>
    <li><b>แบบสอบถามหน้าเดียว</b> แล้ว<b>ดูแดชบอร์ด</b> · ดาวน์โหลดสรุปเฉพาะจำนวนส่งผู้วิจัย</li>
  </ol>
  <p class="hint">ปิดหน้าแล้วกลับมาทำต่อได้ ทุกจุดบันทึกทันที · ขั้นไหนยากหรืออยากให้ปรับ บอกได้ในแบบสอบถาม</p>
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
  .go { display: flex; gap: 12px; align-items: center; justify-content: center; flex-wrap: wrap; margin: 6px 0 22px; }
  .go input { margin-left: 6px; padding: 8px 10px; border: 1px solid #cfd4dc; border-radius: 10px; font: inherit; }
  .steps { padding: 6px 22px 12px; max-width: 980px; margin: 0 auto; }
  .steps li { margin: 6px 0; }
  .warn { padding: 16px; background: #fff8e6; }
  .spin.small { width: 14px; height: 14px; border-width: 2px; border-color: rgba(255,255,255,.4); border-top-color: #fff; }
  @media (max-width: 700px) { .fan { height: 330px; } }
</style>
