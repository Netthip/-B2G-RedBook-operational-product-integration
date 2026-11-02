<script lang="ts">
  // แบบสอบถามหลังใช้ผล = แบบ 03 ฉบับ 0.2 (ถ้อยคำจากเซิร์ฟเวอร์) — เปิดได้หลังจบการใช้ผลเท่านั้น
  import { get, post, type Meta, type Result, type Session } from "../lib/api";
  import { go, link } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";

  let { sid, meta }: { sid: string; meta: Meta } = $props();
  // svelte-ignore state_referenced_locally
  const SID = sid;
  let s = $state<Session | null>(null);
  let ans = $state<Record<string, string>>({});
  let saving = $state(false);
  const v03 = $derived(!!s?.v03);
  const scale = $derived(v03 ? ["5", "4", "3", "2", "1"] : ["1", "2", "3", "4", "5"]);

  get<Session>(`/api/trial/s/${SID}`).then((x) => {
    s = x;
    if (x.survey_state === "open" || x.survey_state === "legacy")
      get<Result>(`/api/trial/s/${SID}/result`).then((r) => (ans = { ...r.answers })).catch(() => {});
  });

  const likert = $derived(v03 ? meta.likert_v03 : meta.likert);
  const total = $derived(likert.reduce((n, g) => n + g.items.length, 0));
  const answered = $derived(likert.flatMap((g) => g.items).filter((i) => ans[i.key]).length);

  async function save() {
    saving = true;
    try {
      await post(`/api/trial/s/${SID}/survey`, ans);
      toast("บันทึกคำตอบลงเครื่องแล้ว");
      go(`/r/s/${SID}/dashboard`);
    } catch (e) { toast((e as Error).message, true); } finally { saving = false; }
  }
</script>

