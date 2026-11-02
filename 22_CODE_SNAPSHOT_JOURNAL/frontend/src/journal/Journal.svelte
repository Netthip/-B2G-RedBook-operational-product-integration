<script lang="ts">
  // สมุดของระบบ (/r/book) — กิ๊ฟ 1 พ.ย. 69: ชอบสมุดป๊อปอัปแบบงานเสี่ยวหงซู อยากให้อยู่หน้าเว็บ · แยกเป็นเซกชัน
  // แต่ละหน้าเป็นไฟล์ของตัวเองใน ./pages (หยิบไปวางหน้าอื่นได้) · ที่วางสมุด/รูปผู้พัฒนาตั้งใน ./content.ts
  // พลิกหน้าด้วย CSS 3 มิติล้วน (ไม่มีไลบรารีเพิ่ม · ไม่มีสไตล์ฝังในแท็กตาม CSP) · จอแคบกว่า 900px เรียงหน้าลงมาอ่านทีละหน้า
  import "./journal.css";
  import Cover from "./pages/Cover.svelte";
  import Intro from "./pages/Intro.svelte";
  import Why from "./pages/Why.svelte";
  import Steps from "./pages/Steps.svelte";
  import Compare from "./pages/Compare.svelte";
  import Source from "./pages/Source.svelte";
  import Limits from "./pages/Limits.svelte";
  import Maker from "./pages/Maker.svelte";
  import End from "./pages/End.svelte";

  // ใบที่ i: หน้าใบ = หน้าขวาของคู่หน้า i (ใบแรกคือปก) · หลังใบ = หน้าซ้ายของคู่หน้า i+1 · คู่หน้าสุดท้ายขวามือคือปกหลังด้านใน (End)
  const LEAVES = [[Cover, Intro], [Why, Steps], [Compare, Source], [Limits, Maker]];
  const LAST = LEAVES.length;
  const NAMES = ["ปก", "ทำไมถึงมีระบบนี้", "ใช้งาน 3 ขั้น", "ข้อมูลมาจากไหน", "ผู้พัฒนา"];

  let spread = $state(0);
  const turn = (n: number) => { spread = Math.max(0, Math.min(LAST, n)); };

  const wideQuery = matchMedia("(min-width: 900px)");
  let wide = $state(wideQuery.matches);
  $effect(() => {
    const f = (e: MediaQueryListEvent) => { wide = e.matches; };
    wideQuery.addEventListener("change", f);
    return () => wideQuery.removeEventListener("change", f);
  });

  function onkey(e: KeyboardEvent) {
    if (!wide || e.altKey || e.ctrlKey || e.metaKey || (e.target as HTMLElement).closest?.("input, textarea, select")) return;
    const to = { ArrowRight: spread + 1, PageDown: spread + 1, ArrowLeft: spread - 1, PageUp: spread - 1, Home: 0, End: LAST }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    turn(to);
  }

  // แตะครึ่งขวาของสมุด = พลิกไปหน้าถัดไป · ครึ่งซ้าย = ย้อน (ลิงก์/ปุ่มในหน้าทำงานตามปกติ) · ปุ่มด้านล่างใช้กับแป้นพิมพ์/โปรแกรมอ่านจอ
  let bookEl = $state<HTMLElement>();
  function tap(e: MouseEvent) {
    if (!bookEl || (e.target as HTMLElement).closest("a, button")) return;
    if (spread === 0) return turn(1);
    const r = bookEl.getBoundingClientRect();
    turn(e.clientX > r.left + r.width / 2 ? spread + 1 : spread - 1);
  }
</script>

<svelte:window onkeydown={onkey} />

