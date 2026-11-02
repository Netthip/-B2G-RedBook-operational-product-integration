<script lang="ts">
  // ใช้งาน 3 ขั้น — ภาพร่างแบบที่ "ก่อร่าง" ขึ้นทีละขั้น (กิ๊ฟ 1 พ.ย.: ภาพมากกว่าตัวหนังสือ เหมือนร่างแบบบ้าน ต่อจุดแล้วกลายเป็นภาพ)
  // ลำดับ: เส้นร่างจาง → ลากเส้นภาพขั้น 1 → ป้าย → เส้นต่อไปขั้น 2 → … → ลงสีทั้งภาพ (จากร่างเป็นภาพจริง)
  // เล่นเมื่อหน้านี้เปิดอยู่ (.on จากสมุด) และเห็นบนจอแล้ว (.seen) — เปิดกลับมาใหม่ก็เล่นใหม่ · ผู้ที่ปิดภาพเคลื่อนไหวเห็นภาพเสร็จเลย
  // ภาพประกอบล้วน ไม่มีชื่อหน่วยงานหรือตัวเลขจริง · ข้อความขั้นตอนอ่านได้ครบจากรายการซ่อนสำหรับโปรแกรมอ่านหน้าจอ
  import { ABOUT } from "../content";
  import Th from "../Th.svelte";

  const POS = ["l1", "l2", "l3"];
  let shown = $state(false);
  function seen(node: HTMLElement) {
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { shown = true; io.disconnect(); } }, { threshold: 0.3 });
    io.observe(node);
    return { destroy: () => io.disconnect() };
  }
</script>

