async function loadDashboard() {
  const response = await fetch('/dashboard/data');
  const data = await response.json();

  renderSummary(data.summary);
  document.getElementById('project-state').textContent = JSON.stringify(data.status, null, 2);
  renderToolchains(data.toolchains);
  renderBoards(data.boards);
  renderMapList('protocols', data.protocols);
  renderMapList('networks', data.networks);
}

function renderSummary(summary) {
  const host = document.getElementById('summary-grid');
  const items = [
    ['Board', summary.selected_board || 'Not selected'],
    ['Packages', String(summary.package_count)],
    ['Protocols', String(summary.protocol_count)],
    ['Networks', String(summary.network_count)],
    ['Toolchains', String(summary.toolchain_count)],
    ['Dashboard', summary.dashboard_enabled ? 'Enabled' : 'Disabled'],
  ];
  host.innerHTML = items
    .map(([label, value]) => `
      <article class="summary-card">
        <h3>${value}</h3>
        <p>${label}</p>
      </article>
    `)
    .join('');
}

function renderToolchains(toolchains) {
  const host = document.getElementById('toolchains');
  host.innerHTML = toolchains
    .map(
      (item) => `
        <div class="list-item">
          <strong>${item.name}</strong>
          <small>${item.summary}</small>
          <div class="chip-list" style="margin-top:0.7rem;">
            <span class="chip">${item.available ? 'available' : 'not on PATH'}</span>
            ${item.executables.map((value) => `<span class="chip">${value}</span>`).join('')}
          </div>
        </div>
      `,
    )
    .join('');
}

function renderBoards(boards) {
  const host = document.getElementById('boards');
  host.innerHTML = boards
    .map((board) => `<span class="chip">${board.family}:${board.name}</span>`)
    .join('');
}

function renderMapList(id, items) {
  const host = document.getElementById(id);
  host.innerHTML = Object.entries(items)
    .map(
      ([name, meta]) => `
        <div class="list-item">
          <strong>${name}</strong>
          <small>${meta.description}</small>
        </div>
      `,
    )
    .join('');
}

document.getElementById('refresh').addEventListener('click', loadDashboard);
window.addEventListener('DOMContentLoaded', loadDashboard);
