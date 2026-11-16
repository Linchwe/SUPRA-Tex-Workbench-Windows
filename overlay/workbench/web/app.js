import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const $ = (s) => document.querySelector(s);

// ------------------------------------------------------------------ 언어
const T = {
  ko: {
    brand_sub:'메시 텍스처 굽기 워크벤치', nav_bake:'텍스처 굽기', nav_history:'작업 기록', shutdown:'워크벤치 끄기',
    bake_title:'메시에 이미지로 PBR 텍스처 입히기', bake_desc:'같은 물체의 메시와, 배경을 지운 이미지를 넣으세요. 이미지에 보이는 면은 이미지를 따르고, 안 보이는 면은 AI 가 채웁니다.',
    step_input:'입력', mesh_label:'메시', mesh_hint:'GLB / OBJ / PLY / STL. 정면이 앞(+Z, 블렌더 정면 뷰)을 보게', image_label:'이미지', image_hint:'배경을 지운 투명 PNG',
    step_options:'설정', opt_yaw:'메시 방향 돌리기', opt_fov:'화각', auto:'자동', opt_metal:'금속성 보정', opt_rough:'거칠기 보정', opt_faces:'면 수 상한', opt_seed:'시드',
    opt_rotate:'작은 회전 자동 보정', opt_zup:'Z 가 위쪽인 파일', opt_restore:'결과를 원래 메시 위치로 되돌리기',
    opt_note:'처음에는 기본값 그대로 쓰세요. 유리처럼 매끈한 물체는 거칠기 보정을 0 으로, 금속이 덜 잡히면 금속성 보정을 0.35 로 낮춥니다.',
    btn_preview:'맞춤 미리보기 (약 1분)', btn_run:'텍스처 굽기 시작', btn_cancel:'작업 멈추기',
    s1:'메시 읽기', s2:'카메라 맞추기', s3:'재질 지도', s4:'텍스처 굽기', s5:'저장', log:'작업 로그',
    fit_title:'맞춤 확인', fit_note:'빨간 선이 메시 윤곽입니다. 물체 테두리와 맞으면 정상입니다. 겹침이 0.8 보다 낮으면 메시 방향이나 이미지를 확인하세요.',
    result_title:'결과', viewer_empty:'텍스처 굽기가 끝나면 여기에 3D 결과가 나옵니다.', download:'결과 GLB 받기',
    history_title:'작업 기록', history_desc:'작업마다 입력, 맞춤 결과, 로그, 결과 GLB 가 저장됩니다. 필요한 결과를 받은 뒤에는 기록을 정리하세요.',
    refresh:'새로고침', clear:'기록 정리', seed_auto:'기본',
    help_need:'메시와 이미지를 넣으세요.', help_ready:'준비됐습니다. 처음이면 맞춤 미리보기로 빨간 선이 맞는지 먼저 보세요.',
    help_busy:'작업 중입니다. 처음 실행은 모델을 받고 GPU 코드를 컴파일해서 오래 걸립니다(RTX 20 은 40분 이상). 화면이 멈춘 것처럼 보여도 기다리세요.',
    elapsed:'걸린 시간', st_running:'진행 중', st_succeeded:'완료', st_failed:'실패', st_cancelled:'멈춤', st_interrupted:'중단됨',
    failed_hint:'실패했습니다. 작업 로그의 마지막 30줄을 복사해서 LLM 모델에 공유해 주세요.',
    fit_line:(f)=>`겹침(IoU) ${f.silhouette_iou?.toFixed(3)} · 화각 ${f.fov_deg}° · 보정 회전 좌우 ${f.yaw_fix}° 위아래 ${f.pitch_fix}°`,
    low_iou:'겹침이 낮습니다. 로그에 --yaw 안내가 있으면 메시 방향 돌리기를 그 값으로 바꿔 보세요.',
    kind_preview:'맞춤 미리보기', kind_full:'텍스처 굽기', open:'열기 →', del:'지우기',
    empty_history:'아직 작업이 없습니다.', uploading:'올리는 중…', err_no_alpha:'이미지에 투명 배경(알파)이 없습니다. 배경을 지운 PNG 를 넣으세요.',
    err_bad_type:'지원하지 않는 파일 형식입니다.', err_busy:'다른 작업이 돌고 있습니다. 끝나거나 멈춘 뒤 다시 하세요.', err_generic:'요청이 실패했습니다.',
    clear_ask:(u)=>`작업 기록과 올린 파일을 모두 지웁니다.\n\n작업 기록 ${u.jobs.count}개\n올린 파일 ${u.uploads.count}개\n합계 약 ${gb(u.jobs.bytes+u.uploads.bytes)} GB\n\n필요한 결과 GLB 는 먼저 받아 두세요. 지울까요?`,
    clear_empty:'지울 기록이 없습니다.', cleared:(b)=>`정리했습니다. 약 ${b} GB 를 비웠습니다.`,
    shutdown_ask:'워크벤치를 끌까요? 돌고 있는 작업이 있으면 멈춥니다.', shutdown_done:'워크벤치를 껐습니다. 이 탭과 검은 실행 창을 닫아도 됩니다.',
    del_ask:'이 작업 기록을 지울까요?', busy_badge:'작업 중',
  },
  en: {
    brand_sub:'Mesh texture baking workbench', nav_bake:'Bake texture', nav_history:'Task history', shutdown:'Close workbench',
    bake_title:'Put PBR textures on a mesh from an image', bake_desc:'Add a mesh and an image of the same object with the background removed. Faces visible in the image follow the image; hidden faces are filled in by AI.',
    step_input:'Input', mesh_label:'Mesh', mesh_hint:'GLB / OBJ / PLY / STL. Front facing forward (+Z, Blender front view)', image_label:'Image', image_hint:'Transparent PNG, background removed',
    step_options:'Settings', opt_yaw:'Rotate mesh', opt_fov:'Field of view', auto:'Auto', opt_metal:'Metallic correction', opt_rough:'Roughness correction', opt_faces:'Max faces', opt_seed:'Seed',
    opt_rotate:'Auto-correct small rotations', opt_zup:'File is Z-up', opt_restore:'Return result to the original mesh position',
    opt_note:'Start with the defaults. For glossy objects such as glass, set roughness correction to 0. If metal is missed, lower metallic correction to 0.35.',
    btn_preview:'Fit preview (about 1 min)', btn_run:'Start baking', btn_cancel:'Stop task',
    s1:'Read mesh', s2:'Fit camera', s3:'Material maps', s4:'Bake texture', s5:'Save', log:'Task log',
    fit_title:'Fit check', fit_note:'The red line is the mesh outline. It is fine if it follows the object edge. If the overlap is below 0.8, check the mesh direction or the image.',
    result_title:'Result', viewer_empty:'The 3D result appears here when baking finishes.', download:'Download result GLB',
    history_title:'Task history', history_desc:'Each task keeps its inputs, fit result, log and result GLB. Clear the history after you have downloaded what you need.',
    refresh:'Refresh', clear:'Clear history', seed_auto:'Default',
    help_need:'Add a mesh and an image.', help_ready:'Ready. The first time, use Fit preview to check the red line first.',
    help_busy:'Working. The first run downloads models and compiles GPU code, so it takes long (40+ min on RTX 20). Wait even if it looks stuck.',
    elapsed:'Elapsed', st_running:'Running', st_succeeded:'Done', st_failed:'Failed', st_cancelled:'Stopped', st_interrupted:'Interrupted',
    failed_hint:'Failed. Copy the last 30 lines of the task log and share them with an LLM.',
    fit_line:(f)=>`Overlap (IoU) ${f.silhouette_iou?.toFixed(3)} · FOV ${f.fov_deg}° · rotation fix yaw ${f.yaw_fix}° pitch ${f.pitch_fix}°`,
    low_iou:'Low overlap. If the log suggests --yaw, set Rotate mesh to that value.',
    kind_preview:'Fit preview', kind_full:'Bake texture', open:'Open →', del:'Delete',
    empty_history:'No tasks yet.', uploading:'Uploading…', err_no_alpha:'The image has no transparent background (alpha). Use a PNG with the background removed.',
    err_bad_type:'Unsupported file type.', err_busy:'Another task is running. Try again after it finishes or is stopped.', err_generic:'The request failed.',
    clear_ask:(u)=>`This deletes all task history and uploaded files.\n\nTasks: ${u.jobs.count}\nUploaded files: ${u.uploads.count}\nTotal: about ${gb(u.jobs.bytes+u.uploads.bytes)} GB\n\nDownload any result GLB you need first. Delete now?`,
    clear_empty:'There is nothing to clear.', cleared:(b)=>`Cleared about ${b} GB.`,
    shutdown_ask:'Close the workbench? A running task will be stopped.', shutdown_done:'The workbench is closed. You can close this tab and the black window.',
    del_ask:'Delete this task?', busy_badge:'Working',
  },
};
let lang = 'en';   // 기본 언어는 영어. 왼쪽 아래 버튼으로 한국어로 바꾸면 이 브라우저에 기억된다.
try { const saved = localStorage.getItem('supratex-lang'); if (saved === 'ko' || saved === 'en') lang = saved; } catch {}
const t = (k, ...a) => { const v = T[lang][k] ?? T.en[k] ?? k; return typeof v === 'function' ? v(...a) : v; };
function applyLang() {
  document.documentElement.lang = lang;
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
  document.querySelectorAll('[data-lang]').forEach(b => b.classList.toggle('on', b.dataset.lang === lang));
  $('#opt-seed').placeholder = t('seed_auto');
  refreshHelp();
  if (current) renderJob(current);
  if ($('#page-history').classList.contains('active')) loadHistory();
}
document.querySelectorAll('[data-lang]').forEach(b => b.onclick = () => { lang = b.dataset.lang; try { localStorage.setItem('supratex-lang', lang); } catch {} applyLang(); });
const gb = (b) => (b / 1073741824).toFixed(2);

