"""
IC File Registry — General-purpose on-chain file store

Stores arbitrary files indexed by (namespace, path) with:
  - HTTP serving with CORS (browser fetch / script src)
  - Inter-canister Candid query API (realm backends fetch Python/WASM)
  - Per-namespace publisher ACL
  - Chunked upload for files > 1 MB

Storage layout (persistent filesystem, survives upgrades):
  /registry/_namespaces.json                       index of all namespaces
  /registry/_acl.json                              {namespace: [principal_str, ...]}
  /registry/{namespace}/_meta.json                 file index with version history
  /registry/{namespace}/{path}                     current file content
  /registry/{namespace}/__versions/{path}/v{N}     archived version blobs
  /registry/_chunks/                               temporary chunk staging area
"""

import base64
import hashlib
import json
import os
from typing import Tuple

from basilisk import (
    blob,
    ic,
    nat16,
    Opt,
    Principal,
    query,
    Record,
    text,
    update,
    Vec,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTRY_DIR = "/registry"
CHUNKS_DIR = "/registry/_chunks"
NAMESPACES_FILE = "/registry/_namespaces.json"
ACL_FILE = "/registry/_acl.json"
MAX_VERSIONS = 20

CONTENT_TYPES = {
    ".py":   "text/plain",
    ".js":   "application/javascript",
    ".mjs":  "application/javascript",
    ".json": "application/json",
    ".html": "text/html",
    ".css":  "text/css",
    ".wasm": "application/wasm",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
    ".svg":  "image/svg+xml",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif":  "image/gif",
    ".ico":  "image/x-icon",
    ".ts":   "text/plain",
    ".toml": "text/plain",
    ".yaml": "text/plain",
    ".yml":  "text/plain",
}

# ---------------------------------------------------------------------------
# HTTP types (for the http_request query endpoint)
# ---------------------------------------------------------------------------

Header = Tuple[str, str]


class HttpRequest(Record):
    method: str
    url: str
    headers: Vec["Header"]
    body: blob


class HttpResponseIncoming(Record):
    status_code: nat16
    headers: Vec["Header"]
    body: blob
    streaming_strategy: Opt[str]
    upgrade: Opt[bool]


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _ensure_dirs():
    os.makedirs(REGISTRY_DIR, exist_ok=True)
    os.makedirs(CHUNKS_DIR, exist_ok=True)


def _file_path(namespace: str, path: str) -> str:
    return os.path.join(REGISTRY_DIR, namespace, path.lstrip("/"))


def _meta_path(namespace: str) -> str:
    return os.path.join(REGISTRY_DIR, namespace, "_meta.json")


def _load_namespaces() -> dict:
    try:
        with open(NAMESPACES_FILE, "r") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_namespaces(ns: dict):
    _ensure_dirs()
    with open(NAMESPACES_FILE, "w") as f:
        f.write(json.dumps(ns))


def _load_acl() -> dict:
    try:
        with open(ACL_FILE, "r") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_acl(acl: dict):
    _ensure_dirs()
    with open(ACL_FILE, "w") as f:
        f.write(json.dumps(acl))


def _load_meta(namespace: str) -> dict:
    try:
        with open(_meta_path(namespace), "r") as f:
            return json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"files": {}}


def _save_meta(namespace: str, meta: dict):
    ns_dir = os.path.join(REGISTRY_DIR, namespace)
    os.makedirs(ns_dir, exist_ok=True)
    with open(_meta_path(namespace), "w") as f:
        f.write(json.dumps(meta))


def _versions_dir(namespace: str, path: str) -> str:
    return os.path.join(REGISTRY_DIR, namespace, "__versions", path.lstrip("/"))


def _version_file(namespace: str, path: str, version: int) -> str:
    return os.path.join(_versions_dir(namespace, path), f"v{version}")


