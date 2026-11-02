<script lang="ts">
  // ใช้ผลของระบบ (วิธีวัดผลฉบับ 0.2): จับคู่ประเด็น ↔ ข้อสังเกต (ระบบเสนอ ผู้ตรวจยืนยัน · หลายต่อหลาย) · รหัสเหตุ ·
  // หลักฐานชี้ตำแหน่ง · ฐานการวินิจฉัย · ส1–ส4 · บัญชี F · ข้อสังเกตหลังล็อก · จบการใช้ผล · รอบกติกา 0.1 อ่านอย่างเดียว
  import { onMount } from "svelte";
  import { ApiError, get, post, postDims, reloadOnRestore, scoped, short, xtypesFor, type AnyResult, type Finding, type Issue, type LegacyResult,
           type Meta, type Result, type Side } from "../lib/api";
  import { go, link } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";
  import Metrics from "../lib/Metrics.svelte";

  let { sid, meta }: { sid: string; meta: Meta } = $props();
  // svelte-ignore state_referenced_locally
  const SID = sid;

  let res = $state<AnyResult | null>(null);
  let err = $state("");
  let runFailed = $state(false);
  let busy = $state<string | null>(null);
  let filter = $state<"todo" | "all">("todo");
  type Draft = { ids: string[]; verdict: string; reason: string; evidence: string; basis: string; change: string; q: string;
                 location: string; sides: string[]; scope: string };
  type ODraft = { fidelity: string; reason: string; dims: Record<string, string>; und: boolean; basis: string; change: string };
  let odrafts = $state<Record<string, ODraft>>({});
  let drafts = $state<Record<string, Draft>>({});
  type GDraft = { grp: string; s3: string; basis: string; ref: string; change: string; part: string; note: string };
  let gdrafts = $state<Record<string, GDraft>>({});
  let note = $state({ part: "", topic: "", note: "" });
  let finishReason = $state("");
  let stOpen = $state(false), stStatus = $state(""), stReason = $state(""), stNoUse = $state(false), stConfirm = $state(false);

  function load() {
    get<AnyResult>(`/api/trial/s/${SID}/result`).then(set).catch((e) => {
      err = e.message;
      runFailed = e instanceof ApiError && e.code === "conflict" && e.message.includes("ลองเทียบอีกครั้ง");
    });
  }
  load();
  onMount(reloadOnRestore);

  function set(x: AnyResult) {
    res = x;
    err = "";
    runFailed = false;
    if (x.legacy) return;
    for (const i of x.issues) {
      const d = i.decision;
      drafts[i.id] = { ids: d ? [...i.links] : (i.proposal ? [i.proposal] : []), verdict: d?.verdict ?? "",
                       reason: d?.reason ?? "", evidence: d?.evidence ?? "", basis: d?.basis ?? "", change: "", q: "",
                       location: d?.location ?? "", sides: d?.relevant_sides ? d.relevant_sides.split(",") : ["A", "B"],
                       scope: d?.search_scope ?? "" };
    }
    for (const fid of x.u_ids) {
      const e = x.obs_eval[fid];
      odrafts[fid] = { fidelity: e?.fidelity ?? "", reason: e?.fidelity_reason ?? "", dims: { ...(e?.dims ?? {}) },
                       und: e?.assertion === "undecidable" && !Object.keys(e?.dims ?? {}).length, basis: e?.basis ?? "",
                       change: "" };
    }
    for (const u of x.unmatched) {
      const g = u.group;
      gdrafts[u.id] = { grp: g?.grp ?? "", s3: g?.s3_reason ?? "", basis: g?.basis ?? "", ref: g?.issue_ref ?? "", change: "",
                        part: g?.part ?? "", note: g?.note ?? "" };
    }
  }

  const r = $derived(res && !res.legacy ? (res as Result) : null);
  const legacy = $derived(res && res.legacy ? (res as LegacyResult) : null);
  const live = $derived(!!r && r.session.active);
  const F = (id: string): Finding | undefined => r?.findings[id];
  const L = (side: string) => (side ? res?.session.labels[side as Side] ?? "" : "");
  const issues = $derived(r ? (filter === "todo" ? r.issues.filter((i) => i.gaps.length) : r.issues) : []);
  const unmatched = $derived(r ? (filter === "todo" ? r.unmatched.filter((u) => !u.group || !u.group.grp) : r.unmatched) : []);
  const todo = $derived(r ? r.issues.filter((i) => i.gaps.length).length + r.unmatched.filter((u) => !u.group || !u.group.grp).length : 0);
  const matchable = $derived(r ? Object.values(r.findings).filter((f) => f.level !== "unread") : []);

  function pageOf(f: Finding, side: string): number | null { return side === "prev" ? f.page_prev : f.page_cur; }
  /** ข้อสังเกตที่เลือกจับคู่ได้ — หน้าใกล้ในฉบับเดียวกันก่อน แล้วหัวข้อเดียวกัน (ย้ายหน้าได้ เลือกจากหน้าอื่นได้เสมอ) */
  function candidates(i: Issue, q: string): Finding[] {
    const words = q.trim().toLowerCase();
    const list = words ? matchable.filter((f) => `${f.subject} ${f.kind} ${f.column} หน้า ${f.page_cur ?? ""} ${f.page_prev ?? ""}`
      .toLowerCase().includes(words)) : matchable;
    const key = (f: Finding) => {
      const p = i.side ? pageOf(f, i.side) : null;
      const near = p != null && i.page && Math.abs(p - i.page) <= 1;
      return [near ? 0 : f.topic_code === i.topic ? 1 : 2, Math.abs((p ?? f.page_cur ?? f.page_prev ?? 0) - (i.page || 0)), f.info ? 1 : 0];
    };
    return [...list].sort((a, b) => { const x = key(a), y = key(b); return x[0] - y[0] || x[1] - y[1] || x[2] - y[2]; }).slice(0, 8);
  }
  const toggle = (d: Draft, id: string) => { d.ids = d.ids.includes(id) ? d.ids.filter((x) => x !== id) : [...d.ids, id]; };

  async function call(key: string, url: string, body: Record<string, unknown>, ok = "บันทึกแล้ว") {
    busy = key;
    try { set(await post<Result>(url, body)); toast(ok); }
    catch (e) {
      toast((e as Error).message, true);
      if (e instanceof ApiError && e.code === "locked") load();
    } finally { busy = null; }
  }
  const decide = (i: Issue) => {
    const d = drafts[i.id];
    return call(i.id, `/api/trial/s/${SID}/issue/${i.id}`, { verdict: d.verdict, finding_ids: d.ids, reason: d.reason,
      evidence: d.evidence, basis: d.basis, change_reason: d.change, location: d.location, relevant_sides: d.sides,
      search_scope: d.scope });
  };
  const evalObs = (fid: string) => {
    const o = odrafts[fid];
    return call(fid, `/api/trial/s/${SID}/obs/${fid}`, { fidelity: o.fidelity, fidelity_reason: o.reason, dims: o.dims,
      assertion_undecidable: o.und, basis: o.basis, change_reason: o.change });
  };
  const toggleSide = (d: Draft, s: string) => { d.sides = d.sides.includes(s) ? d.sides.filter((x) => x !== s) : [...d.sides, s].sort(); };
  const saveRow = (i: Issue, patch: Record<string, unknown>) => call(i.id, `/api/trial/s/${SID}/row/${i.id}`, patch);
  const group = (id: string) => {
    const g = gdrafts[id];
    return call(id, `/api/trial/s/${SID}/finding/${id}`, { group: g.grp, s3_reason: g.s3, basis: g.basis,
      issue_ref: g.ref, change_reason: g.change, part: g.part, note: g.note });
  };
  async function addNote() {
    await call("note", `/api/trial/s/${SID}/note`, note, "จดข้อสังเกตหลังล็อกแล้ว");
    note = { part: "", topic: "", note: "" };
  }
  async function retry() {
    busy = "run";
    try { await post(`/api/trial/s/${SID}/run`); load(); toast("ระบบเทียบสำเร็จ"); }
    catch (e) { toast((e as Error).message, true); } finally { busy = null; }
  }
  async function finish() {
    busy = "finish";
    try { await post(`/api/trial/s/${SID}/finish`, { reason: finishReason }); go(`/r/s/${SID}/survey`); }
    catch (e) { toast((e as Error).message, true); } finally { busy = null; }
  }
  async function setStatus() {
    try {
      await post(`/api/trial/s/${SID}/status`, { status: stStatus, reason: stReason, no_data_use: stNoUse, confirm: true });
      stOpen = false; load(); toast(`บันทึกสถานะแล้ว — ${meta.statuses[stStatus]}`);
    } catch (e) { toast((e as Error).message, true); }
  }
  const verdictText = (h: Record<string, unknown> | null) => (h && h.verdict ? meta.verdicts[h.verdict as string] : "—");
