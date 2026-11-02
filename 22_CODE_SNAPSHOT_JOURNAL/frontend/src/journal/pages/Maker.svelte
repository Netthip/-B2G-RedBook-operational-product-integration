<script lang="ts">
  // ผู้พัฒนา — โพลารอยด์ป๊อปอัป (รูปตั้งใน ../content: MAKER_PHOTO · ยังไม่มีรูปใช้อักษรย่อแทน ไม่มีคำขอรูปที่ไม่มีอยู่จริง)
  import { ABOUT, MAKER_PHOTO } from "../content";
</script>

<div class="jr-pg">
  <h2>ผู้พัฒนา</h2>
  <div class="scene">
    <span class="jr-ground"></span>
    <figure class="jr-pol jr-pop pol">
      <span class="jr-tape pink t"></span>
      {#if MAKER_PHOTO}
        <img src={MAKER_PHOTO} alt={`รูปผู้พัฒนา ${ABOUT.maker}`} />
      {:else}
        <span class="initial" aria-hidden="true">น</span>
      {/if}
      <figcaption>{ABOUT.maker}</figcaption>
    </figure>
  </div>
  <p class="who">{ABOUT.makerNote}</p>
</div>

<style>
  .scene { position: absolute; left: 50%; top: calc(var(--u) * 26); width: calc(var(--u) * 52); height: calc(var(--u) * 62);
    translate: -50% 0; transform-style: preserve-3d; }
  .pol { position: absolute; left: 0; right: 0; bottom: 0; rotate: -3deg; --jr-rise: -28deg; }
  .t { left: 34%; top: calc(var(--u) * -2.6); rotate: 4deg; }
  img, .initial { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; }
  .initial { display: grid; place-items: center; background: linear-gradient(135deg, #e8eef9, #e2f3ee); color: var(--jr-navy);
    font-size: calc(var(--u) * 20); font-weight: 700; }
  .who { position: absolute; left: 0; right: 0; bottom: calc(var(--u) * 9); margin: 0; text-align: center; color: var(--muted); white-space: pre-line; }
</style>
