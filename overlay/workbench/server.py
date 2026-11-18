# -*- coding: utf-8 -*-
"""
SUPRA-Tex Workbench : 브라우저 화면에서 mesh_texture.py 를 실행하는 작은 로컬 서버

- 파이썬 기본 모듈만 쓴다. (추가 설치 없음)
- 127.0.0.1 에서만 열린다. 다른 PC 에서는 접속할 수 없다.
- 한 번에 작업 하나만 돌린다. 작업은 별도 프로세스(mesh_texture.py)로 실행한다.
- 작업 폴더 : SUPRA-Tex\\workbench_data\\jobs\\<작업ID>  (입력, 맞춤 결과, 로그, 결과 GLB)
"""
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent          # SUPRA-Tex 폴더
WEB = Path(__file__).resolve().parent / "web"
DATA = ROOT / "workbench_data"
UPLOADS = DATA / "uploads"
JOBS = DATA / "jobs"
CUTOUTS = DATA / "cutouts"      # 배경을 지운 이미지 (같은 이미지는 다시 지우지 않게)
PORT = int(os.environ.get("SUPRATEX_WORKBENCH_PORT", "8390"))
MAX_UPLOAD = 512 * 1024 * 1024
MESH_EXT = {".glb", ".gltf", ".obj", ".ply", ".stl"}
IMAGE_EXT = {".png", ".webp", ".jpg", ".jpeg"}
ID_RE = re.compile(r"^[0-9a-f]{8,40}$")

LOCK = threading.RLock()
RUNNING = {"id": None, "proc": None}


# --------------------------------------------------------------------------------------
def now():
    return time.time()


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, value):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def safe_name(name):
    name = Path(unquote(name or "")).name
    name = re.sub(r"[^0-9A-Za-z._-]+", "_", name).strip("._")
    return name or "file"


def job_dir(jid):
    if not ID_RE.match(jid or ""):
        raise KeyError(jid)
    path = JOBS / jid
    if not path.is_dir():
        raise KeyError(jid)
    return path


def folder_size(path):
    total = 0
    for f in Path(path).rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def remove_tree(path):
    def force(func, p, _exc):
        try:
            os.chmod(p, 0o666)
            func(p)
        except OSError:
            pass
    shutil.rmtree(path, onerror=force)


