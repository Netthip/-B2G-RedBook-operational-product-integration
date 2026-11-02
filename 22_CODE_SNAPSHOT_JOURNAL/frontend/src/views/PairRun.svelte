<script lang="ts">
  // ภาพรวมของรอบเทียบเล่ม — คิวข้อที่ต้องตัดสิน แยกตามหัวข้อ · ตัวกรองเก็บใน URL (กดย้อนกลับแล้วได้มุมมองเดิม)
  // ทวนรอบ 2 (U2): ด้านบนเหลือความคืบหน้า + รายการจุด · การใช้ผล/ส่งออก/ข้อมูลฉบับ/รุ่น พับไว้ท้ายหน้า
  import { tick } from "svelte";
  import { link, nav } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import Count from "../lib/Count.svelte";
  import PairRow from "./PairRow.svelte";
  import DevBadge from "../lib/DevBadge.svelte";
  import { backTo, loadList, loadRun, offsetsOf, peekList, peekRun, prefetch, rangeFull, type PFinding, type PRun } from "../lib/pair";

  let { rid }: { rid: string } = $props();

  type Show = "todo" | "done" | "info" | "all";
  const SHOWS = [["todo", "ยังไม่บันทึก"], ["done", "บันทึกแล้ว"], ["info", "ข้อมูลเพิ่มเติม"], ["all", "ทั้งหมด"]] as const;
  const RING = 2 * Math.PI * 52;

  let r = $state<PRun | null>(peekRun(rid) ?? null);
  let list = $state<PFinding[] | null>(peekList(rid) ?? null);
  let err = $state("");
  const q0 = nav.query;
  let topic = $state(q0.get("topic") ?? "");
  let show = $state<Show>(SHOWS.some(([k]) => k === q0.get("show")) ? (q0.get("show") as Show) : "todo");
  let q = $state(q0.get("q") ?? "");
  const target = location.hash.startsWith("#f-") ? location.hash.slice(3) : "";
  let flashId = $state("");

  function fail(e: unknown) {
    const msg = (e as Error).message;
    if (r && list) toast(msg, true); else err = msg;
  }
  function refresh(maxAge: number) {
    loadRun(rid).then((x) => { r = x; prefetch(rid, x.next_pending_id); }).catch(fail);
    loadList(rid, maxAge).then((x) => (list = x)).catch(fail);
  }
  // รายการในแคชถูกแก้ทุกครั้งที่บันทึกผลจากหน้านี้ · กลับมาที่แท็บ = ดึงใหม่ทั้งหมด (อาจตัดสินจากแท็บหน้าเดิม)
  refresh(60000);
  const onvis = () => { if (document.visibilityState === "visible") refresh(0); };
  $effect(() => { document.addEventListener("visibilitychange", onvis); return () => document.removeEventListener("visibilitychange", onvis); });

  // ตัวกรอง → URL (แทนที่ ไม่เพิ่มประวัติ) + จำไว้ให้ปุ่มกลับของหน้าหลักฐาน
  $effect(() => {
    const p = new URLSearchParams();
    if (topic) p.set("topic", topic);
    if (show !== "todo") p.set("show", show);
    if (q.trim()) p.set("q", q.trim());
    const url = `/r/p/${rid}${p.toString() ? `?${p}` : ""}`;
    backTo.set(rid, url);
    history.replaceState(null, "", url);
  });

  // กลับมาจากหน้าหลักฐาน (#f-<id>) → เลื่อนไปแถวเดิมแล้วเน้นสั้น ๆ · ถ้าแถวนั้นถูกกรองออก (เช่น เพิ่งตัดสิน
  // ขณะดู "ยังไม่ตัดสิน") ไปแถวถัดไปที่ยังแสดงอยู่ = ที่ที่ทำค้างไว้ในคิว
  let scrolled = false;
  $effect(() => {
    if (!list || !r || scrolled || !target) return;
    scrolled = true;
    const i = list.findIndex((f) => f.id === target);
    const to = i < 0 ? undefined : list.slice(i).find(keep) ?? list.slice(0, i).reverse().find(keep);
    if (!to) return;
    tick().then(() => {
      const el = document.getElementById(`f-${to.id}`);
      if (el) { el.scrollIntoView({ block: "center" }); flashId = to.id; }
    });
  });

  const decided = $derived(r ? r.counts.actionable - r.counts.pending : 0);
  const pct = $derived(r && r.counts.actionable ? decided / r.counts.actionable : 0);
  const yearsFirst = $derived(!!r && !r.run.superseded_by && r.preflight.failing.includes("years"));
  const needle = $derived(q.trim().toLowerCase());
  const tally = $derived.by(() => {
    const c = { todo: 0, done: 0, info: 0, all: 0 };
    for (const f of list ?? []) {
      if (topic && f.topic !== topic) continue;
      c.all++;
      if (f.info) c.info++; else if (f.decision) c.done++; else c.todo++;
    }
    return c;
  });
  function keep(f: PFinding) {
    if (topic && f.topic !== topic) return false;
    if (show === "todo" && (f.info || f.decision)) return false;
    if (show === "done" && (f.info || !f.decision)) return false;
    if (show === "info" && !f.info) return false;
    return !needle || `${f.subject} ${f.column} ${f.kind_label}`.toLowerCase().includes(needle);
  }
  const sections = $derived(r && list
    ? r.groups.map((g) => ({ g, rows: list!.filter((f) => f.topic === g.key && keep(f)) })).filter((s) => s.rows.length)
    : []);
  const roots = $derived.by(() => {
    if (!r?.item_change_ids || !list) return [];
    const byId = new Map(list.map((f) => [f.id, f]));
    return r.item_change_ids.map((id) => byId.get(id)).filter((f): f is PFinding => !!f);
  });
  const when = (s: string) => s.slice(0, 16).replace("T", " ");
  const short = (l: string) => l.replace(/^ฉบับ [AB] · /, "");

  // การ์ด "ต้องทำอีก": หัวข้อที่ยังค้างมากสุดก่อน (สูงสุด 4) · กดแล้วกรองรายการด้านล่างแล้วเลื่อนไปหา
  const pendingGroups = $derived(r ? r.groups.filter((g) => g.pending > 0).sort((a, b) => b.pending - a.pending) : []);
  const todoGroups = $derived(pendingGroups.slice(0, 4));
  const moreTopics = $derived(Math.max(0, pendingGroups.length - 4));
  function pickTopic(k: string) {
    topic = k; show = "todo";
    tick().then(() => document.querySelector(".results")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }
  // แถบการใช้ผล — ลำดับและชื่อย่อตาม use_breakdown ของเซิร์ฟเวอร์ (ตัวหารเต็ม)
  const USE_PARTS = [["usable", "ปิดแล้ว"], ["excluded", "ไม่นับ"], ["open", "ยังไม่ปิด"], ["pending", "ยังไม่ตัดสิน"]] as const;
</script>

{#if err}
  <div class="card msg">{err} · <a href="/r/p" onclick={link}>กลับไปรายการรอบ</a></div>
{:else if !r}
  <div class="card skeleton sk-hero"></div>
  <div class="card skeleton sk-list"></div>
{:else}
  {@const run = r.run}
  <a class="back" href="/r/p" onclick={link}>← รอบทั้งหมด</a>

  {#if run.superseded_by}
    <div class="note danger" role="alert"><b>รอบนี้ถูกแทนแล้ว</b> — มีรอบใหม่ที่คำนวณด้วยปีงบที่ยืนยันแล้ว ·
      ผลและคำตัดสินเดิมเก็บไว้ดูย้อนหลังเท่านั้น บันทึกเพิ่มหรือส่งออกไม่ได้
      <a class="btn small" href="/r/p/{run.superseded_by}" onclick={link}>ไปรอบใหม่ →</a></div>
  {:else if run.supersedes}
    <div class="note" role="status">รอบนี้คำนวณแทน<a href="/r/p/{run.supersedes}" onclick={link}>รอบเดิม</a>ด้วยปีงบที่ผู้ตรวจยืนยัน ·
      คำตัดสินของรอบเดิมไม่ถูกคัดลอกมา — ตัดสินรอบนี้ใหม่</div>
  {/if}

  <header class="head">
    <div>
      <h1>{run.agency || "ไม่ระบุหน่วยงาน"} <DevBadge text={run.profile_status_label} /></h1>
      <p class="pair">
        <span class="side side-a">{short(run.sides.A.label)} <small class="code">A</small></span>
        <span class="arrow" aria-label="เทียบกับ">→</span>
        <span class="side side-b">{short(run.sides.B.label)} <small class="code">B</small></span>
        <span class="hint">{run.mode_label} · สร้างเมื่อ {when(run.created_at)}</span>
      </p>
    </div>
    <nav class="tabs" aria-label="มุมมองของรอบ">
      <span class="tab on" aria-current="page">ภาพรวม</span>
      <!-- ด่านก่อนส่งออก/ประวัติไม่ใช่งานระหว่างทวน (กิ๊ฟ 28 ต.ค. "คนไม่เข้าใจว่าคืออะไร") — ย้ายไปหน้าสรุปผลและรายละเอียดของรอบ -->
      {#if r.next_pending_id}<a class="tab" href="/r/p/{rid}/f/{r.next_pending_id}" onclick={link}>ตรวจทีละจุด</a>{/if}
      <a class="tab" href="/r/p/{rid}/summary" onclick={link}>สรุปผล</a>
    </nav>
  </header>

  {#if yearsFirst}
    <p class="years-first">⚠ ปีงบของรอบนี้ยังไม่ยืนยัน — ถ้าปีที่ยืนยันต่างจากปีที่ระบบใช้คำนวณ ระบบจะสร้างรอบใหม่
      และ<b>คำตัดสินในรอบนี้จะไม่ถูกคัดลอกไป</b> · ยืนยันปีก่อนเริ่มตัดสินจะไม่ต้องทำซ้ำ
      <a class="btn small" href="/r/p/{rid}/preflight#years" onclick={link}>ยืนยันปีงบก่อน →</a></p>
  {/if}

  <div class="mods one">
    <section class="card mod hero">
      <h2><span class="ico ico-a" aria-hidden="true">◔</span> ความคืบหน้า</h2>
      <div class="prog">
        <div class="ring" role="img" aria-label="บันทึกความเห็นแล้ว {decided} จาก {r.counts.actionable} จุด">
          <svg viewBox="0 0 120 120" aria-hidden="true">
            <circle class="ring-bg" cx="60" cy="60" r="52" />
            <circle class="ring-fg" class:zero={!decided} cx="60" cy="60" r="52" style:stroke-dashoffset="{RING * (1 - pct)}px" />
          </svg>
          <span class="ring-pct">{r.counts.actionable ? Math.round(pct * 100) : 0}%</span>
        </div>
        <div>
          <p class="big"><Count to={decided} /><small>{` / ${r.counts.actionable}`}</small></p>
          <p class="hint">บันทึกแล้ว</p>
        </div>
      </div>
      {#if r.next_pending_id && !run.superseded_by}
        <a class="btn mod-cta" href="/r/p/{rid}/f/{r.next_pending_id}" onclick={link}>{decided ? "ตรวจต่อ →" : "เริ่มตรวจ →"}</a>
      {:else if !run.superseded_by && r.counts.actionable}
        <p class="done-note">✓ บันทึกครบแล้ว</p>
        <p class="hint">ทุกจุดที่ระบบพบมีความเห็นของคุณแล้ว — ไม่ได้แปลว่าเอกสารถูกต้อง</p>
        <a class="btn mod-cta" href="/r/p/{rid}/summary" onclick={link}>ดูสรุปของรอบ →</a>
      {/if}
    </section>


  </div>


  <div class="notes">
    {#each r.year_warnings as w, i (i)}
      <p class="note warn" role="alert"><b>ปีงบของฉบับ {w.side}:</b> {w.text} — ตรวจปีจากภาพหน้าเอกสารก่อนใช้ผลเทียบ
        (รูปแบบการเทียบที่ใช้: {run.mode_label})</p>
    {/each}
    {#each r.stage_warnings as w, i (i)}
      <p class="note warn"><b>ขั้นเอกสารของฉบับ {w.side}:</b> {w.text}</p>
    {/each}
  </div>


  {#if list && !list.length}
    <section class="card none">
      <h2>ระบบไม่ยกจุดที่ต่างในรอบนี้</h2>
      <p>ระบบอ่านสองฉบับในช่วงหน้าที่ระบุแล้วไม่พบความต่างที่ต้องให้คนตัดสิน — <b>ไม่ได้รับรองว่าสองฉบับเหมือนกัน</b>
        ผู้ตรวจยังควรเปิดดูเล่ม โดยเฉพาะส่วนที่เป็นภาพหรือตารางที่ระบบอ่านไม่ได้</p>
    </section>
  {:else}

    <div class="body one">

      <div class="results">
        <div class="tools">
          <div class="seg" role="tablist" aria-label="แสดงจุดที่ต่าง">
            {#each SHOWS as [k, label] (k)}
              <button role="tab" aria-selected={show === k} class:on={show === k} onclick={() => (show = k)}>
                {label} <span class="chip">{tally[k]}</span></button>
            {/each}
          </div>
          <select class="tsel" bind:value={topic} aria-label="หัวข้อ">
            <option value="">ทุกหัวข้อ ({decided}/{r.counts.actionable})</option>
            {#each r.groups as g (g.key)}<option value={g.key}>{g.label} ({g.total ? `${g.decided}/${g.total}` : "ข้อมูลเพิ่มเติม"})</option>{/each}
          </select>
          <input class="search" type="search" placeholder="ค้นหา" bind:value={q}
                 aria-label="ค้นในจุดที่ต่าง" />
        </div>
        {#if !list}
          <div class="card skeleton sk-list"></div>
        {:else if !sections.length}
          <p class="empty">{show === "todo" && !needle ? "บันทึกครบทุกจุดในส่วนนี้แล้ว" : "ไม่มีข้อที่ตรงเงื่อนไข"}</p>
        {:else}
          {#each sections as s (s.g.key)}
            <section class="card grp">
              <h2>{s.g.label} <span class="hint">{s.g.total ? `${s.g.decided}/${s.g.total}` : ""}{#if s.g.info}{` · ข้อมูลเพิ่มเติม ${s.g.info}`}{/if}</span></h2>
              {#each s.rows as f (f.id)}<PairRow {rid} {f} off={offsetsOf(r)} flash={f.id === flashId} />{/each}
            </section>
          {/each}
        {/if}
      </div>
    </div>
  {/if}


  <details class="rundet">
    <summary>รายละเอียดของรอบ — การใช้ผล · ส่งออก · ไฟล์ที่เทียบ · รุ่นของระบบ</summary>
    <div class="mods two">
      <section class="card mod">
      <h2><span class="ico ico-w" aria-hidden="true">☰</span> {r.counts.pending ? `ต้องทำอีก ${r.counts.pending} ข้อ` : "ไม่มีข้อค้าง"}</h2>
      {#if todoGroups.length}
        <ul class="tg">
          {#each todoGroups as g (g.key)}
            <li><button class="tg-row" onclick={() => pickTopic(g.key)} title="ดูเฉพาะหัวข้อนี้">
              <span class="tg-l">{g.label}</span><span class="hint">{g.decided}/{g.total}</span>
              {#if g.total <= 12}
                <span class="segs">{#each Array(g.total) as _, i (i)}<span class="tick" class:on={i < g.decided}></span>{/each}</span>
              {:else}
                <span class="bar2"><span class="fill2" style:width="{(100 * g.decided) / g.total}%"></span></span>
              {/if}
            </button></li>
          {/each}
        </ul>
        {#if moreTopics}<p class="hint">และอีก {moreTopics} หัวข้อ — ดูทั้งหมดในรายการด้านล่าง</p>{/if}
      {:else}
        <p class="hint">บันทึกครบทุกหัวข้อแล้ว</p>
      {/if}
    </section>
    <section class="card mod">
      <h2><span class="ico ico-g" aria-hidden="true">⇩</span> ส่งออก</h2>
      {#if r.preflight.ok}
        <p class="big ok-t">พร้อมแล้ว</p>
        <p class="hint">ผ่านด่านก่อนส่งออกครบ · เซิร์ฟเวอร์ตรวจซ้ำทุกครั้งที่ดาวน์โหลด</p>
        <a class="btn mod-cta" href={r.preflight.export_url}>ดาวน์โหลด CSV</a>
      {:else}
        <p class="big">{r.preflight.failing.length}<small>{" ด่านที่ยังไม่ผ่าน"}</small></p>
        <ul class="fails">
          {#each r.preflight.failing_checks ?? r.preflight.failing.map((k) => ({ key: k, label: k })) as c (c.key)}
            <li>{c.label}</li>
          {/each}
        </ul>
        <a class="btn ghost mod-cta" href="/r/p/{rid}/preflight" onclick={link}>ตรวจก่อนส่งออกไฟล์</a>
      {/if}
    </section>
    </div>
  <section class="card usebar" aria-label="การใช้ผล">
    <div class="ub-h"><b>การใช้ผล · {r.preflight.actionable} ข้อที่ต้องตรวจ</b>
      <span class="chip use use-{r.preflight.use_status}">{r.preflight.use_status_label}</span></div>
    <div class="ub" role="img" aria-label={r.preflight.use_breakdown}>
      {#each USE_PARTS as [k] (k)}
        {#if (r.preflight.use_counts[k] ?? 0) > 0}
          <span class="ub-s ub-{k}" style:flex-grow={r.preflight.use_counts[k]}></span>
        {/if}
      {/each}
    </div>
    <p class="ub-l">{#each USE_PARTS as [k, label] (k)}<span><i class="dot ub-{k}" aria-hidden="true"></i>{label} {r.preflight.use_counts[k] ?? 0}</span>{/each}</p>
    <p class="hint scope">{r.preflight.use_status_scope}</p>
  </section>
  {#if roots.length}
      <details class="card roots">
        <summary><b>สรุปการเปลี่ยนแปลงระดับรายการ</b> <span class="chip">{roots.length} รายการ</span></summary>
        <p class="hint pad">รายการในรายละเอียดงบประมาณที่ค่าต่างกัน — จุดที่ต่างในหัวข้ออื่น (ยอดรวม หมวดงบ ประมาณการ ฯลฯ)
          มักเป็นผลที่ไล่ตามมาจากรายการเหล่านี้ ยังต้องตรวจแต่ละข้อตามปกติ</p>
        {#each roots as f (f.id)}<PairRow {rid} {f} off={offsetsOf(r)} anchor={false} />{/each}
      </details>
    {/if}
  <details class="sidesd" open>
    <summary>ข้อมูลฉบับ A และ B — ไฟล์ · ช่วงหน้าที่อ่าน · ความครอบคลุมของการอ่าน</summary>
  <div class="sides">
    {#each ["A", "B"] as const as s (s)}
      {@const sd = run.sides[s]}
      <section class="card side-card side-{s.toLowerCase()}">
        <h2><span class="tag tag-{s.toLowerCase()}">{s}</span> {sd.label}</h2>
        <dl class="kv">
          <dt>ไฟล์</dt><dd>{sd.file}</dd>
          <dt>ช่วงหน้าที่ตรวจ</dt><dd>{rangeFull(sd.first, sd.last, sd.printed_offset)}{#if sd.pages_in_file} · ไฟล์ PDF มี {sd.pages_in_file} หน้า{/if}</dd>
          <dt>ได้ช่วงหน้าจาก</dt><dd>{sd.method_label || "—"}</dd>
          {#if sd.coverage}
            <dt>หัวข้อที่พบ</dt><dd>{sd.coverage.sections_found} หัวข้อ</dd>
            <dt>คำที่ระบบซ่อมอักษรไทย</dt><dd>{sd.coverage.repaired_words} คำ <span class="hint">(สระอำแตก · ลำดับวรรณยุกต์ · อักขระ PUA)</span></dd>
            <dt>หน้าที่ไม่มีชั้นข้อความ</dt><dd>{sd.coverage.pages_no_text.length ? sd.coverage.pages_no_text.join(", ") : "ไม่มี"}</dd>
          {/if}
        </dl>
      </section>
    {/each}
  </div>
  </details>
  <section class="card next">
    <h2>ขั้นต่อไป</h2>
    {#if r.preflight.ok}
      <p><span class="chip ok">พร้อมส่งออกไฟล์</span></p>
    {:else}
      <p><span class="chip warn">ยังส่งออกไฟล์ไม่ได้ — เหลือ {r.preflight.failing.length} เรื่อง</span>
        {#if r.preflight.failing_checks}<span class="hint">{r.preflight.failing_checks.map((c) => c.label).join(" · ")}</span>{/if}</p>
    {/if}
    <div class="actions">
      <a class="btn small ghost" href="/r/p/{rid}/preflight" onclick={link}>ตรวจก่อนส่งออกไฟล์</a>
      <a class="btn small ghost" href="/r/p/{rid}/preflight#export" onclick={link}>ส่งออกไฟล์ CSV</a>
      <a class="btn small ghost" href="/r/p/{rid}/audit" onclick={link}>ประวัติการบันทึก</a>
    </div>
    <p class="hint">ระบบตรวจด่านก่อนส่งออกใหม่ที่เซิร์ฟเวอร์ทุกครั้งที่ส่งออก ไม่ใช่แค่ที่หน้าจอ</p>
  </section>
  <details class="tech"><summary>รุ่นของระบบที่ใช้ในรอบนี้</summary>
    <dl class="kv">
      {#each Object.entries(run.versions) as [k, val] (k)}<dt>{k}</dt><dd class="mono">{val}</dd>{/each}
      <dt>SHA-256 ฉบับ A</dt><dd class="mono hash">{run.sides.A.sha256}</dd>
      <dt>SHA-256 ฉบับ B</dt><dd class="mono hash">{run.sides.B.sha256}</dd>
    </dl>
  </details>
  </details>

  <p class="scope-foot">ระบบบอกว่า<b>อะไรต่างและหลักฐานอยู่หน้าไหน</b> — การตัดสินว่าเป็นการปรับที่ตั้งใจหรือต้องแก้เป็นของผู้ตรวจ ·
    ผลนี้ไม่ใช่การรับรองความถูกต้องของเอกสาร · ส่วนที่ระบบอ่านไม่ได้แสดงไว้ในหัวข้อสุดท้าย</p>
{/if}

<style>
  .msg { padding: 16px; }
  .sk-hero { height: 220px; margin-bottom: 14px; }
  .sk-list { height: 50vh; }
  .back { display: inline-block; margin: 0 0 10px; font-size: .92em; text-decoration: none; }

  .head { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 10px 16px; margin-bottom: 12px; }
  h1 { margin: 0 0 4px; font-size: 1.6em; line-height: 1.3; display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
  h1 :global(.dev) { font-size: .5em; }
  .pair { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin: 0; }
  .side { display: inline-flex; align-items: center; gap: 8px; padding: 3px 12px 3px 3px; border: 1px solid var(--line);
    border-radius: 999px; background: #fff; font-size: .92em; }
  .arrow { color: var(--muted); }
  .tabs { display: inline-flex; gap: 4px; padding: 4px; border-radius: 14px; background: #e9ecf1; }
  .tab { padding: 6px 14px; border-radius: 10px; color: #344054; text-decoration: none; font-size: .92em; }
  .tab:hover { background: #fff; }
  .tab.on { background: #fff; color: var(--ink); font-weight: 600; box-shadow: 0 1px 4px rgba(16, 24, 40, .12); }
  .chip.use { font-weight: 600; }
  .use-validated { background: var(--ok-bg); color: var(--ok); }
  .use-review_complete { background: var(--warn-bg); color: var(--warn); }
  .use-blocked { background: var(--danger-bg); color: var(--danger); }
  .scope { margin: 6px 0 0; }
  .years-first { margin: 0 0 12px; padding: 10px 14px; border-radius: 14px; background: var(--warn-bg);
    border: 1px solid var(--warn-line); color: #5c3d00; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

  .mods { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 12px; }
  .mod { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; transition: transform .15s, box-shadow .2s; }
  .mod:hover { transform: translateY(-2px); box-shadow: 0 10px 28px rgba(16, 24, 40, .1); }
  .mod h2 { display: flex; align-items: center; gap: 8px; margin: 0; font-size: 1em; }
  .ico { display: inline-grid; place-items: center; width: 26px; height: 26px; border-radius: 8px; font-size: .9em; }
  .ico-a { background: var(--accent-bg); color: var(--accent); } .ico-w { background: var(--warn-bg); color: var(--warn); }
  .ico-g { background: var(--ok-bg); color: var(--ok); }
  .prog { display: flex; align-items: center; gap: 14px; }
  .ring { position: relative; width: 84px; height: 84px; flex: none; display: grid; place-items: center; }
  .ring svg { position: absolute; inset: 0; transform: rotate(-90deg); }
  .ring-bg, .ring-fg { fill: none; stroke-width: 12; }
  .ring-bg { stroke: #eef0f3; }
  .ring-fg { stroke: var(--accent); stroke-linecap: round; stroke-dasharray: 326.73px;
    transition: stroke-dashoffset .9s cubic-bezier(.22, 1, .36, 1), opacity .3s; }
  .ring-fg.zero { opacity: 0; }
  .ring-pct { font-weight: 700; font-size: 1.05em; }
  .big { margin: 0; font-size: 1.7em; font-weight: 700; line-height: 1.15; }
  .big small { font-size: .5em; font-weight: 400; color: var(--muted); }
  .ok-t { color: var(--ok); }
  .prog .hint, .mod > .hint { margin: 0; }
  .mod-cta { margin-top: auto; justify-content: center; }
  .done-note { margin: auto 0 0; color: var(--ok); font-weight: 600; }
  .tg { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
  .tg-row { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px; padding: 5px 6px; border: 0;
    border-radius: 8px; background: transparent; cursor: pointer; text-align: left; font: inherit; font-size: .88em; color: inherit; }
  .tg-row:hover { background: #f4f6f9; }
  .tg-l { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .segs { grid-column: 1 / -1; display: flex; gap: 2px; }
  /* ช่องความคืบหน้ารายหัวข้อ — ชื่อคลาสแยกจาก .seg (แถบกรอง) ไม่ให้ความสูง 6px ไปกดแถบกรองจนปุ่มล้นทับรายการ */
  .tick { flex: 1; height: 6px; border-radius: 2px; background: #e4e7ec; }
  .tick.on { background: var(--accent); }
  .bar2 { grid-column: 1 / -1; height: 6px; border-radius: 3px; background: #e4e7ec; overflow: hidden; }
  .fill2 { display: block; height: 100%; background: var(--accent); transition: width .6s cubic-bezier(.22, 1, .36, 1); }
  .fails { margin: 0; padding-left: 18px; font-size: .9em; color: #344054; }

  .usebar { padding: 12px 16px; margin-bottom: 12px; }
  .ub-h { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 6px; margin-bottom: 8px; font-size: .95em; }
  .ub { display: flex; gap: 2px; height: 12px; border-radius: 6px; overflow: hidden; background: #e4e7ec; }
  .ub-s { flex-basis: 0; min-width: 4px; }
  .ub-usable { background: var(--ok); } .ub-excluded { background: #98a2b3; } .ub-open { background: #d99a1e; }
  .ub-pending { background: #d0d5dd; }
  .ub-l { display: flex; flex-wrap: wrap; gap: 4px 16px; margin: 8px 0 0; font-size: .88em; color: #344054; }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; vertical-align: 1px; }
  .sidesd { margin-bottom: 14px; }
  .sidesd summary { cursor: pointer; color: var(--muted); font-size: .92em; padding: 4px 2px 8px; }

  .notes { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
  .notes .note { margin: 0; }
  .sides { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
  .side-card { padding: 12px 16px; }
  .side-card h2 { font-size: 1em; margin: 0 0 6px; display: flex; align-items: center; gap: 8px; }
  .side-a { border-top: 4px solid var(--a); } .side-b { border-top: 4px solid var(--b); }

  .none { padding: 16px 20px; margin-bottom: 14px; }
  .none h2 { margin: 0 0 6px; font-size: 1.1em; }
  .roots { margin-bottom: 14px; overflow: hidden; }
  .roots summary { padding: 12px 16px; cursor: pointer; }
  .pad { margin: 0; padding: 0 16px 8px; }

  .body { display: grid; grid-template-columns: 290px minmax(0, 1fr); gap: 16px; align-items: start; }
  .body.one { grid-template-columns: minmax(0, 1fr); }
  .mods.one { grid-template-columns: minmax(0, 1fr); }
  .hero .prog { flex-wrap: wrap; }
  .hero { flex-direction: row; flex-wrap: wrap; align-items: center; gap: 12px 24px; }
  .hero h2 { flex-basis: 100%; }
  .hero .mod-cta { margin: 0 0 0 auto; padding: 12px 28px; }
  .mods.two { grid-template-columns: 1fr 1fr; margin-top: 10px; }
  .rundet { margin-top: 18px; border-top: 1px solid var(--line); padding-top: 10px; }
  .rundet > summary { cursor: pointer; font-weight: 600; color: #344054; padding: 4px 2px 6px; }
  .tsel { padding: 8px 10px; border-radius: 12px; border: 1px solid #cfd4dc; font: inherit; background: #fff; max-width: 360px; }
  .side-a { color: var(--a); border-color: var(--a); font-weight: 600; } .side-b { color: var(--b); border-color: var(--b); font-weight: 600; }
  .side { padding: 3px 12px; }
  .code { color: var(--muted); font-weight: 400; }
  .topics { position: sticky; top: 64px; display: flex; flex-direction: column; gap: 4px; max-height: calc(100vh - 80px); overflow: auto;
    padding-bottom: 8px; }
  .topic { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 8px; text-align: left; padding: 8px 10px;
    border-radius: 12px; border: 1px solid transparent; background: transparent; cursor: pointer; color: inherit; font-size: .92em; }
  .topic:hover { background: #fff; border-color: var(--line); }
  .topic.on { background: #fff; border-color: var(--accent); box-shadow: var(--shadow); }
  .topic .n { color: var(--muted); font-variant-numeric: tabular-nums; }
  .topic .bar { grid-column: 1 / -1; height: 5px; border-radius: 999px; background: #eef0f3; overflow: hidden; }
  .topic .fill { display: block; height: 100%; background: var(--accent); transition: width .6s cubic-bezier(.22, 1, .36, 1); }
  .legend { margin: 6px 10px 0; font-size: .8em; }

  .tools { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; margin-bottom: 10px; }
  .seg { display: inline-flex; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 14px; background: #e9ecf1; }
  .seg button { border: 0; background: transparent; border-radius: 10px; padding: 6px 12px; cursor: pointer; color: #344054; }
  .seg button.on { background: #fff; color: var(--ink); box-shadow: 0 1px 4px rgba(16, 24, 40, .12); font-weight: 600; }
  .search { flex: 1; min-width: 220px; max-width: 360px; padding: 8px 12px; border-radius: 12px; border: 1px solid #cfd4dc;
    font: inherit; background: #fff; }
  .grp { margin-bottom: 12px; overflow: hidden; }
  .grp h2 { font-size: 1.02em; margin: 0; padding: 12px 14px 10px; }

  .next { padding: 14px 18px; margin-top: 18px; }
  .next h2 { margin: 0 0 6px; font-size: 1.05em; }
  .next p { margin: 4px 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  .actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 4px; }
  .scope-foot { color: var(--muted); font-size: .9em; margin: 14px 2px 6px; }
  .tech { color: var(--muted); font-size: .9em; }
  .tech summary { cursor: pointer; }
  .hash { overflow-wrap: anywhere; }

  @media (max-width: 980px) {
    .body { grid-template-columns: 1fr; }
    .topics { position: static; flex-direction: row; overflow-x: auto; max-height: none; }
    .topic { min-width: 220px; }
    .legend { display: none; }
  }
  @media (max-width: 1100px) { .mods { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 760px) {
    .mods, .sides { grid-template-columns: 1fr; }
  }
</style>