<article class="jr">
  <h1 class="sr-only">สมุดของระบบ RedBook Verify</h1>
  {#if wide}
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div class="stage" onclick={tap}>
      <div class="book" class:closed={spread === 0} bind:this={bookEl}>
        <div class="board jr-paper" class:on={spread === LAST} inert={spread !== LAST}><End restart={() => turn(0)} /></div>
        {#each LEAVES as [Front, Back], i (i)}
          <div class="leaf" class:flipped={i < spread} style:--z="{(i < spread ? i + 1 : LAST - i + 1) * 1.5}px">
            <div class="face front" class:jr-paper={i > 0} class:cover={i === 0} class:on={spread === i} inert={spread !== i}><Front /></div>
            <div class="face back jr-paper" class:on={spread === i + 1} inert={spread !== i + 1}><Back /></div>
          </div>
        {/each}
      </div>
    </div>
    <div class="ctrl">
      <button class="btn ghost small" type="button" onclick={() => turn(spread - 1)} disabled={spread === 0}>‹ ย้อน</button>
      <div class="dots">
        {#each NAMES as name, i (i)}
          <button type="button" class:on={spread === i} aria-label={name} aria-current={spread === i ? "page" : undefined} onclick={() => turn(i)}></button>
        {/each}
      </div>
      <button class="btn ghost small" type="button" onclick={() => turn(spread + 1)} disabled={spread === LAST}>ถัดไป ›</button>
    </div>
    <p class="sr-only" aria-live="polite">{`หน้า ${spread + 1} จาก ${LAST + 1} · ${NAMES[spread]}`}</p>
  {:else}
    <div class="jr-stack">
      {#each [Cover, Intro, Why, Steps, Compare, Source, Limits, Maker] as Page, i (i)}
        <section class="sheet on" class:jr-paper={i > 0}><Page /></section>
      {/each}
      <section class="sheet on jr-paper"><End restart={() => scrollTo({ top: 0 })} /></section>
    </div>
  {/if}
</article>

<style>
  .jr { padding: 0 0 8px; }
  .stage { display: flex; justify-content: center; padding: 22px 0 10px; perspective: 2600px; perspective-origin: 50% 0%; cursor: pointer;
    user-select: none; -webkit-user-select: none; }
  .book { --tilt: 13deg; --shift: 0px; position: relative; width: calc(var(--pw) * 2); height: var(--ph); transform-style: preserve-3d;
    transform: rotateX(var(--tilt)) translateX(var(--shift)); transition: transform .9s cubic-bezier(.645, .045, .355, 1); }
  .book.closed { --shift: calc(var(--pw) * -.5); }
  .board, .leaf { position: absolute; top: 0; left: var(--pw); width: var(--pw); height: 100%; }
  .board { transform: translateZ(0); }
  .leaf { transform-origin: 0 50%; transform-style: preserve-3d; transform: translateZ(var(--z)) rotateY(0deg);
    transition: transform .9s cubic-bezier(.645, .045, .355, 1); }
  .leaf.flipped { transform: translateZ(var(--z)) rotateY(-180deg); }
  .face { position: absolute; inset: 0; backface-visibility: hidden; transform-style: preserve-3d; }
  .face.back { transform: rotateY(180deg); }
  /* ของในหน้าอยู่ในภาพ 3 มิติเดียวกับหน้า (เพื่อให้ป๊อปอัปตั้งขึ้นได้) จึงไม่ถูกซ่อนตามด้านหลังของหน้า — ต้องซ่อนทีละชิ้น
     ไม่งั้นตัวหนังสือของอีกด้านของใบจะกลับด้านทะลุขึ้นมา */
  .face :global(*) { backface-visibility: hidden; }
  /* ขอบกระดาษ + เงาตรงสันเล่ม (หน้าขวาเงาอยู่ซ้าย · หน้าซ้ายเงาอยู่ขวา) */
  .board, .face.front.jr-paper { border-radius: 0 calc(var(--u) * 1.4) calc(var(--u) * 1.4) 0; }
  .face.back { border-radius: calc(var(--u) * 1.4) 0 0 calc(var(--u) * 1.4); }
  .board, .face.jr-paper { box-shadow: 0 calc(var(--u) * 1.2) calc(var(--u) * 4) rgba(16, 24, 40, .14); }
  .board::after, .face.jr-paper::after { content: ""; position: absolute; inset: 0; border-radius: inherit; pointer-events: none;
    background: linear-gradient(90deg, rgba(31, 35, 40, .12), rgba(31, 35, 40, 0) 9%); }
  .face.back::after { background: linear-gradient(270deg, rgba(31, 35, 40, .12), rgba(31, 35, 40, 0) 9%); }

  .ctrl { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 10px; }
  .dots { display: flex; gap: 2px; }
  .dots button { display: grid; place-items: center; width: 28px; height: 28px; padding: 0; border: 0; background: none; cursor: pointer; }
  .dots button::before { content: ""; width: 9px; height: 9px; border-radius: 999px; background: #cfd4dc; transition: width .25s, background .25s; }
  .dots button.on::before { width: 22px; background: var(--jr-navy); }

  .jr-stack { --pw: min(calc(100vw - 32px), 560px); display: flex; flex-direction: column; align-items: center; gap: 18px; }
  .sheet { position: relative; width: var(--pw); height: var(--ph); border-radius: calc(var(--u) * 1.4);
    box-shadow: 0 calc(var(--u) * 1.2) calc(var(--u) * 4) rgba(16, 24, 40, .14); }
</style>
