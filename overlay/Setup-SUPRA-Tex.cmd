@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title SUPRA-Tex Setup

rem ============================================================
rem  SUPRA-Tex Workbench setup (Windows, Python 3.14, CUDA 12.8)
rem  Run this file in the SUPRA-Tex folder after git clone and after
rem  copying the files in the overlay folder into it.
rem  Optional: set SUPRATEX_PYTHON to the full path of python.exe 3.14.
rem ============================================================

set "WHEELS=https://github.com/voxta-ai/voxta-python-packaging/releases/download/trellis2-wheels-1.0.0"
set "PINNED=cee4435652d0f23737bd28d5704e0fae9830b411"
set "STEP="

echo.
echo ==== SUPRA-Tex Workbench Setup ====
echo.

rem ---- 0. folder check
if not exist "texturing.py" goto NOT_HERE
if not exist "mesh_texture.py" goto NO_PATCH
if not exist "workbench\server.py" goto NO_PATCH

rem ---- 1. SUPRA-Tex version check
set "STEP=1/7 SUPRA-Tex version"
echo [1/7] Checking SUPRA-Tex version / SUPRA-Tex 버전 확인
set "HEAD="
for /f %%H in ('git rev-parse HEAD 2^>nul') do set "HEAD=%%H"
if not defined HEAD goto VERSION_UNKNOWN
if /i not "%HEAD%"=="%PINNED%" goto WRONG_VERSION
echo       OK %HEAD:~0,7%
goto FIND_PY
:VERSION_UNKNOWN
echo       git version could not be read. Continuing. / git 버전을 읽지 못했습니다. 계속 진행합니다.

rem ---- 2. Python 3.14
:FIND_PY
set "STEP=2/7 Python 3.14"
echo [2/7] Finding Python 3.14 / Python 3.14 찾기
set "PY="
if defined SUPRATEX_PYTHON if exist "%SUPRATEX_PYTHON%" set "PY=%SUPRATEX_PYTHON%"
if not defined PY if exist "C:\Programs\Python\Python314\python.exe" set "PY=C:\Programs\Python\Python314\python.exe"
if not defined PY if exist "D:\Programs\Python\Python314\python.exe" set "PY=D:\Programs\Python\Python314\python.exe"
if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set "PY=%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
if not defined PY for /f "delims=" %%P in ('py -3.14 -c "import sys; print(sys.executable)" 2^>nul') do set "PY=%%P"
if not defined PY goto NO_PYTHON
"%PY%" -c "import sys; sys.exit(0 if sys.version_info[:2]==(3,14) else 1)"
if errorlevel 1 goto NO_PYTHON
echo       %PY%

rem ---- 3. venv
set "STEP=3/7 Python environment (.venv314)"
echo [3/7] Creating the Python environment / 전용 파이썬 환경 만들기 (.venv314)
if exist ".venv314\Scripts\python.exe" goto VENV_OK
"%PY%" -m venv .venv314
if errorlevel 1 goto FAIL
:VENV_OK
set "VPY=%~dp0.venv314\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto FAIL

rem ---- 4. PyTorch, Triton
set "STEP=4/7 PyTorch and Triton"
echo [4/7] Installing PyTorch (about 3GB) and Triton / PyTorch(약 3GB)와 Triton 설치
"%VPY%" -m pip install torch==2.9.1+cu128 torchvision==0.24.1+cu128 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto FAIL
"%VPY%" -m pip install "triton-windows>=3.6,<3.7"
if errorlevel 1 goto FAIL

rem ---- 5. packages, SUPRA-Tex
set "STEP=5/7 Packages and SUPRA-Tex"
echo [5/7] Installing packages and SUPRA-Tex / 패키지와 SUPRA-Tex 설치
"%VPY%" -m pip install -r requirements-win-py314.txt
if errorlevel 1 goto FAIL
"%VPY%" -m pip install --no-deps -e .
if errorlevel 1 goto FAIL
"%VPY%" -m pip install --no-deps deployment\runtime\utils3d
if errorlevel 1 goto FAIL

