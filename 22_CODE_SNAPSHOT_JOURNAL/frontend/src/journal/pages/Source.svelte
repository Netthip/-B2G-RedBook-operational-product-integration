<script lang="ts">
  // ข้อมูลมาจากไหน — สองทางที่ได้เอกสารมาเทียบ: ① เล่มที่มีในระบบ (ชั้นเล่มที่ดาวน์โหลดไว้แล้ว) ② ไฟล์ในเครื่อง (คลิกเลือก/ลากวาง PDF)
  // ชื่อสองทางตรงกับปุ่มบนหน้าเริ่มรอบเทียบ (PairNew) · หนึ่งรอบเทียบใช้ทางเดียวกันทั้งฉบับ A และ B — ระบบยังเลือกปนกันไม่ได้ (กิ๊ฟ 1 พ.ย.: ยังไม่ต้องทำ)
  // เลขทาง 1/2 ใช้เลขอารบิกแบบหน้า "ใช้งาน 3 ขั้น" · "หรือ" ไม่ซ่อนจากโปรแกรมอ่านหน้าจอ จะได้ฟังรู้ว่าเลือกทางเดียว
  // ภาพจึงมีป้าย A/B อยู่ในทั้งสองทาง และเส้นจากสองทางไปรวมที่คู่เทียบเดียวกัน (ไม่ลากทาง ๑ → A ทาง ๒ → B)
  // ภาพประกอบล้วน ไม่มีชื่อหน่วยงาน ตัวเลข หรือที่อยู่เว็บจริง
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";
</script>

<div class="jr-pg">
  <h2>ข้อมูลมาจากไหน</h2>
  <p><Th s={ABOUT.source} /></p>

  <div class="ways">
    <div class="way">
      <div class="art" aria-hidden="true">
        <span class="jr-ground"></span>
        <span class="jr-pop shelf">
          <i class="v"></i><i class="v"><b class="tag tag-a">A</b></i><i class="v"></i><i class="v"><b class="tag tag-b">B</b></i><i class="v lean"></i>
          <span class="dl"></span>
        </span>
      </div>
      <h3><span class="no">1</span>เล่มที่มีในระบบ</h3>
      <p class="d">ระบบดาวน์โหลดเล่มที่เผยแพร่บนเว็บไซต์ <span class="jr-nw">เก็บไว้ให้แล้ว</span> <span class="jr-nw">เลือกได้ทันที</span></p>
    </div>

    <span class="or jr-hand">หรือ</span>

    <div class="way">
      <div class="art" aria-hidden="true">
        <span class="jr-ground"></span>
        <span class="jr-pop drop">
          <span class="file fa"><b class="tag tag-a">A</b><em>PDF</em></span>
          <span class="file fb"><b class="tag tag-b">B</b><em>PDF</em></span>
          <span class="ptr"></span>
        </span>
      </div>
      <h3><span class="no">2</span>ไฟล์ในเครื่อง</h3>
      <p class="d">คลิกเลือกไฟล์ PDF จากคอมพิวเตอร์ของตัวเอง หรือลากไฟล์มาวาง</p>
    </div>
  </div>

  <svg class="flow" viewBox="0 0 80 10" preserveAspectRatio="none" aria-hidden="true">
    <path d="M20 0 C20 6 40 3 40 9.4" /><path d="M60 0 C60 6 40 3 40 9.4" /><path class="hd" d="M38.2 7.4 L40 9.6 L41.8 7.4" />
  </svg>

  <div class="pair">
    <span class="slot"><b class="tag tag-a">A</b>ฉบับตั้งต้น</span>
    <span class="vs" aria-hidden="true">⇄</span>
    <span class="slot"><b class="tag tag-b">B</b>ฉบับที่นำมาเทียบ</span>
  </div>
  <p class="rule jr-hand">ฉบับ A และ B ต้องมาจาก<span class="jr-nw">ทางเดียวกัน</span></p>
</div>

