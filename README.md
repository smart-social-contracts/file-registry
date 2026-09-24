# file-registry

General-purpose on-chain file storage for the Internet Computer.

> Part of the [Casals](https://github.com/smart-social-contracts/Casals) ecosystem: this is the
> durable, hash-addressed artifact registry that holds the authorized WASMs (and extension /
> codex / frontend bundles) Casals installs onto its stands. It is a standalone canister and can
> be used on its own. Generalized from the realms `file_registry`.

Stores arbitrary files (extensions, WASMs, codex scripts, frontend assets) indexed by `(namespace, path)` with:
- **HTTP serving with CORS** — browser `fetch()` / `<script src>` directly from the canister URL
- **Inter-canister Candid API** — realm backends fetch Python/WASM via `get_file` without HTTP outcalls
- **Per-namespace publisher ACL** — grant upload access per namespace without exposing full controller access
- **Chunked upload** — files > 500 KB are automatically split and reassembled (handles WASMs up to ~400 MB)
- **Internet Identity frontend** — browse, upload, manage via browser with II login

Built with [basilisk](https://github.com/smart-social-contracts/basilisk) — Python on the IC.

## Architecture

```
Browser / CLI
    │
    ├── HTTPS  →  GET /{namespace}/{path}    (CORS, public)
    └── Candid →  store_file / get_file / ...

Realm backend (inter-canister)
    └── Candid →  get_file("extensions/hello_world", "entry.py")
```

Files are stored in the canister's persistent filesystem (`/registry/...`), backed by `StableBTreeMap` in stable memory — survives upgrades automatically.

## API

### Public queries (no auth)
| Method | Args | Description |
|---|---|---|
| `list_namespaces()` | — | List all namespaces with file counts and sizes |
| `list_files(args)` | `{namespace}` | List files in a namespace |
| `get_file(args)` | `{namespace, path}` | Get file content (base64) + metadata |
| `get_stats()` | — | Overall storage statistics |
| `get_acl()` | — | Publisher ACL for all namespaces |
| `http_request(req)` | HTTP | Serve files via HTTP with CORS |

### Package catalog (no auth)

Extension and codex packages are plain namespaces that follow a convention: `ext/{id}/{version}`
(or legacy `codex/{id}/{version}`) with a `manifest.json` at the root. These queries resolve
"install `hello_world`" to a namespace, which callers then read with the generic API above.
A version counts as a package once its `manifest.json` exists, so a namespace still mid-upload
is never resolved as latest. (Issue [#3](https://github.com/smart-social-contracts/file-registry/issues/3).)

| Method | Args | Returns |
|---|---|---|
| `list_extensions()` | — | `[{ext_id, versions, latest, manifest}]` — `manifest` is the latest version's |
| `list_codices()` | — | `[{codex_id, versions, latest, namespace_prefix}]` — `ext/…` packages whose manifest has `"kind": "codex"`, plus legacy `codex/…` |
| `latest_version(args)` | `{category: "ext"\|"codex", item_id}` | `{latest, namespace}` |
| `get_extension_manifest(args)` | `{ext_id, version?}` | the manifest plus `_version` and `_namespace`; `version` null or `"latest"` picks the highest |

### Authenticated updates (publisher or controller)
| Method | Args | Description |
|---|---|---|
| `store_file(args)` | `{namespace, path, content_b64, content_type?}` | Upload file (≤ 500 KB) |
| `store_file_chunk(args)` | `{namespace, path, chunk_index, total_chunks, data_b64}` | Upload one chunk |
| `finalize_chunked_file(args)` | `{namespace, path}` | Assemble chunks into file |
| `delete_file(args)` | `{namespace, path}` | Delete a file |

### Controller-only
| Method | Args | Description |
|---|---|---|
| `grant_publish(args)` | `{namespace, principal}` | Grant upload access |
| `revoke_publish(args)` | `{namespace, principal}` | Revoke upload access |
| `delete_namespace(args)` | `{namespace}` | Delete namespace + all files |
| `update_namespace(args)` | `{namespace, description}` | Update namespace metadata |

## HTTP serving

Files are served at:
```
https://{canister_id}.icp0.io/{namespace}/{path}
```

With CORS headers — suitable for:
```html
<script type="module" src="https://{canister}.icp0.io/extensions/hello_world/main.js"></script>
```
```python
# Inter-canister (realm backend)
result = yield registry_canister.get_file('{"namespace": "extensions/hello_world", "path": "entry.py"}')
```

## CLI upload

```bash
# Single file
python3 scripts/upload_file.py \
  --canister <CANISTER_ID> \
  --namespace extensions/hello_world \
  --file ./hello_world/backend/entry.py \
  --network ic

# Entire directory
python3 scripts/upload_file.py \
  --canister <CANISTER_ID> \
  --namespace extensions/hello_world \
  --dir ./hello_world/ \
  --network ic
```

## Deploy

Deployed with [`icp-cli`](https://github.com/dfinity/icp-cli) (`icp.yaml`); **dfx is not used**.
The Basilisk backend WASM is built out-of-band and installed via the `prebuilt` recipe; the
SvelteKit frontend is built by the `asset-canister` recipe at deploy time.

```bash
# Install deps
pip install ic-basilisk-toolkit

# Build the backend WASM + deploy both canisters (local)
make deploy

# Mainnet
make deploy-ic
```

Under the hood `make deploy` runs:

```bash
# 1. Build the Basilisk backend WASM
CANISTER_CANDID_PATH=./ic_file_registry.did python3 -m basilisk ic_file_registry src/main.py
# 2. icp-cli builds the frontend (npm) and installs both canisters
icp deploy            # add --network ic for mainnet
```

### How the frontend finds its backend

The same `frontend/dist` is served locally and on mainnet, so the backend id is resolved at
runtime, in this order (`frontend/src/lib/api.ts`):

1. `PUBLIC_CANISTER_ID:ic_file_registry` in the `ic_env` cookie — set by icp-cli's asset
   canister, i.e. the `icp deploy` path above.
2. `globalThis.__CANISTER_IDS.file_registry` from `/canister_ids.js`, loaded by `app.html` —
   the path used when a Casals sheet publishes the dist into a plain certified-assets canister
   (`realms/casals.json`, stand `file-registry`, canister `fleet-file-registry-frontend`) and
   writes that file next to it.
3. `VITE_CANISTER_ID` at build time — only for a standalone `vite dev` server.

### Building the dist for a Casals sheet

```bash
make build            # backend wasm + frontend/dist
make build-frontend   # frontend/dist only (npm ci + vite build)
```

`make build` produces the wasm and `frontend/dist`. The Realms and GaaS sheets
install the published release instead of these local paths.

## File size limits

| Limit | Value |
|---|---|
| Per-file max (single call) | 500 KB |
| Per-file max (chunked) | ~400 MB (practical) |
| Per-file hard limit (stable memory) | 2 MB per chunk |
| Total storage | 50 MB default (soft limit, adjustable) |

Files > 500 KB are automatically uploaded in chunks by `scripts/upload_file.py` and the frontend.
