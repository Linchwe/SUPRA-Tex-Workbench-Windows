# -*- coding: utf-8 -*-
"""
SUPRA-Tex 메시 + 이미지 -> PBR 텍스처 (한 번에 실행)

용도
  이미 있는 메시(GLB/OBJ/PLY)에 참조 이미지 한 장을 기준으로 PBR 텍스처(색, 거칠기, 금속성)를 새로 입힌다.
  이미지에 보이는 면은 이미지를 따르고, 안 보이는 옆면/뒷면은 SUPRA-Tex 가 채운다.

하는 일
  0. 배경 지우기 (GPU) : 이미지에 투명 배경이 없으면 BiRefNet 으로 배경을 지운다.
                          처음 한 번 모델(약 900MB)을 models 폴더에 받는다. 끝나면 VRAM 을 비운다.
  1. 메시 정리 (CPU)   : 가운데로 옮기고 크기를 SUPRA-Tex 기준 상자(-0.5~0.5)에 맞춘다.
  2. 카메라 맞춤 (CPU) : 메시 실루엣과 이미지 알파(투명 배경)가 가장 잘 겹치도록
                          화각, 작은 회전(좌우 ±10도, 위아래 ±5도), 이미지 위치/크기를 찾는다.
  3. 재질 지도 (GPU)   : SuperMat 으로 albedo.png, mra.png 를 만든다. (1024, 정밀도 자동)
                          비금속에 남은 낮은 금속성은 0 으로 보정한다. (--metal-cut)
                          비금속의 너무 낮은 거칠기는 올린다. (--rough-min)
  4. 텍스처 굽기 (GPU) : texturing.py 를 실행한다.
  5. 위치 복원         : 결과 GLB 를 원래 메시의 위치/크기/방향으로 되돌린다.

조건
  이미지와 메시는 같은 물체여야 하고, 메시는 정면이 +Z(블렌더 기준 -Y, 정면 뷰에서 보이는 쪽)를 봐야 한다.
  이미지는 PNG / WEBP / JPG. 배경이 있으면 자동으로 지운다. 이미 투명 배경이면 그대로 쓴다.
  상반신처럼 이미지 가장자리에서 잘린 그림도 된다. 잘린 바깥은 맞춤 비교에서 뺀다.
  결과 메시는 SUPRA-Tex 가 새로 만든 메시다. (원래 메시의 폴리곤/UV 는 그대로 남지 않는다)

사용법 (SUPRA-Tex 폴더에서)
  .venv314\\Scripts\\python.exe mesh_texture.py 메시.glb 이미지.png
  .venv314\\Scripts\\python.exe mesh_texture.py 메시.glb 이미지.png --output outputs\\결과.glb
  옵션
    --output 경로        결과 GLB (기본: outputs\\<메시이름>_tex.glb, 있으면 _2, _3 ... 으로 새로 만든다)
    --yaw 0|90|180|270   메시가 정면을 안 보고 있을 때 Y축으로 돌린다
    --zup                Z 가 위쪽인 파일일 때
    --fov 도             화각을 직접 지정 (기본: 자동으로 찾음)
    --no-rotate-search   작은 회전 자동 보정을 끈다
    --keep-normalized    위치 복원을 하지 않는다 (SUPRA-Tex 기준 좌표 그대로)
    --prep-only          1~2 단계만 하고 멈춘다 (fit_preview.png 확인용)
    --seed 숫자          SUPRA-Tex 시드
    --supermat-cache 폴더  SuperMat/SD2.1 모델을 받을 폴더 (기본: models)
    --supermat-python 경로  SuperMat 단계만 다른 파이썬으로 실행 (기본: 지금 파이썬)
    --metal-cut 값       금속성 보정 (기본 0.45). 이 값보다 낮은 금속성은 0(비금속)으로 내린다.
                         SuperMat 은 피부/천/식물 같은 비금속도 0.2~0.4 로 내는 경우가 있어서다.
                         값+0.1 보다 높은 곳(진짜 금속)은 그대로 둔다. 0 이면 보정하지 않는다.
    --no-bg-remove       배경 자동 지우기를 끈다 (투명 배경이 없는 이미지는 멈춘다)
    --rough-min 값       거칠기 보정 (기본 0.6). 비금속의 거칠기가 이 값보다 낮으면 이 값으로 올린다.
                         SuperMat 은 피부도 0.4 정도로 매끈하게 내서 번들거리기 때문이다.
                         금속은 그대로 둔다. 유리/에나멜처럼 원래 매끈한 물체는 0 으로 끈다.
  그 외 처음 보는 옵션은 texturing.py 로 그대로 넘긴다.
"""
import argparse
import json
import math
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
LANG = os.environ.get("SUPRATEX_LANG", "ko")   # 화면 메시지 언어. 워크벤치가 en 또는 ko 로 넘긴다.


def L(ko, en):
    """메시지를 SUPRATEX_LANG 에 맞는 언어로 고른다."""
    return en if LANG == "en" else ko
