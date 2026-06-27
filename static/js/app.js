/* ===================== EPP Guard · App ===================== */
const PAGES = {
  dashboard: ['Dashboard', 'Resumen de cumplimiento de EPP'],
  inspect: ['Inspección', 'Analiza una foto y detecta el EPP'],
  live: ['En vivo', 'Detección en tiempo real desde cámara o video'],
  history: ['Historial', 'Registro de todas las inspecciones'],
  config: ['Configuración', 'Ajusta el modelo, las reglas y las alertas'],
};

const cfgTags = { required: [], ppe: [], violation: [] };
let availableClasses = { all: [], positives: [], negatives: [] };
let tokenIsSet = false;

/* ---------- utilidades ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const icons = () => window.lucide && lucide.createIcons();

function toast(msg, type = 'ok') {
  const t = $('#toast');
  t.innerHTML = `<div class="toast-box ${type}">
    <i data-lucide="${type === 'ok' ? 'check-circle-2' : 'alert-triangle'}" class="h-4 w-4"></i>${msg}</div>`;
  t.classList.remove('hidden');
  icons();
  clearTimeout(t._tmr);
  t._tmr = setTimeout(() => t.classList.add('hidden'), 3200);
}

function fmtDate(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleString('es', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

/* ---------- navegación ---------- */
function go(view) {
  if (view !== 'live') Live.stop(); // libera la cámara al salir
  $$('#nav .nav-item').forEach(b => b.classList.toggle('active', b.dataset.view === view));
  $$('section[data-panel]').forEach(s => s.classList.toggle('hidden', s.dataset.panel !== view));
  $('#page-title').textContent = PAGES[view][0];
  $('#page-sub').textContent = PAGES[view][1];
  if (view === 'dashboard') loadDashboard();
  if (view === 'history') loadHistory();
  if (view === 'config') loadConfig();
}

/* ---------- status pills ---------- */
async function loadHealth() {
  try {
    const h = await API.health();
    setPill('#pill-roboflow', h.roboflow_configurado);
    setPill('#pill-telegram', h.telegram_configurado);
    const badge = $('#model-badge');
    badge.innerHTML = `<i data-lucide="cpu" class="h-3.5 w-3.5"></i> ${h.modelo || 'sin modelo'}`;
    badge.classList.remove('hidden');
    icons();
  } catch (e) { /* noop */ }
}
function setPill(sel, ok) {
  const el = $(sel);
  el.textContent = ok ? 'OK' : 'OFF';
  el.className = 'status-pill ' + (ok ? 'ok' : 'off');
}

/* ---------- Dashboard ---------- */
async function loadDashboard() {
  try {
    const [s, ts, bc] = await Promise.all([API.stats(), API.timeseries(), API.byClass()]);
    renderKpis(s);
    Charts.renderTrend(ts);
    Charts.renderClass(bc);
  } catch (e) { toast(e.message, 'err'); }
}

function renderKpis(s) {
  const cards = [
    { label: 'Inspecciones', val: s.total_inspecciones, icon: 'scan-line', color: '#3b82f6' },
    { label: 'Cumplimiento', val: s.porcentaje_cumplimiento + '%', icon: 'shield-check', color: '#10b981' },
    { label: 'Violaciones', val: s.violaciones, icon: 'shield-alert', color: '#ef4444' },
    { label: 'Alertas enviadas', val: s.alertas_enviadas, icon: 'send', color: '#f59e0b' },
  ];
  $('#kpis').innerHTML = cards.map(c => `
    <div class="card kpi">
      <div class="kpi-icon" style="background:${c.color}1f;color:${c.color}"><i data-lucide="${c.icon}" class="h-5 w-5"></i></div>
      <div class="kpi-val">${c.val}</div>
      <div class="kpi-label">${c.label}</div>
    </div>`).join('');
  icons();
}

/* ---------- Inspección ---------- */
let selectedFile = null;

