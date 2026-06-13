/* ============================================================
   Admissional Bot — Frontend SPA
   Lógica de autenticação, navegação, campanhas, envio avulso e logs.
   ============================================================ */

const API = "";          // mesma origem — FastAPI serve o HTML e a API
let TOKEN = localStorage.getItem("token") || "";

// ── Inicialização ─────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  if (TOKEN) {
    showApp();
    loadCampanhas();
  }
});

// ── Auth ──────────────────────────────────────────────────────────────────────
async function doLogin() {
  const user = document.getElementById("login-user").value.trim();
  const pass = document.getElementById("login-pass").value;
  const errEl = document.getElementById("login-error");
  errEl.style.display = "none";

  try {
    const res = await fetch(`${API}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: user, password: pass }),
    });
    if (!res.ok) throw new Error("Credenciais inválidas");
    const data = await res.json();
    TOKEN = data.token;
    localStorage.setItem("token", TOKEN);
    showApp();
    loadCampanhas();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.style.display = "block";
  }
}

function logout() {
  TOKEN = "";
  localStorage.removeItem("token");
  document.getElementById("app").style.display = "none";
  document.getElementById("login-screen").style.display = "flex";
}

function showApp() {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app").style.display = "flex";
}

// Enter no campo de senha dispara login
document.addEventListener("DOMContentLoaded", () => {
  const passEl = document.getElementById("login-pass");
  if (passEl) passEl.addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });
});

// ── Navegação ─────────────────────────────────────────────────────────────────
function navigate(el) {
  document.querySelectorAll(".nav-item").forEach(i => i.classList.remove("active"));
  el.classList.add("active");

  const page = el.dataset.page;
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.getElementById(`page-${page}`).classList.add("active");

  if (page === "campanhas") loadCampanhas();
  if (page === "logs")      loadLogs();
}

// ── Helpers HTTP ──────────────────────────────────────────────────────────────
async function apiFetch(path, opts = {}) {
  const res = await fetch(`${API}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOKEN}`,
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401) { logout(); throw new Error("Sessão expirada."); }
  return res;
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = `toast toast-${type} show`;
  setTimeout(() => t.classList.remove("show"), 3500);
}

// ── Badge de status ───────────────────────────────────────────────────────────
const STATUS_BADGE = {
  agendado:              "badge-warning",
  executando:            "badge-info",
  concluido:             "badge-success",
  concluido_com_erros:   "badge-warning",
  erro:                  "badge-danger",
  enviado:               "badge-success",
  pendente:              "badge-secondary",
};

function badge(status) {
  const cls = STATUS_BADGE[String(status).toLowerCase()] || "badge-secondary";
  return `<span class="badge ${cls}">${status}</span>`;
}

// ── Campanhas ─────────────────────────────────────────────────────────────────
async function loadCampanhas() {
  const tbody = document.getElementById("camp-tbody");
  tbody.innerHTML = `<tr><td colspan="6" class="empty">Carregando...</td></tr>`;

  try {
    const res = await apiFetch("/api/campanhas");
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    const campanhas = await res.json();

    if (!campanhas.length) {
      tbody.innerHTML = `<tr><td colspan="6" class="empty">Nenhuma campanha encontrada. Crie uma na planilha.</td></tr>`;
      return;
    }

    tbody.innerHTML = campanhas.map((c, idx) => `
      <tr>
        <td><code>${esc(c.id)}</code></td>
        <td>${esc(c.nome)}</td>
        <td>${esc(c.disparo_em)}</td>
        <td>${badge(c.status)}</td>
        <td>
          <span class="counter">${c.total_pendentes}</span>
        </td>
        <td>
          <button
            class="btn btn-sm btn-primary"
            onclick="dispararCampanha('${esc(c.id)}', this)"
            ${["executando"].includes(c.status) ? "disabled" : ""}
            title="Disparar agora (ignora o horário agendado)"
          >
            <i class="ti ti-player-play"></i> Disparar
          </button>
        </td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty error">${e.message}</td></tr>`;
  }
}

async function dispararCampanha(campanha_id, btn) {
  if (!confirm(`Disparar a campanha "${campanha_id}" agora para todos os destinatários pendentes?`)) return;

  btn.disabled = true;
  btn.innerHTML = `<i class="ti ti-loader ti-spin"></i> Enviando...`;

  try {
    const res = await apiFetch(`/api/campanhas/${encodeURIComponent(campanha_id)}/disparar`, {
      method: "POST",
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || `Erro ${res.status}`);

    showToast(
      `Campanha "${data.campanha}": ${data.enviados}/${data.total} enviadas — status: ${data.status}`,
      data.erros === 0 ? "success" : "warning"
    );
    await loadCampanhas();
  } catch (e) {
    showToast(e.message, "error");
    btn.disabled = false;
    btn.innerHTML = `<i class="ti ti-player-play"></i> Disparar`;
  }
}

// ── Envio Avulso ──────────────────────────────────────────────────────────────
async function sendSingle() {
  const phone = document.getElementById("single-phone").value.trim();
  const text  = document.getElementById("single-msg").value.trim();
  const result = document.getElementById("single-result");
  const btn = document.getElementById("btn-single-send");

  if (!phone || !text) {
    result.innerHTML = `<div class="alert alert-danger">Preencha o telefone e a mensagem.</div>`;
    return;
  }

  btn.disabled = true;
  btn.innerHTML = `<i class="ti ti-loader ti-spin"></i> Enviando...`;
  result.innerHTML = "";

  try {
    const res = await apiFetch("/api/dispatch/single", {
      method: "POST",
      body: JSON.stringify({ phone, text }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Falha no envio");

    result.innerHTML = `<div class="alert alert-success"><i class="ti ti-check"></i> Mensagem enviada com sucesso.</div>`;
    document.getElementById("single-phone").value = "";
    document.getElementById("single-msg").value = "";
    showToast("Mensagem enviada!");
  } catch (e) {
    result.innerHTML = `<div class="alert alert-danger">${e.message}</div>`;
    showToast(e.message, "error");
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="ti ti-send"></i> Enviar`;
  }
}

// ── Logs ──────────────────────────────────────────────────────────────────────
async function loadLogs() {
  const tbody = document.getElementById("logs-tbody");
  tbody.innerHTML = `<tr><td colspan="4" class="empty">Carregando...</td></tr>`;

  try {
    const res = await apiFetch("/api/logs");
    if (!res.ok) throw new Error(`Erro ${res.status}`);
    const logs = await res.json();

    if (!logs.length) {
      tbody.innerHTML = `<tr><td colspan="4" class="empty">Nenhum log registrado ainda.</td></tr>`;
      return;
    }

    tbody.innerHTML = logs.slice(0, 200).map(l => `
      <tr>
        <td>${esc(l.criado_em || "")}</td>
        <td>${esc(l.telefone  || "")}</td>
        <td class="msg-cell" title="${esc(l.mensagem || "")}">${esc((l.mensagem || "").substring(0, 60))}${(l.mensagem || "").length > 60 ? "…" : ""}</td>
        <td>${badge(l.status || "")}</td>
      </tr>
    `).join("");
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty error">${e.message}</td></tr>`;
  }
}

// ── Utilitários ───────────────────────────────────────────────────────────────
function esc(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
