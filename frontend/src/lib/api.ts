import { Actor, HttpAgent } from '@dfinity/agent';
import { idlFactory } from './declarations';
import { get } from 'svelte/store';
import { identity } from './auth';
import { canisterHttpUrl, icHost, isLocalHost } from './ic-host';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface NamespaceInfo {
  namespace: string;
  file_count: number;
  total_bytes: number;
  created: number;
  owner: string;
  description: string;
}

export interface FileInfo {
  path: string;
  size: number;
  content_type: string;
  sha256: string;
  updated: number;
  current_version?: number;
}

export interface FileContent {
  content_b64: string;
  content_type: string;
  size: number;
  sha256: string;
  version?: number;
}

export interface FileVersion {
  version: number;
  size: number;
  sha256: string;
  content_type: string;
  updated: number;
  is_current: boolean;
}

export interface Stats {
  namespaces: number;
  total_files: number;
  total_bytes: number;
}

export type AclMap = Record<string, string[]>;

export interface RegistryConfig {
  auto_grant_publishers: boolean;
}

// ---------------------------------------------------------------------------
// Actor setup
// ---------------------------------------------------------------------------

function _canisterEnv(): Record<string, string> {
  if (typeof document === 'undefined') return {};
  const match = document.cookie.match(/(?:^|;\s*)ic_env=([^;]+)/);
  if (!match) return {};
  const env: Record<string, string> = {};
  for (const pair of decodeURIComponent(match[1]).split('&')) {
    const eq = pair.indexOf('=');
    if (eq > 0) env[pair.slice(0, eq)] = pair.slice(eq + 1);
  }
  return env;
}

function _registryCanisterId(): string {
  // Three sources, in order; the same dist is served locally and on mainnet,
  // so the id must come from the environment, never be baked in:
  //  1. icp-cli's asset canister sets an `ic_env` cookie with the live id of
  //     every canister in the project (this repo's own `icp deploy` path).
  //  2. A Casals sheet publishes this dist into a plain certified-assets
  //     canister and writes `/canister_ids.js` next to it, which app.html
  //     loads synchronously: `globalThis.__CANISTER_IDS.file_registry`.
  //  3. VITE_CANISTER_ID at build time, for a standalone `vite dev` server
  //     that is served outside any asset canister and gets neither.
  const fromCookie = _canisterEnv()['PUBLIC_CANISTER_ID:ic_file_registry'];
  if (fromCookie) return fromCookie;
  const fromRuntime = (globalThis as any).__CANISTER_IDS?.file_registry;
  if (typeof fromRuntime === 'string' && fromRuntime) return fromRuntime;
  return (import.meta.env.VITE_CANISTER_ID as string | undefined) ?? '';
}

const CANISTER_ID = _registryCanisterId();
const IS_LOCAL = isLocalHost();
const HOST = icHost();

function _makeActor(id: any = null) {
  const agent = new HttpAgent({ identity: id ?? undefined, host: HOST });
  if (IS_LOCAL) agent.fetchRootKey().catch(() => {});
  if (!CANISTER_ID) {
    throw new Error(
      'Backend canister ID not found. Expected PUBLIC_CANISTER_ID:ic_file_registry in the ' +
        'ic_env cookie, __CANISTER_IDS.file_registry from /canister_ids.js, or VITE_CANISTER_ID at build time.'
    );
  }
  return Actor.createActor(idlFactory, { agent, canisterId: CANISTER_ID });
}

function _actor(authenticated = false): any {
  if (authenticated) {
    const id = get(identity);
    if (!id) throw new Error('Not authenticated');
    return _makeActor(id);
  }
  return _makeActor();
}

function _parse(raw: string) {
  const result = JSON.parse(raw);
  if (result?.error) throw new Error(result.error);
  return result;
}

// ---------------------------------------------------------------------------
// Public queries
// ---------------------------------------------------------------------------

export async function listNamespaces(): Promise<NamespaceInfo[]> {
  const raw = await _actor().list_namespaces();
  return JSON.parse(raw);
}

export async function listFiles(namespace: string): Promise<FileInfo[]> {
  const raw = await _actor().list_files(JSON.stringify({ namespace }));
  return JSON.parse(raw);
}

export async function getFile(namespace: string, path: string): Promise<FileContent> {
  const raw = await _actor().get_file(JSON.stringify({ namespace, path }));
  return _parse(raw);
}

export async function listFileVersions(namespace: string, path: string): Promise<FileVersion[]> {
  const raw = await _actor().list_file_versions(JSON.stringify({ namespace, path }));
  return _parse(raw);
}

