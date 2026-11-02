<script lang="ts">
  // ส่วนผู้พัฒนา (กิ๊ฟ 29 ต.ค.): แยกของทีมพัฒนาออกจากหน้าผู้ใช้ — ชุดประเมิน · ขั้นตอนวันตรวจของผู้ตรวจ · งานที่ทำไว้
  // ⚠️ ซ่อนลิงก์ ≠ ล็อก — หน้านี้ต้องไม่มีของลับ: ชุดประเมินแสดงแค่รหัส C1… จากจำนวนที่เซิร์ฟเวอร์ส่งมา (ไม่มีชื่อหน่วยงาน)
  //    การล็อกจริงอยู่ที่เซิร์ฟเวอร์ (redbook/eval_guard.py)
  import { link } from "../lib/router.svelte";
  import { lane } from "../lib/lane.svelte";

  const g = $derived(lane.evalGuard);
  const codes = $derived(Array.from({ length: g?.agencies ?? 0 }, (_, i) => `C${i + 1}`));

  // แบบฟอร์มสาย PDF ฉบับ 0.3 ร่าง 2 (84_PDF_PAIR_EVALUATION) — ชื่อแบบเท่านั้น ไฟล์อยู่ในโฟลเดอร์งานของกิ๊ฟ
  const KIT: { where: string; mark: string; items: [string, string][] }[] = [
    { where: "ก่อนวันตรวจ · เครื่องของผู้ตรวจเอง", mark: "1", items: [
      ["แบบ 01 รายการอ้างอิงของผู้ตรวจ", "จดจุดต่างเอง ปิดส่วนที่ 0–1 ก่อนเห็นผลของระบบ · เก็บไว้กับตัว ไม่ส่งผู้ศึกษา"]] },
    { where: "วันตรวจ · เครื่องของกิ๊ฟ", mark: "2", items: [
      ["เปิดรอบของกรณีที่ได้รับ", "ดูหลักฐาน A | B แล้วให้ความเห็นทุกจุด"],
      ["แบบ 02 ใบสรุปจำนวน", "นับเทียบกับรายการของตัวเอง · ส่งผู้ศึกษาใบเดียวนี้"]] },
    { where: "หลังตรวจ", mark: "3", items: [
      ["แบบ 03 แบบสอบถามหลังใช้ผล", "ใช้รหัสผู้ตอบ ไม่ลงชื่อ"]] },
  ];
</script>

<article class="dev">
  <header>
    <h1>ส่วนผู้พัฒนา</h1>
    <p class="hint">สำหรับทีมพัฒนาและผู้ศึกษา · ผู้ตรวจทั่วไปไม่ต้องใช้หน้านี้</p>
  </header>

  <section class="card box">
    <h2>ชุดประเมิน</h2>
    {#if !lane.known}
      <div class="skeleton sk"></div>
    {:else if !g}
      <p class="hint">เซิร์ฟเวอร์นี้ไม่รายงานสถานะชุดประเมิน</p>
    {:else if !g.configured}
      <p class="note danger">ยังไม่ได้ตั้งค่าด่านชุดประเมินบนเครื่องนี้</p>
    {:else}
      <p class="big"><b>{g.agencies}</b> กรณี
        <span class="chip" class:ok={g.unlocked} class:lock={!g.unlocked}>{g.unlocked ? "✓ เปิดให้ตรวจแล้ว" : "🔒 ล็อกอยู่"}</span></p>
      <div class="codes">{#each codes as c (c)}<span class="code" class:open={g.unlocked}>{c}</span>{/each}</div>
      <p class="hint">{g.unlocked
        ? `เปิดสำหรับตัวสกัดรุ่น ${g.pdfbook} · รุ่นเปลี่ยนเมื่อไรจะล็อกเองอีกครั้ง`
        : `ระบบยังไม่เปิดเล่มของกรณีเหล่านี้ จนกว่าจะตรึงรุ่นเครื่องมือ (ตอนนี้ ${g.pdfbook})`}</p>
    {/if}
  </section>

  <section class="card box">
    <h2>ขั้นตอนของผู้ตรวจ <span class="hint">ผู้ตรวจ 3 คน · แต่ละคนมีรายการอ้างอิงของตัวเอง</span></h2>
    <ol class="kit">
      {#each KIT as k (k.mark)}
        <li><span class="n">{k.mark}</span>
          <div><p class="where">{k.where}</p>
            {#each k.items as [t, d] (t)}<p class="it"><b>{t}</b><span class="hint">{d}</span></p>{/each}</div></li>
      {/each}
    </ol>
    <!-- กิ๊ฟ 30 ต.ค.: เลือกแบบ 03 ฉบับ 0.3 ร่าง 2 · ฉบับย่อ 10 เก็บเป็นประวัติ · มีแบบ IOC ≠ ผ่าน IOC · มีช่องยินยอม ≠ ยืนยัน E1 -->
    <p class="hint warn">แบบฟอร์มยังเป็นฉบับ 0.3 ร่าง 2 — ยังไม่ใช้เก็บข้อมูลจริง จนกว่าจะครบ 3 ข้อ:
      สถานะจริยธรรมยืนยันแล้ว · ผู้เชี่ยวชาญตรวจเครื่องมือ (IOC) แล้ว · ตรึงฉบับสุดท้ายแล้ว</p>
  </section>

  <a class="card box go" href="/r/p" onclick={link}>
    <span><b>งานที่ทำไว้</b><span class="hint">รอบเทียบทุกรอบ · ทำต่อหรือดูผล</span></span><span aria-hidden="true">→</span></a>
</article>

<style>
  .dev { max-width: 760px; margin: 8px auto 0; display: flex; flex-direction: column; gap: 12px; }
  header h1 { margin: 0; font-size: 1.5em; color: #475467; }
  header p { margin: 2px 0 0; }
  .box { padding: 14px 18px; }
  .box h2 { margin: 0 0 8px; font-size: 1.05em; color: var(--accent); }
  .sk { height: 60px; }
  .big { margin: 0 0 8px; font-size: 1.1em; display: flex; align-items: center; gap: 10px; }
  .big b { font-size: 1.6em; color: var(--accent); }
  .chip.lock { background: #eef0f3; color: #475467; }
  .codes { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
  .code { display: inline-grid; place-items: center; min-width: 48px; padding: 6px 10px; border-radius: 12px;
    border: 1px solid #cfd4dc; background: #f5f6f8; color: #475467; font-weight: 700; }
  .code.open { border-color: var(--ok); background: var(--ok-bg); color: var(--ok); }
  .kit { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
  .kit li { display: grid; grid-template-columns: 34px 1fr; gap: 10px; }
  .n { display: inline-grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; background: #e4e7ec; color: #344054; font-weight: 700; }
  .where { margin: 4px 0 4px; font-weight: 600; color: #344054; }
  .it { margin: 0 0 4px; display: flex; flex-direction: column; }
  .warn { margin: 10px 0 0; }
  .go { display: flex; justify-content: space-between; align-items: center; color: inherit; text-decoration: none; }
  .go > span:first-child { display: flex; flex-direction: column; }
  .go:hover { box-shadow: 0 0 0 2px var(--accent); }
</style>
