<script lang="ts">
  import { get, post, type Meta, type Session } from "../lib/api";
  import { go, link } from "../lib/router.svelte";
  import { toast } from "../lib/notify.svelte";

  let { sid, meta }: { sid: string; meta: Meta } = $props();
  let s = $state<Session | null>(null);
  let ans = $state<Record<string, string>>({});
  let saving = $state(false);

  get<Session>(`/api/trial/s/${sid}`).then((x) => (s = x));
  get<{ answers: Record<string, string> }>(`/api/trial/s/${sid}/result`).then((x) => (ans = { ...x.answers })).catch(() => {});

  const total = meta.likert.reduce((n, g) => n + g.items.length, 0);
  const answered = $derived(meta.likert.flatMap((g) => g.items).filter((i) => ans[i.key]).length);

  async function save() {
    saving = true;
    try {
      await post(`/api/trial/s/${sid}/survey`, ans);
      toast("บันทึกคำตอบลงเครื่องแล้ว");
      go(`/r/s/${sid}/dashboard`);
    } catch (e) { toast((e as Error).message, true); } finally { saving = false; }
  }
</script>

<div class="bar">
  <a class="btn ghost small" href="/r/s/{sid}/result" onclick={link}>← ระบบเจออะไร</a>
  <div class="title"><b>แบบสอบถามหลังใช้</b>{#if s} · {s.book.title}{/if}</div>
  <span class="chip">ตอบแล้ว {answered}/{total}</span>
</div>
<p class="hint">ไม่ต้องลงชื่อ ตอบตามที่ใช้จริง คำตอบเชิงลบมีประโยชน์เท่ากับเชิงบวก · 1 = ไม่เห็นด้วยอย่างยิ่ง … 5 = เห็นด้วยอย่างยิ่ง ·
  ข้อไหนไม่อยากตอบเว้นไว้ได้ · ใช้ประกอบเท่านั้น ไม่แทนผลการตรวจจับ</p>

{#each meta.likert as g, gi (g.group)}
  <fieldset class="card">
    <legend>{gi + 1}. {g.group}</legend>
    {#each g.items as it (it.key)}
      <div class="q" role="radiogroup" aria-label={it.text}>
        <span class="qt">{it.text}</span>
        <span class="scale">
          {#each ["1", "2", "3", "4", "5"] as v (v)}
            <button class="pt" class:on={ans[it.key] === v} role="radio" aria-checked={ans[it.key] === v}
                    onclick={() => (ans[it.key] = ans[it.key] === v ? "" : v)}>{v}</button>
          {/each}
        </span>
      </div>
    {/each}
  </fieldset>
{/each}

<fieldset class="card">
  <legend>{meta.likert.length + 1}. ความเห็นเพิ่มเติม</legend>
  {#each meta.open as o (o.key)}
    <label class="open">{o.text}<textarea rows="2" maxlength="2000" bind:value={ans[o.key]}></textarea></label>
  {/each}
</fieldset>

<div class="next"><button class="btn" disabled={saving} onclick={save}>{saving ? "กำลังบันทึก…" : "บันทึกลงเครื่อง แล้วดูแดชบอร์ด →"}</button></div>

<style>
  .bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-bottom: 6px; }
  .title { flex: 1; }
  fieldset { padding: 8px 18px 12px; margin: 12px 0; border: 1px solid var(--line); }
  legend { font-weight: 700; padding: 0 6px; }
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
  .next { margin-top: 14px; }
</style>