rem ---- 6. CUDA extensions
set "STEP=6/7 CUDA extensions"
echo [6/7] Installing CUDA extensions (RTX 20-50) / CUDA 확장 설치
"%VPY%" -m pip install --no-deps "%WHEELS%/cumesh-1.0-cp314-cp314-win_amd64.whl" "%WHEELS%/flex_gemm-1.0.0-cp314-cp314-win_amd64.whl" "%WHEELS%/nvdiffrast-0.4.0-cp314-cp314-win_amd64.whl" "%WHEELS%/o_voxel-0.0.1-cp314-cp314-win_amd64.whl"
if errorlevel 1 goto FAIL

rem ---- 7. check
set "STEP=7/7 Check"
echo [7/7] Checking the install / 설치 확인
"%VPY%" -c "import torch, cumesh, flex_gemm, o_voxel, nvdiffrast.torch, utils3d, diffusers, trimesh, scipy; ok=torch.cuda.is_available(); print('      torch', torch.__version__, '/ CUDA', ok, '/', torch.cuda.get_device_name(0) if ok else '-', torch.cuda.get_device_capability(0) if ok else ''); raise SystemExit(0 if ok else 3)"
if errorlevel 3 goto NO_CUDA
if errorlevel 1 goto FAIL
"%VPY%" -m pip cache purge >nul 2>&1

echo.
echo ==== Setup finished / 설치 완료 ====
echo Start the workbench with Start-SUPRA-Tex.cmd
echo Start-SUPRA-Tex.cmd 로 워크벤치를 실행하세요.
echo The first bake downloads about 17GB of models into the models folder.
echo 첫 굽기 때 모델 약 17GB 를 models 폴더에 받습니다.
echo.
pause
exit /b 0

:NOT_HERE
echo This file must be in the SUPRA-Tex folder (where texturing.py is).
echo 이 파일은 SUPRA-Tex 폴더(texturing.py 가 있는 곳)에 있어야 합니다.
goto END_FAIL

:NO_PATCH
echo SUPRA-Tex Workbench files are missing. Copy everything in the overlay folder into this folder first.
echo SUPRA-Tex Workbench 파일이 없습니다. overlay 폴더 안의 내용을 먼저 이 폴더에 넣으세요.
goto END_FAIL

:WRONG_VERSION
echo This SUPRA-Tex is a different version (%HEAD:~0,7%). The workbench files are made for cee4435.
echo Run this line in this folder, then run Setup again:
echo SUPRA-Tex 버전이 다릅니다. 이 폴더에서 아래 줄을 실행한 뒤 Setup 을 다시 실행하세요.
echo.
echo git checkout --detach %PINNED%
goto END_FAIL

:NO_PYTHON
echo Python 3.14 was not found. Install python-3.14.10-amd64.exe to C:\Programs\Python\Python314 first.
echo Python 3.14 를 찾지 못했습니다. 먼저 C:\Programs\Python\Python314 에 설치하세요.
echo Another location: set SUPRATEX_PYTHON=full path of python.exe, then run this file from the same window.
echo 다른 위치에 설치했다면 같은 창에서 set SUPRATEX_PYTHON=python.exe 전체 경로 를 실행한 뒤 이 파일을 실행하세요.
goto END_FAIL

:NO_CUDA
echo PyTorch cannot see the NVIDIA GPU. Update the graphics driver (CUDA 12.8 or newer, check with nvidia-smi).
echo PyTorch 가 그래픽카드를 찾지 못했습니다. 그래픽 드라이버를 업데이트하세요. (nvidia-smi 에서 CUDA 12.8 이상)
goto END_FAIL

:FAIL
echo.
echo Setup stopped at step %STEP%. Copy the last 30 lines of this window and share them with an LLM.
echo 설치가 %STEP% 단계에서 멈췄습니다. 이 창의 마지막 30줄을 복사해서 LLM 모델에 공유해 주세요.
echo You can run Setup again after fixing it. Finished steps are skipped quickly.
echo 고친 뒤 Setup 을 다시 실행하면 됩니다. 이미 끝난 단계는 빠르게 넘어갑니다.

:END_FAIL
echo.
pause
exit /b 1
