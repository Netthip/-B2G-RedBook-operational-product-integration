<script lang="ts">
  // ปกหน้า: ปกขาวคาดแดงแบบเล่มงบประมาณจริง (แถบแนวนอน + สันเทา แบบเดียวกับคลังเล่ม) + โพลารอยด์ภาพประกอบหน้าหลักฐาน A | B
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";
</script>

<div class="cv">
  <span class="kick">สมุดบันทึกของระบบ</span>
  <h2>RedBook<br />Verify</h2>
  <p class="lede"><Th s={ABOUT.lead[0]} /></p>
  <span class="band" aria-hidden="true"></span>
  <figure class="jr-pol pol" aria-hidden="true">
    <span class="jr-tape t"></span>
    <span class="mini">
      <span class="sheet"><b class="tag tag-a">A</b><i></i><i></i><i class="hl"></i><i></i><i></i></span>
      <span class="sheet"><b class="tag tag-b">B</b><i></i><i></i><i class="hl"></i><i></i><i></i></span>
    </span>
    <figcaption>หน้าหลักฐาน A | B</figcaption>
  </figure>
  <p class="open jr-hand jr-booktip">เปิดสมุด →</p>
</div>

<style>
  .cv { position: absolute; inset: 0; padding: calc(var(--u) * 10) calc(var(--u) * 9) calc(var(--u) * 8) calc(var(--u) * 12);
    background: #fff; color: var(--ink); border-radius: 0 calc(var(--u) * 1.6) calc(var(--u) * 1.6) 0;
    box-shadow: inset calc(var(--u) * 2.2) 0 0 #e4e7ec, 0 calc(var(--u) * 1.6) calc(var(--u) * 5) rgba(16, 24, 40, .2); }
  .kick { display: inline-block; padding: calc(var(--u) * .7) calc(var(--u) * 2.6); border-radius: 999px; background: var(--jr-navy);
    color: #fff; font-size: calc(var(--u) * 3.1); font-weight: 600; }
  h2 { margin: calc(var(--u) * 5) 0 0; font-size: calc(var(--u) * 12); line-height: 1.02; color: var(--jr-navy); letter-spacing: -.01em; }
  .lede { margin: calc(var(--u) * 3.4) 0 0; font-size: calc(var(--u) * 4.4); color: #344054; }
  .band { position: absolute; left: 0; right: 0; top: 58%; height: calc(var(--u) * 4.2); background: var(--jr-red); }
  .pol { position: absolute; right: calc(var(--u) * 9); top: 50%; width: calc(var(--u) * 44); rotate: 4deg; }
  .t { left: 30%; top: calc(var(--u) * -2.6); rotate: -5deg; }
  .mini { display: grid; grid-template-columns: 1fr 1fr; gap: calc(var(--u) * 2); padding: calc(var(--u) * 2.6); background: #eef0f3; }
  .sheet { display: flex; flex-direction: column; gap: calc(var(--u) * 1.3); padding: calc(var(--u) * 1.8); background: #fff;
    box-shadow: 0 calc(var(--u) * .3) calc(var(--u) * .8) rgba(16, 24, 40, .12); }
  .sheet .tag { width: calc(var(--u) * 4.6); height: calc(var(--u) * 4.6); font-size: calc(var(--u) * 2.8); border-radius: calc(var(--u) * 1.2);
    margin-bottom: calc(var(--u) * .6); }
  .sheet i { display: block; height: calc(var(--u) * 1); border-radius: 99px; background: #d0d5dd; }
  .sheet i:nth-of-type(2n) { width: 74%; }
  .sheet i.hl { background: var(--warn-line); box-shadow: 0 0 0 calc(var(--u) * .5) var(--warn-bg); }
  .open { position: absolute; left: calc(var(--u) * 12); bottom: calc(var(--u) * 8); margin: 0; font-size: calc(var(--u) * 5); }
</style>