CANVAS = 1024          # condition_rgba / albedo / mra 해상도 (SUPRA-Tex 요구)
EXTENT = 0.95          # 메시 가장 긴 변 (기준 상자 1.0 안에서 여유)
FOV_CANDIDATES = (10.0, 20.0, 30.0, 40.0, 50.0)
FOV_TIE = 0.005        # 겹침 차이가 이 안이면 좁은 화각을 고른다.
                       # 사람 흉상처럼 화각을 바꿔도 윤곽이 거의 같은 물체는 윤곽만으로 화각을 정할 수 없고,
                       # 이미지->3D 모델 결과는 좁은 화각에서 눈코입이 맞았다. (넓은 화각이 맞는 물체는 겹침 차이로 구별됨)
ROT_PENALTY = 0.0015   # 회전 1도당 IoU 감점 (윤곽이 확실히 더 맞을 때만 돌리도록)
FILL = 0.92            # 물체가 화면에서 차지하는 최대 폭 (가운데 기준, 이미지 픽셀을 최대한 쓰도록)


# --------------------------------------------------------------------------------------
# 1. 메시
# --------------------------------------------------------------------------------------
def load_mesh(path):
    import trimesh
    loaded = trimesh.load(str(path), force="scene", process=False)
    if hasattr(loaded, "to_geometry"):
        mesh = loaded.to_geometry()
    else:
        mesh = loaded.dump(concatenate=True)
    if not hasattr(mesh, "faces") or len(mesh.faces) == 0:
        raise SystemExit(L(f"메시에서 면을 찾지 못했습니다: {path}", f"No faces found in the mesh: {path}"))
    return trimesh.Trimesh(vertices=np.asarray(mesh.vertices, np.float64),
                           faces=np.asarray(mesh.faces, np.int64), process=False)


def rot_x(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], np.float64)


def rot_y(deg):
    a = math.radians(deg); c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float64)


def normalize_frame(verts, R):
    """회전 R 을 적용한 뒤 가운데로 옮기고 가장 긴 변을 EXTENT 로 맞추는 값 (c, s) 를 돌려준다.
    정규화 좌표 n = s * (R v - c)"""
    rv = verts @ R.T
    lo, hi = rv.min(0), rv.max(0)
    c = (lo + hi) / 2
    s = EXTENT / float((hi - lo).max())
    return c, s


# --------------------------------------------------------------------------------------
# 2. 실루엣과 카메라
#   SUPRA-Tex 카메라: (0,0,D) 에서 원점을 보고 위쪽은 +Y, 정사각형 화각.
#   이미지 좌표 u = 0.5 + f*x/(D-z),  v = 0.5 - f*y/(D-z),  f = 0.5/tan(fov/2)
#   (예제 pitcher_plant 로 확인: 이 식으로 투영하면 알파와 IoU 0.93)
# --------------------------------------------------------------------------------------
def render_mask(points, fov_deg, distance, n):
    from scipy import ndimage
    f = 0.5 / math.tan(math.radians(fov_deg) / 2)
    z = distance - points[:, 2]
    u = 0.5 + f * points[:, 0] / z
    v = 0.5 - f * points[:, 1] / z
    ui = np.floor(u * n).astype(np.int64)
    vi = np.floor(v * n).astype(np.int64)
    ok = (ui >= 0) & (ui < n) & (vi >= 0) & (vi < n)
    mask = np.zeros((n, n), bool)
    mask[vi[ok], ui[ok]] = True
    return ndimage.binary_closing(mask, structure=np.ones((3, 3), bool), border_value=0) | mask


def camera_distance(points_n, fov_deg, fill=FILL):
    """물체가 화면 가운데에서 가장 멀리 나간 점이 0.5 +- fill/2 에 오도록 하는 거리 (이분법)"""
    f = 0.5 / math.tan(math.radians(fov_deg) / 2)
    x, y, z = points_n[:, 0], points_n[:, 1], points_n[:, 2]

    def reach(d):
        return float((f * np.maximum(np.abs(x), np.abs(y)) / (d - z)).max())

    lo = float(z.max()) + 0.05
    hi = float(np.linalg.norm(points_n, axis=1).max()) / math.sin(math.radians(fov_deg) / 2) * 1.5 + 0.1
    if reach(lo) <= fill / 2:
        return lo
    for _ in range(50):
        mid = (lo + hi) / 2
        if reach(mid) > fill / 2:
            lo = mid
        else:
            hi = mid
    return hi


def bbox(mask):
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return xs.min(), xs.max() + 1, ys.min(), ys.max() + 1


