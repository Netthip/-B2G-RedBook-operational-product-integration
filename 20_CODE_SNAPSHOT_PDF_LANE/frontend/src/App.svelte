<script lang="ts">
  import { nav, link } from "./lib/router.svelte";
  import { get, type Meta } from "./lib/api";
  import Home from "./views/Home.svelte";
  import Review from "./views/Review.svelte";
  import Result from "./views/Result.svelte";
  import Survey from "./views/Survey.svelte";
  import Dashboard from "./views/Dashboard.svelte";
  import PairRuns from "./views/PairRuns.svelte";
  import PairNew from "./views/PairNew.svelte";
  import PairRun from "./views/PairRun.svelte";
  import PairFinding from "./views/PairFinding.svelte";
  import PairPreflight from "./views/PairPreflight.svelte";
  import PairAudit from "./views/PairAudit.svelte";
  import PairSummary from "./views/PairSummary.svelte";
  import Toast from "./lib/Toast.svelte";
  import { lane } from "./lib/lane.svelte";
  import Help from "./lib/Help.svelte";
  import Library from "./views/Library.svelte";
  import About from "./views/About.svelte";
  import Dev from "./views/Dev.svelte";
  import { go } from "./lib/router.svelte";

  let meta = $state<Meta | null>(null);
  get<Meta>("/api/trial/meta").then((m) => (meta = m));
  // สายเทียบเล่ม PDF ไม่ต้องรอข้อมูลของสายทดลอง (meta)
  const pairLane = $derived(["lib", "about", "dev", "pairs", "pairNew", "pair", "pairFinding", "pairPreflight", "pairAudit", "pairSummary"].includes(nav.route.name));
  // เซิร์ฟเวอร์สาย PDF: หน้าแรกคือคลังเล่ม (หน้าแรกเดิมของสายทดลอง Excel ไม่เปิดบนเซิร์ฟเวอร์นี้)
  $effect(() => { if (lane.known && lane.pdfOnly && nav.route.name === "home") go("/r/lib", true); });
  const kind = $derived(nav.route.name === "pairNew" ? nav.query.get("kind") ?? "" : "");
  let dd = $state<HTMLDetailsElement>();
  const closeDd = () => { if (dd) dd.open = false; };
  $effect(() => { document.title = pairLane ? "ตรวจเทียบเอกสารงบประมาณ · RedBook Verify" : "ทดลองตรวจเล่ม · RedBook Verify"; });
</script>

<header class="top">
  {#if pairLane}
    <a class="brand" href="/r/lib" onclick={link}><span class="mark">RV</span> RedBook Verify</a>
    <nav class="menu" aria-label="เมนูหลัก">
      <a href="/r/lib" onclick={link} class:on={nav.route.name === "lib"}>คลังเล่มงบประมาณ</a>
      <details class="dd" bind:this={dd}>
        <summary class:on={nav.route.name === "pairNew"}>ตรวจเล่มงบประมาณ <span class="hot">HOT</span> <span aria-hidden="true">▾</span></summary>
        <div class="ddm" role="menu">
          <a role="menuitem" href="/r/p/new?kind=cross" onclick={(e) => { closeDd(); link(e); }} class:on={kind === "cross"}>
            <b>ตรวจเล่มงบประมาณข้ามปี</b><small>เทียบกับปีก่อน</small></a>
          <a role="menuitem" href="/r/p/new?kind=same" onclick={(e) => { closeDd(); link(e); }} class:on={kind === "same"}>
            <b>ตรวจเล่มงบประมาณในปีเดียวกัน</b><small>ร่าง พ.ร.บ. ↔ พ.ร.บ.</small></a>
        </div>
      </details>
      <!-- "งานที่ทำไว้" ย้ายไปท้ายหน้าเกี่ยวกับระบบ (กิ๊ฟ 29 ต.ค.: ไม่ต้องโชว์ให้คนอื่นเห็น) -->
      <a href="/r/about" onclick={link} class:on={nav.route.name === "about"}>เกี่ยวกับระบบ</a>
      <span class="soon" title="อยู่ระหว่างพัฒนา">ตรวจจาก Excel <small>เร็ว ๆ นี้</small></span>
    </nav>
  {:else}
    <a class="brand" href="/r" onclick={link}><span class="mark">RV</span> ทดลองตรวจเล่มงบประมาณ</a>
    <span class="tagline">รุ่นทดลอง · ข้อมูลเก็บในเครื่องนี้เท่านั้น</span>
  {/if}
  {#if pairLane}<span class="out"><Help /></span>{/if}
  {#if lane.known && !lane.pdfOnly}<a class="out" href="/">ไปโต๊ะตรวจเต็ม</a>{/if}
</header>

<main id="main" class:pair={pairLane} class:pairwide={nav.route.name === "pairFinding"}>
  {#if nav.route.name === "lib"}
    <Library />
  {:else if nav.route.name === "about"}
    <About />
  {:else if nav.route.name === "dev"}
    <Dev />
  {:else if nav.route.name === "pairs"}
    <PairRuns />
  {:else if nav.route.name === "pairNew"}
    {#key kind}<PairNew {kind} />{/key}
  {:else if nav.route.name === "pair"}
    {#key nav.route.rid}<PairRun rid={nav.route.rid} />{/key}
  {:else if nav.route.name === "pairFinding"}
    {#key `${nav.route.rid}/${nav.route.fid}`}<PairFinding rid={nav.route.rid} fid={nav.route.fid} />{/key}
  {:else if nav.route.name === "pairPreflight"}
    {#key nav.route.rid}<PairPreflight rid={nav.route.rid} />{/key}
  {:else if nav.route.name === "pairAudit"}
    {#key nav.route.rid}<PairAudit rid={nav.route.rid} />{/key}
  {:else if nav.route.name === "pairSummary"}
    {#key nav.route.rid}<PairSummary rid={nav.route.rid} />{/key}
  {:else if !meta}
    <div class="boot"><span class="spin"></span></div>
  {:else if nav.route.name === "home"}
    <Home />
  {:else if nav.route.name === "review"}
    {#key nav.route.sid}<Review sid={nav.route.sid} {meta} />{/key}
  {:else if nav.route.name === "result"}
    {#key nav.route.sid}<Result sid={nav.route.sid} {meta} />{/key}
  {:else if nav.route.name === "survey"}
    <Survey sid={nav.route.sid} {meta} />
  {:else if nav.route.name === "dashboard"}
    <Dashboard sid={nav.route.sid} />
  {:else}
    <p class="empty">ไม่พบหน้านี้ · <a href="/r" onclick={link}>กลับไปเลือกเล่ม</a></p>
  {/if}
</main>

<footer class="foot">ระบบเสนอจุดที่ต่างพร้อมหลักฐาน คนเป็นผู้ตัดสิน · ไม่ใช่การรับรองความถูกต้องของเอกสาร
  {#if meta && !pairLane}{` · ${meta.versions.trial} · ${meta.versions.pdfbook}`}{/if}</footer>
<Toast />
