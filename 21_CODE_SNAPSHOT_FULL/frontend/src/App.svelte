<script lang="ts">
  import { nav, link } from "./lib/router.svelte";
  import { get, type Meta } from "./lib/api";
  import Home from "./views/Home.svelte";
  import Review from "./views/Review.svelte";
  import Result from "./views/Result.svelte";
  import Survey from "./views/Survey.svelte";
  import Dashboard from "./views/Dashboard.svelte";
  import Toast from "./lib/Toast.svelte";

  let meta = $state<Meta | null>(null);
  get<Meta>("/api/trial/meta").then((m) => (meta = m));
</script>

<header class="top">
  <a class="brand" href="/r" onclick={link}><span class="mark">RV</span> ทดลองตรวจเล่มงบประมาณ</a>
  <span class="note">รุ่นทดลอง · ข้อมูลเก็บในเครื่องนี้เท่านั้น</span>
  <a class="out" href="/">ไปโต๊ะตรวจเต็ม</a>
</header>

<main id="main">
  {#if !meta}
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

<footer class="foot">ระบบเสนอข้อสังเกตพร้อมหลักฐาน คนเป็นผู้ตัดสิน · ไม่ใช่การรับรองความถูกต้องของเอกสาร
  {#if meta} · {meta.versions.trial} · {meta.versions.pdfbook}{/if}</footer>
<Toast />
