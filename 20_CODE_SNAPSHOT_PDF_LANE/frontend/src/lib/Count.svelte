<script lang="ts">
  // ตัวเลขนับขึ้นนุ่ม ๆ เมื่อค่าเปลี่ยน (ลดการเคลื่อนไหวตามค่าระบบ)
  import { untrack } from "svelte";
  let { to }: { to: number } = $props();
  let shown = $state(0);
  $effect(() => {
    const target = to, from = untrack(() => shown), t0 = performance.now(), dur = 600;
    if (matchMedia("(prefers-reduced-motion: reduce)").matches || document.hidden || from === target) { shown = target; return; }
    let raf = 0;
    const step = (t: number) => {
      const k = Math.min(1, (t - t0) / dur);
      shown = Math.round(from + (target - from) * (1 - (1 - k) ** 3));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    // หน้าต่างที่ไม่ได้วาด (ถูกบัง/ย่อ) ไม่เรียก requestAnimationFrame — ตัวเลขต้องถึงค่าจริงเสมอ ไม่ค้างค่าเก่า
    const done = setTimeout(() => { cancelAnimationFrame(raf); shown = target; }, dur + 150);
    return () => { cancelAnimationFrame(raf); clearTimeout(done); };
  });
</script>

{shown}
