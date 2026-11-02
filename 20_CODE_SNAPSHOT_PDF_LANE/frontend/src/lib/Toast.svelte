<script lang="ts">
  import { dismiss, toasts } from "./notify.svelte";
</script>

<div class="toasts" role="status" aria-live="polite">
  {#each toasts as t (t.id)}
    <div class="toast" class:bad={t.bad}>{t.text}
      {#if t.action}<button class="act" onclick={() => { t.action!.run(); dismiss(t.id); }}>{t.action.label}</button>{/if}</div>
  {/each}
</div>

<style>
  .toasts { position: fixed; right: 16px; bottom: 16px; display: flex; flex-direction: column; gap: 8px; z-index: 100; }
  .toast { background: #1f2328; color: #fff; padding: 10px 16px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.18);
    animation: pop .25s ease-out; max-width: 380px; }
  .toast.bad { background: #b42318; }
  .act { margin-left: 10px; background: transparent; color: #ffd27a; border: 1px solid rgba(255,255,255,.35); border-radius: 8px;
    padding: 2px 10px; cursor: pointer; font: inherit; font-weight: 600; }
  @keyframes pop { from { opacity: 0; transform: translateY(8px) scale(.98); } to { opacity: 1; transform: none; } }
  @media (prefers-reduced-motion: reduce) { .toast { animation: none; } }
</style>
