const API = window.location.origin + '/api';
let TOKEN = localStorage.getItem('adm_token') || '';
let allCandidatos = [];
let allAgendamentos = [];
let allLogs = [];

// ── AUTH ────────────────────────────────────────────────────────────────────

async function doLogin() {
  const user = document.getElementById('login-user').value.trim();
  const pass = document.getElementById('login-pass').value.trim();
  const err  = document.getElementById('login-error');
  err.style.display = 'none';

  try {
    const res = await apiFetch('/auth/login', 'POST', { username: user, password: pass }, false);
    TOKEN = res.token;
    localStorage.setItem('adm_token', TOKEN);
    showApp();
  } catch (e) {
    err.textContent = 'Usuário ou senha inválidos.';
    err.style.display = 'block';
  }
}

function logout() {
  TOKEN = '';
  localStorage.removeItem('adm_token');
  document.getElementById('app').style.display = 'none';
  document.getElementById('login-screen').style.display = 'flex';
}

function showApp() {
  document.getElementById('login-screen').style.display = 'none';
  document.getElementById('app').style.display = 'flex';
  loadDashboard();
}

// ── API ──────────────────────────────────────────────────────────────────────

async function apiFetch(path, method = 'GET', body = null, auth = true) {
  const headers = { 'Content-Type': 'application/json' };
  if (auth && TOKEN) headers['Authorization'] = `Bearer ${TOKEN}`;
  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (res.status === 401) { logout(); throw new Error('Unauthorized'); }
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── NAVIGATION ───────────────────────────────────────────────────────────────

function navigate(el) {
  event.preventDefault();
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  el.classList.add('active');
  const page = el.dataset.page;
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + page).classList.add('active');
  if (page === 'dashboard')    loadDashboard();
  if (page === 'candidatos')   loadCandidatos();
  if (page === 'agendamentos') loadAgendamentos();
  if (page === 'disparos')     loadDispatchPreview();
  if (page === 'logs')         loadLogs();
}

// ── DASHBOARD ────────────────────────────────────────────────────────────────

async function loadDashboard() {
  try {
    const data = await apiFetch('/dashboard');
    renderMetrics(data.metrics);
    renderDashTable(data.proximos);
  } catch (e) {
    toast('Erro ao carregar dashboard: ' + e.message, true);
  }
}

function renderMetrics(m) {
  const grid = document.getElementById('metrics-grid');
  grid.innerHTML = `
    <div class="metric-card">
      <div class="metric-label">Total de candidatos</div>
      <div class="metric-value">${m.total}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Pendentes</div>
      <div class="metric-value warning">${m.pendentes}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Agendados</div>
      <div class="metric-value accent">${m.agendados}</div>
    </div>
    <div class="metric-card">
      <div class="metric-label">Realizados</div>
      <div class="metric-value success">${m.realizados}</div>
    </div>
  `;
}

function renderDashTable(rows) {
  const tbody = document.getElementById('dash-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">Nenhuma admissão nos próximos 7 dias.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.nome || ''}</td>
      <td>${r.cargo || ''}</td>
      <td>${r.data_admissao || ''}</td>
      <td>${badge(r.status)}</td>
    </tr>
  `).join('');
}

// ── CANDIDATOS ───────────────────────────────────────────────────────────────

async function loadCandidatos() {
  try {
    allCandidatos = await apiFetch('/candidatos');
    renderCandidatos(allCandidatos);
  } catch (e) {
    toast('Erro ao carregar candidatos: ' + e.message, true);
  }
}

function renderCandidatos(rows) {
  const tbody = document.getElementById('cand-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">Nenhum candidato encontrado.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map((r, i) => `
    <tr>
      <td>${r.nome || ''}</td>
      <td>${r.cpf || ''}</td>
      <td>${r.telefone || ''}</td>
      <td>${r.cargo || ''}</td>
      <td>${r.data_admissao || ''}</td>
      <td>${badge(r.status)}</td>
      <td>
        <div class="actions">
          <button class="btn btn-sm btn-outline" onclick='editCandidato(${JSON.stringify(r)}, ${i})'>
            <i class="ti ti-edit"></i>
          </button>
          <button class="btn btn-sm btn-outline" onclick="deleteCandidato(${i})" style="color:var(--danger)">
            <i class="ti ti-trash"></i>
          </button>
        </div>
      </td>
    </tr>
  `).join('');
}

function filterCandidatos() {
  const q = document.getElementById('search-candidatos').value.toLowerCase();
  const s = document.getElementById('filter-status-cand').value;
  const filtered = allCandidatos.filter(r => {
    const match = !q || (r.nome||'').toLowerCase().includes(q)
      || (r.cpf||'').includes(q) || (r.cargo||'').toLowerCase().includes(q);
    const statusMatch = !s || r.status === s;
    return match && statusMatch;
  });
  renderCandidatos(filtered);
}

function openModal(id) {
  document.getElementById(id).style.display = 'flex';
}
function closeModal(id) {
  document.getElementById(id).style.display = 'none';
}

function editCandidato(r, idx) {
  document.getElementById('modal-cand-title').textContent = 'Editar candidato';
  document.getElementById('cand-row-index').value = idx;
  document.getElementById('cand-nome').value     = r.nome || '';
  document.getElementById('cand-cpf').value      = r.cpf || '';
  document.getElementById('cand-telefone').value = r.telefone || '';
  document.getElementById('cand-cargo').value    = r.cargo || '';
  document.getElementById('cand-gestor').value   = r.gestor || '';
  document.getElementById('cand-data').value     = r.data_admissao || '';
  document.getElementById('cand-status').value   = r.status || 'pendente';
  openModal('modal-candidato');
}

async function saveCandidato() {
  const idx = document.getElementById('cand-row-index').value;
  const payload = {
    nome:         document.getElementById('cand-nome').value.trim(),
    cpf:          document.getElementById('cand-cpf').value.trim(),
    telefone:     document.getElementById('cand-telefone').value.trim(),
    cargo:        document.getElementById('cand-cargo').value.trim(),
    gestor:       document.getElementById('cand-gestor').value.trim(),
    data_admissao: document.getElementById('cand-data').value.trim(),
    status:       document.getElementById('cand-status').value,
  };
  try {
    if (idx === '') {
      await apiFetch('/candidatos', 'POST', payload);
      toast('Candidato adicionado.');
    } else {
      await apiFetch('/candidatos/' + idx, 'PUT', payload);
      toast('Candidato atualizado.');
    }
    closeModal('modal-candidato');
    loadCandidatos();
  } catch (e) {
    toast('Erro ao salvar: ' + e.message, true);
  }
}

async function deleteCandidato(idx) {
  if (!confirm('Remover este candidato da planilha?')) return;
  try {
    await apiFetch('/candidatos/' + idx, 'DELETE');
    toast('Candidato removido.');
    loadCandidatos();
  } catch (e) {
    toast('Erro ao remover: ' + e.message, true);
  }
}

// ── AGENDAMENTOS ─────────────────────────────────────────────────────────────

async function loadAgendamentos() {
  try {
    allAgendamentos = await apiFetch('/agendamentos');
    renderAgendamentos(allAgendamentos);
  } catch (e) {
    toast('Erro ao carregar agendamentos: ' + e.message, true);
  }
}

function renderAgendamentos(rows) {
  const tbody = document.getElementById('agend-tbody');
  if (!rows || rows.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="empty">Nenhum agendamento encontrado.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${r.telefone || ''}</td>
      <td>${r.data || ''}</td>
      <td>${r.horario || ''}</td>
      <td>${r.local || ''}</td>
      <td>${badge(r.status)}</td>
      <td style="color:var(--text-2)">${r.criado_em || ''}</td>
    </tr>
  `).join('');
}

