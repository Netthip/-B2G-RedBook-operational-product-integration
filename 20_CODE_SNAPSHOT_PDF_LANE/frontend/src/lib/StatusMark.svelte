<script lang="ts">
  // สถานะระหว่างระบบอ่านเล่ม/สร้างรอบ (ใบงาน #44 Status Mark): วงรอ → วงความคืบหน้า → วงปิด "อ่านเล่มเสร็จ"
  // ความคืบหน้า (value 0–1) แสดงเฉพาะเมื่อเซิร์ฟเวอร์ส่งค่าจริงมา · ไม่มีค่า = วงหมุนแบบไม่ระบุ % (ไม่เดาตัวเลขเอง)
  // เสร็จ = วงปิดสีน้ำเงิน ไม่ใช่เครื่องหมายถูก/สีเขียว — "อ่านเล่มเสร็จ" ไม่ได้แปลว่าเอกสารถูกต้อง
  // ล้มเหลวไม่ใช้วงนี้ — ผู้เรียกแสดงข้อความผิดพลาดเอง · ระบบตั้งลดการเคลื่อนไหว = วงไม่หมุน
  let { state, value, label = "" }: { state: "wait" | "done"; value?: number; label?: string } = $props();
  const C = 2 * Math.PI * 9;
  const known = $derived(state === "wait" && typeof value === "number" && Number.isFinite(value));
</script>

<span class="sm" class:done={state === "done"} role="status">
  <svg viewBox="0 0 24 24" aria-hidden="true" class:spin={state === "wait" && !known}>
    <circle class="bg" cx="12" cy="12" r="9" />
    {#if state === "done"}
      <circle class="fg" cx="12" cy="12" r="9" />
      <circle class="dot" cx="12" cy="12" r="3.5" />
    {:else if known}
      <circle class="fg" cx="12" cy="12" r="9" stroke-dasharray={C} stroke-dashoffset={C * (1 - Math.min(1, Math.max(0, value!)))} />
    {:else}
      <circle class="fg" cx="12" cy="12" r="9" stroke-dasharray="{C * 0.28} {C}" />
    {/if}
  </svg>
  {#if known}<span class="pct">{Math.round(value! * 100)}%</span>{/if}
  {#if label}<span class="lbl">{label}</span>{/if}
</span>

<style>
  .sm { display: inline-flex; align-items: center; gap: 8px; color: var(--accent, #0e2f6e); font-weight: 600; }
  svg { width: 22px; height: 22px; flex: none; }
  circle { fill: none; stroke-width: 3; }
  .bg { stroke: #d5dbe6; }
  .fg { stroke: var(--accent, #0e2f6e); stroke-linecap: round; transform: rotate(-90deg); transform-origin: 12px 12px; transition: stroke-dashoffset .3s; }
  .dot { fill: var(--accent, #0e2f6e); stroke: none; }
  .spin { animation: sm-spin 1s linear infinite; }
  @keyframes sm-spin { to { transform: rotate(360deg); } }
  .pct { font-variant-numeric: tabular-nums; font-size: .9em; }
  @media (prefers-reduced-motion: reduce) { .spin { animation: none; } .fg { transition: none; } }
</style>