</script>

{#if err}
  <div class="card msg">{err}
    {#if runFailed}<div class="act"><button class="btn" disabled={busy === "run"} onclick={retry}>
      {busy === "run" ? "ระบบกำลังเทียบเล่ม…" : "ลองเทียบอีกครั้ง"}</button></div>{/if}
    · <a href="/r/s/{SID}" onclick={link}>กลับไปหน้าตรวจ</a></div>
{:else if !res}
  <div class="card skeleton sk"></div>
{:else if legacy}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>{legacy.session.book.title}</b> · ผลของรอบกติกา 0.1</div>
    <span class="chip ok">ส่งผลแล้ว {legacy.session.locked_at.slice(0, 16).replace("T", " ")}</span>
  </div>
  <div class="card note warn"><b>รอบกติกา 0.1 — อ่านได้อย่างเดียว</b> · รอบนี้ส่งผลก่อนเปลี่ยนเป็นวิธีวัดผลฉบับ 0.2 จึงนับตามฉบับ 0.1
    และไม่ใช้ในผลฉบับ 0.2 · ข้อมูลเดิมเก็บไว้ครบ · ถ้าจะนับตามฉบับ 0.2 ให้เริ่มรอบใหม่จากหน้าเลือกเล่ม</div>
  <div class="grid">
    {#each Object.entries(meta.pens) as [k, l] (k)}
      {@const c = legacy.metrics.pens[k as "red"]}
      <div class="card metric"><span class="hint">{short(l)}</span><b>{c.exact} / {c.total}</b>
        <small>บางส่วน {c.partial} · ระบบไม่ได้ยก {c.missed}{c.pending ? ` · ยังไม่ยืนยัน ${c.pending}` : ""}</small></div>
    {/each}
  </div>
  <h2>จุดที่วง <span class="hint">({legacy.marks.length})</span></h2>
  {#each legacy.marks as m (m.id)}
    <article class="card item item-{m.pen}">
      <header><b>{short(meta.pens[m.pen as "red"])}</b> · {L(m.side)} หน้า {m.page}{#if m.topic}{` · ${m.topic}`}{/if}
        <span class="chip" class:ok={!!m.verdict}>{m.verdict ? meta.legacy_link_verdicts[m.verdict] : "ยังไม่ยืนยัน"}</span></header>
      {#if m.finding}<p>{m.proposed && !m.verdict ? "ระบบเสนอว่าตรงกับ" : "จับคู่กับ"}: <b>{m.finding.subject}</b> · {m.finding.kind}
        · <a href={m.finding.evidence} target="_blank" rel="noopener">ดูหลักฐาน ↗</a></p>{/if}
    </article>
  {/each}
  <h2>ข้อที่ระบบยกเพิ่ม <span class="hint">({legacy.extras.length})</span></h2>
  {#each legacy.extras as f (f.id)}
    <article class="card item"><header><b>{f.subject}</b> · {f.kind}
      {#if f.verdict}<span class="chip ok">{meta.legacy_extra_verdicts[f.verdict]}</span>{/if}</header></article>
  {/each}
  <div class="next"><a class="btn ghost" href="/trial/s/{SID}/summary.json">ดาวน์โหลดสรุปของรอบนี้ (ฉบับ 0.1 · เฉพาะจำนวน)</a></div>
{:else if r}
  {@const st = r.status}
  <div class="bar">
    <a class="btn ghost small" href="/r" onclick={link}>← เล่มทั้งหมด</a>
    <div class="title"><b>{r.session.book.title}</b> · {r.session.book.agency} · ระบบเจออะไร</div>
    <span class="chip">{meta.paths[r.session.path]}</span>
    <span class="chip ok">ส่งใบประกาศแล้ว {r.session.locked_at.slice(0, 16).replace("T", " ")}</span>
  </div>
  {#if !live}<div class="card note">รอบนี้{meta.statuses[r.session.status]}แล้ว — ดูได้อย่างเดียว</div>{/if}
  <p class="hint lead">รายการของท่านล็อกไว้ก่อนระบบเทียบ · ระบบ<b>เสนอ</b>คู่จากหน้าและตำแหน่ง ท่านเป็นผู้ยืนยันทุกข้อ ·
    จับคู่ได้ทั้งข้อ{meta.finding_levels.must}และ{meta.finding_levels.info} · ในภาพหลักฐาน {r.session.labels.prev} = ซ้าย · {r.session.labels.cur} = ขวา</p>
  {#if st.flags.length}<p class="flags">{#each st.flags as f (f)}<span class="chip">{meta.status_text.flags[f]}</span>{/each}</p>{/if}

  <Metrics m={r.metrics} {meta} />

  <div class="filter" role="tablist">
    <button role="tab" class:on={filter === "todo"} aria-selected={filter === "todo"} onclick={() => (filter = "todo")}>
      ยังไม่ครบ <span class="chip">{todo}</span></button>
    <button role="tab" class:on={filter === "all"} aria-selected={filter === "all"} onclick={() => (filter = "all")}>ทั้งหมด</button>
    {#if r.complete}<span class="chip ok">จับคู่และจัดกลุ่มครบแล้ว</span>{/if}
  </div>

  <h2>๑. ประเด็นในรายการของท่าน <span class="hint">({r.issues.length}){r.session.path === "r1" ? " — กรอกลักษณะของแต่ละแถวจากรายการของท่าน (ไม่ต้องใส่เนื้อหา) แล้วจับคู่" : ""}</span></h2>
  {#if !issues.length}<p class="hint">{filter === "todo" ? "ครบทุกประเด็นแล้ว" : "ไม่มีประเด็นในรายการ"}</p>{/if}
  {#each issues as i (i.id)}
    {@const d = drafts[i.id]}
    {@const prop = i.proposal ? F(i.proposal) : undefined}
    <article class="card item item-{i.pen || i.level || 'row'}" class:busy={busy === i.id}>
      <header>
        {#if i.origin === "row"}<b>ประเด็น {i.topic}-{i.seq}</b>{#if i.ref}{` · ข้อ ${i.ref} ในรายการของท่าน`}{/if}
        {:else}<span class="dot dot-{i.pen}" aria-hidden="true"></span> <b>{short(meta.pens[i.pen as "red"])}</b> · {L(i.side)} หน้า {i.page}
          · <a href="/r/s/{SID}?{i.side === 'cur' ? `p=${i.page}` : `pp=${i.page}`}" onclick={link}>ดูจุดบนหน้า</a>{/if}
        {` · ${i.topic} ${meta.topics.find((t) => t.code === i.topic)?.label ?? ""}`}{#if i.part}{` · ส่วน ${i.part}`}{/if}
        {#if i.cause}{` · ${short(meta.causes[i.cause])}`}{/if}{#if i.level}{` · ${short(meta.levels[i.level])}`}{/if}
        {#if i.note}{` · “${i.note}”`}{/if}
        {#if postDims(i.row_source).length}<span class="chip">จัดใหม่หลังเห็นผล: {postDims(i.row_source).map((d) => meta.post_dims[d]).join(" · ")} — แยกเฉพาะมิตินี้</span>{/if}
        {#if i.part && !i.in_scope}<span class="chip">นอกส่วนที่ตรวจครบ — ไม่นับในตัวหาร</span>{/if}
        {#if !i.gaps.length && i.decision}<span class="chip ok">{meta.verdicts[i.decision.verdict]}</span>
        {:else}<span class="chip">ยังขาด: {i.gaps.join(", ")}</span>{/if}
      </header>

      {#if i.origin === "row" && live}
        <div class="rowform">
          <label>ส่วน <select value={i.part} onchange={(e) => saveRow(i, { part: e.currentTarget.value })}>
            <option value="">—</option>{#each meta.parts as p (p.code)}<option value={p.code}>{p.code} {p.label.slice(0, 36)}</option>{/each}</select></label>
          <label>ต/ล <select value={i.cause} onchange={(e) => saveRow(i, { cause: e.currentTarget.value })}>
            <option value="">—</option>{#each Object.entries(meta.causes) as [k, l] (k)}<option value={k}>{l}</option>{/each}</select></label>
          <label>ระดับ <select value={i.level} onchange={(e) => saveRow(i, { level: e.currentTarget.value })}>
            <option value="">—</option>{#each Object.entries(meta.levels) as [k, l] (k)}<option value={k}>{l}</option>{/each}</select></label>
          <label>ข้อที่ในรายการที่ล็อก <input size="6" maxlength="40" value={i.ref} onchange={(e) => saveRow(i, { ref: e.currentTarget.value })}></label>
          {#if r.session.xkind === "cross_year"}
            <label>ชนิดประเด็น (คู่ข้ามปี) <select value={i.xtype ?? ""} onchange={(e) => saveRow(i, { xtype: e.currentTarget.value })}>
              <option value="">—</option>{#each xtypesFor(meta, i.topic) as k (k)}<option value={k}>{meta.xtypes[k]}</option>{/each}</select></label>
          {/if}
          <label>ที่มาของลักษณะ <select value={i.row_source === "transcribed" ? "transcribed" : postDims(i.row_source).length ? "post" : ""}
              onchange={(e) => saveRow(i, { row_source: e.currentTarget.value === "transcribed" ? "transcribed" : e.currentTarget.value === "post" ? "post:level" : "" })}>
            <option value="">—</option><option value="transcribed">{meta.row_sources.transcribed}</option>
            <option value="post">{meta.row_sources.post_result}</option></select></label>
          {#if postDims(i.row_source).length}
            <span class="dims">จัดใหม่หลังเห็นผล:
              {#each Object.entries(meta.post_dims) as [d, l] (d)}
                <label class="dim"><input type="checkbox" checked={postDims(i.row_source).includes(d)}
                  onchange={(e) => { const cur = postDims(i.row_source).filter((x) => x !== d);
                    const next = e.currentTarget.checked ? [...cur, d] : cur;
                    saveRow(i, { row_source: next.length ? `post:${next.join(",")}` : "transcribed" }); }}> {l}</label>
              {/each}</span>
          {/if}
          <label>อยู่ที่ <select value={i.side} onchange={(e) => saveRow(i, { side: e.currentTarget.value })}>
            <option value="">—</option>{#each ["prev", "cur"] as k (k)}<option value={k}>{L(k)}</option>{/each}</select></label>
          <label>หน้า <input size="4" inputmode="numeric" value={i.page || ""} onchange={(e) => saveRow(i, { page: e.currentTarget.value })}></label>
          <label>ของที่หาย — ฉบับที่พบ <select value={i.found_in} onchange={(e) => saveRow(i, { found_in: e.currentTarget.value })}>
            <option value="">ไม่ใช่ของที่หาย</option>{#each ["prev", "cur"] as k (k)}<option value={k}>{L(k)}</option>{/each}</select></label>
          {#if i.found_in}<label>ขอบเขตที่ค้นในอีกฉบับ <input maxlength="200" value={i.searched}
            onchange={(e) => saveRow(i, { searched: e.currentTarget.value })}></label>{/if}
        </div>
      {/if}

      {#if prop}
        <p>ระบบเสนอ: <b>{prop.subject}</b> · {prop.kind}{#if prop.column}{` · ${prop.column}`}{/if}
          <span class="chip">{meta.finding_levels[prop.level]}</span> · <a href={prop.evidence} target="_blank" rel="noopener">ดูหลักฐาน ↗</a></p>
      {:else if i.origin !== "row"}
        <p class="hint">ระบบไม่มีข้อสังเกตบนตำแหน่งนี้ — ถ้าระบบยกไว้ที่อื่น (ย้ายหน้า) ค้นจากช่องด้านล่าง · {meta.p1_hint}</p>
      {/if}

      {#if live && d}
        <div class="decide">
          <div class="picked">
            <span class="hint">ข้อสังเกตที่ตรงกับประเด็นนี้ (พบตรง/บางส่วน · หลายข้อได้):</span>
            {#each d.ids as id (id)}
              {@const f = F(id)}
              <span class="pick">{f ? f.subject.slice(0, 50) : id} <span class="chip">{f ? meta.finding_levels[f.level] : ""}</span>
                {#if f}<a href={f.evidence} target="_blank" rel="noopener">หลักฐาน ↗</a>{/if}
                <button class="x" aria-label="เอาออก" onclick={() => toggle(d, id)}>×</button></span>
            {/each}
          </div>
          <label class="search">ค้นข้อสังเกต (ชื่อรายการ/หน้า) <input bind:value={d.q} placeholder="เช่น หน้า 5 หรือ ชื่อรายการ"></label>
          <div class="cands">
            {#each candidates(i, d.q).filter((f) => !d.ids.includes(f.id)) as f (f.id)}
              <button class="cand" onclick={() => toggle(d, f.id)}>+ หน้า {pageOf(f, i.side || "cur") ?? f.page_cur ?? f.page_prev ?? "—"} · {f.subject.slice(0, 46)}
                <span class="chip">{meta.finding_levels[f.level]}</span></button>
            {/each}
          </div>
          <div class="radios"><span class="lbl">ผล</span>
            {#each Object.entries(meta.verdicts) as [k, l] (k)}<label><input type="radio" bind:group={d.verdict} value={k}> {l}</label>{/each}
            {#if d.verdict === "partial"}<select bind:value={d.reason} aria-label="รหัสเหตุ บ"><option value="">— รหัสเหตุ —</option>
              {#each Object.entries(r.session.v03 ? meta.partial_reasons_v03 : meta.partial_reasons) as [k, l] (k)}<option value={k}>{l}</option>{/each}</select>{/if}
            {#if d.verdict === "missed"}<select bind:value={d.reason} aria-label="รหัสเหตุ พ"><option value="">— รหัสเหตุ —</option>
              {#each Object.entries(meta.miss_reasons) as [k, l] (k)}<option value={k}>{l}</option>{/each}</select>{/if}
          </div>
          {#if (d.verdict === "exact" || d.verdict === "partial") && r.session.v03}
            <fieldset class="loc"><legend>ตำแหน่ง (A2) — ขั้นแยกหลังตัดสินผลจากเนื้อหา · เลือกข้อแรกที่เข้าตามลำดับ</legend>
              <div class="radios">{#each Object.entries(meta.locations) as [k, l] (k)}<label><input type="radio" bind:group={d.location} value={k}> {l}</label>{/each}</div>
              <div class="radios"><span class="lbl">ฝั่งที่เกี่ยวข้อง</span>
                {#each [["A", r.session.labels.prev], ["B", r.session.labels.cur]] as [k, l] (k)}
                  <label><input type="checkbox" checked={d.sides.includes(k)} onchange={() => toggleSide(d, k)}> {l}</label>{/each}
                <span class="hint">เพิ่ม/หาย = ฉบับที่มี</span></div>
              {#if d.sides.length === 1}<label>ขอบเขตที่ค้นในอีกฉบับ <input maxlength="200" bind:value={d.scope} placeholder="ส่วน · หน้า"></label>{/if}
            </fieldset>
          {:else if d.verdict === "exact" || d.verdict === "partial"}
            <div class="radios"><span class="lbl">หลักฐานชี้ตำแหน่ง</span>
              {#each Object.entries(meta.evidence) as [k, l] (k)}<label><input type="radio" bind:group={d.evidence} value={k}> {l}</label>{/each}</div>
          {/if}
          <div class="radios"><span class="lbl">ฐานการวินิจฉัย</span>
            {#each Object.entries(meta.basis) as [k, l] (k)}<label><input type="radio" bind:group={d.basis} value={k}> {l}</label>{/each}</div>
          {#if i.decision}<label class="change">เหตุผลที่เปลี่ยนคู่หรือผลเดิม <input maxlength="300" bind:value={d.change}></label>{/if}
          <button class="btn small" disabled={busy === i.id} onclick={() => decide(i)}>บันทึกผล</button>
        </div>
      {/if}
      {#if i.history.length > 1}
        <details class="hist"><summary>ประวัติการเปลี่ยนคู่ ({i.history.length})</summary><ol>
          {#each i.history as h, k (k)}<li>{h.at.slice(0, 16).replace("T", " ")} · {verdictText(h.before)} → {verdictText(h.after)}
            ({((h.after.links as string[]) ?? []).length} ข้อสังเกต){#if h.reason}{` · เหตุผล: ${h.reason}`}{/if}</li>{/each}</ol></details>
      {/if}
    </article>
  {/each}

  <h2>๒. ข้อสังเกต{meta.finding_levels.must}ที่ไม่ได้จับคู่ <span class="hint">({r.unmatched.length})</span></h2>
  <p class="hint">ตัดสินจาก<b>ภาพหน้าเอกสาร</b> ไม่ใช่จากข้อความที่ระบบแสดง · การเปลี่ยนที่ตั้งใจซึ่งระบบรายงานถูก (เช่น ปรับวงเงินจริง)
    ที่ไม่อยู่ในรายการ = ส1 · ข้อในส่วนที่ท่านไม่ได้ตรวจครบ เลือก "{meta.groups.outside}"</p>
  {#if !unmatched.length}<p class="hint">{filter === "todo" ? "จัดครบทุกข้อแล้ว" : "ไม่มี"}</p>{/if}
  {#each unmatched as u (u.id)}
    {@const f = F(u.id)}
    {@const g = gdrafts[u.id]}
    {#if f && g}
      <article class="card item" class:busy={busy === u.id}>
        <header><b>{f.subject}</b> · {f.kind}{#if f.column}{` · ${f.column}`}{/if}
          {#if f.page_prev}{` · ${r.session.labels.prev} หน้า ${f.page_prev}`}{/if}{#if f.page_cur}{` · ${r.session.labels.cur} หน้า ${f.page_cur}`}{/if}
          · <a href={f.evidence} target="_blank" rel="noopener">ดูหลักฐาน ↗</a>
          {#if u.group?.grp}<span class="chip ok">{meta.groups[u.group.grp].split(" (")[0]}</span>{/if}</header>
        {#if f.a || f.b}<p class="mono">{f.a} → {f.b}</p>{/if}
        {#if f.caveats?.length}<p class="caveat">⚠ ต้องให้คนยืนยันก่อนใช้: {f.caveats.join(" · ")}</p>{/if}
        {#if live}
          <div class="radios">
            {#each Object.entries(meta.groups) as [k, l] (k)}<label><input type="radio" bind:group={g.grp} value={k}> {l}</label>{/each}
          </div>
          {#if g.grp === "s3"}<label>เหตุของ ส3 <select bind:value={g.s3}><option value="">—</option>
            {#each Object.entries(meta.s3_reasons) as [k, l] (k)}<option value={k}>{l}</option>{/each}</select></label>{/if}
          {#if g.grp === "s2"}<label>เป็นผลที่ตามมาของ <select bind:value={g.ref}><option value="">—</option>
            {#each r.issues as i (i.id)}<option value={i.id}>{i.origin === "row" ? `ประเด็น ${i.topic}-${i.seq}` : `${L(i.side)} หน้า ${i.page} · ${i.topic}`}</option>{/each}</select></label>{/if}
          {#if g.grp === "outside"}
            <label>ส่วนที่ใบประกาศระบุว่าไม่ได้ตรวจครบ <select bind:value={g.part}><option value="">—</option>
              {#each meta.parts.filter((p) => r!.declaration.parts[p.code] !== "full") as p (p.code)}
                <option value={p.code}>{p.code} ({meta.coverage[r!.declaration.parts[p.code]]})</option>{/each}</select></label>
            <label>เหตุของข้อนี้ <input maxlength="200" bind:value={g.note}></label>
          {/if}
          {#if g.grp && g.grp !== "outside"}
            <div class="radios"><span class="lbl">ฐานการวินิจฉัย</span>
              {#each Object.entries(meta.basis) as [k, l] (k)}<label><input type="radio" bind:group={g.basis} value={k}> {l}</label>{/each}</div>
          {/if}
          {#if u.group}<label class="change">เหตุผลที่เปลี่ยนกลุ่มเดิม <input maxlength="300" bind:value={g.change}></label>{/if}
          <button class="btn ghost small" disabled={busy === u.id || !g.grp} onclick={() => group(u.id)}>บันทึก</button>
        {/if}
      </article>
    {/if}
  {/each}

  {#if r.session.v03}
    <h2>๒ก. ประเมินข้อสังเกตในบัญชี F (A3) <span class="hint">({Object.keys(r.obs_eval).filter((x) => r!.u_ids.includes(x)).length}/{r.u_ids.length})</span></h2>
    <p class="hint">ทุกข้อใน U = จ + ส1–ส4 · <b>A3-อ</b> สิ่งที่ระบบแสดงตรงกับภาพทุกฝั่งที่เกี่ยวข้องหรือไม่ ·
      <b>A3-ข</b> ข้อสรุปที่ข้อสังเกตอ้างถูกหรือไม่ — มิติที่ไม่ใช้เลือก N/A พร้อมเหตุ (ไม่ถือว่าไม่ถูก) ·
      คำเตือนจับคู่ไม่แน่ชัด ประเมินว่าความกำกวมมีจริงหรือไม่ ไม่ใช่ "คนละรายการแน่นอน"</p>
    {#each r.u_ids as fid (fid)}
      {@const f = F(fid)}
      {@const o = odrafts[fid]}
      {#if f && o}
        <article class="card item" class:busy={busy === fid}>
          <header><b>{f.subject}</b> · {f.kind} · <span class="chip">{meta.obs_kinds[f.obs_kind] ?? f.obs_kind}</span>
            · <a href={f.evidence} target="_blank" rel="noopener">ดูหลักฐาน ↗</a>
            {#if r.obs_eval[fid]}<span class="chip ok">A3-อ {meta.fidelity[r.obs_eval[fid].fidelity]} · A3-ข {meta.assertion[r.obs_eval[fid].assertion]}</span>{/if}</header>
          {#if live}
            <div class="radios"><span class="lbl">A3-อ</span>
              {#each Object.entries(meta.fidelity) as [k, l] (k)}<label><input type="radio" bind:group={o.fidelity} value={k}> {l}</label>{/each}
              {#if o.fidelity === "partial" || o.fidelity === "none"}<select bind:value={o.reason} aria-label="เหตุ"><option value="">— เหตุ —</option>
                {#each Object.entries(meta.fidelity_reasons) as [k, l] (k)}<option value={k}>{l}</option>{/each}</select>{/if}
            </div>
            <div class="dims"><span class="lbl">A3-ข</span>
              <label><input type="checkbox" bind:checked={o.und}> ตัดสินไม่ได้</label>
              {#if !o.und}
                {#each meta.dims_by_obs_kind[f.obs_kind] ?? ["real"] as dm (dm)}
                  <label>{meta.dims[dm]} <select bind:value={o.dims[dm]}><option value="">—</option>
                    {#each Object.entries(meta.dim_values) as [k, l] (k)}<option value={k}>{short(l)}</option>{/each}</select></label>
                  {#if o.dims[dm] === "na"}<input maxlength="120" placeholder="เหตุที่ไม่ใช้" bind:value={o.dims[`${dm}_na`]}>{/if}
                {/each}
              {/if}
            </div>
            <div class="radios"><span class="lbl">ฐานการวินิจฉัย</span>
              {#each Object.entries(meta.basis) as [k, l] (k)}<label><input type="radio" bind:group={o.basis} value={k}> {l}</label>{/each}</div>
            {#if r.obs_eval[fid]}<label class="change">เหตุผลที่เปลี่ยนผลเดิม <input maxlength="300" bind:value={o.change}></label>{/if}
            <button class="btn ghost small" disabled={busy === fid || !o.fidelity} onclick={() => evalObs(fid)}>บันทึก</button>
          {/if}
        </article>
      {/if}
    {/each}
  {/if}

  <details class="card more"><summary>๓. {meta.finding_levels.info}ของระบบ ({r.info_ids.length} ข้อ · จับคู่แล้ว {r.metrics.A4.info_matched}) — นับจำนวนเท่านั้น ไม่นับเป็นแจ้งเกิน</summary>
    <p class="hint">{meta.finding_levels.info}ไม่เท่ากับนอกขอบเขต — ถ้าตรงกับประเด็นในรายการ เลือกจับคู่ได้ในข้อ ๑</p>
    <ul>{#each r.info_ids as id (id)}{@const f = F(id)}{#if f}<li>{f.subject.slice(0, 90)} · {f.kind.slice(0, 50)} · หน้า {f.page_cur ?? f.page_prev ?? "—"}
      · <a href={f.evidence} target="_blank" rel="noopener">หลักฐาน ↗</a></li>{/if}{/each}</ul>
  </details>
  {#if r.review.length}
    <details class="card more" open><summary>ต้องทบทวนกติกาก่อนสรุปผล ({r.review.length} ข้อ)</summary>
      <p class="hint">{meta.finding_levels.review} — ไม่จับคู่ ไม่จัดกลุ่ม ไม่นับใน F จนกว่าจะทบทวนกติกา</p>
      <ul>{#each r.review as x (x.id)}{@const f = F(x.id)}{#if f}<li>{f.subject.slice(0, 80)} · {x.reason}
        · <a href={f.evidence} target="_blank" rel="noopener">หลักฐาน ↗</a></li>{/if}{/each}</ul>
    </details>
  {/if}
  <details class="card more"><summary>๔. ปัญหาการอ่านของระบบ ({Object.entries(meta.read_problems).map(([k, l]) => `${l.split(" — ")[0].split(" (")[0]} ${r.metrics.A4.read_problems[k] ?? 0}`).join(" · ")})</summary>
    <p>หน้าที่ไม่มีชั้นข้อความ — {r.session.labels.prev}: {r.metrics.A4.unread_pages.prev.join(", ") || "ไม่มี"} ·
      {r.session.labels.cur}: {r.metrics.A4.unread_pages.cur.join(", ") || "ไม่มี"}</p>
    <p class="hint">{meta.p1_hint}</p>
    {#each Object.entries(meta.read_problems) as [k, l] (k)}
      {#if r.read_problem_ids[k]?.length}
        <h3>{l} ({r.read_problem_ids[k].length})</h3>
        <ul>{#each r.read_problem_ids[k] as id (id)}{@const f = F(id)}{#if f}<li>{f.subject.slice(0, 90)}
          {#if f.within} · เกิดที่ {f.within === "A" ? r.session.labels.prev : r.session.labels.cur}{/if}
          · <a href={f.evidence} target="_blank" rel="noopener">หลักฐาน ↗</a></li>{/if}{/each}</ul>
      {/if}
    {/each}
  </details>

  <section class="card more">
    <h2>ข้อสังเกตหลังล็อก ({r.notes}) <span class="hint">— ประเด็นที่เห็นเพิ่มหลังส่ง ไม่เพิ่มเข้ารายการที่ล็อก</span></h2>
    {#if live}
      <div class="rowform">
        <label>ส่วน <select bind:value={note.part}><option value="">—</option>{#each meta.parts as p (p.code)}<option value={p.code}>{p.code}</option>{/each}</select></label>
        <label>หัวข้อ <select bind:value={note.topic}><option value="">—</option>{#each scoped(meta, r.session).topics as t (t.code)}<option value={t.code}>{t.code}</option>{/each}</select></label>
        <label>ลักษณะสั้น ๆ <input maxlength="300" size="40" bind:value={note.note}></label>
        <button class="btn ghost small" disabled={busy === "note"} onclick={addNote}>จดไว้</button>
      </div>
    {/if}
  </section>

  <section class="card more">
    <h2>จบการใช้ผล</h2>
    {#if r.session.use_done}<p class="ok">จบการใช้ผลแล้ว · <a href="/r/s/{SID}/survey" onclick={link}>ไปแบบสอบถามหลังใช้ผล →</a></p>
    {:else if live}
      {#if r.complete}<p>จับคู่และจัดกลุ่มครบแล้ว</p>
      {:else}<p class="hint">ยังจับคู่หรือจัดกลุ่มไม่ครบ — ถ้าจะจบตอนนี้ ระบุเหตุ (สถานะจะเป็น "ไม่ครบ")</p>
        <label>เหตุ <input maxlength="300" size="50" bind:value={finishReason}></label>{/if}
      <div class="act"><button class="btn" disabled={busy === "finish"} onclick={finish}>จบการใช้ผล แล้วไปแบบสอบถาม →</button></div>
    {/if}
  </section>

  {#if live}
    <details class="card more" bind:open={stOpen}><summary>หยุดรอบนี้ / ถอนตัว</summary>
      <div class="stack">
        {#each Object.entries(meta.statuses) as [k, l] (k)}<label><input type="radio" bind:group={stStatus} value={k}> {l}</label>{/each}
        <label>เหตุ (หยุดรอบนี้ต้องระบุ · ไม่ต้องระบุตัวเลขจริง) <input maxlength="300" bind:value={stReason}></label>
        <label><input type="checkbox" bind:checked={stNoUse}> ถอนตัวและขอไม่ให้ใช้ข้อมูลที่ทำไว้</label>
        <label><input type="checkbox" bind:checked={stConfirm}> ยืนยัน — หลังจากนี้บันทึกเพิ่มในรอบนี้ไม่ได้</label>
        <div><button class="btn ghost small" disabled={!stConfirm || !stStatus} onclick={setStatus}>บันทึกสถานะ</button></div>
      </div>
    </details>
  {/if}

  <div class="next">
    {#if r.session.use_done}<a class="btn" href="/r/s/{SID}/survey" onclick={link}>แบบสอบถามหลังใช้ผล →</a>{/if}
    <a class="btn ghost" href="/r/s/{SID}/dashboard" onclick={link}>ดูแดชบอร์ด</a>
  </div>
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }
  .title { flex: 1; }
  .lead { margin: 0 0 12px; }
  .msg { padding: 16px; }
  .sk { height: 60vh; }
  .note { padding: 12px 16px; margin-bottom: 10px; }
  .note.warn { background: #fff8e6; border-color: #f1d58a; }
  .flags { display: flex; gap: 6px; flex-wrap: wrap; }
  h2 { font-size: 1.15em; margin: 22px 0 8px; }
  .filter { display: flex; gap: 8px; align-items: center; margin: 16px 0 0; }
  .filter button { padding: 6px 14px; border-radius: 999px; border: 1px solid #cfd4dc; background: #fff; cursor: pointer; }
  .filter button.on { background: var(--dark); color: #fff; border-color: var(--dark); }
  .item { padding: 10px 14px; margin: 8px 0; transition: opacity .2s; }
  .item.busy { opacity: .55; }
  .item-red { border-left: 5px solid var(--red); } .item-brown { border-left: 5px solid var(--brown); }
  .item-pin { border-left: 5px solid var(--pin); } .item-row { border-left: 5px solid #c9ccd2; }
  .item p { margin: 6px 0; }
  .mono { font-family: ui-monospace, Consolas, monospace; font-size: .92em; color: #344054; }
  .caveat { background: #fff8e6; border: 1px solid #f1d58a; border-radius: 10px; padding: 6px 10px; font-size: .92em; }
  .dot { display: inline-block; width: 12px; height: 12px; border-radius: 50%; border: 3px solid var(--pin); vertical-align: middle; }
  .dot-red { border-color: var(--red); } .dot-brown { border-color: var(--brown); } .dot-pin { background: var(--pin); }
  .rowform { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: flex-end; background: #f8f9fb; border-radius: 10px;
    padding: 8px 10px; margin: 6px 0; }
  .dims { display: inline-flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  .dims .dim { flex-direction: row; display: inline-flex; gap: 4px; }
  .loc { border: 1px solid var(--line, #ddd); border-radius: 8px; padding: 6px 10px; margin: 6px 0; }
  .dims { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 4px 0; }
  .rowform label, .search, .change { display: flex; flex-direction: column; gap: 2px; font-size: .92em; }
  select, input:not([type]), input[inputmode] { padding: 5px 8px; border-radius: 8px; border: 1px solid #cfd4dc; font: inherit; }
  .decide { border-top: 1px dashed var(--line); margin-top: 6px; padding-top: 6px; display: flex; flex-direction: column; gap: 6px; }
  .picked { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  .pick { display: inline-flex; gap: 4px; align-items: center; background: #eef0f3; border-radius: 999px; padding: 2px 4px 2px 10px; }
  .x { border: 0; background: transparent; cursor: pointer; font-size: 1.1em; line-height: 1; padding: 0 6px; }
  .cands { display: flex; flex-wrap: wrap; gap: 4px; }
  .cand { border: 1px dashed #b8bec9; background: #fff; border-radius: 10px; padding: 3px 8px; cursor: pointer; font: inherit; font-size: .88em; text-align: left; }
  .radios { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; }
  .lbl { font-weight: 600; }
  .hist { font-size: .92em; margin-top: 6px; }
  .more { padding: 10px 16px; margin: 12px 0; }
  .more summary { cursor: pointer; font-weight: 600; }
  .ok { color: #1f6b35; }
  .act { margin-top: 8px; }
  .stack { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; margin-top: 8px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
  .metric { padding: 14px; display: flex; flex-direction: column; }
  .metric b { font-size: 1.6em; }
  .next { display: flex; gap: 10px; margin-top: 22px; flex-wrap: wrap; }
</style>
