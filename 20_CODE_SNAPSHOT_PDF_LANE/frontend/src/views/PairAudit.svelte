<script lang="ts">
  // Audit ของรอบเทียบเล่ม — ทุกเหตุการณ์ของรอบนี้ + สถานะสายโซ่แฮชของทั้งระบบ (อ่านอย่างเดียว)
  import { link } from "../lib/router.svelte";
  import { lane } from "../lib/lane.svelte";
  import { slide, fadeOn } from "../lib/motion";
  import { loadAudit, loadRun, peekRun, type PAudit, type PRun } from "../lib/pair";

  let { rid }: { rid: string } = $props();
  let a = $state<PAudit | null>(null);
  let r = $state<PRun | null>(peekRun(rid) ?? null);
  let err = $state("");
  let kind = $state("");
  let newest = $state(true);
  loadAudit(rid).then((x) => (a = x)).catch((e) => (err = (e as Error).message));
  loadRun(rid, 30000).then((x) => (r = x)).catch(() => {});

  const kinds = $derived.by(() => {
    const m = new Map<string, { label: string; n: number }>();
    for (const e of a?.entries ?? []) {
      const k = m.get(e.action) ?? { label: e.action_label, n: 0 };
      k.n++; m.set(e.action, k);
    }
    return [...m.entries()];
  });
  const rows = $derived.by(() => {
    const xs = (a?.entries ?? []).filter((e) => !kind || e.action === kind);
    return newest ? [...xs].reverse() : xs;
  });
  const fidOf = (o: string) => (o.includes("/") ? o.split("/", 2)[1] : "");
  const when = (s: string) => s.slice(0, 19).replace("T", " ");
</script>

{#if err}
  <div class="card msg">{err} · <a href="/r/p/{rid}" onclick={link}>กลับไปภาพรวม</a></div>
{:else if !a}
  <div class="card skeleton sk"></div>
{:else}
  <div class="bar">
    <a class="btn small ghost" href="/r/p/{rid}" onclick={link}>← ภาพรวม</a>
    <h1>ประวัติการบันทึกของรอบนี้</h1>
    {#if r}<span class="hint">{r.run.agency} · {r.run.mode_label}</span>{/if}
  </div>
  <p class="hint lead">สร้างรอบ บันทึกความเห็น ยืนยันปีงบ หรือส่งออก — ระบบจดไว้ที่นี่ทุกครั้ง{#if !lane.pdfOnly}{" · "}<a href="/audit">ดู Audit ทั้งระบบ (หน้าเดิม)</a>{/if}</p>

  {#if a.chain.ok}
    <p class="note ok"><b>✓ ประวัติครบ ไม่มีการแก้ย้อนหลัง</b> <span class="hint">(ตรวจแล้ว {a.chain.checked.toLocaleString("th-TH")} รายการ)</span></p>
  {:else}
    <p class="note danger" role="alert"><b>ประวัติไม่ต่อเนื่อง</b> — พบความผิดปกติที่ลำดับ {a.chain.broken_at_seq}</p>
  {/if}

  <div class="tools">
    <div class="seg" role="tablist" aria-label="ชนิดเหตุการณ์" use:slide>
      <button role="tab" aria-selected={!kind} class:on={!kind} onclick={() => (kind = "")}>ทั้งหมด <span class="chip">{a.entries.length}</span></button>
      {#each kinds as [k, v] (k)}
        <button role="tab" aria-selected={kind === k} class:on={kind === k} onclick={() => (kind = k)}>{v.label} <span class="chip">{v.n}</span></button>
      {/each}
    </div>
    <button class="btn small ghost" onclick={() => (newest = !newest)}>{newest ? "ใหม่ → เก่า" : "เก่า → ใหม่"}</button>
  </div>

  {#if !rows.length}
    <p class="empty">ยังไม่มีเหตุการณ์ของรอบนี้</p>
  {:else}
    <ol class="timeline" use:fadeOn={kind}>
      {#each rows as e (e.seq)}
        {@const fid = fidOf(e.object_id)}
        <li class="card ev">
          <div class="meta"><span class="mono seq">#{e.seq}</span> <span class="mono">{when(e.at)}</span>
            <span class="chip">{e.action_label}</span>
            {#if fid && e.action === "pdfpair_decision"}<a class="mono" href="/r/p/{rid}/f/{fid}" onclick={link}>ข้อ {fid}</a>{/if}</div>
          <p class="sum">{e.summary || "—"}</p>
          <details><summary>ข้อมูลเต็ม</summary>
            <pre class="mono">{JSON.stringify(e.detail, null, 2)}</pre>
            <p class="mono hash">{e.entry_hash}</p></details>
        </li>
      {/each}
    </ol>
  {/if}
{/if}

<style>
  .msg { padding: 16px; }
  .sk { height: 50vh; }
  .bar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 14px; margin-bottom: 4px; }
  .bar h1 { margin: 0; font-size: 1.5em; }
  .lead { margin: 0 0 12px; }
  .tools { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; justify-content: space-between; margin: 12px 0 10px; }
  .seg { display: inline-flex; flex-wrap: wrap; gap: 4px; padding: 4px; border-radius: 14px; background: #e9ecf1; }
  .seg button { border: 0; background: transparent; border-radius: 10px; padding: 6px 12px; cursor: pointer; color: #344054; }
  .seg button.on { background: #fff; color: var(--ink); box-shadow: 0 1px 4px rgba(16, 24, 40, .12); font-weight: 600; }
  .timeline { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  .ev { padding: 10px 14px; }
  .meta { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; color: var(--muted); }
  .seq { color: var(--ink); font-weight: 600; }
  .sum { margin: 6px 0 4px; }
  details summary { cursor: pointer; color: var(--muted); font-size: .9em; }
  pre { margin: 6px 0; padding: 8px 10px; background: #f6f7f9; border-radius: 10px; overflow-x: auto; white-space: pre-wrap;
    word-break: break-word; font-size: .85em; }
  .hash { overflow-wrap: anywhere; color: var(--muted); font-size: .8em; }
</style>
