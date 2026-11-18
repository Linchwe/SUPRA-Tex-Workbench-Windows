# SUPRA-Tex Workbench for Windows

A Windows port of [SUPRA-Tex](https://github.com/Supra-3D/SUPRA-Tex) with a browser workbench.
Give it a 3D mesh and one image of the same object, and it puts PBR textures (base color, roughness, metallic) on the mesh.
Faces visible in the image follow the image; the hidden sides and back are filled in by the SUPRA-Tex completion model.

This is an unofficial community project. It is not made or endorsed by the SUPRA-Tex authors.

A Korean guide is available in `README_KO.txt` and `docs/`.

## What is changed from the original

- **Windows**: runs on Windows with RTX 20 to RTX 50 series cards, using prebuilt Windows CUDA extensions.
- **Commercial-use material model**: the original uses Qwen-Image (non-commercial) for material maps. This version uses [SuperMat](https://github.com/hyj542682306/SuperMat) (MIT, on Stable Diffusion 2.1) instead. Qwen-Image is never downloaded.
- **8GB VRAM**: the completion model runs in reduced precision (bf16 on RTX 30 and newer, fp16 on RTX 20) and streams its blocks to the GPU when VRAM is short.
- **Mesh + image input**: the camera is fitted automatically from the silhouettes (field of view, small rotations, image position), so any mesh can be used, not only meshes made by SUPRA-Tex.
- **Material correction**: metallic and roughness are corrected so non-metal parts such as skin and cloth do not look shiny.
- **Automatic background removal**: an image with a background (PNG / JPG / WEBP) is cut out automatically with [BiRefNet](https://github.com/ZhengPeng7/BiRefNet) (MIT). It runs in its own process and frees VRAM before the next step; a transparent PNG is used as it is.
- **Result in place**: the result GLB is returned to the position, size and direction of the original mesh.
- **Workbench**: a local browser page with fit preview, progress, 3D result view, task history and cleanup. English by default, Korean available.

## Requirements

- Windows 10/11, NVIDIA RTX 20 series or newer with 8GB VRAM or more
- Graphics driver supporting CUDA 12.8 (check with `nvidia-smi`)
- Git, Python 3.14 (64-bit)
- About 26GB of disk space (Python environment about 7GB + models about 18GB)

Tested: RTX 3060 12GB (about 6 minutes per bake), RTX 2070 SUPER 8GB (about 5.5 minutes after the first run; the first run compiles GPU code and takes about 45 minutes).

## Install

The full step-by-step guide is in `docs/[3D] SUPRA-Tex Workbench Usage.txt`. In short:

1. Install Python 3.14 (64-bit), for example to `D:\Programs\Python\Python314`. Do not add it to PATH.
2. Get SUPRA-Tex and lock it to the version this workbench is made for:

```
git clone https://github.com/Supra-3D/SUPRA-Tex.git
cd SUPRA-Tex
git checkout --detach cee4435652d0f23737bd28d5704e0fae9830b411
```

3. Download this repository (Code > Download ZIP), unzip it, and copy everything inside the `overlay` folder into the `SUPRA-Tex` folder (overwrite).
4. Double-click `Setup-SUPRA-Tex.cmd`. It creates `.venv314` and installs PyTorch, Triton, the packages and the CUDA extensions, then checks the install.
5. Double-click `Start-SUPRA-Tex.cmd`. The workbench opens at `http://127.0.0.1:8390`.

The first bake downloads about 17GB of models into `SUPRA-Tex\models` (SUPRA-Tex completion model, TRELLIS.2 VAE, Stable Diffusion 2.1, SuperMat). The first image without a transparent background also downloads the BiRefNet background removal model (about 900MB).

## Use

1. Drag a mesh (GLB / OBJ / PLY / STL) and an image (PNG / JPG / WEBP) into the workbench. If the image has no transparent background, it is removed automatically.
2. Optional: click **Fit preview** to check the cut-out and that the red outline follows the object.
3. Click **Start baking**. When it finishes, check the result in 3D and click **Download result GLB**.

Tips:

- The mesh front should face +Z (Blender front view; the default glTF export does this).
- Meshes built to match the image (for example Pixal3D or Idol) give the best texture alignment.
- The result mesh is rebuilt by SUPRA-Tex (about 500,000 faces, 4096 textures). The original polygons and UVs are not kept; bake the texture onto your own mesh if you need them.

A command line tool is also included: `mesh_texture.py mesh.glb image.png` (run with `.venv314\Scripts\python.exe`, see the header of the file).

## Repository layout

| Path | Contents |
|---|---|
| `overlay/` | Files to copy into the SUPRA-Tex folder |
| `overlay/workbench/` | Browser workbench (Python standard library server + HTML/JS) |
| `overlay/mesh_texture.py` | Mesh + image pipeline: background removal, camera fit, SuperMat, SUPRA-Tex, position restore |
| `overlay/supratex/` | Patched SUPRA-Tex files (reduced precision, block streaming for 8GB) |
| `overlay/third_party/SuperMat/` | SuperMat inference code (MIT) |
| `overlay/mesh_texture_test/` | Test mesh and image for the install check |
| `docs/` | Install and usage guides in English and Korean |
| `assets/` | Icon for a desktop shortcut |

## License

The code written for this project is under the MIT License (`LICENSE`).
Third-party code and models keep their own licenses; see `NOTICE`.

- SUPRA-Tex code and completion model: MIT
- TRELLIS.2 VAE: MIT
- SuperMat: MIT; Stable Diffusion 2.1: CreativeML Open RAIL++-M
- BiRefNet (background removal): MIT
- three.js: MIT
- Windows CUDA extension builds ([voxta-ai](https://github.com/voxta-ai/voxta-python-packaging/releases/tag/trellis2-wheels-1.0.0)): the license of each original project