<div class="bar">
  <a class="btn ghost small" href="/r/s/{SID}/result" onclick={link}>← ระบบเจออะไร</a>
  <div class="title"><b>แบบสอบถามหลังใช้ผล</b>{#if s}{` · ${s.book.title}`}{/if}</div>
  {#if s?.survey_state === "open"}<span class="chip">ตอบแล้ว {answered}/{total}</span>{/if}
</div>

{#if !s}
  <div class="card skeleton sk"></div>
{:else if s.survey_state !== "open"}
  <div class="card gate">{meta.survey_state_text[s.survey_state] ?? "ยังเปิดแบบสอบถามไม่ได้"}
    {#if s.survey_state === "in_use"}{" · "}<a href="/r/s/{SID}/result" onclick={link}>ไปใช้ผลต่อ</a>{/if}</div>
  {#if s.survey_state === "legacy" && Object.keys(ans).length}
    <ul class="card legacy">{#each Object.entries(ans) as [k, v] (k)}<li>{k}: {v}</li>{/each}</ul>
  {/if}
{:else}
  <p class="hint">โปรดตอบหลังจากได้ใช้ผลของระบบกับคู่เอกสารของท่านแล้ว · ไม่ต้องลงชื่อ ใช้รหัสผู้ตอบแทน · ไม่ต้องระบุตัวเลขงบประมาณจริง ·
    คำตอบเชิงลบมีประโยชน์เท่ากับเชิงบวก · ผลรายงานเป็นภาพรวม · ถอนตัวได้ทุกเมื่อโดยแจ้งรหัสผู้ตอบ</p>

  <p class="hint">ให้ความยินยอมไว้แล้วก่อนเริ่มรอบ · ถอนตัวได้ทุกเมื่อ</p>

  <fieldset class="card">
    <legend>ส่วนที่ ๑ ขั้นตอนที่ท่านทำได้</legend>
    <table>
      <thead><tr><th scope="col">ขั้นตอน</th>{#each Object.values(meta.step_choices) as l (l)}<th scope="col">{l}</th>{/each}</tr></thead>
      <tbody>
        {#each meta.steps as st (st.key)}
          <tr><th scope="row" class="left">{st.text}</th>
            {#each Object.entries(meta.step_choices) as [k, l] (k)}
              <td><input type="radio" name={st.key} value={k} checked={ans[st.key] === k} aria-label="{st.text} {l}"
                         onchange={() => (ans[st.key] = k)}></td>
            {/each}</tr>
        {/each}
      </tbody>
    </table>
  </fieldset>

  <fieldset class="card">
    <legend>{#if v03}ส่วนที่ ๒ ความคิดเห็นต่อความเหมาะสมในการใช้งาน <span class="hint">(๕ = มากที่สุด · ๔ = มาก · ๓ = ปานกลาง · ๒ = น้อย · ๑ = น้อยที่สุด · ข้อไหนไม่อยากตอบเว้นไว้ได้)</span>{:else}ส่วนที่ ๒ ความเห็นหลังใช้ผล <span class="hint">(๑ = ไม่เห็นด้วยอย่างยิ่ง … ๕ = เห็นด้วยอย่างยิ่ง · ข้อไหนไม่อยากตอบเว้นไว้ได้)</span>{/if}</legend>
    {#each likert as g (g.group)}
      <h3>{g.group}</h3>
      {#each g.items as it (it.key)}
        <div class="q" role="radiogroup" aria-label={it.text}>
          <span class="qt">{it.text}</span>
          <span class="scale">
            {#each scale as v (v)}
              <button class="pt" class:on={ans[it.key] === v} role="radio" aria-checked={ans[it.key] === v}
                      onclick={() => (ans[it.key] = ans[it.key] === v ? "" : v)}>{v}</button>
            {/each}
          </span>
        </div>
      {/each}
    {/each}
  </fieldset>

  <fieldset class="card">
    <legend>ส่วนที่ ๓ คำถามปลายเปิด</legend>
    {#each meta.open as o (o.key)}
      <label class="open">{o.text}<textarea rows="2" maxlength="2000" bind:value={ans[o.key]}></textarea></label>
    {/each}
  </fieldset>

  <fieldset class="card">
    <legend>ส่วนที่ ๔ ข้อมูลทั่วไป</legend>
    {#each meta.general as g (g.key)}
      <div class="radios" role="radiogroup" aria-label={g.text}><span>{g.text}</span>
        {#each Object.entries(g.choices) as [k, l] (k)}
          <label><input type="radio" name={g.key} value={k} checked={ans[g.key] === k} onchange={() => (ans[g.key] = k)}> {l}</label>
        {/each}
      </div>
    {/each}
  </fieldset>

  <div class="next"><button class="btn" disabled={saving} onclick={save}>{saving ? "กำลังบันทึก…" : "บันทึกลงเครื่อง แล้วดูแดชบอร์ด →"}</button></div>
  <p class="hint">ความเห็นใช้ประกอบด้านประโยชน์ต่อผู้ใช้เท่านั้น — ไม่ใช้แทนผลด้านความถูกต้องในการหาจุดต่าง</p>
{/if}

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
  .title { flex: 1; }
  .sk { height: 40vh; }
  .gate, .legacy { padding: 14px 18px; margin: 10px 0; }
  fieldset { padding: 8px 18px 12px; margin: 12px 0; border: 1px solid var(--line); }
  legend { font-weight: 700; padding: 0 6px; }
  h3 { font-size: 1em; margin: 12px 0 2px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid var(--line); padding: 4px 8px; text-align: center; }
  .left { text-align: left; font-weight: 600; }
  .q { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 9px 0; border-bottom: 1px dashed #e4e7ec; flex-wrap: wrap; }
  .q:last-child { border-bottom: 0; }
  .qt { flex: 1 1 380px; }
  .scale { display: flex; gap: 6px; }
  .pt { width: 40px; height: 40px; border-radius: 50%; border: 1px solid #cfd4dc; background: #fff; cursor: pointer; font-weight: 600;
    transition: transform .12s, background .15s; }
  .pt:hover { transform: scale(1.06); }
  .pt.on { background: var(--dark); color: #fff; border-color: var(--dark); transform: scale(1.08); }
  .open { display: block; margin: 8px 0; }
  textarea { display: block; width: 100%; margin-top: 4px; padding: 8px; border: 1px solid #cfd4dc; border-radius: 10px; font: inherit; }
  .radios { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; margin: 6px 0; }
  .next { margin-top: 14px; }
</style>