class ImageFit:
    """출력 캔버스 좌표 (0~1) -> 원본 이미지 픽셀:  src = (uv - o) * S + c
    물체가 원본 이미지 가장자리에서 잘려 있으면(예: 가슴 아래가 잘린 상반신 그림),
    잘린 쪽 바깥은 '알 수 없음'으로 보고 겹침 계산에서 뺀다."""

    def __init__(self, alpha_mask):
        self.alpha = alpha_mask
        self.h, self.w = alpha_mask.shape
        x0, x1, y0, y1 = bbox(alpha_mask)
        self.box = (x0, x1, y0, y1)
        self.src_center = np.array([(x0 + x1) / 2, (y0 + y1) / 2])
        self.src_size = np.array([x1 - x0, y1 - y0], np.float64)
        need_x, need_y = max(8, 0.02 * self.w), max(8, 0.02 * self.h)
        self.cut = {"top": alpha_mask[:2].sum() > need_x, "bottom": alpha_mask[-2:].sum() > need_x,
                    "left": alpha_mask[:, :2].sum() > need_y, "right": alpha_mask[:, -2:].sum() > need_y}

    def cut_names(self):
        names = {"top": "위", "bottom": "아래", "left": "왼쪽", "right": "오른쪽"}
        return [names[k] for k, v in self.cut.items() if v]

    def initial(self, sil):
        n = sil.shape[0]
        x0, x1, y0, y1 = bbox(sil)
        sx0, sx1, sy0, sy1 = self.box
        sw, sh = sx1 - sx0, sy1 - sy0
        cut_v = self.cut["top"] or self.cut["bottom"]
        cut_h = self.cut["left"] or self.cut["right"]
        if cut_v and not cut_h:
            S = sw / ((x1 - x0) / n)
        elif cut_h and not cut_v:
            S = sh / ((y1 - y0) / n)
        else:
            S = math.sqrt((sw / ((x1 - x0) / n)) * (sh / ((y1 - y0) / n)))
        cx, cy = self.src_center
        ox = (x0 + x1) / 2 / n
        oy = (y0 + y1) / 2 / n
        # 잘린 축은 안 잘린 쪽 끝을 맞춘다
        if self.cut["bottom"] and not self.cut["top"]:
            oy = y0 / n - (sy0 - cy) / S
        elif self.cut["top"] and not self.cut["bottom"]:
            oy = y1 / n - (sy1 - cy) / S
        if self.cut["right"] and not self.cut["left"]:
            ox = x0 / n - (sx0 - cx) / S
        elif self.cut["left"] and not self.cut["right"]:
            ox = x1 / n - (sx1 - cx) / S
        return np.array([math.log(S), ox, oy])

    def warp(self, p, n):
        S, o = math.exp(p[0]), p[1:]
        g = (np.arange(n) + 0.5) / n
        fx = (g - o[0]) * S + self.src_center[0]
        fy = (g - o[1]) * S + self.src_center[1]
        sx, sy = np.floor(fx).astype(np.int64), np.floor(fy).astype(np.int64)
        okx = (sx >= 0) & (sx < self.w)
        oky = (sy >= 0) & (sy < self.h)
        out = np.zeros((n, n), bool)
        out[np.ix_(oky, okx)] = self.alpha[np.ix_(sy[oky], sx[okx])]
        vx = ~((self.cut["left"] & (sx < 0)) | (self.cut["right"] & (sx >= self.w)))
        vy = ~((self.cut["top"] & (sy < 0)) | (self.cut["bottom"] & (sy >= self.h)))
        return out, vy[:, None] & vx[None, :]

    def iou(self, p, sil):
        a, valid = self.warp(p, sil.shape[0])
        union = ((a | sil) & valid).sum()
        return float((a & sil & valid).sum()) / max(float(union), 1.0)

    def refine(self, p, sil, step=(0.04, 0.02, 0.02), stop=0.002):
        p = np.array(p, np.float64)
        best = self.iou(p, sil)
        step = np.array(step, np.float64)
        while step.max() > stop:
            moved = False
            for i in range(3):
                for sign in (1, -1):
                    q = p.copy(); q[i] += sign * step[i]
                    val = self.iou(q, sil)
                    if val > best + 1e-6:
                        p, best, moved = q, val, True
                        break
            if not moved:
                step /= 2
        return p, best


def fit_camera(mesh, alpha_mask, base_R, fov_fixed, rotate_search):
    import trimesh
    verts = np.asarray(mesh.vertices)
    rng = np.random.default_rng(0)
    try:
        surf = trimesh.sample.sample_surface(mesh, 300000, seed=0)[0]
    except TypeError:
        surf = trimesh.sample.sample_surface(mesh, 300000)[0]
    vsub = verts if len(verts) <= 200000 else verts[rng.choice(len(verts), 200000, replace=False)]
    pts = np.concatenate([np.asarray(surf), vsub], 0)
    fit = ImageFit(alpha_mask)
    fovs = (fov_fixed,) if fov_fixed else FOV_CANDIDATES

    def evaluate(yaw, pitch, fov, n, p0=None):
        R = rot_x(pitch) @ rot_y(yaw) @ base_R
        c, s = normalize_frame(verts, R)
        pn = s * (pts @ R.T - c)
        D = camera_distance(s * (verts @ R.T - c), fov)
        sil = render_mask(pn, fov, D, n)
        p = fit.initial(sil) if p0 is None else p0
        p, val = fit.refine(p, sil)
        return val - ROT_PENALTY * (abs(yaw) + abs(pitch)), val, p

    def pick(results):
        """겹침 최고값에서 FOV_TIE 안에 드는 것 중 화각이 가장 좁은 것 (같으면 점수 높은 것)"""
        top = max(r[0] for r in results)
        near = [r for r in results if r[0] >= top - FOV_TIE]
        return min(near, key=lambda r: (r[4], -r[0]))

    # 거친 탐색
    angles = [(y, x) for y in (-10, -5, 0, 5, 10) for x in (-5, 0, 5)] if rotate_search else [(0, 0)]
    results = []
    for fov in fovs:
        best_fov = None
        for yaw, pitch in angles:
            score, val, p = evaluate(yaw, pitch, fov, 160)
            if best_fov is None or score > best_fov[0]:
                best_fov = (score, val, yaw, pitch, fov, p)
        results.append(best_fov)
    best = pick(results)
    # 주변 세밀 탐색
    _, _, yaw, pitch, fov, p = best
    if rotate_search or not fov_fixed:
        cand = []
        for dy in ((-2.5, 0, 2.5) if rotate_search else (0,)):
            for dx in ((-2.5, 0, 2.5) if rotate_search else (0,)):
                for df in ((-5, 0, 5) if not fov_fixed else (0,)):
                    y2 = float(np.clip(yaw + dy, -12.5, 12.5)); x2 = float(np.clip(pitch + dx, -7.5, 7.5))
                    f2 = float(np.clip(fov + df, 8, 60))
                    cand.append((y2, x2, f2))
        fine = {}
        for y2, x2, f2 in sorted(set(cand)):
            score, val, p2 = evaluate(y2, x2, f2, 320)
            if f2 not in fine or score > fine[f2][0]:
                fine[f2] = (score, val, y2, x2, f2, p2)
        _, _, yaw, pitch, fov, p = pick(list(fine.values()))
    # 최종
    _, val, p = evaluate(yaw, pitch, fov, 512)
    R = rot_x(pitch) @ rot_y(yaw) @ base_R
    c, s = normalize_frame(verts, R)
    D = camera_distance(s * (verts @ R.T - c), fov)
    return {"R": R, "c": c, "s": s, "fov": fov, "distance": D, "yaw": yaw, "pitch": pitch,
            "iou": val, "image": p, "fit": fit, "points": pts}


