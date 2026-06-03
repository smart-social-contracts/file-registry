<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import {
    listFiles, uploadFile, deleteFile, grantPublish, revokePublish,
    deleteNamespace, getAcl, fileUrl, guessContentType, formatBytes, timeAgo,
  } from '$lib/api';
  import type { FileInfo, AclMap } from '$lib/api';
  import { isAuthenticated, principal } from '$lib/auth';
  import { toasts } from '$lib/stores/toast';
  import ConfirmModal from '$lib/components/ConfirmModal.svelte';

  $: namespace = decodeURIComponent($page.params.namespace);

  let files: FileInfo[] = [];
  let acl: AclMap = {};
  let loading = true;
  let error = '';
  let search = '';
  let uploading = false;
  let uploadProgress = { current: 0, total: 0, filename: '' };
  let copiedPath = '';
  let showAcl = false;
  let newPrincipal = '';
  let aclError = '';

  let confirmOpen = false;
  let confirmTitle = '';
  let confirmMessage = '';
  let confirmAction: (() => void) | null = null;

  $: filtered = files.filter((f) =>
    f.path.toLowerCase().includes(search.toLowerCase()) ||
    f.content_type.toLowerCase().includes(search.toLowerCase()),
  );

  async function load() {
    loading = true;
    error = '';
    try {
      [files, acl] = await Promise.all([listFiles(namespace), getAcl()]);
    } catch (e: any) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function handleFileUpload(e: Event & { dataTransfer?: DataTransfer }) {
    const target = e.target as HTMLInputElement | null;
    const fileList = target?.files ?? (e as any).dataTransfer?.files;
    if (!fileList?.length) return;
    uploading = true;
    error = '';
    for (const file of fileList) {
      try {
        uploadProgress = { current: 0, total: 1, filename: file.name };
        const buf = await file.arrayBuffer();
        const ct = guessContentType(file.name);
        await uploadFile(namespace, file.name, buf, ct, (c, t) => {
          uploadProgress = { current: c, total: t, filename: file.name };
        });
        toasts.success(`Uploaded ${file.name}`);
      } catch (e: any) {
        toasts.error(`Upload failed for ${file.name}: ${e.message}`);
      }
    }
    uploading = false;
    if (target) target.value = '';
    await load();
  }

  function askDeleteFile(path: string) {
    confirmTitle = 'Delete file';
    confirmMessage = `Are you sure you want to delete "${path}"? This will remove the file and all its version history.`;
    confirmAction = async () => {
      try {
        await deleteFile(namespace, path);
        toasts.success(`Deleted ${path}`);
        await load();
      } catch (e: any) {
        toasts.error(e.message);
      }
    };
    confirmOpen = true;
  }

  function askDeleteNamespace() {
    confirmTitle = 'Delete namespace';
    confirmMessage = `Delete entire namespace "${namespace}" and ALL its files? This cannot be undone.`;
    confirmAction = async () => {
      try {
        await deleteNamespace(namespace);
        toasts.success(`Deleted namespace ${namespace}`);
        goto('/');
      } catch (e: any) {
        toasts.error(e.message);
      }
    };
    confirmOpen = true;
  }

  async function handleGrant() {
    aclError = '';
    try {
      await grantPublish(namespace, newPrincipal.trim());
      toasts.success('Publisher access granted');
      newPrincipal = '';
      acl = await getAcl();
    } catch (e: any) {
      aclError = e.message;
    }
  }

  async function handleRevoke(p: string) {
    try {
      await revokePublish(namespace, p);
      toasts.success('Publisher access revoked');
      acl = await getAcl();
    } catch (e: any) {
      toasts.error(e.message);
    }
  }

  function copyUrl(path: string) {
    const url = fileUrl(namespace, path);
    navigator.clipboard.writeText(url);
    copiedPath = path;
    toasts.info('URL copied to clipboard');
    setTimeout(() => (copiedPath = ''), 2000);
  }

  let dragOver = false;
  function onDragOver(e: DragEvent) { e.preventDefault(); dragOver = true; }
  function onDragLeave() { dragOver = false; }
  function onDrop(e: DragEvent) { e.preventDefault(); dragOver = false; handleFileUpload(e); }

  $: nsAcl = acl[namespace] ?? [];
</script>

<svelte:head><title>{namespace} — IC File Registry</title></svelte:head>

<div class="space-y-6 animate-fade-in">
  <!-- Breadcrumb -->
  <nav class="flex items-center gap-2 text-sm">
    <a href="/" class="text-primary-500 hover:text-primary-700 transition-colors">Registry</a>
    <svg class="w-4 h-4 text-primary-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
    </svg>
    <span class="text-primary-800 font-medium font-mono">{namespace}</span>
  </nav>

  <!-- Header -->
  <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
    <div>
      <h1 class="text-xl font-bold text-primary-900 font-mono">{namespace}</h1>
      <p class="text-xs text-primary-500 mt-0.5">{files.length} {files.length === 1 ? 'file' : 'files'}</p>
    </div>
    <div class="flex items-center gap-2 self-start">
      <button class="btn-icon" on:click={load} title="Refresh">
        <svg class="w-4 h-4 {loading ? 'animate-spin' : ''}" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
        </svg>
      </button>
      {#if $isAuthenticated}
        <button class="btn-secondary btn-sm" on:click={() => showAcl = !showAcl}>
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
          </svg>
          ACL
        </button>
        <button class="btn-danger btn-sm" on:click={askDeleteNamespace}>
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
          </svg>
          Delete
        </button>
      {/if}
    </div>
  </div>

  <!-- Error -->
  {#if error}
    <div class="card border-red-200 bg-red-50 px-4 py-3 flex items-center gap-3">
      <svg class="w-5 h-5 text-red-500 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10" /><path stroke-linecap="round" d="M12 8v4m0 4h.01" />
      </svg>
      <span class="text-sm text-red-700">{error}</span>
    </div>
  {/if}

  <!-- ACL panel -->
  {#if showAcl}
    <div class="card p-5 space-y-4 animate-fade-in">
      <h3 class="font-semibold text-primary-800 flex items-center gap-2">
        <svg class="w-4 h-4 text-primary-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
        </svg>
        Publisher Access Control
      </h3>
      {#if aclError}
        <p class="text-red-600 text-sm">{aclError}</p>
      {/if}
      {#if nsAcl.length === 0}
        <p class="text-primary-500 text-sm">No publishers granted. Controllers always have access.</p>
      {:else}
        <ul class="space-y-1.5">
          {#each nsAcl as p (p)}
            <li class="flex items-center justify-between bg-primary-50 rounded-lg px-3 py-2">
              <span class="font-mono text-xs text-primary-700">{p}</span>
              <button class="btn-icon p-1" on:click={() => handleRevoke(p)} title="Revoke">
                <svg class="w-4 h-4 text-primary-400 hover:text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M22 10.5h-6m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
                </svg>
              </button>
            </li>
          {/each}
        </ul>
      {/if}
      <div class="flex gap-2">
        <input
          bind:value={newPrincipal}
          placeholder="Principal ID"
          class="input font-mono text-xs flex-1"
        />
        <button class="btn-primary btn-sm" on:click={handleGrant}>
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 7.5v3m0 0v3m0-3h3m-3 0h-3m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z" />
          </svg>
          Grant
        </button>
      </div>
    </div>
  {/if}

  <!-- Upload zone -->
  {#if $isAuthenticated}
    <div
      role="region"
      aria-label="File upload area"
      class="card border-2 border-dashed p-8 text-center transition-all cursor-pointer
             {dragOver ? 'border-primary-500 bg-primary-50' : 'border-primary-200 hover:border-primary-400'}"
      on:dragover={onDragOver}
      on:dragleave={onDragLeave}
      on:drop={onDrop}
    >
      {#if uploading}
        <div class="space-y-3">
          <svg class="w-8 h-8 mx-auto text-primary-400 animate-spin" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
          </svg>
          <p class="text-sm text-primary-600 font-medium">{uploadProgress.filename}</p>
          {#if uploadProgress.total > 1}
            <div class="max-w-xs mx-auto">
              <div class="flex justify-between text-xs text-primary-500 mb-1">
                <span>Chunk {uploadProgress.current} of {uploadProgress.total}</span>
                <span>{Math.round((uploadProgress.current / uploadProgress.total) * 100)}%</span>
              </div>
              <div class="h-1.5 bg-primary-100 rounded-full overflow-hidden">
                <div
                  class="h-full rounded-full transition-all duration-300"
                  style="width: {(uploadProgress.current / uploadProgress.total) * 100}%; background: var(--gradient-institutional);"
                ></div>
              </div>
            </div>
          {/if}
        </div>
      {:else}
        <svg class="w-8 h-8 mx-auto text-primary-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
        <p class="text-primary-500 text-sm mb-3">Drag & drop files here, or</p>
        <label class="cursor-pointer">
          <span class="btn-primary btn-sm">Choose files</span>
          <input type="file" multiple class="hidden" on:change={handleFileUpload} />
        </label>
        <p class="text-xs text-primary-400 mt-3">Files &gt; 500 KB are uploaded in chunks automatically.</p>
      {/if}
    </div>
  {/if}

  <!-- Search (when many files) -->
  {#if files.length > 5}
    <div class="relative">
      <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <circle cx="11" cy="11" r="8" /><path stroke-linecap="round" d="m21 21-4.35-4.35" />
      </svg>
      <input
        type="text"
        bind:value={search}
        placeholder="Filter files..."
        class="input pl-10"
      />
    </div>
  {/if}

  <!-- File list -->
  {#if loading && files.length === 0}
    <div class="card overflow-hidden">
      <div class="px-4 py-3 bg-primary-50 border-b border-primary-200">
        <div class="skeleton h-3 w-20"></div>
      </div>
      {#each [1, 2, 3, 4, 5] as _}
        <div class="px-4 py-3 border-b border-primary-100 flex items-center justify-between">
          <div class="skeleton h-4 w-48"></div>
          <div class="skeleton h-4 w-16"></div>
        </div>
      {/each}
    </div>
  {:else if files.length === 0}
    <div class="text-center py-12">
      <svg class="w-12 h-12 mx-auto text-primary-200 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
      <p class="text-primary-500 text-sm font-medium">No files in this namespace yet</p>
      {#if $isAuthenticated}
        <p class="text-primary-400 text-xs mt-1">Upload files using the area above.</p>
      {/if}
    </div>
  {:else}
    <div class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="bg-primary-50 border-b border-primary-200">
              <th class="text-left px-4 py-3 text-xs font-semibold text-primary-500 uppercase tracking-wider">File</th>
              <th class="text-left px-4 py-3 text-xs font-semibold text-primary-500 uppercase tracking-wider hidden sm:table-cell">Type</th>
              <th class="text-right px-4 py-3 text-xs font-semibold text-primary-500 uppercase tracking-wider">Size</th>
              <th class="text-right px-4 py-3 text-xs font-semibold text-primary-500 uppercase tracking-wider hidden md:table-cell">Updated</th>
              <th class="text-right px-4 py-3 text-xs font-semibold text-primary-500 uppercase tracking-wider w-24"></th>
            </tr>
          </thead>
          <tbody>
            {#each filtered as file (file.path)}
              <tr class="border-b border-primary-100 hover:bg-primary-50/50 transition-colors">
                <td class="px-4 py-3">
                  <a
                    href="/{encodeURIComponent(namespace)}/{file.path}"
                    class="font-mono text-xs text-primary-700 hover:text-primary-900 hover:underline transition-colors"
                  >
                    {file.path}
                  </a>
                </td>
                <td class="px-4 py-3 text-xs text-primary-400 hidden sm:table-cell">{file.content_type}</td>
                <td class="px-4 py-3 text-xs text-primary-500 text-right">{formatBytes(file.size)}</td>
                <td class="px-4 py-3 text-xs text-primary-400 text-right hidden md:table-cell">{timeAgo(file.updated)}</td>
                <td class="px-4 py-3">
                  <div class="flex items-center justify-end gap-1">
                    <a
                      href="/{encodeURIComponent(namespace)}/{file.path}"
                      class="btn-icon p-1.5"
                      title="View file"
                    >
                      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                        <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" /><circle cx="12" cy="12" r="3" />
                      </svg>
                    </a>
                    <button
                      on:click={() => copyUrl(file.path)}
                      title="Copy URL"
                      class="btn-icon p-1.5"
                    >
                      {#if copiedPath === file.path}
                        <svg class="w-4 h-4 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                        </svg>
                      {:else}
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
                        </svg>
                      {/if}
                    </button>
                    {#if $isAuthenticated}
                      <button
                        on:click={() => askDeleteFile(file.path)}
                        title="Delete file"
                        class="btn-icon p-1.5 hover:!text-red-500"
                      >
                        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                          <path stroke-linecap="round" stroke-linejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                        </svg>
                      </button>
                    {/if}
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>

    {#if search && filtered.length === 0}
      <div class="text-center py-8">
        <p class="text-primary-500 text-sm">No files match "{search}"</p>
      </div>
    {/if}
  {/if}
</div>

<ConfirmModal
  bind:open={confirmOpen}
  title={confirmTitle}
  message={confirmMessage}
  confirmLabel="Delete"
  danger
  on:confirm={() => confirmAction?.()}
/>