// ------------------------------------------------------------------ 공통
function toast(msg) { const el = $('#toast'); el.textContent = msg; el.hidden = false; clearTimeout(toast.t); toast.t = setTimeout(() => el.hidden = true, 7000); }
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  let data = null; try { data = await r.json(); } catch {}
  if (!r.ok) { const e = new Error((data && data.error) || 'http'); e.status = r.status; throw e; }
  return data;
}
const post = (path, body) => api(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body || {}) });
function errText(e) { return ({ no_alpha: t('err_no_alpha'), bad_type: t('err_bad_type'), busy: t('err_busy') })[e.message] || t('err_generic'); }

document.querySelectorAll('.nav-item').forEach(b => b.onclick = () => {
  document.querySelectorAll('.nav-item').forEach(x => x.classList.toggle('active', x === b));
  document.querySelectorAll('.page').forEach(p => p.classList.toggle('active', p.id === 'page-' + b.dataset.page));
  if (b.dataset.page === 'history') loadHistory();
});

// ------------------------------------------------------------------ 입력
const inputs = { mesh: null, image: null };
function setupDrop(kind) {
  const drop = $('#drop-' + kind), file = $('#file-' + kind);
  file.onchange = () => file.files[0] && upload(kind, file.files[0]);
  drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); };
  drop.ondragleave = () => drop.classList.remove('over');
  drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) upload(kind, f); };
}
async function upload(kind, f) {
  $('#' + kind + '-name').textContent = t('uploading');
  try {
    const r = await api(`/api/upload?kind=${kind}&name=${encodeURIComponent(f.name)}`, { method: 'POST', body: f });
    inputs[kind] = r.id;
    $('#' + kind + '-name').textContent = f.name;
    $('#drop-' + kind).classList.add('done');
    if (kind === 'image') { const img = $('#image-thumb'); img.src = URL.createObjectURL(f); img.hidden = false; $('#image-icon').hidden = true; }
  } catch (e) { inputs[kind] = null; $('#' + kind + '-name').textContent = ''; $('#drop-' + kind).classList.remove('done'); toast(errText(e)); }
  refreshHelp();
}
setupDrop('mesh'); setupDrop('image');

