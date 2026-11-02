<script lang="ts">
  // ดูจุดที่ต่าง — ป๊อปอัปหน้า PDF ฉบับ A | B ยืนคู่กัน มีแว่นขยายส่องบรรทัดที่ต่าง (ภาพประกอบ ไม่มีตัวเลขหรือข้อความจริง)
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";
</script>

<div class="jr-pg">
  <h2>{ABOUT.steps[1][1]}</h2>
  <ul class="key">
    {#each ABOUT.compareKey as [k, t, d] (k)}<li><span class={`sw ${k}`} aria-hidden="true"></span><span><b>{t}</b><br /><Th s={d} /></span></li>{/each}
  </ul>
  <div class="scene" aria-hidden="true">
    <span class="jr-ground"></span>
    <span class="jr-pop sh a"><b class="tag tag-a">A</b><i></i><i></i><i></i><i class="hl"></i><i></i><i></i><i></i></span>
    <span class="jr-pop sh b"><b class="tag tag-b">B</b><i></i><i></i><i></i><i class="hl"></i><i></i><i></i><i></i>
      <span class="lens"></span></span>
  </div>
  <p class="cap">ภาพประกอบ</p>
</div>

<style>
  .scene { position: absolute; left: calc(var(--u) * 10); right: calc(var(--u) * 10); bottom: calc(var(--u) * 15); height: calc(var(--u) * 50);
    transform-style: preserve-3d; }
  .sh { position: absolute; bottom: 0; width: 46%; height: 100%; display: flex; flex-direction: column; gap: calc(var(--u) * 2.4);
    padding: calc(var(--u) * 3.4); background: #fff; border-top: calc(var(--u) * 1.2) solid var(--doc);
    box-shadow: 0 calc(var(--u) * .8) calc(var(--u) * 2.2) rgba(16, 24, 40, .18); }
  .sh.a { left: 0; --doc: var(--a); --jr-rise: -40deg; }
  .sh.b { right: 0; --doc: var(--b); --jr-rise: -40deg; --jr-delay: .74s; }
  .sh .tag { width: calc(var(--u) * 6.4); height: calc(var(--u) * 6.4); font-size: calc(var(--u) * 3.6); border-radius: calc(var(--u) * 1.5);
    margin-bottom: calc(var(--u) * 1); }
  .sh i { display: block; height: calc(var(--u) * 1.4); border-radius: 99px; background: #d0d5dd; }
  .sh i:nth-of-type(3n + 2) { width: 70%; }
  .sh i:nth-of-type(3n) { width: 86%; }
  .sh i.hl { background: var(--warn-line); box-shadow: 0 0 0 calc(var(--u) * .8) var(--warn-bg); }
  .lens { position: absolute; right: 12%; top: 40%; width: calc(var(--u) * 15); height: calc(var(--u) * 15); border-radius: 50%;
    border: calc(var(--u) * 1.3) solid var(--jr-navy); background: rgba(255, 255, 255, .28); animation: bob 2.8s ease-in-out infinite; }
  .lens::after { content: ""; position: absolute; left: 82%; top: 86%; width: calc(var(--u) * 8); height: calc(var(--u) * 2);
    border-radius: 99px; background: var(--jr-navy); rotate: 45deg; transform-origin: 0 50%; }
  .key { list-style: none; margin: 0; padding: 0; display: grid; gap: calc(var(--u) * 1.6); }
  .key li { display: grid; grid-template-columns: calc(var(--u) * 7) 1fr; align-items: start; gap: calc(var(--u) * 2.4); line-height: 1.45; }
  .key b { color: var(--jr-navy); }
  .sw { margin-top: calc(var(--u) * 1.6); width: calc(var(--u) * 7); height: calc(var(--u) * 3); border-radius: 99px; }
  .sw.hl { background: var(--warn-line); box-shadow: 0 0 0 calc(var(--u) * .7) var(--warn-bg); }
  .sw.ab { background: linear-gradient(90deg, var(--a) 0 48%, transparent 48% 52%, var(--b) 52%); }
  .cap { position: absolute; right: calc(var(--u) * 10); bottom: calc(var(--u) * 7); margin: 0; font-size: calc(var(--u) * 2.9); color: var(--muted); }
  @keyframes bob { 0%, 100% { translate: 0 0; } 50% { translate: calc(var(--u) * -1.6) calc(var(--u) * -1); } }
</style>