def _archive_current_version(namespace: str, path: str, meta: dict):
    """If the file already exists, copy current blob into the version store."""
    file_info = meta.get("files", {}).get(path)
    if not file_info:
        return
    fp = _file_path(namespace, path)
    if not os.path.exists(fp):
        return
    version = file_info.get("current_version", 1)
    vdir = _versions_dir(namespace, path)
    os.makedirs(vdir, exist_ok=True)
    vfp = _version_file(namespace, path, version)
    with open(fp, "rb") as src, open(vfp, "wb") as dst:
        dst.write(src.read())


def _trim_old_versions(namespace: str, path: str, meta: dict):
    """Keep only the last MAX_VERSIONS entries in history."""
    file_info = meta.get("files", {}).get(path)
    if not file_info:
        return
    history = file_info.get("history", [])
    while len(history) > MAX_VERSIONS:
        oldest = history.pop(0)
        vfp = _version_file(namespace, path, oldest["version"])
        try:
            os.remove(vfp)
        except FileNotFoundError:
            pass
    file_info["history"] = history


def _delete_all_versions(namespace: str, path: str):
    """Remove the entire __versions directory for a file."""
    vdir = _versions_dir(namespace, path)
    if not os.path.isdir(vdir):
        return
    for fname in os.listdir(vdir):
        try:
            os.remove(os.path.join(vdir, fname))
        except FileNotFoundError:
            pass
    try:
        os.rmdir(vdir)
    except OSError:
        pass


def _guess_content_type(path: str) -> str:
    for ext, ct in CONTENT_TYPES.items():
        if path.endswith(ext):
            return ct
    return "application/octet-stream"


def _ensure_namespace_exists(namespace: str, caller_str: str):
    namespaces = _load_namespaces()
    if namespace not in namespaces:
        namespaces[namespace] = {
            "namespace": namespace,
            "created": ic.time(),
            "owner": caller_str,
            "description": "",
        }
        _save_namespaces(namespaces)


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

def _require_controller() -> str | None:
    if not ic.is_controller(ic.caller()):
        return json.dumps({"error": "Unauthorized: caller is not a controller"})
    return None


def _require_publisher(namespace: str) -> str | None:
    if ic.is_controller(ic.caller()):
        return None
    caller = ic.caller().to_str()
    acl = _load_acl()
    ns_acl = acl.get(namespace, [])
    if caller in ns_acl:
        return None
    # Auto-grant: first authenticated caller to a new namespace becomes its publisher
    if not ns_acl:
        acl[namespace] = [caller]
        _save_acl(acl)
        return None
    return json.dumps({"error": f"Unauthorized: not a publisher for namespace '{namespace}'"})


# ---------------------------------------------------------------------------
# Public query endpoints
# ---------------------------------------------------------------------------

@query
def list_namespaces() -> text:
    """Return JSON list of all namespaces with file counts and sizes."""
    namespaces = _load_namespaces()
    result = []
    for ns_name, ns_info in namespaces.items():
        meta = _load_meta(ns_name)
        files = meta.get("files", {})
        total_bytes = sum(f.get("size", 0) for f in files.values())
        result.append({
            "namespace": ns_name,
            "file_count": len(files),
            "total_bytes": total_bytes,
            "created": ns_info.get("created", 0),
            "owner": ns_info.get("owner", ""),
            "description": ns_info.get("description", ""),
        })
    result.sort(key=lambda x: x["namespace"])
    return json.dumps(result)


@query
def list_files(args: text) -> text:
    """Return JSON list of files in a namespace.

    Args (JSON): {"namespace": str}
    """
    params = json.loads(args)
    namespace = params["namespace"]
    meta = _load_meta(namespace)
    files = meta.get("files", {})
    result = [
        {
            "path": path,
            "size": info.get("size", 0),
            "content_type": info.get("content_type", "application/octet-stream"),
            "sha256": info.get("sha256", ""),
            "updated": info.get("updated", 0),
            "current_version": info.get("current_version", 1),
        }
        for path, info in files.items()
    ]
    result.sort(key=lambda x: x["path"])
    return json.dumps(result)