# --------------------------------------------------------------------------------------
# 케이스 폴더 만들기
# --------------------------------------------------------------------------------------
def has_cutout_alpha(path):
    """이미지에 쓸 만한 투명 배경(알파)이 있으면 True."""
    with Image.open(path) as img:
        img.load()
        if img.mode not in ("RGBA", "LA", "PA") and not (img.mode == "P" and "transparency" in img.info):
            return False
        alpha = np.asarray(img.convert("RGBA"))[:, :, 3] > 127
    return 0.0 < alpha.mean() <= 0.98 and alpha.sum() >= 100


def load_rgba(path, removed=False):
    img = Image.open(path)
    img.load()
    if img.mode not in ("RGBA", "LA", "PA") and not (img.mode == "P" and "transparency" in img.info):
        raise SystemExit(L("이미지에 투명 배경(알파)이 없습니다. 배경 자동 지우기를 켜거나 배경을 지운 PNG 를 넣어 주세요.", "The image has no transparent background (alpha). Turn on automatic background removal or use a PNG with the background removed."))
    rgba = img.convert("RGBA")
    alpha = np.asarray(rgba)[:, :, 3] > 127
    if alpha.mean() > 0.98 or alpha.sum() < 100:
        if removed:
            raise SystemExit(L("배경을 지웠지만 물체를 찾지 못했습니다. 물체가 또렷하게 보이는 이미지를 쓰거나, 배경을 직접 지운 PNG 를 넣어 주세요.", "The background was removed but no object was found. Use an image where the object is clearly visible, or a PNG with the background removed by hand."))
        raise SystemExit(L("이미지 알파가 거의 전부 불투명하거나 비어 있습니다. 배경을 지운 PNG 인지 확인하세요.", "The image alpha is almost fully opaque or empty. Check that the background was removed."))
    return rgba, alpha


# --------------------------------------------------------------------------------------
# 0. 배경 지우기 (BiRefNet, MIT 라이선스. 별도 프로세스: 끝나면 VRAM 이 완전히 비워진다)
# --------------------------------------------------------------------------------------
BIREFNET_REPO = "ZhengPeng7/BiRefNet"
BIREFNET_REV = "e2bf8e4460fc8fa32bba5ea4d94b3233d367b0e4"   # 받는 코드를 이 버전으로 고정한다
BIREFNET_SIZE = 1024
CUTOUT_CACHE = ROOT / "workbench_data" / "cutouts"          # 같은 이미지는 다시 지우지 않는다


