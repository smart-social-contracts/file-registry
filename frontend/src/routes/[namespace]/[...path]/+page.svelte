<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import {
    getFile, listFileVersions, getFileAtVersion,
    formatBytes, timeAgo, fileUrl, isTextType, isImageType,
  } from '$lib/api';
  import type { FileContent, FileVersion } from '$lib/api';
  import FileViewer from '$lib/components/FileViewer.svelte';
  import VersionTimeline from '$lib/components/VersionTimeline.svelte';
  import { toasts } from '$lib/stores/toast';

  $: namespace = decodeURIComponent($page.params.namespace);
  $: filePath = $page.params.path;
  $: filename = filePath.split('/').pop() ?? filePath;

  let content: FileContent | null = null;
  let versions: FileVersion[] = [];
  let loading = true;
  let error = '';
  let activeVersion: number | null = null;
  let copiedUrl = false;

  async function load() {
    loading = true;
    error = '';
    try {
      const [file, vers] = await Promise.all([
        getFile(namespace, filePath),
        listFileVersions(namespace, filePath),
      ]);
      content = file;
      versions = vers;
      const current = vers.find((v) => v.is_current);
      activeVersion = current?.version ?? (file.version ?? null);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function selectVersion(e: CustomEvent<number>) {
    const version = e.detail;
    activeVersion = version;
    const current = versions.find((v) => v.is_current);
    try {
      if (current && version === current.version) {
        content = await getFile(namespace, filePath);
      } else {
        content = await getFileAtVersion(namespace, filePath, version);
      }
    } catch (e: any) {
      toasts.error(`Failed to load version ${version}: ${e.message}`);
    }
  }

  function copyUrl() {
    const url = fileUrl(namespace, filePath);
    navigator.clipboard.writeText(url);
    copiedUrl = true;
    toasts.info('URL copied to clipboard');
    setTimeout(() => (copiedUrl = false), 2000);
  }

  function downloadFile() {
    if (!content) return;
    const bytes = atob(content.content_b64);
    const arr = new Uint8Array(bytes.length);
    for (let i = 0; i < bytes.length; i++) arr[i] = bytes.charCodeAt(i);
    const blob = new Blob([arr], { type: content.content_type });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  onMount(load);
</script>

<svelte:head><title>{filename} — {namespace} — IC File Registry</title></svelte:head>

<div class="space-y-6 animate-fade-in">
  <!-- Breadcrumb -->
  <nav class="flex items-center gap-2 text-sm flex-wrap">
    <a href="/" class="text-primary-500 hover:text-primary-700 transition-colors">Registry</a>
    <svg class="w-4 h-4 text-primary-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
    <a href="/{encodeURIComponent(namespace)}" class="text-primary-500 hover:text-primary-700 transition-colors font-mono">{namespace}</a>
    <svg class="w-4 h-4 text-primary-300 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
    <span class="text-primary-800 font-medium font-mono">{filename}</span>
  </nav>

  <!-- Error -->
  {#if error}
    <div class="card border-red-200 bg-red-50 px-4 py-3 flex items-center gap-3">
      <svg class="w-5 h-5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><path stroke-linecap="round" d="M12 8v4m0 4h.01" />
      </svg>
      <span class="text-sm text-red-700">{error}</span>
    </div>
  {/if}

  {#if loading}
    <div class="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
      <div>
        <div class="card p-4 mb-4">
          <div class="flex items-center gap-3 mb-4">
            <div class="skeleton h-6 w-48"></div>
          </div>
          <div class="skeleton h-3 w-32 mb-2"></div>
          <div class="skeleton h-3 w-24"></div>
        </div>
        <div class="card overflow-hidden">
          {#each [1, 2, 3, 4, 5, 6, 7, 8] as _}
            <div class="px-4 py-2 border-b border-primary-100">
              <div class="skeleton h-4 w-full"></div>
            </div>
          {/each}
        </div>
      </div>
      <div class="card p-4">
        <div class="skeleton h-4 w-20 mb-4"></div>
        {#each [1, 2, 3] as _}
          <div class="skeleton h-12 w-full mb-2 rounded-lg"></div>
        {/each}
      </div>
    </div>
  {:else if content}
    <div class="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6">
      <!-- Main content area -->
      <div>
        <!-- File header -->
        <div class="card p-4 mb-4">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div class="flex items-center gap-3 min-w-0">
              <div class="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center shrink-0">
                {#if isImageType(content.content_type)}
                  <svg class="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.41a2.25 2.25 0 013.182 0l2.909 2.909M18 3.75H6A2.25 2.25 0 003.75 6v12A2.25 2.25 0 006 20.25h12A2.25 2.25 0 0020.25 18V6A2.25 2.25 0 0018 3.75z" />
                  </svg>
                {:else if isTextType(content.content_type)}
                  <svg class="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M17.25 6.75L22.5 12l-5.25 5.25m-10.5 0L1.5 12l5.25-5.25m7.5-3l-4.5 16.5" />
                  </svg>
                {:else}
                  <svg class="w-5 h-5 text-primary-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                  </svg>
                {/if}
              </div>
              <div class="min-w-0">
                <h1 class="text-lg font-semibold text-primary-900 font-mono truncate">{filename}</h1>
                <div class="flex items-center gap-3 mt-0.5 text-xs text-primary-500">
                  <span>{formatBytes(content.size)}</span>
                  <span class="text-primary-300">&middot;</span>
                  <span>{content.content_type}</span>
                  {#if content.sha256}
                    <span class="text-primary-300">&middot;</span>
                    <span class="font-mono">{content.sha256.slice(0, 12)}</span>
                  {/if}
                </div>
              </div>
            </div>
            <div class="flex items-center gap-2 shrink-0">
              <button class="btn-secondary btn-sm" on:click={copyUrl}>
                {#if copiedUrl}
                  <svg class="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                  </svg>
                  Copied
                {:else}
                  <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.07-9.07a4.5 4.5 0 00-6.364 0l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                  </svg>
                  Copy URL
                {/if}
              </button>
              <button class="btn-secondary btn-sm" on:click={downloadFile}>
                <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                </svg>
                Download
              </button>
            </div>
          </div>
        </div>

        <!-- Version indicator -->
        {#if activeVersion !== null}
          {@const current = versions.find((v) => v.is_current)}
          {#if current && activeVersion !== current.version}
            <div class="card border-amber-200 bg-amber-50 px-4 py-2.5 mb-4 flex items-center gap-2">
              <svg class="w-4 h-4 text-amber-600 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
              </svg>
              <span class="text-sm text-amber-800">
                Viewing version {activeVersion} — <button class="underline font-medium" on:click={() => { activeVersion = current.version; load(); }}>switch to current (v{current.version})</button>
              </span>
            </div>
          {/if}
        {/if}

        <!-- File content viewer -->
        <FileViewer
          content={content.content_b64}
          contentType={content.content_type}
          {filename}
          size={content.size}
        />
      </div>

      <!-- Sidebar: Version timeline -->
      <div class="lg:sticky lg:top-20 lg:self-start">
        <div class="card p-4">
          <h3 class="text-sm font-semibold text-primary-800 mb-3 flex items-center gap-2">
            <svg class="w-4 h-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            Version History
          </h3>
          {#if versions.length === 0}
            <p class="text-xs text-primary-400">No version history available.</p>
          {:else}
            <VersionTimeline {versions} {activeVersion} on:select={selectVersion} />
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>