function options() {
  return {
    yaw: +$('#opt-yaw').value, fov: $('#opt-fov').value || null, metal_cut: $('#opt-metal').value, rough_min: $('#opt-rough').value,
    decimation_target: +$('#opt-faces').value, seed: $('#opt-seed').value === '' ? null : $('#opt-seed').value,
    no_rotate_search: !$('#opt-rotate').checked, zup: $('#opt-zup').checked, keep_normalized: !$('#opt-restore').checked,
  };
}

// ------------------------------------------------------------------ 실행
let busy = false, current = null, pollTimer = null;
function refreshHelp() {
  const ready = inputs.mesh && inputs.image;
  $('#btn-run').disabled = $('#btn-preview').disabled = busy || !ready;
  $('#btn-cancel').hidden = !busy;
  $('#run-help').textContent = busy ? t('help_busy') : ready ? t('help_ready') : t('help_need');
  $('#busy-badge').hidden = !busy; $('#busy-badge').textContent = t('busy_badge');
}
async function start(preview) {
  try {
    const job = await post('/api/jobs', { mesh: inputs.mesh, image: inputs.image, preview, lang, options: options() });
    busy = true; refreshHelp(); follow(job.id);
  } catch (e) { toast(errText(e)); }
}
$('#btn-preview').onclick = () => start(true);
$('#btn-run').onclick = () => start(false);
$('#btn-cancel').onclick = async () => { if (current) await post(`/api/jobs/${current.id}/cancel`).catch(() => {}); };