def run_cutout(src, dst, cache_dir):
    """src 이미지의 배경을 지워 dst(RGBA PNG)로 저장한다. --_cutout 으로 따로 실행된다."""
    import torch
    from PIL import ImageOps
    from torchvision import transforms
    from transformers import AutoModelForImageSegmentation

    cuda = torch.cuda.is_available()
    device = "cuda" if cuda else "cpu"
    where = torch.cuda.get_device_name(0) if cuda else "CPU"
    print(L("[배경]", "[background]") + f" BiRefNet / {where}", flush=True)
    torch.set_float32_matmul_precision("high")
    model = AutoModelForImageSegmentation.from_pretrained(
        BIREFNET_REPO, revision=BIREFNET_REV, trust_remote_code=True,
        cache_dir=str(cache_dir), token=False)
    model.to(device).eval()
    if cuda:
        model.half()

    with Image.open(src) as img:
        img.load()
        img = ImageOps.exif_transpose(img).convert("RGB")
    prep = transforms.Compose([
        transforms.Resize((BIREFNET_SIZE, BIREFNET_SIZE)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    x = prep(img).unsqueeze(0).to(device)
    if cuda:
        x = x.half()
    with torch.no_grad():
        pred = model(x)[-1].sigmoid().float().cpu()[0, 0].numpy()
    mask = Image.fromarray((np.clip(pred, 0, 1) * 255).astype(np.uint8)).resize(img.size, Image.Resampling.BICUBIC)
    out = img.copy()
    out.putalpha(mask)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + "_tmp.png")
    out.save(tmp)
    os.replace(tmp, dst)
    return 0


def prepare_image(image_path, case_dir, cache_dir, python):
    """투명 배경이 없으면 배경을 지운 이미지 경로를, 있으면 원래 경로를 돌려준다."""
    if has_cutout_alpha(image_path):
        return image_path, False
    import hashlib
    key = hashlib.sha1(Path(image_path).read_bytes() + BIREFNET_REV.encode()).hexdigest()[:16]
    cached = CUTOUT_CACHE / f"{key}.png"
    if cached.is_file():
        print("        " + L("투명 배경이 없어서 배경을 지웠습니다. (전에 지운 결과를 다시 씀)", "No transparent background, so the background was removed. (reused an earlier result)"), flush=True)
    else:
        print("        " + L("투명 배경이 없어서 배경을 지우는 중 (BiRefNet). 처음 한 번은 모델(약 900MB)을 받습니다.",
                             "No transparent background, removing it (BiRefNet). The first time downloads the model (about 900MB)."), flush=True)
        env = dict(os.environ)
        env.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
        cmd = [python, str(Path(__file__).resolve()), "--_cutout", str(image_path), str(cached),
               "--supermat-cache", str(cache_dir)]
        if subprocess.run(cmd, env=env).returncode != 0 or not cached.is_file():
            raise SystemExit(L("배경 지우기에서 멈췄습니다. 위 오류를 확인하세요. 배경을 직접 지운 투명 PNG 를 넣어도 됩니다.",
                               "Stopped at background removal. See the error above. You can also use a transparent PNG with the background removed by hand."))
    case_dir.mkdir(parents=True, exist_ok=True)
    cutout = case_dir / "cutout.png"
    cutout.write_bytes(cached.read_bytes())
    return cutout, True


def write_case(case_dir, mesh, rgba, result):
    case_dir.mkdir(parents=True, exist_ok=True)
    R, c, s = result["R"], result["c"], result["s"]
    verts_n = (s * (np.asarray(mesh.vertices) @ R.T - c)).astype(np.float32)
    if np.abs(verts_n).max() > 0.5:
        raise SystemExit(L("정규화한 메시가 기준 상자를 벗어났습니다. (내부 오류)", "The normalized mesh is outside the unit box. (internal error)"))
    np.savez_compressed(case_dir / "geometry.npz", verts=verts_n, faces=np.asarray(mesh.faces, np.int64))
    (case_dir / "camera.json").write_text(json.dumps({
        "camera_angle_x": math.radians(result["fov"]), "distance": result["distance"], "mesh_scale": 1.0,
    }, indent=2), encoding="utf-8")

    fit, p = result["fit"], result["image"]
    S = math.exp(p[0])
    a = S / CANVAS
    cx = fit.src_center[0] - p[1] * S
    cy = fit.src_center[1] - p[2] * S
    cond = rgba.transform((CANVAS, CANVAS), Image.Transform.AFFINE, (a, 0, cx, 0, a, cy),
                          resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
    cond.save(case_dir / "condition_rgba.png")

    # 확인용 그림: 이미지 위에 메시 실루엣 테두리(빨강)
    from scipy import ndimage
    pn = s * (result["points"] @ R.T - c)
    sil = render_mask(pn, result["fov"], result["distance"], 512)
    sil = np.asarray(Image.fromarray(sil).resize((CANVAS, CANVAS), Image.NEAREST))
    edge = sil & ~ndimage.binary_erosion(sil, iterations=2)
    base = Image.new("RGBA", (CANVAS, CANVAS), (128, 128, 128, 255))
    base.alpha_composite(cond)
    arr = np.asarray(base.convert("RGB")).copy()
    arr[edge] = (255, 0, 0)
    Image.fromarray(arr).save(case_dir / "fit_preview.png")

    transform = {
        "note": "normalized = s * (R @ original - c); SUPRA-Tex GLB = diag(-1,1,-1) @ normalized",
        "R": R.tolist(), "c": c.tolist(), "s": s,
        "yaw_fix": result["yaw"], "pitch_fix": result["pitch"], "fov_deg": result["fov"],
        "silhouette_iou": result["iou"],
    }
    (case_dir / "transform.json").write_text(json.dumps(transform, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------------------
# 3. SuperMat (별도 프로세스: 끝나면 VRAM 이 완전히 비워진다)
# --------------------------------------------------------------------------------------
SUPERMAT_BASE = "sd2-community/stable-diffusion-2-1"
SUPERMAT_REPO = "oyiya/SuperMat"


def metal_correct(metal, cut):
    """cut 아래는 0, cut+0.1 위는 그대로, 사이는 부드럽게 (smoothstep). metal 은 0~1 배열."""
    if cut <= 0:
        return metal
    x = np.clip((metal - cut) / 0.1, 0.0, 1.0)
    return metal * (x * x * (3.0 - 2.0 * x))


def rough_correct(rough, metal, rough_min):
    """비금속(metal 0)은 rough_min 아래를 rough_min 으로 올리고, 금속(metal 1)은 그대로. 사이는 비율대로."""
    if rough_min <= 0:
        return rough
    lift = np.maximum(rough_min - rough, 0.0)
    return rough + lift * (1.0 - np.clip(metal, 0.0, 1.0))


def run_supermat(case_dir, cache_dir, dtype_name, seed, metal_cut=0.45, rough_min=0.6):
    sys.path.insert(0, str(ROOT / "third_party" / "SuperMat"))
    import torch
    from diffusers import DDIMScheduler
    from huggingface_hub import hf_hub_download
    from src.adapters import SuperMatAdapterWrapper
    from src.pipelines.pipeline_supermat_stable_diffusion import SuperMatStableDiffusionPipeline

    if not torch.cuda.is_available():
        raise SystemExit(L("CUDA 를 찾지 못했습니다.", "CUDA was not found."))
    if dtype_name == "auto":
        dtype_name = "bf16" if torch.cuda.get_device_capability()[0] >= 8 else "fp16"
    dtype = {"fp16": torch.float16, "bf16": torch.bfloat16, "fp32": torch.float32}[dtype_name]
    print(L("[재질]", "[material]") + f" SuperMat {dtype_name} / {torch.cuda.get_device_name(0)}", flush=True)

    pipe = SuperMatStableDiffusionPipeline.from_pretrained(
        SUPERMAT_BASE, safety_checker=None, requires_safety_checker=False,
        cache_dir=str(cache_dir), token=False)
    pipe = SuperMatAdapterWrapper.convert(pipe, use_camera_embeddings=False, camera_embeddings_dim=16)
    ckpt = hf_hub_download(SUPERMAT_REPO, "supermat.pth", cache_dir=str(cache_dir), token=False)
    state = torch.load(ckpt, map_location="cpu")
    result = pipe.unet.load_state_dict(state, strict=False)
    if result.missing_keys or result.unexpected_keys:
        print(L(f"[재질][주의] 가중치 불일치: 없음 {len(result.missing_keys)} / 남음 {len(result.unexpected_keys)}", f"[material][warning] weight mismatch: missing {len(result.missing_keys)} / unexpected {len(result.unexpected_keys)}"))
    del state
    pipe.unet.eval()
    pipe.scheduler = DDIMScheduler.from_config(pipe.scheduler.config, timestep_spacing="trailing")
    pipe.set_progress_bar_config(disable=True)
    pipe = pipe.to(device="cuda", dtype=dtype)

    cond = Image.open(case_dir / "condition_rgba.png").convert("RGBA")
    a = np.asarray(cond).astype(np.float32) / 255.0
    rgb = a[:, :, :3] * a[:, :, 3:4] + 0.5 * (1.0 - a[:, :, 3:4])
    x = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).to(device="cuda", dtype=dtype)
    gen = torch.Generator(device="cuda").manual_seed(seed)
    with torch.no_grad():
        images = pipe(prompt="", num_inference_steps=1, source_image=x, output_type="pt",
                      generator=gen, use_fp32_input=(dtype == torch.float32))
    if any(torch.isnan(im.float()).any().item() for im in images):
        raise SystemExit(L("SuperMat 결과에 NaN(깨진 값)이 있습니다. --supermat-dtype fp32 로 다시 시도하세요.", "SuperMat output contains NaN. Try again with --supermat-dtype fp32."))

    def to_np(t):
        t = t.detach().float().cpu().clamp(0, 1)
        return (t[0] if t.ndim == 4 else t).permute(1, 2, 0).numpy()

    def u8(arr):
        return (np.clip(arr, 0, 1) * 255 + 0.5).astype(np.uint8)

    albedo, orm = to_np(images[0]), to_np(images[1])
    Image.fromarray(u8(albedo)).resize((CANVAS, CANVAS), Image.BICUBIC).save(case_dir / "albedo.png")
    alpha = cond.getchannel("A")
    rough = Image.fromarray(u8(orm[:, :, 1])).resize((CANVAS, CANVAS), Image.BICUBIC)
    raw = Image.fromarray(u8(orm[:, :, 2])).resize((CANVAS, CANVAS), Image.BICUBIC)
    Image.merge("RGB", (raw, rough, alpha)).save(case_dir / "mra_raw.png")      # 보정 전 (비교용)
    raw_f = np.asarray(raw).astype(np.float32) / 255.0
    fixed = metal_correct(raw_f, metal_cut)
    if metal_cut > 0:
        fixed = fixed * (np.asarray(alpha).astype(np.float32) / 255.0)   # 물체 바깥 배경 값이 테두리로 번지지 않게
    rough_f = np.asarray(rough).astype(np.float32) / 255.0
    rough_fixed = rough_correct(rough_f, fixed, rough_min)
    Image.merge("RGB", (Image.fromarray(u8(fixed)), Image.fromarray(u8(rough_fixed)), alpha)).save(case_dir / "mra.png")
    fg = np.asarray(alpha) > 127
    if metal_cut > 0 and fg.any():
        print(L(f"[재질] 금속성 보정 {metal_cut:.2f}: 평균 {raw_f[fg].mean():.2f} -> {fixed[fg].mean():.2f}, "
                f"금속으로 남은 영역 {(fixed[fg] > 0.5).mean() * 100:.1f}%",
                f"[material] metallic correction {metal_cut:.2f}: mean {raw_f[fg].mean():.2f} -> {fixed[fg].mean():.2f}, "
                f"metal area {(fixed[fg] > 0.5).mean() * 100:.1f}%"), flush=True)
    if rough_min > 0 and fg.any():
        print(L(f"[재질] 거칠기 보정 {rough_min:.2f}: 평균 {rough_f[fg].mean():.2f} -> {rough_fixed[fg].mean():.2f}", f"[material] roughness correction {rough_min:.2f}: mean {rough_f[fg].mean():.2f} -> {rough_fixed[fg].mean():.2f}"), flush=True)
    print(L("[재질] 완료, VRAM 최대", "[material] done, peak VRAM") + f" {torch.cuda.max_memory_allocated() / 1024 ** 3:.2f}GB", flush=True)


# --------------------------------------------------------------------------------------
# 5. GLB 위치 복원 (텍스처/재질은 건드리지 않고 맨 위 노드에 변환만 붙인다)
# --------------------------------------------------------------------------------------
def restore_glb(src, dst, transform):
    R = np.asarray(transform["R"]); c = np.asarray(transform["c"]); s = float(transform["s"])
    flip = np.diag([-1.0, 1.0, -1.0])            # SUPRA-Tex 내보내기가 Y축 180도 돌려서 저장함
    L = R.T @ flip.T / s
    t = R.T @ c
    M = np.eye(4); M[:3, :3] = L; M[:3, 3] = t

    data = Path(src).read_bytes()
    magic, version, _ = struct.unpack_from("<4sII", data, 0)
    if magic != b"glTF":
        raise SystemExit(L("GLB 형식이 아닙니다.", "Not a GLB file."))
    jlen, jtype = struct.unpack_from("<II", data, 12)
    gltf = json.loads(data[20:20 + jlen].decode("utf-8"))
    rest = data[20 + jlen:]
    scene = gltf.get("scenes", [{}])[gltf.get("scene", 0)]
    roots = scene.get("nodes", [])
    nodes = gltf.setdefault("nodes", [])
    nodes.append({"name": "restore_original", "matrix": M.T.reshape(-1).tolist(), "children": roots})
    scene["nodes"] = [len(nodes) - 1]
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    js += b" " * ((4 - len(js) % 4) % 4)
    body = struct.pack("<II", len(js), 0x4E4F534A) + js + rest
    Path(dst).write_bytes(struct.pack("<4sII", b"glTF", version, 12 + len(body)) + body)


# --------------------------------------------------------------------------------------
def unique_path(path):
    if not path.exists():
        return path
    i = 2
    while True:
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not cand.exists():
            return cand
        i += 1


def stamp():
    return time.strftime("%H:%M:%S")


def main():
    ap = argparse.ArgumentParser(description="메시 + 이미지 -> SUPRA-Tex PBR 텍스처")
    ap.add_argument("mesh", nargs="?")
    ap.add_argument("image", nargs="?")
    ap.add_argument("--output")
    ap.add_argument("--yaw", type=int, choices=(0, 90, 180, 270), default=0)
    ap.add_argument("--zup", action="store_true")
    ap.add_argument("--fov", type=float, default=None)
    ap.add_argument("--no-rotate-search", action="store_true")
    ap.add_argument("--keep-normalized", action="store_true")
    ap.add_argument("--prep-only", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--supermat-cache", default=str(ROOT / "models"))
    ap.add_argument("--supermat-dtype", choices=("auto", "fp16", "bf16", "fp32"), default="auto")
    ap.add_argument("--supermat-python", default=sys.executable)
    ap.add_argument("--metal-cut", type=float, default=0.45)
    ap.add_argument("--rough-min", type=float, default=0.6)
    ap.add_argument("--no-bg-remove", action="store_true")
    ap.add_argument("--_supermat", help=argparse.SUPPRESS)
    ap.add_argument("--_cutout", nargs=2, help=argparse.SUPPRESS)
    args, extra = ap.parse_known_args()

    if args._cutout:
        return run_cutout(Path(args._cutout[0]), Path(args._cutout[1]), Path(args.supermat_cache))
    if args._supermat:
        run_supermat(Path(args._supermat), Path(args.supermat_cache), args.supermat_dtype,
                     args.seed if args.seed is not None else 0, args.metal_cut, args.rough_min)
        return 0
    if not args.mesh or not args.image:
        ap.error(L("메시와 이미지를 넣어 주세요: mesh_texture.py 메시.glb 이미지.png", "Give a mesh and an image: mesh_texture.py mesh.glb image.png"))

    mesh_path, image_path = Path(args.mesh), Path(args.image)
    output = Path(args.output) if args.output else ROOT / "outputs" / f"{mesh_path.stem}_tex.glb"
    if output.suffix.lower() != ".glb":
        output = output.with_suffix(".glb")
    output = unique_path(output.resolve())
    case_dir = output.with_name(output.stem + "_case")
    t_start = time.time()

    print(f"[{stamp()}] 1/5 " + L("메시 읽는 중: ", "Reading mesh: ") + mesh_path.name, flush=True)
    mesh = load_mesh(mesh_path)
    print("        " + L(f"점 {len(mesh.vertices):,}개, 면 {len(mesh.faces):,}개", f"{len(mesh.vertices):,} vertices, {len(mesh.faces):,} faces"), flush=True)
    base_R = rot_y(args.yaw) @ (rot_x(-90) if args.zup else np.eye(3))
    removed = False
    if not args.no_bg_remove:
        image_path, removed = prepare_image(image_path, case_dir, Path(args.supermat_cache), args.supermat_python)
    rgba, alpha = load_rgba(image_path, removed)

    print(f"[{stamp()}] 2/5 " + L("카메라 맞추는 중 (1~2분)", "Fitting camera (1-2 min)"), flush=True)
    cut = ImageFit(alpha).cut_names()
    if cut:
        print("        " + L(f"이미지 {', '.join(cut)} 가장자리에서 물체가 잘려 있습니다. 잘린 바깥 부분은 비교에서 뺍니다.", "The object is cut off at the image edge. The area beyond the cut is left out of the comparison."), flush=True)
    result = fit_camera(mesh, alpha, base_R, args.fov, not args.no_rotate_search)
    write_case(case_dir, mesh, rgba, result)
    print("        " + L(f"겹침(IoU) {result['iou']:.3f} / 화각 {result['fov']:.1f}도 / "
                         f"보정 회전 좌우 {result['yaw']:+.1f}도 위아래 {result['pitch']:+.1f}도",
                         f"overlap (IoU) {result['iou']:.3f} / FOV {result['fov']:.1f} deg / "
                         f"rotation fix yaw {result['yaw']:+.1f} pitch {result['pitch']:+.1f} deg"), flush=True)
    print("        " + L("확인 그림: ", "Fit preview: ") + str(case_dir / "fit_preview.png"), flush=True)
    if result["iou"] < 0.8:
        print(L("        [주의] 겹침이 낮습니다. fit_preview.png 에서 빨간 테두리가 물체와 맞는지 보세요.\n"
                "        메시 정면 방향(--yaw), 이미지와 같은 물체인지, 배경이 제대로 지워졌는지 확인하세요.",
                "        [warning] Low overlap. Check in fit_preview.png that the red outline follows the object.\n"
                "        Check the mesh front direction (--yaw), that it is the same object, and that the background was removed."), flush=True)
        tries = []
        for extra_yaw in (90, 180, 270):
            yaw = (args.yaw + extra_yaw) % 360
            R2 = rot_y(yaw) @ (rot_x(-90) if args.zup else np.eye(3))
            tries.append((fit_camera(mesh, alpha, R2, 40.0, False)["iou"], yaw))
        best_iou, best_yaw = max(tries)
        if best_iou > result["iou"] + 0.05:
            print("        " + L(f"--yaw {best_yaw} 로 돌리면 겹침이 {best_iou:.3f} 입니다. 메시가 다른 쪽을 보고 있는 것 같습니다.", f"With --yaw {best_yaw} the overlap is {best_iou:.3f}. The mesh seems to face another way."), flush=True)
    if args.prep_only:
        print(L("준비만 하고 멈췄습니다. (--prep-only)", "Stopped after preparation. (--prep-only)"))
        return 0

    env = dict(os.environ)
    env.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")
    env.setdefault("SUPRATEX_COMPLETION_DTYPE", "auto")

    print(f"[{stamp()}] 3/5 " + L("재질 지도 만드는 중 (SuperMat)", "Making material maps (SuperMat)"), flush=True)
    cmd = [args.supermat_python, str(Path(__file__).resolve()), "--_supermat", str(case_dir),
           "--supermat-cache", args.supermat_cache, "--supermat-dtype", args.supermat_dtype,
           "--metal-cut", str(args.metal_cut), "--rough-min", str(args.rough_min)]
    if args.seed is not None:
        cmd += ["--seed", str(args.seed)]
    if subprocess.run(cmd, env=env).returncode != 0:
        print(L("재질 단계에서 멈췄습니다. 위 오류를 확인하세요.", "Stopped at the material step. See the error above."))
        return 1

    print(f"[{stamp()}] 4/5 " + L("텍스처 굽는 중 (SUPRA-Tex)", "Baking texture (SUPRA-Tex)"), flush=True)
    native = case_dir / "supratex_native.glb"
    native.unlink(missing_ok=True)
    cmd = [sys.executable, str(ROOT / "texturing.py"), "--pipeline", "supra3d/supra-tex",
           "--cache-dir", str(ROOT / "models"), "--attention", "sdpa", "--low-vram",
           "--input-dir", str(case_dir), "--output", str(native)]
    if args.seed is not None:
        cmd += ["--seed", str(args.seed)]
    cmd += extra
    if subprocess.run(cmd, env=env, cwd=str(ROOT)).returncode != 0 or not native.exists():
        print(L("텍스처 단계에서 멈췄습니다. 위 오류를 확인하세요.", "Stopped at the texture step. See the error above."))
        return 1

    print(f"[{stamp()}] 5/5 " + L("결과 저장", "Saving result"), flush=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.keep_normalized:
        output.write_bytes(native.read_bytes())
    else:
        transform = json.loads((case_dir / "transform.json").read_text(encoding="utf-8"))
        restore_glb(native, output, transform)
    mins, secs = divmod(int(time.time() - t_start), 60)
    print(L(f"완료: {output}  (걸린 시간 {mins}분 {secs}초)", f"Done: {output}  (took {mins} min {secs} s)"), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