function setupInspect() {
  const dz = $('#dropzone'), input = $('#file-input');
  input.addEventListener('change', () => input.files[0] && pickFile(input.files[0]));
  ['dragover', 'dragenter'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.add('drag'); }));
  ['dragleave', 'drop'].forEach(ev => dz.addEventListener(ev, e => { e.preventDefault(); dz.classList.remove('drag'); }));
  dz.addEventListener('drop', e => { const f = e.dataTransfer.files[0]; if (f) pickFile(f); });
  $('#btn-analyze').addEventListener('click', analyze);
}

function pickFile(file) {
  if (!file.type.startsWith('image/')) return toast('Selecciona una imagen válida.', 'err');
  selectedFile = file;
  $('#preview').src = URL.createObjectURL(file);
  $('#preview-wrap').classList.remove('hidden');
}

async function analyze() {
  if (!selectedFile) return;
  const btn = $('#btn-analyze');
  btn.disabled = true;
  btn.innerHTML = '<i data-lucide="loader-2" class="h-4 w-4 spin"></i> Analizando…';
  icons();
  try {
    const d = await API.detect(selectedFile);
    renderResult(d);
    toast('Análisis completado.');
  } catch (e) {
    toast(e.message, 'err');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i data-lucide="scan-search" class="h-4 w-4"></i> Analizar EPP';
    icons();
  }
}

function renderResult(d) {
  $('#result-empty').classList.add('hidden');
  const body = $('#result-body');
  body.classList.remove('hidden');
  const ok = d.compliant;
  const missing = d.missing_required.length ? d.missing_required.map(x => `<span class="chip bad">${x}</span>`).join('') : '<span class="chip ok">ninguno</span>';
  const viol = d.violations_detected.length ? d.violations_detected.map(x => `<span class="chip bad">${x}</span>`).join('') : '<span class="chip ok">ninguna</span>';
  const detected = d.detected_classes.length ? d.detected_classes.map(x => `<span class="chip">${x}</span>`).join('') : '<span class="chip">nada</span>';
  const al = d.alerta_telegram || {};
  body.innerHTML = `
    <div class="verdict ${ok ? 'ok' : 'bad'} mb-4">
      <i data-lucide="${ok ? 'shield-check' : 'shield-x'}" class="h-6 w-6"></i>
      ${ok ? 'CUMPLE con el EPP' : 'NO CUMPLE — falta EPP'}
    </div>
    <img src="${d.imagen_anotada}?t=${Date.now()}" class="rounded-xl w-full border border-white/5 mb-4" />
    <div class="space-y-3 text-sm">
      <div><p class="text-slate-400 mb-1">Falta obligatorio</p>${missing}</div>
      <div><p class="text-slate-400 mb-1">Detectado sin protección</p>${viol}</div>
      <div><p class="text-slate-400 mb-1">Clases detectadas</p>${detected}</div>
      <div class="pt-2 border-t border-white/5 text-slate-400">
        Alerta Telegram: ${al.sent ? '<span class="text-brand-400">enviada ✓</span>' : (al.reason || 'no enviada')}
      </div>
    </div>`;
  icons();
}

/* ---------- Historial ---------- */
async function loadHistory() {
  try {
    const rows = await API.history(100);
    const empty = $('#history-empty'), table = $('#history-table');
    if (!rows.length) { empty.classList.remove('hidden'); table.classList.add('hidden'); return; }
    empty.classList.add('hidden'); table.classList.remove('hidden');
    $('#history-body').innerHTML = rows.map(r => {
      const missing = JSON.parse(r.missing || '[]');
      const viol = JSON.parse(r.violations || '[]');
      const ok = r.compliant;
      return `<tr>
        <td class="py-2 pr-4"><img src="/annotated/${r.id}" class="h-10 w-14 object-cover rounded-md border border-white/5" loading="lazy" onerror="this.style.display='none'"/></td>
        <td class="py-2 pr-4 text-slate-300">${r.filename || '—'}</td>
        <td class="py-2 pr-4">${ok ? '<span class="chip ok">CUMPLE</span>' : '<span class="chip bad">VIOLACIÓN</span>'}</td>
        <td class="py-2 pr-4 text-slate-400">${missing.join(', ') || '—'}</td>
        <td class="py-2 pr-4 text-slate-400">${viol.join(', ') || '—'}</td>
        <td class="py-2 pr-4">${r.alert_sent ? '🔔' : '—'}</td>
        <td class="py-2 pr-4 text-slate-500 whitespace-nowrap">${fmtDate(r.created_at)}</td>
      </tr>`;
    }).join('');
  } catch (e) { toast(e.message, 'err'); }
}

