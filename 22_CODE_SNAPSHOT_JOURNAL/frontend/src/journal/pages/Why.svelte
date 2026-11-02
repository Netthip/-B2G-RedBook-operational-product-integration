<script lang="ts">
  // ทำไมถึงมีระบบนี้ + ป๊อปอัปเล่มงบประมาณสองฉบับแบบเล่มปิดเห็นหน้าปก (สีฉบับ A/B ตามแอป) — กิ๊ฟ 1 พ.ย.: ของเดิมเตี้ยไป ให้ใหญ่และเด้งขึ้น
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";
</script>

<div class="jr-pg">
  <h2>ทำไมถึงมีระบบนี้</h2>
  {#each ABOUT.why as p (p)}<p><Th s={p} /></p>{/each}
  <p class="scope jr-hand"><Th s={ABOUT.whyNote} /></p>
  <div class="scene" aria-hidden="true">
    <span class="jr-ground"></span>
    <span class="jr-pop bk a"><span class="band"></span><b class="tag tag-a">A</b><i></i><i></i><small>ฉบับตั้งต้น</small></span>
    <span class="vs">⇄</span>
    <span class="jr-pop bk b"><span class="band"></span><b class="tag tag-b">B</b><i></i><i></i><small>ฉบับที่นำมาเทียบ</small></span>
  </div>
</div>

<style>
  .scope { font-size: calc(var(--u) * 3.6); }
  /* เล่มปิดสองเล่มเห็นหน้าปก ยืนเด้งขึ้นจากหน้า — ตัวใหญ่ เอียงน้อย (−28°) จะได้ไม่เตี้ยแบน · สันสีฉบับ A/B ตามแอป · ขอบกระดาษซ้อนด้านขวา */
  .scene { position: absolute; left: calc(var(--u) * 11); right: calc(var(--u) * 11); bottom: calc(var(--u) * 9); height: calc(var(--u) * 44);
    transform-style: preserve-3d; }
  .bk { position: absolute; bottom: 0; width: 42%; height: 100%; display: flex; flex-direction: column; align-items: center;
    gap: calc(var(--u) * 1.6); padding: calc(var(--u) * 5) calc(var(--u) * 3) calc(var(--u) * 3.4) calc(var(--u) * 5); background: #fff;
    border-radius: calc(var(--u) * .6) calc(var(--u) * 1.4) calc(var(--u) * 1.4) calc(var(--u) * .6);
    box-shadow: inset calc(var(--u) * 2.4) 0 0 var(--spine), inset calc(var(--u) * 2.9) 0 0 rgba(16, 24, 40, .12),
      calc(var(--u) * .7) calc(var(--u) * .5) 0 #eef0f3, calc(var(--u) * 1.4) calc(var(--u) * 1) 0 #dfe3e9,
      0 calc(var(--u) * 1.6) calc(var(--u) * 3) rgba(16, 24, 40, .2); }
  .bk.a { left: 2%; rotate: -4deg; --spine: var(--a); --jr-rise: -28deg; }
  .bk.b { right: 2%; rotate: 3deg; --spine: var(--b); --jr-rise: -28deg; --jr-delay: .8s; }
  .band { position: absolute; left: calc(var(--u) * 2.4); right: 0; top: 46%; height: calc(var(--u) * 3); background: var(--jr-red); }
  .bk .tag { width: calc(var(--u) * 10); height: calc(var(--u) * 10); font-size: calc(var(--u) * 5.6); border-radius: calc(var(--u) * 2.2); }
  .bk i { display: block; width: 70%; height: calc(var(--u) * 1.3); border-radius: 99px; background: #d0d5dd; }
  .bk i + i { width: 48%; }
  .bk small { margin-top: auto; font-size: calc(var(--u) * 3.2); line-height: 1.3; color: #344054; text-align: center; }
  .vs { position: absolute; left: 50%; top: 40%; translate: -50% -50%; display: grid; place-items: center; width: calc(var(--u) * 8);
    height: calc(var(--u) * 8); border-radius: 50%; background: var(--jr-navy); color: #fff; font-size: calc(var(--u) * 4.4); }
</style>