@query
def get_file(args: text) -> text:
    """Return file content as base64 + metadata.

    Args (JSON): {"namespace": str, "path": str}
    Returns JSON: {"content_b64": str, "content_type": str, "size": int, "sha256": str}
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")
    fp = _file_path(namespace, path)
    try:
        with open(fp, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"Not found: {namespace}/{path}"})

    meta = _load_meta(namespace)
    file_info = meta.get("files", {}).get(path, {})
    return json.dumps({
        "content_b64": base64.b64encode(content).decode("ascii"),
        "content_type": file_info.get("content_type") or _guess_content_type(path),
        "size": len(content),
        "sha256": file_info.get("sha256") or hashlib.sha256(content).hexdigest(),
    })


@query
def get_stats() -> text:
    """Return overall registry statistics."""
    namespaces = _load_namespaces()
    total_files = 0
    total_bytes = 0
    for ns_name in namespaces:
        meta = _load_meta(ns_name)
        files = meta.get("files", {})
        total_files += len(files)
        total_bytes += sum(f.get("size", 0) for f in files.values())
    return json.dumps({
        "namespaces": len(namespaces),
        "total_files": total_files,
        "total_bytes": total_bytes,
    })


@query
def list_file_versions(args: text) -> text:
    """Return version history for a specific file.

    Args (JSON): {"namespace": str, "path": str}
    Returns JSON: [{"version": int, "size": int, "sha256": str, "content_type": str, "updated": int, "is_current": bool}]
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")

    meta = _load_meta(namespace)
    file_info = meta.get("files", {}).get(path)
    if not file_info:
        return json.dumps({"error": f"Not found: {namespace}/{path}"})

    history = file_info.get("history", [])
    result = [
        {
            "version": h["version"],
            "size": h.get("size", 0),
            "sha256": h.get("sha256", ""),
            "content_type": h.get("content_type", ""),
            "updated": h.get("updated", 0),
            "is_current": False,
        }
        for h in history
    ]
    result.append({
        "version": file_info.get("current_version", 1),
        "size": file_info.get("size", 0),
        "sha256": file_info.get("sha256", ""),
        "content_type": file_info.get("content_type", ""),
        "updated": file_info.get("updated", 0),
        "is_current": True,
    })
    return json.dumps(result)


@query
def get_file_at_version(args: text) -> text:
    """Return file content at a specific version.

    Args (JSON): {"namespace": str, "path": str, "version": int}
    Returns JSON: {"content_b64": str, "content_type": str, "size": int, "sha256": str, "version": int}
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")
    version = int(params["version"])

    meta = _load_meta(namespace)
    file_info = meta.get("files", {}).get(path)
    if not file_info:
        return json.dumps({"error": f"Not found: {namespace}/{path}"})

    current_version = file_info.get("current_version", 1)

    if version == current_version:
        fp = _file_path(namespace, path)
    else:
        fp = _version_file(namespace, path, version)

    try:
        with open(fp, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        return json.dumps({"error": f"Version {version} not found for {namespace}/{path}"})

    ct = file_info.get("content_type") or _guess_content_type(path)
    history = file_info.get("history", [])
    version_info = next((h for h in history if h["version"] == version), None)
    if version_info:
        ct = version_info.get("content_type", ct)

    return json.dumps({
        "content_b64": base64.b64encode(content).decode("ascii"),
        "content_type": ct,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "version": version,
    })


@query
def get_acl() -> text:
    """Return the full publisher ACL: {namespace: [principal_str]}."""
    return json.dumps(_load_acl())


# ---------------------------------------------------------------------------
# Authenticated update endpoints
# ---------------------------------------------------------------------------

@update
def store_file(args: text) -> text:
    """Store a file. Caller must be a controller or namespace publisher.

    Args (JSON): {
        "namespace": str,
        "path": str,
        "content_b64": str,        (base64-encoded file content)
        "content_type": str        (optional, inferred from extension if absent)
    }
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")
    content_b64 = params["content_b64"]
    content_type = params.get("content_type") or _guess_content_type(path)

    err = _require_publisher(namespace)
    if err:
        return err

    try:
        content = base64.b64decode(content_b64)
    except Exception as e:
        return json.dumps({"error": f"Invalid base64: {e}"})

    caller_str = ic.caller().to_str()
    _ensure_namespace_exists(namespace, caller_str)

    meta = _load_meta(namespace)
    old_info = meta.get("files", {}).get(path)

    _archive_current_version(namespace, path, meta)

    fp = _file_path(namespace, path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "wb") as f:
        f.write(content)

    sha256 = hashlib.sha256(content).hexdigest()
    now = ic.time()
    prev_version = old_info.get("current_version", 0) if old_info else 0
    new_version = prev_version + 1

    history = (old_info.get("history", []) if old_info else [])[:]
    if old_info:
        history.append({
            "version": prev_version,
            "size": old_info.get("size", 0),
            "sha256": old_info.get("sha256", ""),
            "content_type": old_info.get("content_type", ""),
            "updated": old_info.get("updated", 0),
        })

    meta.setdefault("files", {})[path] = {
        "size": len(content),
        "content_type": content_type,
        "sha256": sha256,
        "updated": now,
        "current_version": new_version,
        "history": history,
    }
    _trim_old_versions(namespace, path, meta)
    _save_meta(namespace, meta)

    return json.dumps({
        "ok": True,
        "namespace": namespace,
        "path": path,
        "size": len(content),
        "sha256": sha256,
        "version": new_version,
    })


