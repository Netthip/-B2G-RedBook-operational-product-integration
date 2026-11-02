<script lang="ts">
  // ระบบไม่ได้ทำอะไร — แผนภาพแบ่งงาน "ระบบช่วย → คนตรวจ" + ตรายาง "คนเป็นผู้ตัดสิน" (ข้อความท้ายทุกหน้าของแอป)
  // กิ๊ฟ 1 พ.ย.: หน้าเดิมโล่ง อยากให้เห็นว่างานยังต้องมีคนตรวจ ระบบช่วยให้ทำได้ไวขึ้น ไม่ได้มาแทนคน
  // พูดได้แค่ที่ระบบทำจริง (ชี้จุดต่าง + เปิดหน้าหลักฐานคู่กัน · คนบันทึกผลทีละจุด) · "เร็วขึ้น" เป็นความตั้งใจ ยังไม่ใช่ผลวัด จึงเขียนว่า "ตั้งใจ"
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";
  const SYS = ["ชี้จุดที่ตัวเลขหรือข้อความต่างกัน", "เปิดหน้าหลักฐานสองฉบับคู่กัน", "ไม่ต้องไล่หาเองทีละหน้า"];
  const HUMAN = ["ดูหลักฐานทุกจุด", "ตัดสินว่าต่างจริงไหม ถูกหรือผิด", "บันทึกความเห็น และรับผิดชอบผลตรวจ"];
</script>

<div class="jr-pg">
  <h2>ระบบไม่ได้ทำอะไร</h2>
  <p><Th s={ABOUT.notDo} /></p>

  <div class="split">
    <section class="jr-note col sys">
      <span class="jr-tape blue" aria-hidden="true"></span>
      <h3><span class="ic lens" aria-hidden="true"></span>ระบบช่วย</h3>
      <ul>{#each SYS as t (t)}<li><Th s={t} /></li>{/each}</ul>
    </section>
    <span class="go" aria-hidden="true">→</span>
    <section class="jr-note mint col man">
      <span class="jr-tape mint" aria-hidden="true"></span>
      <h3><span class="ic person" aria-hidden="true"></span>คนตรวจ</h3>
      <ul>{#each HUMAN as t (t)}<li><Th s={t} /></li>{/each}</ul>
    </section>
  </div>

  <p class="say jr-hand">ระบบเป็นผู้ช่วย <span class="jr-nw">ตั้งใจให้ตรวจได้เร็วขึ้น</span><br /><b>ไม่ได้มาแทนคน</b></p>
  <div class="scene" aria-hidden="true">
    <span class="jr-ground"></span>
    <span class="jr-pop sp"><span class="jr-stamp">{ABOUT.rule[1].replace("เป็น", "เป็น\n")}</span></span>
  </div>
</div>

<style>
  .split { display: grid; grid-template-columns: 1fr auto 1fr; align-items: stretch; gap: calc(var(--u) * 1.6); margin-top: calc(var(--u) * 5); }
  .col { padding-top: calc(var(--u) * 4); }
  .sys { rotate: -1.5deg; }
  .man { rotate: 1.2deg; }
  .col .jr-tape { left: 50%; top: calc(var(--u) * -2.6); translate: -50% 0; width: calc(var(--u) * 14); }
  .col h3 { display: flex; align-items: center; gap: calc(var(--u) * 1.6); margin: 0 0 calc(var(--u) * 1.6); font-size: calc(var(--u) * 4.2);
    line-height: 1.3; color: var(--jr-navy); }
  .col ul { margin: 0; padding: 0; list-style: none; display: grid; gap: calc(var(--u) * 1.4); }
  .col li { position: relative; padding-left: calc(var(--u) * 3.4); font-size: calc(var(--u) * 3.3); line-height: 1.45; }
  .col li::before { content: ""; position: absolute; left: 0; top: .62em; width: calc(var(--u) * 1.5); height: calc(var(--u) * 1.5); border-radius: 50%;
    background: #98a2b3; }
  .man li::before { background: var(--jr-navy); }
  .go { align-self: center; font-size: calc(var(--u) * 5.4); color: var(--jr-navy); }

  /* ไอคอนวาดด้วย CSS: แว่นขยาย (ระบบ) · คน (หัว + ไหล่) */
  .ic { position: relative; flex: none; width: calc(var(--u) * 5.6); height: calc(var(--u) * 5.6); }
  .lens::before { content: ""; position: absolute; left: 0; top: 0; width: 66%; height: 66%; border-radius: 50%;
    border: calc(var(--u) * .7) solid #667085; box-sizing: border-box; }
  .lens::after { content: ""; position: absolute; left: 58%; top: 58%; width: 44%; height: calc(var(--u) * .9); border-radius: 99px; background: #667085;
    rotate: 45deg; transform-origin: 0 50%; }
  .person::before { content: ""; position: absolute; left: 30%; top: 0; width: 40%; height: 40%; border-radius: 50%; background: var(--jr-navy); }
  .person::after { content: ""; position: absolute; left: 8%; right: 8%; bottom: 0; height: 48%; border-radius: 99px 99px calc(var(--u) * .6) calc(var(--u) * .6);
    background: var(--jr-navy); }

  .say { width: calc(var(--u) * 50); margin: calc(var(--u) * 7) 0 0;
    font-size: calc(var(--u) * 4); line-height: 1.5; }
  .say b { font-size: calc(var(--u) * 5); }
  .scene { position: absolute; right: calc(var(--u) * 9); bottom: calc(var(--u) * 8); width: calc(var(--u) * 30); height: calc(var(--u) * 30);
    transform-style: preserve-3d; }
  .sp { position: absolute; inset: 0; display: grid; place-items: center; --jr-rise: -38deg; }
  .sp .jr-stamp { width: calc(var(--u) * 27); height: calc(var(--u) * 27); font-size: calc(var(--u) * 4.4); white-space: pre-line; }
</style>