function filterAgendamentos() {
  const q = document.getElementById('search-agend').value.toLowerCase();
  const s = document.getElementById('filter-status-agend').value;
  const filtered = allAgendamentos.filter(r => {
    const match = !q || (r.telefone||'').includes(q);
    const statusMatch = !s || r.status === s;
    return match && statusMatch;
  });
  renderAgendamentos(filtered);
}

// ── DISPAROS ─────────────────────────────────────────────────────────────────

async function loadDispatchPreview() {
  const el = document.getElementById('dispatch-preview');
  el.innerHTML = '<span class="skeleton-line"></span>';
  try {
    const data = await apiFetch('/dispatch/preview');
    el.textContent = `${data.count} candidato(s) serão notificados.`;
  } catch (e) {
    el.textContent = 'Não foi possível carregar a prévia.';
  }
}

async function runDispatch() {
  const result = document.getElementById('dispatch-result');
  result.innerHTML = '<span style="color:var(--text-2)">Disparando...</span>';
  try {
    const data = await apiFetch('/dispatch/run', 'POST');
    result.innerHTML = `<div class="alert alert-success">${data.enviados} mensagem(ns) enviada(s), ${data.erros} erro(s).</div>`;
    toast('Disparo concluído.');
  } catch (e) {
    result.innerHTML = `<div class="alert alert-danger">Erro: ${e.message}</div>`;
  }
}

async function sendSingle() {
  const phone = document.getElementById('single-phone').value.trim();
  const msg   = document.getElementById('single-msg').value.trim();
  const result = document.getElementById('single-result');
  if (!phone || !msg) { toast('Preencha telefone e mensagem.', true); return; }
  result.innerHTML = '<span style="color:var(--text-2)">Enviando...</span>';
  try {
    await apiFetch('/dispatch/single', 'POST', { phone, text: msg });
    result.innerHTML = '<div class="alert alert-success">Mensagem enviada.</div>';
    toast('Enviado.');
  } catch (e) {
    result.innerHTML = `<div class="alert alert-danger">Erro: ${e.message}</div>`;
  }
}

// ── LOGS ──────────────────────────────────────────────────────────────────────

async function loadLogs() {
  try {
    allLogs = await apiFetch('/logs');
    const tbody = document.getElementById('logs-tbody');
    if (!allLogs || allLogs.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="empty">Nenhum log encontrado.</td></tr>';
      return;
    }
    tbody.innerHTML = allLogs.map(r => `
      <tr>
        <td style="white-space:nowrap;color:var(--text-2)">${r.criado_em || ''}</td>
        <td>${r.telefone || ''}</td>
        <td style="max-width:340px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="${(r.mensagem||'').replace(/"/g,'&quot;')}">${r.mensagem || ''}</td>
        <td>${badge(r.status)}</td>
      </tr>
    `).join('');
  } catch (e) {
    toast('Erro ao carregar logs: ' + e.message, true);
  }
}

// ── HELPERS ───────────────────────────────────────────────────────────────────

function badge(status) {
  const s = (status || 'pendente').toLowerCase();
  return `<span class="badge badge-${s}">${s}</span>`;
}

function toast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.background = isError ? 'var(--danger)' : 'var(--text)';
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3000);
}

// ── INIT ──────────────────────────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  if (e.key === 'Enter' && document.getElementById('login-screen').style.display !== 'none') doLogin();
});

if (TOKEN) {
  showApp();
} else {
  document.getElementById('login-screen').style.display = 'flex';
}
