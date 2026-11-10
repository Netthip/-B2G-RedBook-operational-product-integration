<script lang="ts">
  // ปุ่มกดค้าง (ใบงาน #44 Hold Button) — ใช้กับการบันทึกทั้งชุดเท่านั้น: กดค้าง ~1 วินาทีจึงทำงาน · ปล่อยก่อน = ยกเลิก
  // แป้นพิมพ์: กด Enter หรือ Space ค้างไว้ที่ปุ่ม · hold = false → ปุ่มธรรมดา กดครั้งเดียวทำงาน (ไม่เปลี่ยนการบันทึกจุดเดียว)
  // ไม่ได้แทนการทวนหลักฐาน: จะมีชุดให้บันทึกได้ต้องทวนและยืนยันทีละจุดตามกติกาเดิมก่อน (Bo #44) — ปุ่มนี้แค่กันกดพลาด
  // ระบบตั้งลดการเคลื่อนไหว = ไม่มีแถบวิ่ง ยังต้องกดค้างเท่าเดิม
  import type { Snippet } from "svelte";
  import { reduced } from "./motion";
  let { hold, disabled = false, cls = "", hint, onfire, children }:
    { hold: boolean; disabled?: boolean; cls?: string; hint: string; onfire: () => void; children: Snippet } = $props();

  const MS = 1000;
  const id = `hold-${Math.random().toString(36).slice(2, 9)}`;
  let fill = $state<HTMLElement>();
  let holding = $state(false);
  let timer = 0;
  let anim: Animation | undefined;

  function begin() {
    if (!hold || disabled || holding) return;
    holding = true;
    timer = window.setTimeout(() => { stop(); onfire(); }, MS);
    if (fill && !reduced()) anim = fill.animate([{ transform: "scaleX(0)" }, { transform: "scaleX(1)" }], { duration: MS, easing: "linear", fill: "forwards" });
  }
  function stop() { clearTimeout(timer); anim?.cancel(); anim = undefined; holding = false; }
  function click() { if (!hold && !disabled) onfire(); }
  function down(e: KeyboardEvent) {
    if (!hold || (e.key !== "Enter" && e.key !== " ")) return;
    e.preventDefault();            // ไม่ให้ Enter/Space กลายเป็นคลิก (คลิกเดียวต้องไม่บันทึกทั้งชุด)
    if (!e.repeat) begin();
  }
  function up(e: KeyboardEvent) { if (hold && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); stop(); } }
  $effect(() => { if (!hold || disabled) stop(); });
  $effect(() => () => stop());
</script>

<span class="hold-w">
<button class="btn hold {cls}" class:armed={hold} class:holding {disabled} aria-describedby={hold ? id : undefined}
        onclick={click} onpointerdown={(e) => { if (e.button === 0) begin(); }} onpointerup={stop} onpointerleave={stop} onpointercancel={stop}
        onkeydown={down} onkeyup={up} onblur={stop} oncontextmenu={(e) => { if (hold) e.preventDefault(); }}>
  {#if hold}<span class="fill" aria-hidden="true" bind:this={fill}></span>{/if}
  <span class="lbl">{@render children()}</span>
</button>
{#if hold}<small class="hold-hint" {id} aria-live="polite">{holding ? "กดค้างไว้…" : hint}</small>{/if}
</span>

<style>
  .hold-w { display: inline-flex; flex-direction: column; align-items: stretch; }
  .hold { position: relative; overflow: hidden; isolation: isolate; }
  .armed { touch-action: none; user-select: none; -webkit-user-select: none; }
  .fill { position: absolute; inset: 0; z-index: -1; background: #3b5fa8; transform: scaleX(0); transform-origin: left center; pointer-events: none; }
  .holding { outline: 3px solid #9fb3d9; outline-offset: 2px; }
  .lbl { position: relative; }
  .hold-hint { display: block; width: 100%; text-align: right; color: var(--muted); font-size: .82em; margin-top: 4px; }
</style>