export async function getFileAtVersion(
  namespace: string,
  path: string,
  version: number,
): Promise<FileContent> {
  const raw = await _actor().get_file_at_version(JSON.stringify({ namespace, path, version }));
  return _parse(raw);
}

export async function getStats(): Promise<Stats> {
  const raw = await _actor().get_stats();
  return JSON.parse(raw);
}

export async function getAcl(): Promise<AclMap> {
  const raw = await _actor().get_acl();
  return JSON.parse(raw);
}

export async function getConfig(): Promise<RegistryConfig> {
  const raw = await _actor().get_config();
  return JSON.parse(raw);
}

// ---------------------------------------------------------------------------
// Authenticated updates
// ---------------------------------------------------------------------------

export async function storeFile(
  namespace: string,
  path: string,
  fileBytes: ArrayBuffer,
  contentType: string,
) {
  const content_b64 = btoa(String.fromCharCode(...new Uint8Array(fileBytes)));
  const raw = await _actor(true).store_file(
    JSON.stringify({ namespace, path, content_b64, content_type: contentType }),
  );
  return _parse(raw);
}

export async function storeFileChunked(
  namespace: string,
  path: string,
  fileBytes: ArrayBuffer,
  contentType: string,
  onProgress?: (current: number, total: number) => void,
) {
  const CHUNK = 500_000;
  const total = Math.ceil(fileBytes.byteLength / CHUNK);
  for (let i = 0; i < total; i++) {
    const slice = fileBytes.slice(i * CHUNK, (i + 1) * CHUNK);
    const data_b64 = btoa(String.fromCharCode(...new Uint8Array(slice)));
    const raw = await _actor(true).store_file_chunk(
      JSON.stringify({
        namespace,
        path,
        chunk_index: i,
        total_chunks: total,
        data_b64,
        content_type: contentType,
      }),
    );
    _parse(raw);
    onProgress?.(i + 1, total);
  }
  const raw = await _actor(true).finalize_chunked_file(JSON.stringify({ namespace, path }));
  return _parse(raw);
}

export async function uploadFile(
  namespace: string,
  path: string,
  fileBytes: ArrayBuffer,
  contentType: string,
  onProgress?: (current: number, total: number) => void,
) {
  if (fileBytes.byteLength > 500_000) {
    return storeFileChunked(namespace, path, fileBytes, contentType, onProgress);
  }
  return storeFile(namespace, path, fileBytes, contentType);
}

export async function deleteFile(namespace: string, path: string) {
  const raw = await _actor(true).delete_file(JSON.stringify({ namespace, path }));
  return _parse(raw);
}

export async function grantPublish(namespace: string, principalStr: string) {
  const raw = await _actor(true).grant_publish(
    JSON.stringify({ namespace, principal: principalStr }),
  );
  return _parse(raw);
}

export async function revokePublish(namespace: string, principalStr: string) {
  const raw = await _actor(true).revoke_publish(
    JSON.stringify({ namespace, principal: principalStr }),
  );
  return _parse(raw);
}

export async function deleteNamespace(namespace: string) {
  const raw = await _actor(true).delete_namespace(JSON.stringify({ namespace }));
  return _parse(raw);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

export function fileUrl(namespace: string, path: string): string {
  if (!CANISTER_ID) return '#';
  return `${canisterHttpUrl(CANISTER_ID)}/${namespace}/${path}`;
}

const CONTENT_TYPE_MAP: Record<string, string> = {
  '.py': 'text/plain',
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.json': 'application/json',
  '.html': 'text/html',
  '.css': 'text/css',
  '.wasm': 'application/wasm',
  '.txt': 'text/plain',
  '.md': 'text/markdown',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.ts': 'text/plain',
  '.toml': 'text/plain',
  '.yaml': 'text/plain',
  '.yml': 'text/plain',
};

export function guessContentType(filename: string): string {
  for (const [ext, ct] of Object.entries(CONTENT_TYPE_MAP)) {
    if (filename.endsWith(ext)) return ct;
  }
  return 'application/octet-stream';
}

export function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

export function isTextType(ct: string): boolean {
  return (
    ct.startsWith('text/') ||
    ct === 'application/json' ||
    ct === 'application/javascript'
  );
}

export function isImageType(ct: string): boolean {
  return ct.startsWith('image/');
}

export function timeAgo(nanos: number): string {
  if (!nanos) return '';
  const ms = Number(nanos) / 1_000_000;
  const diff = Date.now() - ms;
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(ms).toLocaleDateString();
}