function follow(id) {
  clearInterval(pollTimer);
  const tick = async () => {
    try {
      const job = await api('/api/jobs/' + id);
      renderJob(job);
      if (job.state !== 'running') { clearInterval(pollTimer); busy = false; refreshHelp(); }
    } catch { /* 잠깐 끊김 */ }
  };
  tick(); pollTimer = setInterval(tick, 1500);
}

let shownPreview = null, shownResult = null;
function renderJob(job) {
  current = job;
  const log = job.log || [];
  let step = 0;
  for (const line of log) { const m = line.match(/\] ([1-5])\/5 /); if (m) step = +m[1]; }
  const finished = job.state === 'succeeded';
  document.querySelectorAll('#steps li').forEach((li, i) => {
    const n = i + 1, last = job.kind === 'preview' ? 2 : 5;
    li.classList.toggle('done', (finished && n <= last) || n < step);
    li.classList.toggle('now', job.state === 'running' && n === step);
    li.classList.toggle('fail', job.state !== 'running' && !finished && n === step);
  });
  const end = job.finished || Date.now() / 1000, sec = Math.max(0, Math.round(end - job.created));
  $('#elapsed').textContent = `${t('elapsed')} ${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, '0')}`;
  const st = $('#state-text'); st.textContent = t('st_' + job.state) + (job.state === 'failed' ? ' · ' + t('failed_hint') : '');
  st.className = job.state === 'failed' || job.state === 'cancelled' || job.state === 'interrupted' ? 'failed' : finished ? 'ok' : '';
  const pre = $('#log'); const atBottom = pre.scrollTop + pre.clientHeight >= pre.scrollHeight - 20;
  pre.textContent = log.join('\n'); if (atBottom) pre.scrollTop = pre.scrollHeight;
  if (job.state === 'failed') $('#log-box').open = true;
  $('#result').hidden = !(job.has_preview || job.has_result);
  if (job.has_preview && shownPreview !== job.id) { $('#fit-img').src = `/api/jobs/${job.id}/fit_preview.png?${Date.now()}`; shownPreview = job.id; }
  if (job.fit) $('#fit-text').textContent = t('fit_line', job.fit) + (job.fit.silhouette_iou < 0.8 ? ' — ' + t('low_iou') : '');
  const dl = $('#download');
  dl.hidden = !job.has_result;
  if (job.has_result) { dl.href = `/api/jobs/${job.id}/result.glb?download=1`; if (shownResult !== job.id) { shownResult = job.id; showModel(`/api/jobs/${job.id}/result.glb`); } }
  else if (shownResult && shownResult !== job.id) { clearModel(); shownResult = null; }
}

