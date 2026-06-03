<script lang="ts">
  import { formatBytes, timeAgo } from '$lib/api';
  import type { FileVersion } from '$lib/api';
  import { createEventDispatcher } from 'svelte';

  export let versions: FileVersion[] = [];
  export let activeVersion: number | null = null;

  const dispatch = createEventDispatcher();

  $: sorted = [...versions].sort((a, b) => b.version - a.version);
</script>

<div class="space-y-0">
  {#each sorted as v, i (v.version)}
    {@const isActive = activeVersion === v.version}
    <button
      class="w-full text-left group relative pl-7 pr-3 py-3 rounded-lg transition-all duration-150
             {isActive ? 'bg-primary-100 border border-primary-300' : 'hover:bg-primary-50 border border-transparent'}"
      on:click={() => dispatch('select', v.version)}
    >
      <!-- Timeline connector -->
      <div class="absolute left-[11px] top-0 bottom-0 w-px {i === sorted.length - 1 ? 'h-1/2' : 'h-full'} bg-primary-200"></div>
      {#if i === 0}
        <div class="absolute left-[11px] top-0 h-[50%] w-px bg-transparent"></div>
      {/if}

      <!-- Dot -->
      <div class="absolute left-[6px] top-1/2 -translate-y-1/2 w-[11px] h-[11px] rounded-full border-2 z-10
                  {v.is_current ? 'bg-primary-700 border-primary-700' : 'bg-white border-primary-400 group-hover:border-primary-600'}"></div>

      <div class="flex items-center justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <span class="text-sm font-medium text-primary-800">v{v.version}</span>
            {#if v.is_current}
              <span class="px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider rounded bg-primary-800 text-white">current</span>
            {/if}
          </div>
          <p class="text-xs text-primary-500 mt-0.5">
            {formatBytes(v.size)}
            {#if v.sha256}
              &middot; <span class="font-mono">{v.sha256.slice(0, 8)}</span>
            {/if}
          </p>
        </div>
        <span class="text-xs text-primary-400 shrink-0">{timeAgo(v.updated)}</span>
      </div>
    </button>
  {/each}
</div>