def kill_tree(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except OSError:
        pass


# --------------------------------------------------------------------------------------
# 작업
# --------------------------------------------------------------------------------------
def tail_log(path, lines=40):
    try:
        raw = Path(path).read_bytes()[-200000:].decode("utf-8", errors="replace")
    except OSError:
        return []
    # tqdm 진행 표시줄은 \r 로 같은 줄을 덮어쓴다. 마지막 모습만 남긴다.
    out = []
    for line in raw.split("\n"):
        line = line.rstrip("\r").split("\r")[-1].rstrip()
        if line:
            out.append(line)
    return out[-lines:]


def job_summary(path):
    state = read_json(path / "state.json", {}) or {}
    state["id"] = path.name
    case = path / "result_case"
    state["has_preview"] = (case / "fit_preview.png").is_file()
    state["cutout"] = (case / "cutout.png").is_file()
    state["has_result"] = (path / "result.glb").is_file()
    fit = read_json(case / "transform.json")
    if fit:
        state["fit"] = {k: fit.get(k) for k in ("silhouette_iou", "fov_deg", "yaw_fix", "pitch_fix")}
    return state


def list_jobs():
    if not JOBS.is_dir():
        return []
    items = [job_summary(p) for p in JOBS.iterdir() if p.is_dir() and ID_RE.match(p.name)]
    return sorted(items, key=lambda s: s.get("created", 0), reverse=True)


def build_command(job, mesh, image, opts, prep_only):
    cmd = [sys.executable, "-u", str(ROOT / "mesh_texture.py"), str(mesh), str(image),
           "--output", str(job / "result.glb")]
    yaw = int(opts.get("yaw", 0) or 0)
    if yaw in (90, 180, 270):
        cmd += ["--yaw", str(yaw)]
    if opts.get("zup"):
        cmd.append("--zup")
    fov = opts.get("fov")
    if fov not in (None, "", 0, "0"):
        cmd += ["--fov", str(float(fov))]
    if opts.get("no_rotate_search"):
        cmd.append("--no-rotate-search")
    if opts.get("keep_normalized"):
        cmd.append("--keep-normalized")
    for key, flag in (("metal_cut", "--metal-cut"), ("rough_min", "--rough-min")):
        if opts.get(key) not in (None, ""):
            cmd += [flag, str(float(opts[key]))]
    if opts.get("seed") not in (None, ""):
        cmd += ["--seed", str(int(opts["seed"]))]
    if opts.get("decimation_target") not in (None, "", 0, "0"):
        cmd += ["--decimation-target", str(int(opts["decimation_target"]))]
    if prep_only:
        cmd.append("--prep-only")
    return cmd


def watch(jid, proc, log_handle):
    code = proc.wait()
    log_handle.close()
    with LOCK:
        path = JOBS / jid
        state = read_json(path / "state.json", {}) or {}
        if state.get("state") == "cancelled":
            pass
        elif code == 0 and (state.get("kind") == "preview" or (path / "result.glb").is_file()):
            state["state"] = "succeeded"
        else:
            state["state"] = "failed"
            state["exit_code"] = code
        state["finished"] = now()
        write_json(path / "state.json", state)
        if RUNNING["id"] == jid:
            RUNNING["id"], RUNNING["proc"] = None, None


def start_job(body):
    mesh_id, image_id = body.get("mesh"), body.get("image")
    kind = "preview" if body.get("preview") else "full"
    opts = body.get("options") or {}
    with LOCK:
        if RUNNING["proc"] is not None and RUNNING["proc"].poll() is None:
            raise RuntimeError("busy")
        mesh = upload_file(mesh_id)
        image = upload_file(image_id)
        jid = time.strftime("%Y%m%d%H%M%S") + secrets.token_hex(3)
        job = JOBS / jid
        (job / "input").mkdir(parents=True)
        mesh_copy = job / "input" / mesh.name
        image_copy = job / "input" / image.name
        shutil.copy2(mesh, mesh_copy)
        shutil.copy2(image, image_copy)
        state = {"state": "running", "kind": kind, "created": now(), "mesh_name": mesh.name,
                 "image_name": image.name, "options": opts}
        write_json(job / "state.json", state)
        env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
                   HF_HUB_DISABLE_IMPLICIT_TOKEN="1")
        env.setdefault("SUPRATEX_COMPLETION_DTYPE", "auto")
        env["SUPRATEX_LANG"] = "ko" if body.get("lang") == "ko" else "en"
        log = open(job / "log.txt", "wb")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0
        proc = subprocess.Popen(build_command(job, mesh_copy, image_copy, opts, kind == "preview"),
                                cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=flags, start_new_session=(os.name != "nt"))
        RUNNING["id"], RUNNING["proc"] = jid, proc
        threading.Thread(target=watch, args=(jid, proc, log), daemon=True).start()
        return job_summary(job)


def upload_file(uid):
    if not ID_RE.match(uid or ""):
        raise ValueError("upload")
    folder = UPLOADS / uid
    files = [f for f in folder.iterdir() if f.is_file()] if folder.is_dir() else []
    if not files:
        raise ValueError("upload")
    return files[0]


def cancel_job(jid):
    with LOCK:
        path = job_dir(jid)
        if RUNNING["id"] == jid:
            state = read_json(path / "state.json", {}) or {}
            state["state"] = "cancelled"
            write_json(path / "state.json", state)
            kill_tree(RUNNING["proc"])


def delete_job(jid):
    with LOCK:
        path = job_dir(jid)
        if RUNNING["id"] == jid:
            raise RuntimeError("busy")
        remove_tree(path)


def usage():
    out = {}
    for name, root in (("jobs", JOBS), ("uploads", UPLOADS), ("cutouts", CUTOUTS)):
        items = [p for p in root.iterdir()] if root.is_dir() else []
        out[name] = {"count": len(items), "bytes": sum(folder_size(p) if p.is_dir() else p.stat().st_size for p in items)}
    return out


