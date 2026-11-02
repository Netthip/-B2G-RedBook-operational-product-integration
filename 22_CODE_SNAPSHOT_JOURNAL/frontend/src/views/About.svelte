<script lang="ts">
  // เกี่ยวกับระบบ (กิ๊ฟ 29 ต.ค.): ทำอะไร · ทำอย่างไร · ข้อมูลมาจากไหน · ใครพัฒนา
  // "งานที่ทำไว้" ไม่อยู่ในเมนูหลักแล้ว — อยู่ใน "ส่วนผู้พัฒนา" (/r/dev) ที่ลิงก์จากท้ายหน้านี้
  import { link } from "../lib/router.svelte";

  const STEPS: [string, string, string][] = [
    ["1", "เลือกหน่วยงาน", "พิมพ์ชื่อหน่วยงาน ระบบหาเล่มให้"],
    ["2", "ดูจุดที่ต่าง", "เห็นหน้า PDF ของทั้งสองเล่มคู่กัน"],
    ["3", "ให้ความเห็น", "คนเป็นผู้ตัดสินทุกจุด"],
  ];
</script>

<article class="about">
  <header>
    <p class="mark" aria-hidden="true">RV</p>
    <h1>RedBook Verify</h1>
    <p class="lead">ระบบช่วยตรวจเทียบเล่มงบประมาณ<br />ชี้จุดที่ตัวเลขหรือข้อความต่างกัน พร้อมหน้าหลักฐาน</p>
  </header>

  <ol class="steps">
    {#each STEPS as [n, t, d] (n)}
      <li class="card"><span class="n">{n}</span><b>{t}</b><span class="hint">{d}</span></li>
    {/each}
  </ol>

  <!-- ที่มา (กิ๊ฟ + คณะทำงาน 29 ต.ค.): เล่าว่าช่วยอะไร ไม่เล่าวิธีทำงานภายใน/ข้อผิดพลาดที่ไม่มีหลักฐาน · ไม่อ้างลดภาระ/เวลา -->
  <section class="card info why">
    <h2>ทำไมถึงมีระบบนี้</h2>
    <p>เอกสารงบประมาณเผยแพร่ให้ประชาชนอ่าน และต้องตรวจให้เสร็จในเวลาสั้น ทั้งรอบร่าง พ.ร.บ. และรอบหลังสภาปรับลด</p>
    <p>ระบบนี้ช่วยชี้จุดที่ต่างกันระหว่างสองฉบับ พร้อมหน้าหลักฐาน ให้ผู้ตรวจดูได้ในที่เดียว</p>
    <p class="hint">เริ่มจากไฟล์ PDF ก่อน ไฟล์รูปแบบอื่นจะพัฒนาต่อในขั้นถัดไป</p>
  </section>

  <section class="card info">
    <h2>ข้อมูลมาจากไหน</h2>
    <p>เอกสารงบประมาณที่สำนักงบประมาณเผยแพร่ หรือไฟล์ PDF ที่ผู้ตรวจนำมาเอง</p>
    <h2>ระบบไม่ได้ทำอะไร</h2>
    <p>ไม่ตัดสินว่าเอกสารถูกหรือผิด และไม่รับรองความถูกต้องของเอกสาร</p>
  </section>

  <section class="card info">
    <h2>ผู้พัฒนา</h2>
    <p><b>เนตรทิพย์ วิมลมงคลพร</b><br /><span class="hint">งานค้นคว้าอิสระ ระดับปริญญาโท<br />มหาวิทยาลัยสุโขทัยธรรมาธิราช</span></p>
  </section>

  <p class="dev"><a href="/r/dev" onclick={link}>ส่วนผู้พัฒนา →</a></p>
</article>

<style>
  .about { max-width: 760px; margin: 8px auto 0; }
  header { text-align: center; margin-bottom: 18px; }
  .mark { display: inline-grid; place-items: center; width: 56px; height: 56px; margin: 0 0 6px; border-radius: 16px;
    background: linear-gradient(135deg, #0e2f6e, #1d4690); color: #fff; font-weight: 800; font-size: 1.3em; }
  h1 { margin: 0; font-size: 1.8em; color: #0e2f6e; }
  .lead { margin: 6px 0 0; color: #344054; font-size: 1.05em; }
  .steps { list-style: none; display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 0; margin: 0 0 12px; }
  .steps li { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 16px 12px; text-align: center; }
  .n { display: inline-grid; place-items: center; width: 34px; height: 34px; border-radius: 50%; background: var(--accent); color: #fff; font-weight: 700; }
  .info { padding: 14px 18px; margin-bottom: 12px; }
  .info h2 { margin: 0 0 2px; font-size: 1em; color: var(--accent); }
  .info p { margin: 0 0 10px; } .info p:last-child { margin-bottom: 0; }
  .why { border-left: 4px solid var(--accent); }
  .why p { margin-bottom: 4px; }
  .dev { text-align: center; font-size: .9em; }
  .dev a { color: var(--muted); }
  @media (max-width: 600px) { .steps { grid-template-columns: 1fr; } }
</style>