/* ---------- Configuración ---------- */
async function loadConfig() {
  try {
    const [c, cls] = await Promise.all([API.getConfig(), API.classes()]);
    availableClasses = cls;
    $('#cfg-model').value = c.ROBOFLOW_MODEL_ID.value;
    setRange('#cfg-conf', '#cfg-conf-val', c.CONFIDENCE_THRESHOLD.value, '%');
    setRange('#cfg-overlap', '#cfg-overlap-val', c.OVERLAP_THRESHOLD.value, '%');
    setRange('#cfg-cooldown', '#cfg-cooldown-val', c.ALERT_COOLDOWN_SECONDS.value, 's');
    cfgTags.required = [...c.REQUIRED_PPE.value];
    cfgTags.ppe = [...c.PPE_CLASSES.value];
    cfgTags.violation = [...c.VIOLATION_CLASSES.value];
    renderTags();
    $('#cfg-chat').value = c.TELEGRAM_CHAT_ID.value;
    tokenIsSet = c.TELEGRAM_BOT_TOKEN.set;
    $('#token-state').textContent = tokenIsSet ? 'Token guardado · deja vacío para no cambiarlo' : 'Sin token configurado';
    $('#cfg-token').value = '';
  } catch (e) { toast(e.message, 'err'); }
}

function setRange(rangeSel, valSel, value, unit) {
  const r = $(rangeSel), v = $(valSel);
  r.value = value; v.textContent = value + unit;
  r.oninput = () => { v.textContent = r.value + unit; };
}

function optionsFor(key) {
  // Opciones del desplegable según el tipo de campo.
  const base = key === 'violation' ? availableClasses.negatives : availableClasses.positives;
  const all = base && base.length ? base : availableClasses.all;
  return all.filter(c => !cfgTags[key].includes(c)); // no mostrar las ya elegidas
}

function renderTags() {
  $$('.tagbox').forEach(box => {
    const key = box.dataset.tags;
    const isViol = key === 'violation';
    const chips = cfgTags[key].length
      ? cfgTags[key].map((t, i) =>
          `<span class="tag ${isViol ? 'viol' : ''}">${t}<button data-k="${key}" data-i="${i}" title="quitar">✕</button></span>`).join('')
      : `<span class="text-xs text-slate-500 py-1">Ninguna seleccionada</span>`;
    const opts = optionsFor(key);
    const menu = opts.length
      ? opts.map(o => `<div class="ms-opt" data-k="${key}" data-v="${o}">${o}</div>`).join('')
      : `<div class="ms-empty">No hay más clases</div>`;
    box.innerHTML = `
      <div class="ms-chips">${chips}</div>
      <div class="ms-add">
        <button type="button" class="ms-toggle" data-k="${key}"><i data-lucide="plus" class="h-3.5 w-3.5"></i> Elegir clase</button>
        <div class="ms-menu hidden" data-menu="${key}">
          ${menu}
          <div class="ms-custom">
            <input class="tag-input ms-custom-inp" data-k="${key}" placeholder="otra clase…" />
            <button type="button" class="ms-custom-add" data-k="${key}">＋</button>
          </div>
        </div>
      </div>`;
  });
  icons();
  bindTagEvents();
}

function addTag(key, val) {
  val = (val || '').trim().toLowerCase();
  if (val && !cfgTags[key].includes(val)) cfgTags[key].push(val);
  renderTags();
}