def clear_all():
    with LOCK:
        if RUNNING["proc"] is not None and RUNNING["proc"].poll() is None:
            raise RuntimeError("busy")
        before = usage()
        failed = []
        for root in (JOBS, UPLOADS, CUTOUTS):
            if not root.is_dir():
                continue
            for child in list(root.iterdir()):
                try:
                    remove_tree(child) if child.is_dir() else child.unlink()
                except OSError:
                    pass
                if child.exists():
                    failed.append(child.name)
        return {"before": before, "failed": failed}


def gpu_info():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout.strip().splitlines()
        return out[0] if out else ""
    except (OSError, subprocess.SubprocessError):
        return ""


GPU = {"value": None}


# --------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "SUPRATexWorkbench/1.0"

    def log_message(self, fmt, *args):
        pass

    # --- 응답 도우미
    def send_json(self, value, code=200):
        data = json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, code, key):
        self.send_json({"error": key}, code)

    def send_file(self, path, download_name=None):
        path = Path(path)
        if not path.is_file():
            return self.send_error_json(404, "not_found")
        ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if path.suffix == ".js":
            ctype = "text/javascript; charset=utf-8"
        size = path.stat().st_size
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        if download_name:
            self.send_header("Content-Disposition", f'attachment; filename="{download_name}"')
        self.end_headers()
        with path.open("rb") as f:
            shutil.copyfileobj(f, self.wfile)

    def body_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > 1024 * 1024:
            raise ValueError("too_large")
        return json.loads(self.rfile.read(length) or b"{}")

    def same_origin(self):
        # 다른 웹사이트가 이 서버에 요청을 보내지 못하게 막는다.
        origin = self.headers.get("Origin")
        return origin in (None, f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")

    # --- GET
    def do_GET(self):
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.split("/") if p]
        try:
            if not parts:
                return self.send_file(WEB / "index.html")
            if parts[0] == "static":
                target = (WEB / "/".join(parts[1:])).resolve()
                if WEB.resolve() not in target.parents:
                    return self.send_error_json(404, "not_found")
                return self.send_file(target)
            if parts[:2] == ["api", "status"]:
                if GPU["value"] is None:
                    GPU["value"] = gpu_info()
                with LOCK:
                    busy = RUNNING["proc"] is not None and RUNNING["proc"].poll() is None
                    return self.send_json({"busy": busy, "running": RUNNING["id"] if busy else None,
                                           "gpu": GPU["value"], "usage": usage()})
            if parts[:2] == ["api", "jobs"] and len(parts) == 2:
                return self.send_json(list_jobs())
            if parts[:2] == ["api", "jobs"] and len(parts) == 3:
                path = job_dir(parts[2])
                summary = job_summary(path)
                summary["log"] = tail_log(path / "log.txt")
                return self.send_json(summary)
            if parts[:2] == ["api", "jobs"] and len(parts) == 4:
                path = job_dir(parts[2])
                files = {"result.glb": path / "result.glb",
                         "fit_preview.png": path / "result_case" / "fit_preview.png",
                         "condition.png": path / "result_case" / "condition_rgba.png",
                         "cutout.png": path / "result_case" / "cutout.png",
                         "albedo.png": path / "result_case" / "albedo.png",
                         "mra.png": path / "result_case" / "mra.png",
                         "log.txt": path / "log.txt"}
                if parts[3] not in files:
                    return self.send_error_json(404, "not_found")
                download = None
                if parts[3] == "result.glb" and "download" in parse_qs(url.query):
                    state = read_json(path / "state.json", {}) or {}
                    download = Path(state.get("mesh_name", "result")).stem + "_tex.glb"
                return self.send_file(files[parts[3]], download)
            return self.send_error_json(404, "not_found")
        except KeyError:
            return self.send_error_json(404, "not_found")
        except (BrokenPipeError, ConnectionResetError):
            pass

    # --- POST
    def do_POST(self):
        if not self.same_origin():
            return self.send_error_json(403, "forbidden")
        url = urlparse(self.path)
        parts = [unquote(p) for p in url.path.split("/") if p]
        try:
            if parts[:2] == ["api", "upload"]:
                name = safe_name(parse_qs(url.query).get("name", ["file"])[0])
                ext = Path(name).suffix.lower()
                kind = parse_qs(url.query).get("kind", [""])[0]
                if (kind == "mesh" and ext not in MESH_EXT) or (kind == "image" and ext not in IMAGE_EXT) or kind not in ("mesh", "image"):
                    return self.send_error_json(400, "bad_type")
                length = int(self.headers.get("Content-Length") or 0)
                if length <= 0 or length > MAX_UPLOAD:
                    return self.send_error_json(400, "bad_size")
                uid = secrets.token_hex(8)
                folder = UPLOADS / uid
                folder.mkdir(parents=True)
                remaining = length
                with (folder / name).open("wb") as f:
                    while remaining > 0:
                        chunk = self.rfile.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        f.write(chunk)
                        remaining -= len(chunk)
                if remaining:
                    remove_tree(folder)
                    return self.send_error_json(400, "incomplete")
                if kind == "image":
                    err = check_image(folder / name)
                    if err:
                        remove_tree(folder)
                        return self.send_error_json(400, err)
                return self.send_json({"id": uid, "name": name})
            if parts[:2] == ["api", "jobs"] and len(parts) == 2:
                try:
                    return self.send_json(start_job(self.body_json()))
                except RuntimeError:
                    return self.send_error_json(409, "busy")
                except ValueError:
                    return self.send_error_json(400, "missing_input")
            if parts[:2] == ["api", "jobs"] and len(parts) == 4 and parts[3] == "cancel":
                cancel_job(parts[2])
                return self.send_json({"ok": True})
            if parts[:2] == ["api", "jobs"] and len(parts) == 4 and parts[3] == "delete":
                try:
                    delete_job(parts[2])
                except RuntimeError:
                    return self.send_error_json(409, "busy")
                return self.send_json({"ok": True})
            if parts[:2] == ["api", "clear"]:
                try:
                    return self.send_json(clear_all())
                except RuntimeError:
                    return self.send_error_json(409, "busy")
            if parts[:2] == ["api", "shutdown"]:
                self.send_json({"ok": True})
                threading.Thread(target=shutdown, daemon=True).start()
                return
            return self.send_error_json(404, "not_found")
        except KeyError:
            return self.send_error_json(404, "not_found")
        except (BrokenPipeError, ConnectionResetError):
            pass