// ------------------------------------------------------------------ 3D 보기
let renderer, scene, camera, controls, model;
function initViewer() {
  const box = $('#viewer');
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.outputColorSpace = THREE.SRGBColorSpace;
  box.appendChild(renderer.domElement);
  scene = new THREE.Scene(); scene.background = new THREE.Color(0x8a8a8a);
  scene.environment = new THREE.PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  const light = new THREE.DirectionalLight(0xffffff, 1.2); light.position.set(1, 2, 3); scene.add(light);
  camera = new THREE.PerspectiveCamera(35, 1, 0.01, 1000);
  controls = new OrbitControls(camera, renderer.domElement); controls.enableDamping = true;
  const resize = () => { const w = box.clientWidth, h = box.clientHeight; if (!w || !h) return; renderer.setSize(w, h); camera.aspect = w / h; camera.updateProjectionMatrix(); };
  new ResizeObserver(resize).observe(box); resize();
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
}
function clearModel() { if (model) { scene.remove(model); model = null; } $('#viewer-empty').hidden = false; }
function showModel(url) {
  if (!renderer) initViewer();
  new GLTFLoader().load(url, (g) => {
    clearModel(); model = g.scene; scene.add(model); $('#viewer-empty').hidden = true;
    const b = new THREE.Box3().setFromObject(model), c = b.getCenter(new THREE.Vector3()), s = b.getSize(new THREE.Vector3()).length();
    controls.target.copy(c); camera.near = s / 100; camera.far = s * 20; camera.updateProjectionMatrix();
    camera.position.set(c.x, c.y + s * 0.05, c.z + s * 1.3); controls.update();
  });
}

// ------------------------------------------------------------------ 기록
async function loadHistory() {
  const list = $('#history-list');
  let jobs = [];
  try { jobs = await api('/api/jobs'); } catch { return; }
  list.replaceChildren();
  if (!jobs.length) { list.textContent = t('empty_history'); return; }
  for (const job of jobs) {
    const row = document.createElement('div'); row.className = 'history-item';
    const info = document.createElement('div'); info.className = 'grow';
    const title = document.createElement('b'); title.textContent = `${t(job.kind === 'preview' ? 'kind_preview' : 'kind_full')} · ${job.mesh_name || ''} + ${job.image_name || ''}`;
    const p1 = document.createElement('p'); p1.textContent = new Date(job.created * 1000).toLocaleString();
    const p2 = document.createElement('p'); p2.textContent = job.fit ? t('fit_line', job.fit) : '';
    info.append(title, p1, p2);
    const pill = document.createElement('span'); pill.className = 'pill ' + job.state; pill.textContent = t('st_' + job.state);
    const open = document.createElement('button'); open.textContent = t('open');
    open.onclick = () => { document.querySelector('[data-page=bake]').click(); follow(job.id); };
    const del = document.createElement('button'); del.className = 'danger'; del.textContent = t('del'); del.disabled = job.state === 'running';
    del.onclick = async () => { if (!confirm(t('del_ask'))) return; try { await post(`/api/jobs/${job.id}/delete`); if (current?.id === job.id) { current = null; $('#result').hidden = true; } loadHistory(); } catch (e) { toast(errText(e)); } };
    row.append(info, pill, open, del); list.append(row);
  }
}
$('#btn-refresh').onclick = loadHistory;
$('#btn-clear').onclick = async () => {
  try {
    const s = await api('/api/status');
    if (s.busy) { toast(t('err_busy')); return; }
    if (!s.usage.jobs.count && !s.usage.uploads.count) { toast(t('clear_empty')); return; }
    if (!confirm(t('clear_ask', s.usage))) return;
    const r = await post('/api/clear');
    toast(t('cleared', gb(r.before.jobs.bytes + r.before.uploads.bytes)));
    current = null; $('#result').hidden = true; clearModel(); shownResult = shownPreview = null;
    for (const k of ['mesh', 'image']) { inputs[k] = null; $('#' + k + '-name').textContent = ''; $('#drop-' + k).classList.remove('done'); }
    $('#image-thumb').hidden = true; $('#image-icon').hidden = false; refreshHelp(); loadHistory();
  } catch (e) { toast(errText(e)); }
};

// ------------------------------------------------------------------ 상태, 끄기
async function status() {
  try {
    const s = await api('/api/status');
    $('#gpu').textContent = s.gpu || '';
    if (s.busy && !busy) { busy = true; refreshHelp(); follow(s.running); }
  } catch {}
}
$('#shutdown').onclick = async () => {
  if (!confirm(t('shutdown_ask'))) return;
  try { await post('/api/shutdown'); } catch {}
  document.body.innerHTML = `<main><p style="font-size:16px">${t('shutdown_done')}</p></main>`;
};

applyLang(); status(); setInterval(status, 5000);
