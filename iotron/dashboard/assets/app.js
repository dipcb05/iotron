const state = {
  token: window.localStorage.getItem('iotron.operatorToken') || '',
  data: null,
  activeTab: 'devices',
  search: '',
  scope: 'all',
};

async function loadDashboard() {
  const dataResponse = await fetch('/dashboard/data');
  state.data = await dataResponse.json();

  const [alerts, logs, traces, security, jobs] = await Promise.all([
    fetchProtected('/alerts', []),
    fetchProtected('/logs?limit=25', []),
    fetchProtected('/traces?limit=25', []),
    fetchProtected('/security/metadata', state.data.security || {}),
    fetchProtected('/jobs', []),
  ]);

  state.data.alerts = alerts;
  state.data.logs = logs;
  state.data.traces = traces;
  state.data.security = security;
  state.data.jobs = jobs;

  renderSummary(state.data.summary);
  renderProjectState(state.data.status);
  renderBoards(state.data.boards);
  renderMapList('protocols', state.data.protocols);
  renderMapList('networks', state.data.networks);
  renderPackages(state.data.packages);
  renderSecurity(state.data.security, state.data.tenants, state.data.notification_channels);
  renderWorkspace();
  syncAuthState();
}

async function fetchProtected(path, fallback) {
  try {
    const headers = state.token ? { Authorization: `Bearer ${state.token}` } : {};
    const response = await fetch(path, { headers });
    if (!response.ok) {
      return fallback;
    }
    return await response.json();
  } catch {
    return fallback;
  }
}

function renderSummary(summary) {
  const host = document.getElementById('summary-grid');
  const items = [
    ['Board', summary.selected_board || 'Not selected'],
    ['Packages', String(summary.package_count)],
    ['Devices', String(summary.device_count)],
    ['Protocols', String(summary.protocol_count)],
    ['Networks', String(summary.network_count)],
    ['Toolchains', String(summary.toolchain_count)],
    ['Dashboard', summary.dashboard_enabled ? 'Enabled' : 'Disabled'],
    ['Alerts', String((state.data.alerts || []).length)],
  ];
  host.innerHTML = items.map(([label, value]) => `
    <article class="summary-card">
      <p>${label}</p>
      <h3>${escapeHtml(value)}</h3>
    </article>
  `).join('');
}

function renderProjectState(status) {
  document.getElementById('project-state').textContent = JSON.stringify(status, null, 2);
}

function renderBoards(boards) {
  const host = document.getElementById('boards');
  host.innerHTML = boards.map((board) => `<span class="chip">${escapeHtml(`${board.family}:${board.name}`)}</span>`).join('');
}

function renderMapList(id, items) {
  const host = document.getElementById(id);
  host.innerHTML = Object.entries(items).map(([name, meta]) => `
    <div class="list-item muted-item">
      <strong>${escapeHtml(name)}</strong>
      <small>${escapeHtml(meta.description)}</small>
    </div>
  `).join('');
}

function renderPackages(packages) {
  const host = document.getElementById('packages');
  host.innerHTML = packages.map((item) => `
    <div class="list-item compact-row">
      <strong>${escapeHtml(item.name)}</strong>
      <small>${escapeHtml(item.version)}</small>
    </div>
  `).join('');
}

function renderSecurity(security, tenants, channels) {
  const securityHost = document.getElementById('security-overview');
  securityHost.innerHTML = [
    `OIDC configured: ${security.oidc?.configured ? 'yes' : 'no'}`,
    `Secret sources: ${(security.secret_sources || []).join(', ') || 'environment'}`,
    `Auth modes: ${(security.auth_modes || []).join(', ')}`,
    `RBAC roles: ${(security.rbac_policies || []).map((item) => item.role).join(', ')}`,
  ].map((line) => `<div class="list-item muted-item"><small>${escapeHtml(line)}</small></div>`).join('');

  document.getElementById('tenants').innerHTML = (tenants || [])
    .map((item) => `<span class="chip">${escapeHtml(item.tenant_id)}</span>`)
    .join('');

  document.getElementById('notification-channels').innerHTML = (channels || []).map((item) => `
    <div class="list-item compact-row">
      <strong>${escapeHtml(item.channel_type)}</strong>
      <small>${escapeHtml(item.target)}</small>
    </div>
  `).join('');
}

