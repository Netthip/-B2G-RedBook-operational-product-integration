<script lang="ts">
  // ด้านในปก: ประโยคนำของหน้าเกี่ยวกับระบบ
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";
</script>

<div class="jr-pg">
  <span class="jr-tape blue t"></span>
  <p class="hi jr-hand">สมุดเล่มนี้เล่าว่า…</p>
  <p class="lead"><Th s={ABOUT.lead[0]} /><br /><span class="jr-mark"><Th s={ABOUT.lead[1]} /></span></p>
  <span class="sticker" aria-hidden="true">RV</span>
  <p class="tip jr-note jr-booktip">แตะครึ่งขวาของสมุดเพื่อพลิกหน้า หรือกดปุ่มลูกศรบนแป้นพิมพ์</p>
</div>

<style>
  .t { left: calc(var(--u) * 8); top: calc(var(--u) * 5); rotate: -8deg; }
  .hi { margin-top: calc(var(--u) * 8); font-size: calc(var(--u) * 5); }
  .lead { font-size: calc(var(--u) * 6); line-height: 1.5; font-weight: 600; color: var(--ink); }
  .sticker { position: absolute; right: calc(var(--u) * 11); bottom: calc(var(--u) * 30); display: grid; place-items: center;
    width: calc(var(--u) * 17); height: calc(var(--u) * 17); border-radius: 30%; rotate: 9deg;
    background: linear-gradient(135deg, #0e2f6e, #1d4690); color: #fff; font-weight: 800; font-size: calc(var(--u) * 6.4);
    box-shadow: 0 0 0 calc(var(--u) * 1.2) #fff, 0 calc(var(--u) * 1.4) calc(var(--u) * 3) rgba(16, 24, 40, .22); }
  .tip { position: absolute; left: calc(var(--u) * 10); right: calc(var(--u) * 30); bottom: calc(var(--u) * 10); margin: 0;
    font-size: calc(var(--u) * 3.2); rotate: -1.5deg; }
</style>