function bindTagEvents() {
  // quitar chip
  $$('.tag button').forEach(b => b.onclick = () => { cfgTags[b.dataset.k].splice(+b.dataset.i, 1); renderTags(); });
  // abrir/cerrar desplegable
  $$('.ms-toggle').forEach(b => b.onclick = e => {
    e.stopPropagation();
    const menu = $(`.ms-menu[data-menu="${b.dataset.k}"]`);
    const wasHidden = menu.classList.contains('hidden');
    $$('.ms-menu').forEach(m => m.classList.add('hidden'));
    if (wasHidden) menu.classList.remove('hidden');
  });
  // elegir opción del catálogo
  $$('.ms-opt').forEach(o => o.onclick = () => addTag(o.dataset.k, o.dataset.v));
  // añadir clase personalizada
  $$('.ms-custom-add').forEach(b => b.onclick = () => {
    const inp = $(`.ms-custom-inp[data-k="${b.dataset.k}"]`);
    addTag(b.dataset.k, inp.value);
  });
  $$('.ms-custom-inp').forEach(inp => {
    inp.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); addTag(inp.dataset.k, inp.value); } };
    inp.onclick = e => e.stopPropagation();
  });
}

// cerrar desplegables al hacer clic fuera
document.addEventListener('click', () => $$('.ms-menu').forEach(m => m.classList.add('hidden')));

async function saveConfig() {
  const payload = {
    ROBOFLOW_MODEL_ID: $('#cfg-model').value.trim(),
    CONFIDENCE_THRESHOLD: +$('#cfg-conf').value,
    OVERLAP_THRESHOLD: +$('#cfg-overlap').value,
    ALERT_COOLDOWN_SECONDS: +$('#cfg-cooldown').value,
    REQUIRED_PPE: cfgTags.required,
    PPE_CLASSES: cfgTags.ppe,
    VIOLATION_CLASSES: cfgTags.violation,
    TELEGRAM_CHAT_ID: $('#cfg-chat').value.trim(),
  };
  const token = $('#cfg-token').value.trim();
  if (token) payload.TELEGRAM_BOT_TOKEN = token; // solo si escribió uno nuevo
  try {
    await API.saveConfig(payload);
    toast('Configuración guardada.');
    loadHealth();
    loadConfig();
  } catch (e) { toast(e.message, 'err'); }
}