function renderWorkspace() {
  const views = {
    devices: state.data.devices || [],
    deployments: state.data.deployments || [],
    alerts: state.data.alerts || [],
    logs: state.data.logs || [],
    traces: state.data.traces || [],
    toolchains: state.data.toolchains || [],
  };
  const currentItems = applyFilters(views[state.activeTab] || [], state.activeTab);
  const host = document.getElementById('active-list');
  host.innerHTML = currentItems.map((item, index) => buildWorkspaceCard(item, state.activeTab, index)).join('') || '<div class="list-item">No items match the current filters.</div>';
  document.querySelectorAll('.workspace-card').forEach((node) => {
    node.addEventListener('click', () => showDetail(currentItems[Number(node.dataset.index)], state.activeTab));
  });
  if (currentItems.length > 0) {
    showDetail(currentItems[0], state.activeTab);
  }
  renderWorkflowActions();
}

function applyFilters(items, view) {
  return items.filter((item) => {
    if (state.scope !== 'all' && state.scope !== view) {
      return false;
    }
    if (!state.search) {
      return true;
    }
    return JSON.stringify(item).toLowerCase().includes(state.search.toLowerCase());
  });
}

function buildWorkspaceCard(item, view, index) {
  const title = getPrimaryLabel(item, view);
  const subtitle = getSecondaryLabel(item, view);
  const badge = getBadgeLabel(item, view);
  return `
    <button class="list-item workspace-card" data-index="${index}">
      <div>
        <strong>${escapeHtml(title)}</strong>
        <small>${escapeHtml(subtitle)}</small>
      </div>
      <span class="chip emphasis-chip">${escapeHtml(badge)}</span>
    </button>
  `;
}

function getPrimaryLabel(item, view) {
  const mapping = {
    devices: item.device_id,
    deployments: item.deployment_id,
    alerts: item.message,
    logs: item.event,
    traces: item.name,
    toolchains: item.name,
  };
  return mapping[view] || view;
}

function getSecondaryLabel(item, view) {
  const mapping = {
    devices: `${item.board} ${item.protocol || 'no-protocol'} ${item.network || 'no-network'}`,
    deployments: `${item.operation} ${item.board} ${item.status}`,
    alerts: `${item.severity} ${item.type}`,
    logs: `${item.level} ${item.timestamp}`,
    traces: `${item.status} ${item.started_at}`,
    toolchains: item.summary,
  };
  return mapping[view] || JSON.stringify(item);
}

function getBadgeLabel(item, view) {
  const mapping = {
    devices: item.last_seen || 'registered',
    deployments: item.stage || item.status,
    alerts: item.severity,
    logs: item.level,
    traces: item.status,
    toolchains: item.available ? 'available' : 'missing',
  };
  return mapping[view] || 'detail';
}

function showDetail(item, view) {
  document.getElementById('detail-view').textContent = JSON.stringify({ view, item }, null, 2);
}

function renderWorkflowActions() {
  const actions = [
    ['Validate hardware', 'POST /project/hardware-validate'],
    ['Dispatch alerts', 'POST /alerts/dispatch'],
    ['Rotate tokens', 'POST /auth/revoke + POST /auth/token'],
    ['Backup runtime', 'POST /backups'],
    ['Review traces', 'GET /traces'],
  ];
  document.getElementById('workflow-actions').innerHTML = actions.map(([name, route]) => `
    <div class="workflow-item">
      <strong>${escapeHtml(name)}</strong>
      <small>${escapeHtml(route)}</small>
    </div>
  `).join('');
}

function syncAuthState() {
  const badge = document.getElementById('auth-status');
  badge.textContent = state.token ? 'Operator token loaded' : 'Anonymous';
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function bindEvents() {
  document.getElementById('refresh').addEventListener('click', loadDashboard);
  document.getElementById('save-token').addEventListener('click', () => {
    state.token = document.getElementById('token-input').value.trim();
    window.localStorage.setItem('iotron.operatorToken', state.token);
    loadDashboard();
  });
  document.getElementById('clear-token').addEventListener('click', () => {
    state.token = '';
    document.getElementById('token-input').value = '';
    window.localStorage.removeItem('iotron.operatorToken');
    loadDashboard();
  });
  document.getElementById('search-input').addEventListener('input', (event) => {
    state.search = event.target.value;
    renderWorkspace();
  });
  document.getElementById('scope-filter').addEventListener('change', (event) => {
    state.scope = event.target.value;
    renderWorkspace();
  });
  document.querySelectorAll('.tab-button').forEach((node) => {
    node.addEventListener('click', () => {
      document.querySelectorAll('.tab-button').forEach((button) => button.classList.remove('active'));
      node.classList.add('active');
      state.activeTab = node.dataset.tab;
      renderWorkspace();
    });
  });
}

window.addEventListener('DOMContentLoaded', () => {
  document.getElementById('token-input').value = state.token;
  bindEvents();
  loadDashboard();
});

