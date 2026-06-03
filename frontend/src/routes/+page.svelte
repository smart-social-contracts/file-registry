<script lang="ts">
  import { onMount } from 'svelte';
  import { listNamespaces, getStats, formatBytes } from '$lib/api';
  import type { NamespaceInfo, Stats } from '$lib/api';
  import { isAuthenticated } from '$lib/auth';

  let namespaces: NamespaceInfo[] = [];
  let stats: Stats | null = null;
  let loading = true;
  let error = '';
  let search = '';

  $: filtered = namespaces.filter((ns) =>
    ns.namespace.toLowerCase().includes(search.toLowerCase()) ||
    (ns.description || '').toLowerCase().includes(search.toLowerCase()),
  );

  async function load() {
    loading = true;
    error = '';
    try {
      [namespaces, stats] = await Promise.all([listNamespaces(), getStats()]);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(load);
</script>

<svelte:head><title>IC File Registry</title></svelte:head>

<div class="space-y-6 animate-fade-in">
  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-2xl font-bold text-primary-900">File Registry</h1>
      <p class="text-sm text-primary-500 mt-1">On-chain file storage on the Internet Computer</p>
    </div>
    <button class="btn-secondary btn-sm self-start" on:click={load}>
      <svg class="w-4 h-4 {loading ? 'animate-spin' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
      </svg>
      Refresh
    </button>
  </div>

  <!-- Stats -->
  {#if loading && !stats}
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      {#each [1, 2, 3] as _}
        <div class="card p-5">
          <div class="skeleton h-3 w-20 mb-3"></div>
          <div class="skeleton h-7 w-12"></div>
        </div>
      {/each}
    </div>
  {:else if stats}
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <div class="card p-5">
        <div class="flex items-center gap-2 mb-1">
          <svg class="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
          </svg>
          <span class="text-xs font-semibold text-primary-500 uppercase tracking-wider">Namespaces</span>
        </div>
        <div class="text-2xl font-bold text-primary-900">{stats.namespaces}</div>
      </div>
      <div class="card p-5">
        <div class="flex items-center gap-2 mb-1">
          <svg class="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
          </svg>
          <span class="text-xs font-semibold text-primary-500 uppercase tracking-wider">Total Files</span>
        </div>
        <div class="text-2xl font-bold text-primary-900">{stats.total_files}</div>
      </div>
      <div class="card p-5">
        <div class="flex items-center gap-2 mb-1">
          <svg class="w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125v-3.75" />
          </svg>
          <span class="text-xs font-semibold text-primary-500 uppercase tracking-wider">Total Size</span>
        </div>
        <div class="text-2xl font-bold text-primary-900">{formatBytes(stats.total_bytes)}</div>
      </div>
    </div>
  {/if}

  <!-- Error -->
  {#if error}
    <div class="card border-red-200 bg-red-50 px-4 py-3 flex items-center gap-3">
      <svg class="w-5 h-5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><path stroke-linecap="round" d="M12 8v4m0 4h.01" />
      </svg>
      <span class="text-sm text-red-700">{error}</span>
    </div>
  {/if}

  <!-- Search + namespace list -->
  <div>
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-lg font-semibold text-primary-800">Namespaces</h2>
      {#if namespaces.length > 0}
        <span class="text-xs text-primary-400">{filtered.length} of {namespaces.length}</span>
      {/if}
    </div>

    {#if namespaces.length > 5}
      <div class="relative mb-4">
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8" /><path stroke-linecap="round" d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          bind:value={search}
          placeholder="Search namespaces..."
          class="input pl-10"
        />
      </div>
    {/if}

    {#if loading && namespaces.length === 0}
      <div class="grid gap-3">
        {#each [1, 2, 3, 4] as _}
          <div class="card p-4 flex items-center justify-between">
            <div class="flex items-center gap-3">
              <div class="skeleton w-5 h-5 rounded"></div>
              <div>
                <div class="skeleton h-4 w-40 mb-1.5"></div>
                <div class="skeleton h-3 w-24"></div>
              </div>
            </div>
            <div class="flex gap-6">
              <div class="skeleton h-3 w-16"></div>
              <div class="skeleton h-3 w-12"></div>
            </div>
          </div>
        {/each}
      </div>
    {:else if filtered.length === 0 && search}
      <div class="text-center py-12">
        <svg class="w-12 h-12 mx-auto text-primary-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <circle cx="11" cy="11" r="8" /><path stroke-linecap="round" d="m21 21-4.35-4.35" />
        </svg>
        <p class="text-primary-500 text-sm">No namespaces match "{search}"</p>
      </div>
    {:else if namespaces.length === 0}
      <div class="text-center py-12">
        <svg class="w-12 h-12 mx-auto text-primary-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5m6 4.125l2.25 2.25m0 0l2.25 2.25M12 13.875l2.25-2.25M12 13.875l-2.25 2.25M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
        </svg>
        <p class="text-primary-500 text-sm font-medium">No namespaces yet</p>
        {#if $isAuthenticated}
          <p class="text-primary-400 text-xs mt-1">Upload a file to create the first namespace.</p>
        {:else}
          <p class="text-primary-400 text-xs mt-1">Log in to upload files.</p>
        {/if}
      </div>
    {:else}
      <div class="grid gap-3">
        {#each filtered as ns (ns.namespace)}
          <a
            href="/{encodeURIComponent(ns.namespace)}"
            class="card card-interactive p-4 flex items-center justify-between group"
          >
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-9 h-9 rounded-lg bg-primary-100 flex items-center justify-center shrink-0 group-hover:bg-primary-200 transition-colors">
                <svg class="w-4.5 h-4.5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
                </svg>
              </div>
              <div class="min-w-0">
                <div class="font-mono text-sm font-medium text-primary-800 group-hover:text-primary-600 transition-colors truncate">
                  {ns.namespace}
                </div>
                {#if ns.description}
                  <div class="text-xs text-primary-400 mt-0.5 truncate">{ns.description}</div>
                {/if}
              </div>
            </div>
            <div class="flex items-center gap-5 text-xs text-primary-400 shrink-0 ml-4">
              <span class="flex items-center gap-1.5">
                <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375" />
                </svg>
                {formatBytes(ns.total_bytes)}
              </span>
              <span>{ns.file_count} {ns.file_count === 1 ? 'file' : 'files'}</span>
              <svg class="w-4 h-4 text-primary-300 group-hover:text-primary-500 transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
              </svg>
            </div>
          </a>
        {/each}
      </div>
    {/if}
  </div>
</div>
