<script lang="ts">
  import '../app.css';
  import { onMount } from 'svelte';
  import { initAuth, login, logout, isAuthenticated, principal } from '$lib/auth';
  import Toast from '$lib/components/Toast.svelte';

  onMount(() => initAuth());
</script>

<div class="min-h-screen bg-[var(--color-bg-secondary)]">
  <!-- Navbar -->
  <nav class="sticky top-0 z-30 bg-white border-b border-[var(--color-border-primary)]" style="box-shadow: var(--shadow-sm);">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
      <a href="/" class="flex items-center gap-2.5 group">
        <div class="w-7 h-7 rounded-lg flex items-center justify-center" style="background: var(--gradient-institutional);">
          <svg class="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125v-3.75" />
          </svg>
        </div>
        <span class="text-lg font-semibold text-primary-900 group-hover:text-primary-700 transition-colors">
          IC File Registry
        </span>
      </a>

      <div class="flex items-center gap-3">
        {#if $isAuthenticated}
          <span
            class="hidden sm:block text-xs text-primary-400 font-mono truncate max-w-[180px]"
            title={$principal}
          >
            {$principal.slice(0, 5)}...{$principal.slice(-5)}
          </span>
          <button class="btn-ghost btn-sm" on:click={logout}>
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15m3 0l3-3m0 0l-3-3m3 3H9" />
            </svg>
            <span class="hidden sm:inline">Log out</span>
          </button>
        {:else}
          <button class="btn-primary btn-sm" on:click={login}>
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0" />
            </svg>
            Login with Internet Identity
          </button>
        {/if}
      </div>
    </div>
  </nav>

  <!-- Main content -->
  <main class="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <slot />
  </main>

  <!-- Footer -->
  <footer class="border-t border-[var(--color-border-primary)] mt-auto">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-4">
      <p class="text-xs text-primary-400 text-center">
        IC File Registry &middot; On-chain file storage on the Internet Computer
      </p>
    </div>
  </footer>
</div>

<Toast />