@update
def delete_file(args: text) -> text:
    """Delete a file. Caller must be a controller or namespace publisher.

    Args (JSON): {"namespace": str, "path": str}
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")

    err = _require_publisher(namespace)
    if err:
        return err

    fp = _file_path(namespace, path)
    try:
        os.remove(fp)
    except FileNotFoundError:
        return json.dumps({"error": f"Not found: {namespace}/{path}"})

    _delete_all_versions(namespace, path)

    meta = _load_meta(namespace)
    meta.get("files", {}).pop(path, None)
    _save_meta(namespace, meta)

    return json.dumps({"ok": True, "namespace": namespace, "path": path})


@update
def update_namespace(args: text) -> text:
    """Update namespace description. Controller only.

    Args (JSON): {"namespace": str, "description": str}
    """
    err = _require_controller()
    if err:
        return err

    params = json.loads(args)
    namespace = params["namespace"]
    description = params.get("description", "")

    namespaces = _load_namespaces()
    if namespace not in namespaces:
        return json.dumps({"error": f"Namespace '{namespace}' not found"})

    namespaces[namespace]["description"] = description
    _save_namespaces(namespaces)

    return json.dumps({"ok": True, "namespace": namespace})


@update
def delete_namespace(args: text) -> text:
    """Delete a namespace and all its files. Controller only.

    Args (JSON): {"namespace": str}
    """
    err = _require_controller()
    if err:
        return err

    params = json.loads(args)
    namespace = params["namespace"]

    namespaces = _load_namespaces()
    if namespace not in namespaces:
        return json.dumps({"error": f"Namespace '{namespace}' not found"})

    meta = _load_meta(namespace)
    for path in list(meta.get("files", {}).keys()):
        _delete_all_versions(namespace, path)
        fp = _file_path(namespace, path)
        try:
            os.remove(fp)
        except FileNotFoundError:
            pass

    try:
        os.remove(_meta_path(namespace))
    except FileNotFoundError:
        pass

    del namespaces[namespace]
    _save_namespaces(namespaces)

    acl = _load_acl()
    acl.pop(namespace, None)
    _save_acl(acl)

    return json.dumps({"ok": True, "namespace": namespace})


@update
def grant_publish(args: text) -> text:
    """Grant publish access to a principal for a namespace. Controller only.

    Args (JSON): {"namespace": str, "principal": str}
    """
    err = _require_controller()
    if err:
        return err

    params = json.loads(args)
    namespace = params["namespace"]
    principal = params["principal"]

    acl = _load_acl()
    ns_acl = acl.setdefault(namespace, [])
    if principal not in ns_acl:
        ns_acl.append(principal)
        _save_acl(acl)

    return json.dumps({"ok": True, "namespace": namespace, "principal": principal})


@update
def revoke_publish(args: text) -> text:
    """Revoke publish access from a principal for a namespace. Controller only.

    Args (JSON): {"namespace": str, "principal": str}
    """
    err = _require_controller()
    if err:
        return err

    params = json.loads(args)
    namespace = params["namespace"]
    principal = params["principal"]

    acl = _load_acl()
    ns_acl = acl.get(namespace, [])
    if principal in ns_acl:
        ns_acl.remove(principal)
        _save_acl(acl)

    return json.dumps({"ok": True, "namespace": namespace, "principal": principal})


# ---------------------------------------------------------------------------
# Chunked upload — for files > 1 MB (e.g. WASMs)
# ---------------------------------------------------------------------------

def _chunk_file_path(namespace: str, path: str, chunk_index: int) -> str:
    safe_key = f"{namespace}__{path.replace('/', '__')}"
    return os.path.join(CHUNKS_DIR, f"{safe_key}_{chunk_index:04d}")


def _pending_meta_path(namespace: str, path: str) -> str:
    safe_key = f"{namespace}__{path.replace('/', '__')}"
    return os.path.join(CHUNKS_DIR, f"{safe_key}__pending.json")


@update
def store_file_chunk(args: text) -> text:
    """Upload one chunk of a large file.

    Args (JSON): {
        "namespace": str,
        "path": str,
        "chunk_index": int,
        "total_chunks": int,
        "data_b64": str,
        "content_type": str   (optional)
    }
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")
    chunk_index = int(params["chunk_index"])
    total_chunks = int(params["total_chunks"])
    data_b64 = params["data_b64"]
    content_type = params.get("content_type") or _guess_content_type(path)

    err = _require_publisher(namespace)
    if err:
        return err

    try:
        data = base64.b64decode(data_b64)
    except Exception as e:
        return json.dumps({"error": f"Invalid base64: {e}"})

    _ensure_dirs()
    with open(_chunk_file_path(namespace, path, chunk_index), "wb") as f:
        f.write(data)

    pending_path = _pending_meta_path(namespace, path)
    try:
        with open(pending_path, "r") as f:
            pending = json.loads(f.read())
    except (FileNotFoundError, json.JSONDecodeError):
        pending = {"total_chunks": total_chunks, "uploaded": [], "content_type": content_type}

    if chunk_index not in pending["uploaded"]:
        pending["uploaded"].append(chunk_index)
    with open(pending_path, "w") as f:
        f.write(json.dumps(pending))

    return json.dumps({
        "ok": True,
        "chunk_index": chunk_index,
        "uploaded": len(pending["uploaded"]),
        "total_chunks": total_chunks,
    })


