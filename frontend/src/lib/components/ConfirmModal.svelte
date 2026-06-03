<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import { fade, scale } from 'svelte/transition';

  export let open = false;
  export let title = 'Confirm';
  export let message = '';
  export let confirmLabel = 'Confirm';
  export let danger = false;

  const dispatch = createEventDispatcher();

  function confirm() {
    dispatch('confirm');
    open = false;
  }
  function cancel() {
    dispatch('cancel');
    open = false;
  }
</script>

{#if open}
  <!-- svelte-ignore a11y-click-events-have-key-events -->
  <!-- svelte-ignore a11y-no-static-element-interactions -->
  <div
    class="fixed inset-0 z-40 flex items-center justify-center"
    transition:fade={{ duration: 150 }}
  >
    <div class="absolute inset-0 bg-primary-900/40 backdrop-blur-sm" on:click={cancel}></div>
    <div
      class="relative bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6"
      transition:scale={{ start: 0.95, duration: 200 }}
    >
      <h3 class="text-lg font-semibold text-primary-900 mb-2">{title}</h3>
      <p class="text-sm text-primary-600 mb-6">{message}</p>
      <div class="flex items-center justify-end gap-3">
        <button class="btn-secondary btn-sm" on:click={cancel}>Cancel</button>
        <button
          class="{danger ? 'btn-danger' : 'btn-primary'} btn-sm"
          on:click={confirm}
        >{confirmLabel}</button>
      </div>
    </div>
  </div>
{/if}