<style>
  .ways { position: relative; display: grid; grid-template-columns: 1fr 1fr; gap: calc(var(--u) * 8); margin-top: calc(var(--u) * 4);
    transform-style: preserve-3d; }
  .way { display: flex; flex-direction: column; align-items: center; text-align: center; transform-style: preserve-3d; }
  .art { position: relative; width: 100%; height: calc(var(--u) * 25); transform-style: preserve-3d; }
  .way h3 { display: flex; align-items: center; gap: calc(var(--u) * 1.4); margin: calc(var(--u) * 3.4) 0 calc(var(--u) * 1);
    font-size: calc(var(--u) * 4); line-height: 1.3; color: var(--jr-navy); }
  .no { display: inline-grid; place-items: center; flex: none; width: calc(var(--u) * 5.6); height: calc(var(--u) * 5.6); border-radius: 50%;
    background: var(--jr-navy); color: #fff; font-size: calc(var(--u) * 3.2); }
  .way .d { margin: 0; font-size: calc(var(--u) * 3.5); line-height: 1.5; color: #344054; }
  .or { position: absolute; left: 50%; top: calc(var(--u) * 12); translate: -50% 0; font-size: calc(var(--u) * 4.2); }
  .tag { width: calc(var(--u) * 4.4); height: calc(var(--u) * 4.4); font-size: calc(var(--u) * 2.7); border-radius: 50%; }

  /* ① ชั้นเล่ม: แผ่นชั้น + สันเล่มยืนเรียง (เงิน-น้ำเงิน-ขาว แถบแดงเล่มเดียว) · เล่ม A/B อยู่บนชั้นเดียวกัน + ป้ายดาวน์โหลด */
  .shelf { position: absolute; left: 6%; right: 6%; bottom: 0; height: 100%; display: flex; align-items: flex-end; gap: calc(var(--u) * .8);
    padding: 0 calc(var(--u) * 2.4) calc(var(--u) * 2); --jr-rise: -40deg;
    background: linear-gradient(#c3cad5, #c3cad5) bottom / 100% calc(var(--u) * 2) no-repeat; }
  .v { position: relative; flex: 1; font-style: normal; height: 72%; display: flex; justify-content: center; align-items: flex-end; padding-bottom: calc(var(--u) * 1.6);
    border-radius: calc(var(--u) * .6) calc(var(--u) * .6) 0 0; background: #fff; box-shadow: inset 0 0 0 calc(var(--u) * .4) #d0d5dd; }
  .v::after { content: ""; position: absolute; left: 22%; right: 22%; top: 14%; height: calc(var(--u) * 1.1); border-radius: 99px; background: #d0d5dd; }
  .v:nth-child(2) { height: 86%; background: var(--jr-navy); box-shadow: none; }
  .v:nth-child(2)::after { background: rgba(255, 255, 255, .55); }
  .v:nth-child(3) { height: 76%; background: #e4e7ec; }
  .v:nth-child(3)::before { content: ""; position: absolute; left: 0; right: 0; top: 38%; height: calc(var(--u) * 1.8); background: var(--jr-red); }
  .v:nth-child(4) { height: 90%; background: #8ea2c4; box-shadow: none; }
  .v:nth-child(4)::after { background: rgba(255, 255, 255, .6); }
  .v .tag { box-shadow: 0 0 0 calc(var(--u) * .5) #fff; }
  .v.lean { height: 68%; rotate: 9deg; transform-origin: 0 100%; }
  /* ป้ายดาวน์โหลด: วงกลม + ลูกศรลงบนถาด (วาดด้วย CSS) */
  .dl { position: absolute; right: calc(var(--u) * -1.8); top: calc(var(--u) * -2); width: calc(var(--u) * 8); height: calc(var(--u) * 8);
    border-radius: 50%; background: #fff;
    box-shadow: inset 0 0 0 calc(var(--u) * .6) var(--jr-navy), 0 calc(var(--u) * .4) calc(var(--u) * 1) rgba(16, 24, 40, .16); }
  .dl::before { content: ""; position: absolute; left: 50%; top: 20%; width: calc(var(--u) * 3.6); height: calc(var(--u) * 3.6); translate: -50% 0;
    background: var(--jr-navy); clip-path: polygon(38% 0, 62% 0, 62% 48%, 86% 48%, 50% 92%, 14% 48%, 38% 48%); }
  .dl::after { content: ""; position: absolute; left: 28%; right: 28%; bottom: 22%; height: calc(var(--u) * .7); border-radius: 99px; background: var(--jr-navy); }

  /* ② ไฟล์ในเครื่อง: กรอบเส้นประแบบช่องวางไฟล์ของแอป + ไฟล์ PDF ฉบับ A/B + ลูกศรเมาส์กำลังคลิก */
  .drop { position: absolute; left: 6%; right: 6%; bottom: 0; height: 100%; border-radius: calc(var(--u) * 2.4);
    border: calc(var(--u) * .5) dashed #98a2b3; background: #fff; --jr-rise: -40deg; --jr-delay: .76s; }
  .file { position: absolute; bottom: calc(var(--u) * 2.2); width: calc(var(--u) * 13); height: 72%; display: flex; flex-direction: column;
    justify-content: space-between; align-items: flex-start; padding: calc(var(--u) * 1.2); background: #f2f4f7; border-radius: calc(var(--u) * .8);
    clip-path: polygon(0 0, 70% 0, 100% 22%, 100% 100%, 0 100%); }
  .file::before { content: ""; position: absolute; right: 0; top: 0; width: 30%; height: 22%; background: #d0d5dd; }
  .file.fa { left: 7%; rotate: -6deg; }
  .file.fb { left: 45%; rotate: 4deg; background: #e8eef9; }
  .file em { align-self: center; padding: calc(var(--u) * .2) calc(var(--u) * 1); border-radius: calc(var(--u) * .6); background: var(--jr-navy);
    color: #fff; font-style: normal; font-weight: 700; font-size: calc(var(--u) * 2.5); }
  .ptr { position: absolute; left: 72%; top: 50%; width: calc(var(--u) * 6.6); height: calc(var(--u) * 8.8); background: var(--jr-navy);
    clip-path: polygon(0 0, 0 78%, 24% 60%, 40% 96%, 56% 89%, 41% 54%, 72% 54%); transform-origin: 0 0; animation: tap 2.4s ease-in-out infinite; }
  .drop::after { content: ""; position: absolute; left: 72%; top: 50%; width: calc(var(--u) * 6); height: calc(var(--u) * 6); translate: -50% -50%;
    border-radius: 50%; border: calc(var(--u) * .5) solid var(--jr-navy); opacity: 0; animation: ring 2.4s ease-out infinite; }
  @keyframes tap { 0%, 30%, 100% { scale: 1; } 38% { scale: .86; } 46% { scale: 1; } }
  @keyframes ring { 0%, 36% { opacity: 0; scale: .4; } 42% { opacity: .7; } 70%, 100% { opacity: 0; scale: 1.5; } }
  @media (prefers-reduced-motion: reduce) { .ptr, .drop::after { animation: none; } }

  /* สองทางไหลมารวมที่คู่เทียบเดียวกัน */
  .flow { display: block; width: 100%; height: calc(var(--u) * 9); margin: calc(var(--u) * 2) 0 calc(var(--u) * .4); overflow: visible; }
  .flow path { fill: none; stroke: #98a2b3; stroke-width: calc(var(--u) * .45); stroke-dasharray: calc(var(--u) * 1.4) calc(var(--u) * 1.2);
    vector-effect: non-scaling-stroke; stroke-linecap: round; stroke-linejoin: round; }
  .flow .hd { stroke: var(--jr-navy); stroke-dasharray: none; }
  .pair { display: flex; align-items: center; justify-content: center; gap: calc(var(--u) * 2); width: fit-content; margin: 0 auto;
    padding: calc(var(--u) * 1.8) calc(var(--u) * 2.4); border-radius: calc(var(--u) * 2.4); background: #fff;
    box-shadow: inset 0 0 0 calc(var(--u) * .4) #d0d5dd, 0 calc(var(--u) * .6) calc(var(--u) * 1.8) rgba(16, 24, 40, .12); }
  .slot { display: inline-flex; align-items: center; gap: calc(var(--u) * 1.2); font-size: calc(var(--u) * 3.3); white-space: nowrap; }
  .slot .tag { width: calc(var(--u) * 5.4); height: calc(var(--u) * 5.4); font-size: calc(var(--u) * 3.2); }
  .vs { font-size: calc(var(--u) * 4.4); color: var(--jr-navy); }
  .rule { margin: calc(var(--u) * 3.2) 0 0; text-align: center; font-size: calc(var(--u) * 3.6); line-height: 1.45; }
</style>
