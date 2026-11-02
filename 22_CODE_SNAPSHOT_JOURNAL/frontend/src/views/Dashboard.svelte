<script lang="ts">
  import { get, type Meta, type Result } from "../lib/api";
  import { link } from "../lib/router.svelte";
  import Metrics from "../lib/Metrics.svelte";

  let { sid }: { sid: string } = $props();
  let r = $state<Result | null>(null);
  let meta = $state<Meta | null>(null);
  let err = $state("");
  Promise.all([get<Result>(`/api/trial/s/${sid}/result`), get<Meta>("/api/trial/meta")])
    .then(([a, b]) => { r = a; meta = b; }).catch((e) => (err = e.message));
</script>

{#if err}
  <div class="card msg">{err}</div>
{:else if !r || !meta}
  <div class="card skeleton sk"></div>
{:else}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>แดชบอร์ด</b> · {r.session.book.title} · {r.session.book.agency}</div>
    {#if r.complete}<span class="chip ok">ยืนยันครบ</span>{:else}<a class="chip" href="/r/s/{sid}/result" onclick={link}>ยังยืนยันไม่ครบ — ไปยืนยันต่อ</a>{/if}
  </div>

  <Metrics m={r.metrics} {meta} extrasTotal={r.extras.length} big />

  <section class="card how">
    <h2>อ่านผลนี้อย่างไร</h2>
    <ul>
      <li>เป็นผลของเล่มนี้ ผู้ตรวจหนึ่งคน ระบบรุ่น {r.versions.pdfbook} เท่านั้น — ไม่ใช้กับเอกสารอื่นและไม่ใช่ร้อยละความแม่นยำ</li>
      <li>"พบตรง" นับเมื่อคุณยืนยันเอง · ข้อที่ยังไม่ยืนยันไม่นับเป็นพบ</li>
      <li>ข้อมูลประกอบของระบบ ({r.metrics.info} รายการ) ไม่นับเป็นยกเพิ่ม</li>
      <li>ผลนี้ไม่ได้บอกว่าเอกสารถูกต้อง และไม่ได้วัดเวลาที่ใช้</li>
    </ul>
    <div class="act">
      <a class="btn" href="/trial/s/{sid}/summary.json">ดาวน์โหลดสรุป (เฉพาะจำนวน)</a>
      <a class="btn ghost" href="/r/s/{sid}/survey" onclick={link}>แก้แบบสอบถาม</a>
    </div>
    <p class="hint">ไฟล์สรุปมีเฉพาะจำนวน รุ่นระบบ แฮชของเล่ม และคำตอบแบบสอบถาม — ไม่มีตำแหน่งหรือหมายเหตุของจุดที่วง ·
      ทุกครั้งที่ดาวน์โหลด ระบบบันทึกแฮชของไฟล์ไว้</p>
  </section>
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; }
  .title { flex: 1; }
  .msg { padding: 16px; } .sk { height: 50vh; }
  .how { padding: 6px 22px 14px; margin-top: 18px; }
  .act { display: flex; gap: 10px; flex-wrap: wrap; }
  a.chip { text-decoration: none; color: inherit; }
</style>