/* ---------- Cámara / video en vivo ---------- */
const Live = (() => {
  let stream = null, running = false, busy = false, frames = 0, viols = 0, objUrl = null;
  const grab = document.createElement('canvas');

  const el = {};
  function cache() {
    el.video = $('#live-video'); el.overlay = $('#live-overlay'); el.ph = $('#live-placeholder');
    el.verdict = $('#live-verdict'); el.frames = $('#live-frames'); el.viol = $('#live-viol');
    el.detected = $('#live-detected'); el.start = $('#live-start'); el.stop = $('#live-stop');
    el.interval = $('#live-interval'); el.intVal = $('#live-int-val');
    el.alert = $('#live-alert'); el.save = $('#live-save'); el.file = $('#live-file');
  }

  function setVerdict(text, cls) { el.verdict.className = 'status-pill ' + (cls || ''); el.verdict.textContent = text; }
  function resetStats() { frames = 0; viols = 0; el.frames.textContent = '0'; el.viol.textContent = '0'; }

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
      el.video.srcObject = stream;
      begin();
    } catch (e) {
      toast('No se pudo acceder a la cámara: ' + e.message, 'err');
    }
  }

  function startFile(file) {
    stopStream();
    objUrl = URL.createObjectURL(file);
    el.video.srcObject = null;
    el.video.src = objUrl;
    el.video.loop = true;
    el.video.play();
    begin();
  }

  function begin() {
    running = true; resetStats();
    el.ph.style.display = 'none';
    el.start.disabled = true; el.stop.disabled = false;
    setVerdict('analizando…', 'live-ok');
    el.video.onloadedmetadata = () => el.video.play();
    requestAnimationFrame(tick);
  }

  function stopStream() {
    if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
    if (objUrl) { URL.revokeObjectURL(objUrl); objUrl = null; }
  }

  function stop() {
    if (!running && !stream) return;
    running = false;
    stopStream();
    if (el.video) { el.video.pause(); el.video.srcObject = null; el.video.removeAttribute('src'); }
    if (el.overlay) el.overlay.getContext('2d').clearRect(0, 0, el.overlay.width, el.overlay.height);
    if (el.ph) el.ph.style.display = 'flex';
    if (el.start) el.start.disabled = false;
    if (el.stop) el.stop.disabled = true;
    if (el.verdict) setVerdict('detenido', '');
  }

  async function tick() {
    if (!running) return;
    const v = el.video, interval = +el.interval.value;
    if (!busy && v.readyState >= 2 && v.videoWidth) {
      busy = true;
      grab.width = v.videoWidth; grab.height = v.videoHeight;
      grab.getContext('2d').drawImage(v, 0, 0, grab.width, grab.height);
      grab.toBlob(async (blob) => {
        try {
          const d = await API.detectFrame(blob, { save: el.save.checked, alert: el.alert.checked });
          if (running) render(d);
        } catch (e) { /* frame perdido, seguimos */ }
        finally { busy = false; }
      }, 'image/jpeg', 0.7);
    }
    setTimeout(() => requestAnimationFrame(tick), interval);
  }

  function render(d) {
    frames++; el.frames.textContent = frames;
    const ok = d.compliant;
    if (!ok) { viols++; el.viol.textContent = viols; }
    setVerdict(ok ? '✅ CUMPLE' : '❌ NO CUMPLE', ok ? 'live-ok' : 'live-bad');
    el.detected.innerHTML = (d.detected_classes && d.detected_classes.length)
      ? d.detected_classes.map(c => `<span class="chip ${c.startsWith('no-') ? 'bad' : 'ok'}">${c}</span>`).join('')
      : '<span class="chip">nada</span>';
    drawBoxes(d.predictions || [], d.image || {});
  }

  function drawBoxes(preds, img) {
    const v = el.video, c = el.overlay;
    const rect = v.getBoundingClientRect();
    c.width = rect.width; c.height = rect.height;
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, c.width, c.height);
    if (!img.width || !img.height) return;
    // mapeo respetando object-fit: contain (puede haber bandas negras)
    const scale = Math.min(c.width / img.width, c.height / img.height);
    const offX = (c.width - img.width * scale) / 2;
    const offY = (c.height - img.height * scale) / 2;
    ctx.font = '600 13px Inter, sans-serif';
    preds.forEach(p => {
      const neg = p.class.toLowerCase().startsWith('no-');
      const color = neg ? '#ef4444' : '#10b981';
      const w = p.width * scale, h = p.height * scale;
      const x = offX + (p.x - p.width / 2) * scale, y = offY + (p.y - p.height / 2) * scale;
      ctx.lineWidth = 2.5; ctx.strokeStyle = color;
      ctx.strokeRect(x, y, w, h);
      const label = `${p.class} ${Math.round(p.confidence * 100)}%`;
      const tw = ctx.measureText(label).width;
      ctx.fillStyle = color;
      ctx.fillRect(x, y - 18, tw + 10, 18);
      ctx.fillStyle = '#04140d';
      ctx.fillText(label, x + 5, y - 5);
    });
  }

  function setup() {
    cache();
    el.interval.oninput = () => el.intVal.textContent = el.interval.value + ' ms';
    el.start.onclick = startCamera;
    el.stop.onclick = stop;
    el.file.onchange = () => el.file.files[0] && startFile(el.file.files[0]);
  }

  return { setup, stop };
})();

/* ---------- init ---------- */
function init() {
  $$('#nav .nav-item').forEach(b => b.addEventListener('click', () => go(b.dataset.view)));
  $('#btn-refresh').addEventListener('click', () => { loadHealth(); go($$('#nav .nav-item.active')[0].dataset.view); });
  setupInspect();
  Live.setup();
  $('#btn-save-config').addEventListener('click', saveConfig);
  $('#btn-test-telegram').addEventListener('click', async () => {
    try { const r = await API.testTelegram(); toast(r.sent ? 'Mensaje de prueba enviado ✓' : (r.reason || 'No enviado'), r.sent ? 'ok' : 'err'); }
    catch (e) { toast(e.message, 'err'); }
  });
  $('#btn-clear-history').addEventListener('click', async () => {
    if (!confirm('¿Borrar todo el historial de inspecciones?')) return;
    try { const r = await API.clearHistory(); toast(`${r.borradas} registros borrados.`); loadHistory(); } catch (e) { toast(e.message, 'err'); }
  });
  icons();
  loadHealth();
  loadDashboard();
}
document.addEventListener('DOMContentLoaded', init);