@update
def finalize_chunked_file(args: text) -> text:
    """Assemble previously uploaded chunks into the final file.

    Args (JSON): {"namespace": str, "path": str}
    """
    params = json.loads(args)
    namespace = params["namespace"]
    path = params["path"].lstrip("/")

    err = _require_publisher(namespace)
    if err:
        return err

    pending_path = _pending_meta_path(namespace, path)
    try:
        with open(pending_path, "r") as f:
            pending = json.loads(f.read())
    except FileNotFoundError:
        return json.dumps({"error": f"No pending upload for {namespace}/{path}"})

    total_chunks = pending["total_chunks"]
    content_type = pending.get("content_type") or _guess_content_type(path)

    for i in range(total_chunks):
        if not os.path.exists(_chunk_file_path(namespace, path, i)):
            return json.dumps({"error": f"Missing chunk {i} of {total_chunks}"})

    caller_str = ic.caller().to_str()
    _ensure_namespace_exists(namespace, caller_str)

    meta = _load_meta(namespace)
    old_info = meta.get("files", {}).get(path)

    _archive_current_version(namespace, path, meta)

    fp = _file_path(namespace, path)
    os.makedirs(os.path.dirname(fp), exist_ok=True)

    h = hashlib.sha256()
    total_size = 0
    with open(fp, "wb") as out:
        for i in range(total_chunks):
            chunk_path = _chunk_file_path(namespace, path, i)
            with open(chunk_path, "rb") as cf:
                chunk = cf.read()
            out.write(chunk)
            h.update(chunk)
            total_size += len(chunk)
            os.remove(chunk_path)

    os.remove(pending_path)
    sha256 = h.hexdigest()
    now = ic.time()
    prev_version = old_info.get("current_version", 0) if old_info else 0
    new_version = prev_version + 1

    history = (old_info.get("history", []) if old_info else [])[:]
    if old_info:
        history.append({
            "version": prev_version,
            "size": old_info.get("size", 0),
            "sha256": old_info.get("sha256", ""),
            "content_type": old_info.get("content_type", ""),
            "updated": old_info.get("updated", 0),
        })

    meta.setdefault("files", {})[path] = {
        "size": total_size,
        "content_type": content_type,
        "sha256": sha256,
        "updated": now,
        "current_version": new_version,
        "history": history,
    }
    _trim_old_versions(namespace, path, meta)
    _save_meta(namespace, meta)

    return json.dumps({
        "ok": True,
        "namespace": namespace,
        "path": path,
        "size": total_size,
        "sha256": sha256,
        "version": new_version,
    })


