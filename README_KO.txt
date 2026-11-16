SUPRA-Tex Workbench for Windows

SUPRA-Tex 를 윈도우에서 돌아가게 바꾸고 브라우저 화면(워크벤치)을 붙인 프로그램입니다.
3D 메시와, 같은 물체를 찍은 이미지 한 장을 넣으면 메시에 PBR 텍스처(색, 거칠기, 금속성)를 입혀 줍니다.
이미지에 보이는 면은 이미지를 따르고, 안 보이는 옆면과 뒷면은 SUPRA-Tex 의 보완 모델이 채웁니다.

SUPRA-Tex 원작자가 만든 공식 프로그램이 아닌 개인 수정판입니다.


[원본에서 바뀐 점]
- 윈도우에서 RTX 20 ~ 50 시리즈로 돌아갑니다.
- 재질 지도 모델을 비상업용 Qwen-Image 대신 상업적 사용이 가능한 SuperMat(MIT)으로 바꿨습니다. Qwen-Image 는 받지 않습니다.
- 8GB 그래픽카드에서도 돌아가게 정밀도(RTX 30 이상 bf16, RTX 20 fp16)와 메모리 사용을 조절합니다.
- 메시와 이미지의 각도, 화각, 위치를 윤곽으로 자동으로 맞춰서 어떤 메시든 넣을 수 있습니다.
- 피부, 천처럼 금속이 아닌 곳이 번들거리지 않게 금속성과 거칠기를 보정합니다.
- 결과 GLB 를 원래 메시의 위치, 크기, 방향으로 되돌립니다.
- 맞춤 미리보기, 진행 표시, 결과 3D 보기, 작업 기록과 정리 기능이 있는 브라우저 화면을 씁니다. 기본은 영어이고 한국어로 바꿀 수 있습니다.


[필요한 사양]
- 윈도우 10/11, NVIDIA RTX 20 시리즈 이상, VRAM 8GB 이상
- CUDA 12.8 을 지원하는 그래픽 드라이버 (cmd 에서 nvidia-smi 로 확인)
- Git, Python 3.14 (64-bit)
- 저장 공간 약 25GB (전용 파이썬 환경 약 7GB + 모델 약 17GB)


[설치와 사용법]
자세한 설치와 사용법은 docs 폴더의 아래 설명서를 보세요.

docs\[3D] SUPRA-Tex Workbench 사용법.txt

간단히 정리하면 아래 순서입니다.
1. Python 3.14 (64-bit) 를 설치합니다. 예: D:\Programs\Python\Python314 (PATH 추가는 체크하지 않음)
2. SUPRA-Tex 를 받고 이 워크벤치가 맞춰 둔 버전으로 고정합니다.

git clone https://github.com/Supra-3D/SUPRA-Tex.git

cd SUPRA-Tex

git checkout --detach cee4435652d0f23737bd28d5704e0fae9830b411

3. 이 저장소를 Code > Download ZIP 으로 받아 풀고, overlay 폴더 안의 내용을 모두 SUPRA-Tex 폴더에 넣습니다. (덮어쓰기)
4. Setup-SUPRA-Tex.cmd 를 더블클릭해서 설치합니다.
5. Start-SUPRA-Tex.cmd 를 더블클릭하면 브라우저에 http://127.0.0.1:8390 이 열립니다.

첫 굽기 때 모델 약 17GB 를 SUPRA-Tex\models 폴더에 받습니다.


[폴더 구성]
- overlay : SUPRA-Tex 폴더에 넣을 파일 (워크벤치, mesh_texture.py, 윈도우 패치, SuperMat 코드, 테스트 파일, 설치/실행 파일)
- docs : 영어, 한국어 설명서
- assets : 바로가기용 아이콘


[라이선스]
이 프로젝트에서 작성한 코드는 MIT 라이선스입니다. (LICENSE)
SUPRA-Tex, SuperMat, three.js 등 다른 코드와 모델은 각자의 라이선스를 따릅니다. (NOTICE)
