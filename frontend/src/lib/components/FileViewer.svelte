<script lang="ts">
  import { isTextType, isImageType, formatBytes } from '$lib/api';

  export let content: string;
  export let contentType: string;
  export let filename: string;
  export let size: number;

  $: decoded = (() => {
    try {
      return atob(content);
    } catch {
      return null;
    }
  })();

  $: isText = isTextType(contentType);
  $: isImage = isImageType(contentType);
  $: isJson = contentType === 'application/json';

  $: lines = decoded ? decoded.split('\n') : [];
  $: prettyJson = (() => {
    if (!isJson || !decoded) return null;
    try {
      return JSON.stringify(JSON.parse(decoded), null, 2);
    } catch {
      return decoded;
    }
  })();
  $: jsonLines = prettyJson ? prettyJson.split('\n') : [];

  $: dataUri = isImage ? `data:${contentType};base64,${content}` : '';
</script>

<div class="code-block overflow-hidden">
  {#if isImage}
    <div class="p-6 flex items-center justify-center bg-[#FAFAFA] min-h-[200px]">
      <img
        src={dataUri}
        alt={filename}
        class="max-w-full max-h-[500px] rounded shadow-sm"
      />
    </div>
  {:else if isJson && prettyJson}
    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <tbody>
          {#each jsonLines as line, i}
            <tr class="hover:bg-primary-100/50">
              <td class="line-numbers py-0 px-3 text-xs border-r border-primary-200">{i + 1}</td>
              <td class="py-0 px-4 whitespace-pre font-mono text-sm text-primary-800">{line}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else if isText && decoded}
    <div class="overflow-x-auto">
      <table class="w-full border-collapse">
        <tbody>
          {#each lines as line, i}
            <tr class="hover:bg-primary-100/50">
              <td class="line-numbers py-0 px-3 text-xs border-r border-primary-200">{i + 1}</td>
              <td class="py-0 px-4 whitespace-pre font-mono text-sm text-primary-800">{line}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <div class="p-8 text-center">
      <svg class="w-12 h-12 mx-auto text-primary-300 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
      <p class="text-primary-500 text-sm font-medium mb-1">Binary file</p>
      <p class="text-primary-400 text-xs">{formatBytes(size)} &middot; {contentType}</p>
      <a
        href="data:application/octet-stream;base64,{content}"
        download={filename}
        class="btn-secondary btn-sm mt-4 inline-flex"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
        </svg>
        Download
      </a>
    </div>
  {/if}
</div>
