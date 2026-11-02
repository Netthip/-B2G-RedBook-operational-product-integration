<script lang="ts">
  // ปกหลังด้านใน: ทางไปใช้งานจริง (ทางเข้าเดียวกับเมนูหลัก) + อ่านอีกครั้ง
  import { link } from "../../lib/router.svelte";

  let { restart }: { restart: () => void } = $props();
</script>

<div class="jr-pg">
  <h2>เริ่มใช้งาน</h2>
  <nav class="acts" aria-label="ไปใช้งานระบบ">
    <a class="btn" href="/r/lib" onclick={link}>ไปคลังเล่มงบประมาณ →</a>
    <a class="btn ghost" href="/r/p/new?kind=cross" onclick={link}>ตรวจเล่มงบประมาณข้ามปี</a>
    <a class="btn ghost" href="/r/p/new?kind=same" onclick={link}>ตรวจเล่มงบประมาณในปีเดียวกัน</a>
  </nav>
  <p class="more"><a href="/r/about" onclick={link}>เกี่ยวกับระบบ</a> · <a href="/r/dev" onclick={link}>ส่วนผู้พัฒนา</a></p>
  <button class="again jr-hand" type="button" onclick={restart}>↺ อ่านอีกครั้ง</button>
</div>

<style>
  .acts { display: flex; flex-direction: column; gap: calc(var(--u) * 2.6); margin-top: calc(var(--u) * 6); }
  .acts .btn { justify-content: flex-start; font-size: calc(var(--u) * 3.8); }
  .more { margin-top: calc(var(--u) * 6); color: var(--muted); }
  .more a { color: var(--jr-navy); }
  .again { position: absolute; right: calc(var(--u) * 10); bottom: calc(var(--u) * 9); border: 0; background: none; padding: calc(var(--u) * 1.4);
    font-size: calc(var(--u) * 4.4); cursor: pointer; rotate: -3deg; }
</style>
