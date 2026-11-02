<script lang="ts">
  // ปุ่ม ? — "ทำอะไรได้บ้าง" ของสายเทียบเล่ม · เปิดด้วยปุ่มหรือกด ? บนคีย์บอร์ด · ปิดด้วย Esc
  // ใช้ <dialog> ของเบราว์เซอร์ (โฟกัส/Esc จัดการให้) · ไม่มีสไตล์ฝังในแท็ก (CSP)
  let dlg = $state<HTMLDialogElement>();
  const open = () => dlg?.showModal();

  function onkey(e: KeyboardEvent) {
    if (e.key !== "?" || e.ctrlKey || e.metaKey || e.altKey) return;
    const t = e.target;
    if (t instanceof Element && t.closest("input, textarea, select, [contenteditable]")) return;
    e.preventDefault();
    if (dlg?.open) dlg.close(); else open();
  }

  const GROUPS: { title: string; items: [string, string][] }[] = [
    { title: "ตรวจทีละข้อ", items: [
      ["← →", "เลื่อนดูข้อก่อน/ถัดไป — ดูอย่างเดียว ไม่บันทึกอะไร"],
      ["1–6", "เลือกผลการตรวจ (ยังไม่บันทึก) · ใต้ปุ่มบอกว่าข้อนี้จะ \"ปิดแล้ว\" \"ยังไม่ปิด\" หรือ \"ไม่นับ\""],
      ["Ctrl + Enter", "บันทึกความเห็น แล้วไปจุดถัดไปที่ยังไม่บันทึกให้เอง · ผลเดิมไม่เปลี่ยนจะไม่บันทึกซ้ำ"],
      ["ร่าง", "เลือกผลไว้แล้วเลื่อนออกก่อนบันทึก ระบบเก็บร่างไว้ และมีปุ่ม \"กลับไปบันทึก\""],
      ["ดูทั้งหน้า", "ภาพหลักฐานกดดูทั้งหน้าได้ในที่เดิม · \"เปิดหน้าอื่นของฉบับนี้\" เลื่อนดูหน้าข้าง ๆ"],
      ["หาไม่เจอ", "ระบบไม่พบรายการในฉบับใด จะเปิดหน้าของฉบับนั้นให้หาเองได้ทันที — ไม่ได้แปลว่าไม่มีแน่นอน"],
    ] },
    { title: "ภาพรวมของรอบ", items: [
      ["หัวข้อ", "กดชื่อหัวข้อด้านซ้ายเพื่อดูเฉพาะหัวข้อนั้น · ตัวเลข = ตัดสินแล้ว/ทั้งหมด · +n = ข้อมูลเพิ่มเติม"],
      ["ตัวกรอง", "ยังไม่บันทึก · บันทึกแล้ว · ข้อมูลเพิ่มเติม · ทั้งหมด + ช่องค้น — ตัวกรองติดไปกับลิงก์"],
      ["กลับมาที่เดิม", "กด \"← ภาพรวม\" จากหน้าจุดที่ต่าง แล้วระบบเลื่อนไปที่ข้อที่ทำค้างไว้"],
      ["ระดับรายการ", "\"สรุปการเปลี่ยนแปลงระดับรายการ\" = รายการต้นทางที่มักทำให้ยอดรวมในหัวข้ออื่นเปลี่ยนตาม"],
    ] },
    { title: "ปีงบ · ตรวจก่อนส่งออกไฟล์", items: [
      ["ปีของเล่ม", "ระบบอ่านจากหัวข้อเปรียบเทียบงบประมาณในหน้าของหน่วยงาน (เล่มปี N มีงบปี N−1 กับ N)"],
      ["ยืนยันปี", "ถ้าระบบไม่แน่ใจ จะให้ยืนยันที่หน้าตรวจก่อนส่งออกไฟล์ · ปีที่ยืนยันต่างจากที่ใช้คำนวณ → สร้างรอบใหม่ (คำตัดสินเดิมไม่ตามไป)"],
      ["ส่งออก CSV", "ปุ่มขึ้นเมื่อตรวจก่อนส่งออกผ่านครบ · เซิร์ฟเวอร์ตรวจซ้ำทุกครั้งที่ดาวน์โหลด และบันทึกใน Audit"],
    ] },
    { title: "เริ่มรอบ · ประวัติ", items: [
      ["เริ่มรอบใหม่", "จากหน้ารายการรอบ: เลือกเล่ม A → ค้นหน่วยงาน → เล่ม B (เล่มที่ระบบแนะนำขึ้นก่อน)"],
      ["ประวัติการบันทึก", "ใคร บันทึกอะไร เมื่อไร — ทุกเหตุการณ์ของรอบ กรองตามชนิดได้ · กดที่ข้อเพื่อเปิดข้อนั้น"],
    ] },
  ];
</script>

<svelte:window onkeydown={onkey} />

<button class="help-btn" onclick={open} aria-label="ทำอะไรได้บ้าง (กด ?)" title="ทำอะไรได้บ้าง (กด ?)">?</button>

<dialog bind:this={dlg} class="help" aria-labelledby="help-h">
  <div class="head">
    <h2 id="help-h">ทำอะไรได้บ้าง</h2>
    <form method="dialog"><button class="btn small ghost" aria-label="ปิด">ปิด (Esc)</button></form>
  </div>
  {#each GROUPS as g (g.title)}
    <section>
      <h3>{g.title}</h3>
      <dl>
        {#each g.items as [k, v] (k)}<dt>{k}</dt><dd>{v}</dd>{/each}
      </dl>
    </section>
  {/each}
  <p class="foot">ระบบเสนอจุดที่ต่างพร้อมหลักฐาน — คนเป็นผู้ตัดสินทุกข้อ · บันทึกผลแล้ว ≠ เอกสารถูกต้อง</p>
</dialog>

<style>
  .help-btn { width: 30px; height: 30px; border-radius: 50%; border: 1px solid #cfd4dc; background: #fff; cursor: pointer;
    font-weight: 700; font-size: 1em; line-height: 1; color: var(--ink); }
  .help-btn:hover { border-color: var(--accent); color: var(--accent); }
  .help { max-width: min(760px, 94vw); max-height: 86vh; border: 0; border-radius: 18px; padding: 0 22px 16px;
    box-shadow: 0 24px 60px rgba(16, 24, 40, .25); }
  .help::backdrop { background: rgba(16, 24, 40, .35); }
  .head { position: sticky; top: 0; display: flex; align-items: center; justify-content: space-between; background: #fff;
    padding: 16px 0 8px; border-bottom: 1px solid var(--line); }
  h2 { margin: 0; font-size: 1.2em; }
  h3 { margin: 14px 0 6px; font-size: 1em; color: var(--accent); }
  dl { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 6px 14px; margin: 0; }
  dt { font-weight: 600; }
  dd { margin: 0; color: #344054; }
  .foot { margin: 16px 0 0; color: var(--muted); font-size: .9em; }
  @media (max-width: 600px) { dl { grid-template-columns: 1fr; } dd { margin-bottom: 6px; } }
</style>