<div class="jr-pg">
  <h2>ใช้งาน 3 ขั้น</h2>
  <ol class="sr-only">
    {#each ABOUT.steps as [n, t, d] (n)}<li>{t} — {d}</li>{/each}
  </ol>
  <div class="bp" class:seen={shown} use:seen aria-hidden="true">
    <svg viewBox="0 0 80 92">
      <!-- เส้นร่าง (เส้นไกด์จาง ๆ แบบกระดาษเขียนแบบ) -->
      <g class="guide">
        <path d="M0 24.5 H32" /><path d="M42 34 H78" /><path d="M42 53 H78" /><path d="M2 88.5 H32" />
        <path d="M14 1 V27" /><path d="M60 31 V56" />
      </g>

      <!-- ขั้น 1: อาคาร + แว่นขยาย (เลือกหน่วยงาน) -->
      <g class="ink t-f1">
        <rect x="5" y="13" width="18" height="11" class="f-soft" /><path d="M3 13 L14 5 L25 13 Z" class="f-navy" />
        <circle cx="24.5" cy="21.5" r="4.2" class="f-white" />
      </g>
      <g class="ln t-1">
        <path pathLength="1" d="M3 13 L14 5 L25 13 Z" /><rect pathLength="1" x="5" y="13" width="18" height="11" />
        <path pathLength="1" d="M9 15.5 V22 M14 15.5 V22 M19 15.5 V22" /><path pathLength="1" d="M2 24.5 H26" />
        <circle pathLength="1" cx="24.5" cy="21.5" r="4.2" /><path pathLength="1" d="M27.6 24.6 L31 28" class="thick" />
      </g>

      <!-- เส้นต่อ 1 → 2 -->
      <circle cx="16" cy="30" r="1" class="dot t-c1" />
      <path pathLength="1" class="ln con t-c1" d="M16 30 C16 35 60 26 60 33.6" />
      <path pathLength="1" class="ln con t-c1h" d="M58.2 31.6 L60 33.8 L61.8 31.6" />

      <!-- ขั้น 2: หน้า PDF ฉบับ A | B มีแถบจุดที่ต่าง -->
      <g class="ink t-f2">
        <rect x="47" y="36" width="11" height="15" rx=".6" class="f-white" /><rect x="62" y="36" width="11" height="15" rx=".6" class="f-white" />
        <rect x="47" y="36" width="11" height="2.6" class="f-a" /><rect x="62" y="36" width="11" height="2.6" class="f-b" />
        <rect x="48.4" y="44.9" width="8.2" height="2.2" rx="1" class="f-hl" /><rect x="63.4" y="44.9" width="8.2" height="2.2" rx="1" class="f-hl" />
        <text x="52.5" y="38.1" class="tg">A</text><text x="67.5" y="38.1" class="tg">B</text>
      </g>
      <g class="ln t-2">
        <rect pathLength="1" x="47" y="36" width="11" height="15" rx=".6" /><rect pathLength="1" x="62" y="36" width="11" height="15" rx=".6" />
        <path pathLength="1" d="M49 41.5 H56 M49 46 H56 M49 49 H54" /><path pathLength="1" d="M64 41.5 H71 M64 46 H71 M64 49 H69" />
        <path pathLength="1" d="M58.8 42.6 H61.2 M61.2 45 H58.8" class="thin" />
      </g>

      <!-- เส้นต่อ 2 → 3 -->
      <circle cx="60" cy="56" r="1" class="dot t-c2" />
      <path pathLength="1" class="ln con t-c2" d="M60 56 C60 64 34 62 22.5 68.5" />
      <path pathLength="1" class="ln con t-c2h" d="M25.4 69.3 L22 68.8 L23.6 66" />

      <!-- ขั้น 3: คน + เครื่องหมายถูก (ให้ความเห็น · คนเป็นผู้ตัดสิน) -->
      <g class="ink t-f3">
        <circle cx="12" cy="75" r="3.4" class="f-navy" /><path d="M5 88 Q5 80.5 12 80.5 Q19 80.5 19 88 Z" class="f-navy" />
        <circle cx="22.5" cy="75" r="4.6" class="f-mint" />
      </g>
      <g class="ln t-3">
        <circle pathLength="1" cx="12" cy="75" r="3.4" /><path pathLength="1" d="M5 88 Q5 80.5 12 80.5 Q19 80.5 19 88 Z" />
        <circle pathLength="1" cx="22.5" cy="75" r="4.6" /><path pathLength="1" d="M20.2 75.2 L21.9 77 L25 73.4" class="thick" />
        <path pathLength="1" d="M3 88.5 H30" />
      </g>
    </svg>

    {#each ABOUT.steps as [n, t, d], i (n)}
      <div class="lab {POS[i]}"><b><span class="num">{n}</span><span><Th s={t} /></span></b><span class="d"><Th s={d} /></span></div>
    {/each}
  </div>
</div>

<style>
  /* กล่องภาพ 80 × 92 หน่วย = 1 หน่วยต่อ 1% ของหน้า ตัวหนังสือในป้ายจึงย่อขยายไปกับภาพ */
  .bp { position: absolute; left: calc(var(--u) * 10); top: calc(var(--u) * 26); width: calc(var(--u) * 80); height: calc(var(--u) * 92); }
  .bp svg { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }

  .guide path { fill: none; stroke: #98a2b3; stroke-width: .25; stroke-dasharray: .8 .9; }
  .ln, .ln :global(*) { fill: none; stroke: var(--jr-navy); stroke-width: .55; stroke-linecap: round; stroke-linejoin: round; }
  .ln .thick, .ln.thick { stroke-width: .9; }
  .ln .thin { stroke-width: .4; stroke: #667085; }
  .con { stroke: var(--jr-pin); stroke-width: .5; }
  .dot { fill: var(--jr-pin); }
  .f-soft { fill: #e8eef9; } .f-navy { fill: var(--jr-navy); } .f-white { fill: #fff; } .f-mint { fill: #e2f3ee; }
  .f-a { fill: var(--a); } .f-b { fill: var(--b); } .f-hl { fill: var(--warn-line); }
  .tg { fill: #fff; font-size: 2.1px; font-weight: 700; text-anchor: middle; dominant-baseline: central; }

  .lab { position: absolute; display: flex; flex-direction: column; gap: calc(var(--u) * .6); }
  .lab b { display: flex; align-items: center; gap: calc(var(--u) * 1.6); font-size: calc(var(--u) * 4.6); line-height: 1.3; color: var(--jr-navy); }
  .lab .d { font-size: calc(var(--u) * 3.6); line-height: 1.45; color: #344054; text-wrap: balance; }
  .num { display: inline-grid; place-items: center; flex: none; width: calc(var(--u) * 6.4); height: calc(var(--u) * 6.4); border-radius: 50%;
    background: var(--jr-navy); color: #fff; font-size: calc(var(--u) * 3.6); }
  .l1 { left: 41%; top: 4%; width: 59%; }
  .l2 { left: 0; top: 36%; width: 57%; align-items: flex-end; text-align: right; }
  .l2 b { flex-direction: row-reverse; }
  .l3 { left: 41%; top: 73%; width: 59%; }

  /* ── จังหวะ: ตั้งต้นทุกชิ้นซ่อนไว้ แล้วเล่นเมื่อหน้าเปิด (.on) และเห็นบนจอ (.seen) ── */
  .t-1 { --d: .7s; } .l1 { --d: 1.3s; } .t-c1 { --d: 1.6s; } .t-c1h { --d: 2.1s; }
  .t-2 { --d: 2.2s; } .l2 { --d: 2.8s; } .t-c2 { --d: 3.1s; } .t-c2h { --d: 3.6s; }
  .t-3 { --d: 3.7s; } .l3 { --d: 4.3s; } .t-f1 { --d: 4.6s; } .t-f2 { --d: 4.8s; } .t-f3 { --d: 5s; }
  .guide { --d: .3s; }
  .ln, .ln :global(*) { stroke-dasharray: 1; }
  :global(.on) .seen .ln, :global(.on) .seen .ln :global(*) { stroke-dashoffset: 1; animation: draw .75s cubic-bezier(.5, 0, .3, 1) var(--d) forwards; }
  :global(.on) .seen .ink, :global(.on) .seen .dot, :global(.on) .seen .guide, :global(.on) .seen .lab { opacity: 0; animation: show .5s ease var(--d) forwards; }
  :global(.on) .seen .lab { translate: 0 calc(var(--u) * 1.2); }
  :global(.on) .seen .dot { animation-name: pop; transform-box: fill-box; transform-origin: center; }
  @keyframes draw { to { stroke-dashoffset: 0; } }
  @keyframes show { to { opacity: 1; translate: 0 0; } }
  @keyframes pop { 0% { opacity: 0; scale: 0; } 70% { opacity: 1; scale: 1.6; } 100% { opacity: 1; scale: 1; } }
  @media (prefers-reduced-motion: reduce) {
    :global(.on) .seen .ln, :global(.on) .seen .ln :global(*), :global(.on) .seen .ink, :global(.on) .seen .dot,
    :global(.on) .seen .guide, :global(.on) .seen .lab { animation: none; opacity: 1; stroke-dashoffset: 0; translate: 0 0; }
  }
</style>