# ---------------------------------------------------------------------------
# HTTP endpoint — serve files with CORS headers
# GET /{namespace}/{path}  →  returns file content
# GET /                    →  returns namespaces JSON
# ---------------------------------------------------------------------------

def _http_response(status: int, body: bytes, content_type: str, extra_headers=None) -> dict:
    headers = [
        ("Access-Control-Allow-Origin", "*"),
        ("Access-Control-Allow-Methods", "GET, OPTIONS"),
        ("Access-Control-Allow-Headers", "Content-Type"),
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return {
        "status_code": status,
        "headers": headers,
        "body": body,
        "streaming_strategy": None,
        "upgrade": None,
    }


def _handle_http(req: dict) -> dict:
    """Shared logic for http_request and http_request_update."""
    method = req["method"].upper()
    url = req["url"]
    path = url.split("?")[0].lstrip("/")

    if method == "OPTIONS":
        return _http_response(204, b"", "text/plain")

    if not path:
        body = list_namespaces().encode("utf-8")
        return _http_response(200, body, "application/json")

    parts = path.split("/", 1)
    if len(parts) < 2:
        body = json.dumps({"error": "Path must be /{namespace}/{file_path}"}).encode()
        return _http_response(404, body, "application/json")

    namespace, file_path = parts[0], parts[1]

    if not file_path:
        body = list_files(json.dumps({"namespace": namespace})).encode("utf-8")
        return _http_response(200, body, "application/json")

    fp = _file_path(namespace, file_path)
    try:
        with open(fp, "rb") as f:
            content = f.read()
    except FileNotFoundError:
        body = json.dumps({"error": f"Not found: {namespace}/{file_path}"}).encode()
        return _http_response(404, body, "application/json")

    meta = _load_meta(namespace)
    file_info = meta.get("files", {}).get(file_path, {})
    content_type = file_info.get("content_type") or _guess_content_type(file_path)

    return _http_response(200, content, content_type, [
        ("Cache-Control", "public, max-age=3600"),
    ])


@query
def http_request(req: HttpRequest) -> HttpResponseIncoming:
    """Signal the gateway to upgrade to an update call for certified responses."""
    return {
        "status_code": 200,
        "headers": [],
        "body": b"",
        "streaming_strategy": None,
        "upgrade": True,
    }


@update
def http_request_update(req: HttpRequest) -> HttpResponseIncoming:
    """Serve files over HTTP with CORS. Runs as update so response is certified."""
    return _handle_http(req)
