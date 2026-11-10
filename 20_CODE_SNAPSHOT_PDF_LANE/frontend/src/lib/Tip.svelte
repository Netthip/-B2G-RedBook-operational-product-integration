<script lang="ts">
  // คำอธิบายสั้นเมื่อชี้/โฟกัส (ใบงาน #44 Warm Tooltip) — แทน title ของเบราว์เซอร์ที่เปิดด้วยแป้นพิมพ์ไม่ได้และขึ้นช้า
  // ใช้: <Tip text="…"><button …>‹</button></Tip> · คำศัพท์: <Tip text="…" term>ข้อมูลเพิ่มเติม</Tip>
  // ปุ่ม/คำที่อยู่ข้างใน ได้ aria-describedby ชี้มาที่ข้อความนี้ · Esc ปิด · ขึ้นด้านบนก่อน (ไม่บังภาพหลักฐานที่อยู่ด้านล่าง)
  // ข้อความสั้นไม่เกิน ~1 บรรทัด · ไม่เบลอ ไม่เรืองแสง · ระบบตั้งลดการเคลื่อนไหว = ขึ้นทันที
  import type { Snippet } from "svelte";
  import { reduced } from "./motion";
  let { text, term = false, children }: { text: string; term?: boolean; children: Snippet } = $props();

  const id = `tip-${Math.random().toString(36).slice(2, 9)}`;
  let open = $state(false);
  let below = $state(false);
  let dx = $state(0);
  let wrap = $state<HTMLElement>();
  let bub = $state<HTMLElement>();
  let timer = 0;

  // ปุ่ม/ลิงก์ข้างในได้ aria-describedby (คำศัพท์: ตัว span ที่โฟกัสได้เอง)
  $effect(() => {
    const t = term ? wrap : wrap?.querySelector<HTMLElement>("button, a, [tabindex]");
    t?.setAttribute("aria-describedby", id);
  });

  function show(now: boolean) {
    clearTimeout(timer);
    timer = window.setTimeout(() => { open = true; }, now || reduced() ? 0 : 250);
  }
  function hide() { clearTimeout(timer); open = false; }

  // วางให้อยู่ในจอ: บนก่อน · พื้นที่ด้านบนไม่พอ → ล่าง · ชิดขอบจอไม่ล้นซ้าย/ขวา
  $effect(() => {
    if (!open || !wrap || !bub) return;
    const w = wrap.getBoundingClientRect(), b = bub.getBoundingClientRect();
    below = w.top - b.height - 10 < 64;
    const mid = w.left + w.width / 2, half = b.width / 2, pad = 8;
    dx = Math.min(Math.max(mid, half + pad), innerWidth - half - pad) - mid;
    if (!reduced()) bub.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 120, easing: "ease-out" });
  });
  $effect(() => () => clearTimeout(timer));
</script>

<svelte:window onkeydown={(e) => { if (open && e.key === "Escape") hide(); }} />

<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_static_element_interactions -->
<span class="tip" class:term bind:this={wrap} tabindex={term ? 0 : undefined}
      onmouseenter={() => show(false)} onmouseleave={hide} onfocusin={() => show(true)} onfocusout={hide}>
  {@render children()}
  <span class="bub" class:open class:below role="tooltip" {id} bind:this={bub} style:--tip-dx="{dx}px">{text}</span>
</span>

<style>
  .tip { position: relative; display: inline-flex; }
  .term { text-decoration: underline dotted #98a2b3; text-underline-offset: 3px; cursor: help; border-radius: 4px; }
  .bub { position: absolute; left: 50%; bottom: calc(100% + 8px); z-index: 60; transform: translateX(calc(-50% + var(--tip-dx, 0px)));
    padding: 5px 10px; border-radius: 8px; background: var(--accent, #0e2f6e); color: #fff; font-size: .85rem; font-weight: 400;
    line-height: 1.4; white-space: nowrap; max-width: min(420px, calc(100vw - 16px)); overflow: hidden; text-overflow: ellipsis;
    box-shadow: 0 4px 12px rgba(16, 24, 40, .16); pointer-events: none; visibility: hidden; }
  .bub.below { bottom: auto; top: calc(100% + 8px); }
  .bub.open { visibility: visible; }
  @media print { .bub { display: none; } }
</style>