def check_image(path):
    """이미지로 열리는지만 본다. 투명 배경이 없으면 작업할 때 자동으로 배경을 지운다."""
    try:
        from PIL import Image
        with Image.open(path) as img:
            img.load()
    except Exception:
        return "bad_image"
    return None


SERVER = {"httpd": None}


def shutdown():
    time.sleep(0.3)
    with LOCK:
        kill_tree(RUNNING["proc"])
    if SERVER["httpd"] is not None:
        SERVER["httpd"].shutdown()


def recover():
    """서버가 꺼질 때 돌던 작업은 '중단됨'으로 표시한다."""
    if not JOBS.is_dir():
        return
    for path in JOBS.iterdir():
        state = read_json(path / "state.json")
        if state and state.get("state") == "running":
            state["state"] = "interrupted"
            write_json(path / "state.json", state)


def main():
    UPLOADS.mkdir(parents=True, exist_ok=True)
    JOBS.mkdir(parents=True, exist_ok=True)
    recover()
    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Port {PORT} is in use. If the workbench is already running, open the address below.")
        print(f"포트 {PORT} 을 쓸 수 없습니다. 워크벤치가 이미 켜져 있으면 브라우저에서 아래 주소를 여세요.")
        print(f"http://127.0.0.1:{PORT}")
        if "--open" in sys.argv:
            webbrowser.open(f"http://127.0.0.1:{PORT}")
        return 1
    httpd.daemon_threads = True
    SERVER["httpd"] = httpd
    url = f"http://127.0.0.1:{PORT}"
    print("SUPRA-Tex Workbench")
    print(f"브라우저에서 여세요 / Open in your browser : {url}")
    print("끌 때는 화면의 '워크벤치 끄기' 버튼을 누르세요. / To quit, click 'Close workbench' in the page.")
    if "--open" in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        with LOCK:
            kill_tree(RUNNING["proc"])
        httpd.server_close()
    print("워크벤치를 껐습니다. 이 창을 닫아도 됩니다. / The workbench has stopped. You can close this window.")
    return 0
