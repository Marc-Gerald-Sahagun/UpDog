// ── State ────────────────────────────────────────────────────────────────────
let hostsData        = [];
let selectedHostIp   = null;
let hostsChart       = null;
let hostsChartReady  = false;
let hostsInterval    = null;
let activeHours      = 24;
let activeStatus     = '';

// ── Init / teardown ───────────────────────────────────────────────────────────
async function initHostsView() {
  await loadHosts();
  if (!hostsInterval) {
    hostsInterval = setInterval(loadHosts, 30000);
  }
}

function teardownHostsView() {
  if (hostsInterval) {
    clearInterval(hostsInterval);
    hostsInterval = null;
  }
}

// ── Data ──────────────────────────────────────────────────────────────────────
async function loadHosts() {
  try {
    const res  = await fetch('/api/hosts');
    const data = await res.json();
    hostsData  = data.hosts || [];
    renderManagedHosts(getFilteredHosts());
    populateGroupFilter();
    // Refresh detail panel if a host is selected
    if (selectedHostIp) {
      const host = hostsData.find(h => h.ip === selectedHostIp);
      if (host) updateDetailInfo(host);
    }
  } catch (err) {
    console.error('Failed to load hosts:', err);
  }
}

// ── Filters ───────────────────────────────────────────────────────────────────
function getFilteredHosts() {
  const query = (document.getElementById('host-search')?.value || '').toLowerCase();
  const group = document.getElementById('group-filter')?.value || '';

  return hostsData.filter(h => {
    const matchSearch = !query ||
      h.ip.includes(query) ||
      (h.label || '').toLowerCase().includes(query) ||
      (h.hostname || '').toLowerCase().includes(query);
    const matchGroup  = !group || h.group_name === group;
    const matchStatus = !activeStatus || h.status === activeStatus;
    return matchSearch && matchGroup && matchStatus;
  });
}

function applyHostFilters() {
  renderManagedHosts(getFilteredHosts());
}

function setStatusFilter(btn, status) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeStatus = status;
  applyHostFilters();
}

function populateGroupFilter() {
  const groups  = [...new Set(hostsData.map(h => h.group_name).filter(Boolean))].sort();
  const select  = document.getElementById('group-filter');
  const current = select.value;

  select.innerHTML = '<option value="">All Groups</option>' +
    groups.map(g => `<option value="${escHtml(g)}"${g === current ? ' selected' : ''}>${escHtml(g)}</option>`).join('');

  // Populate datalist for the Add Host modal
  const dl = document.getElementById('group-datalist');
  if (dl) dl.innerHTML = groups.map(g => `<option value="${escHtml(g)}">`).join('');
}

// ── Render table ──────────────────────────────────────────────────────────────
function renderManagedHosts(hosts) {
  const tbody = document.getElementById('managed-host-table-body');

  if (!hosts || hosts.length === 0) {
    const msg = hostsData.length === 0
      ? 'No hosts yet — run a scan or add one manually'
      : 'No hosts match the current filters';
    tbody.innerHTML = `<tr><td colspan="7" class="empty-state">${msg}</td></tr>`;
    return;
  }

  tbody.innerHTML = hosts.map(host => `
    <tr onclick="selectHostDetail('${host.ip}')" data-ip="${host.ip}"
        class="${host.ip === selectedHostIp ? 'selected' : ''}">
      <td class="mono">${escHtml(host.ip)}</td>
      <td class="editable-cell" onclick="startEditField(event, '${host.ip}', 'label', ${JSON.stringify(host.label || '')})"
          title="Click to edit">${escHtml(host.label) || '<span class="muted">—</span>'}</td>
      <td class="mono muted-text">${escHtml(host.hostname || host.ip)}</td>
      <td class="editable-cell" onclick="startEditField(event, '${host.ip}', 'group_name', ${JSON.stringify(host.group_name || '')})"
          title="Click to edit">${host.group_name ? `<span class="group-tag">${escHtml(host.group_name)}</span>` : '<span class="muted">—</span>'}</td>
      <td><span class="status-badge status-${host.status}">${host.status}</span></td>
      <td>${renderUptime(host.uptime_pct)}</td>
      <td>
        <button class="icon-btn danger" title="Remove host"
          onclick="removeHost(event, '${host.ip}')">✕</button>
      </td>
    </tr>
  `).join('');
}

function renderUptime(pct) {
  if (pct == null) return '<span class="muted">—</span>';
  const color = pct >= 95 ? 'var(--green)' : pct >= 80 ? 'var(--yellow)' : 'var(--red)';
  return `<span style="color:${color};font-family:var(--font-mono)">${pct}%</span>`;
}

// ── Inline editing ────────────────────────────────────────────────────────────
function startEditField(event, ip, field, currentValue) {
  event.stopPropagation(); // don't trigger row click → selectHostDetail

  const cell = event.currentTarget;
  if (cell.querySelector('input')) return; // already editing

  const input = document.createElement('input');
  input.className   = 'inline-edit';
  input.value       = currentValue;
  input.placeholder = field === 'label' ? 'Label...' : 'Group...';
  if (field === 'group_name') {
    input.setAttribute('list', 'group-datalist');
  }

  cell.innerHTML = '';
  cell.appendChild(input);
  input.focus();
  input.select();

  async function save() {
    const value = input.value.trim();
    try {
      await fetch(`/api/hosts/${encodeURIComponent(ip)}?field=${field}&value=${encodeURIComponent(value)}`, {
        method: 'PATCH',
      });
      // Update local state
      const host = hostsData.find(h => h.ip === ip);
      if (host) host[field] = value;
      renderManagedHosts(getFilteredHosts());
      populateGroupFilter();
      if (selectedHostIp === ip) updateDetailInfo(hostsData.find(h => h.ip === ip));
    } catch (err) {
      console.error('Save failed:', err);
      renderManagedHosts(getFilteredHosts());
    }
  }

  function cancel() {
    renderManagedHosts(getFilteredHosts());
  }

  input.addEventListener('blur', save);
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter') { input.blur(); }
    if (e.key === 'Escape') { input.removeEventListener('blur', save); cancel(); }
  });
}

// ── Add host modal ────────────────────────────────────────────────────────────
function openAddHostModal() {
  document.getElementById('new-host-ip').value    = '';
  document.getElementById('new-host-label').value = '';
  document.getElementById('new-host-group').value = '';
  hideFormError();
  document.getElementById('add-host-modal').classList.remove('hidden');
  document.getElementById('new-host-ip').focus();
}

function closeAddHostModal() {
  document.getElementById('add-host-modal').classList.add('hidden');
}

function closeAddHostModalIfOutside(event) {
  if (event.target === document.getElementById('add-host-modal')) {
    closeAddHostModal();
  }
}

async function submitAddHost() {
  const ip         = document.getElementById('new-host-ip').value.trim();
  const label      = document.getElementById('new-host-label').value.trim();
  const group_name = document.getElementById('new-host-group').value.trim();

  if (!ip) { showFormError('IP address is required'); return; }

  const btn = document.getElementById('add-host-submit-btn');
  btn.disabled    = true;
  btn.textContent = 'Adding...';

  try {
    const params = new URLSearchParams({ ip });
    if (label)      params.append('label', label);
    if (group_name) params.append('group_name', group_name);

    const res = await fetch('/api/hosts?' + params.toString(), { method: 'POST' });
    if (!res.ok) {
      const data = await res.json();
      showFormError(data.detail || 'Failed to add host');
      return;
    }
    closeAddHostModal();
    await loadHosts();
  } catch (err) {
    showFormError('Network error — try again');
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Add Host';
  }
}

function showFormError(msg) {
  const el = document.getElementById('add-host-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function hideFormError() {
  document.getElementById('add-host-error').classList.add('hidden');
}

// ── Remove host ───────────────────────────────────────────────────────────────
async function removeHost(event, ip) {
  event.stopPropagation();
  if (!confirm(`Remove ${ip} from monitoring?`)) return;
  try {
    await fetch(`/api/hosts/${encodeURIComponent(ip)}`, { method: 'DELETE' });
    if (selectedHostIp === ip) {
      selectedHostIp = null;
      resetDetailPanel();
    }
    await loadHosts();
  } catch (err) {
    console.error('Remove failed:', err);
  }
}

// ── Detail panel ──────────────────────────────────────────────────────────────
async function selectHostDetail(ip) {
  selectedHostIp = ip;

  // Highlight selected row
  document.querySelectorAll('#managed-host-table-body tr').forEach(r => r.classList.remove('selected'));
  const row = document.querySelector(`#managed-host-table-body tr[data-ip="${ip}"]`);
  if (row) row.classList.add('selected');

  const host = hostsData.find(h => h.ip === ip);
  if (!host) return;

  document.getElementById('detail-host-title').textContent = host.label || host.ip;
  renderDetailPanel(host);
  await loadHistoryChart(ip, activeHours);
}

function renderDetailPanel(host) {
  const ports = (host.open_ports || [])
    .slice(0, 6)
    .map(p => `<span class="port-tag">${p.port}/${p.service}</span>`)
    .join('') || '<span class="muted">none</span>';

  const source = host.manually_added ? 'Manual' : 'Scan';

  document.getElementById('host-detail-content').innerHTML = `
    <div class="host-info-card">
      <div class="info-row"><span>IP</span><span class="mono" id="detail-ip">${escHtml(host.ip)}</span></div>
      <div class="info-row"><span>Label</span><span id="detail-label">${escHtml(host.label) || '<span class="muted">—</span>'}</span></div>
      <div class="info-row"><span>Hostname</span><span class="mono muted-text" id="detail-hostname">${escHtml(host.hostname || '—')}</span></div>
      <div class="info-row"><span>Group</span><span id="detail-group">${host.group_name ? `<span class="group-tag">${escHtml(host.group_name)}</span>` : '<span class="muted">—</span>'}</span></div>
      <div class="info-row"><span>Status</span><span><span class="status-badge status-${host.status}" id="detail-status">${host.status}</span></span></div>
      <div class="info-row"><span>Open Ports</span><span id="detail-ports">${ports}</span></div>
      <div class="info-row"><span>Source</span><span class="muted" id="detail-source">${source}</span></div>
    </div>
    <div class="time-range-tabs">
      <button class="tab-btn${activeHours === 1   ? ' active' : ''}" onclick="changeHistoryRange(1)">1h</button>
      <button class="tab-btn${activeHours === 24  ? ' active' : ''}" onclick="changeHistoryRange(24)">24h</button>
      <button class="tab-btn${activeHours === 168 ? ' active' : ''}" onclick="changeHistoryRange(168)">7d</button>
    </div>
    <div class="chart-wrap">
      <canvas id="hosts-latency-chart"></canvas>
    </div>
  `;

  hostsChartReady = false;
  hostsChart      = null;
}

function updateDetailInfo(host) {
  const ipEl     = document.getElementById('detail-ip');
  if (!ipEl) return; // panel not rendered yet
  const labelEl  = document.getElementById('detail-label');
  const groupEl  = document.getElementById('detail-group');
  const statusEl = document.getElementById('detail-status');

  if (labelEl)  labelEl.innerHTML  = escHtml(host.label) || '<span class="muted">—</span>';
  if (groupEl)  groupEl.innerHTML  = host.group_name ? `<span class="group-tag">${escHtml(host.group_name)}</span>` : '<span class="muted">—</span>';
  if (statusEl) { statusEl.className = `status-badge status-${host.status}`; statusEl.textContent = host.status; }
}

function resetDetailPanel() {
  document.getElementById('detail-host-title').textContent = '— select a host —';
  document.getElementById('host-detail-content').innerHTML = '<div class="detail-placeholder">Click a host to view details</div>';
  hostsChart      = null;
  hostsChartReady = false;
}

// ── History chart ─────────────────────────────────────────────────────────────
async function changeHistoryRange(hours) {
  activeHours = hours;
  document.querySelectorAll('.tab-btn').forEach(b => {
    b.classList.toggle('active', parseInt(b.textContent) === hours ||
      (b.textContent === '7d' && hours === 168));
  });
  if (selectedHostIp) await loadHistoryChart(selectedHostIp, hours);
}

async function loadHistoryChart(ip, hours) {
  try {
    const res  = await fetch(`/api/hosts/${encodeURIComponent(ip)}/history?hours=${hours}`);
    const data = await res.json();

    const labels = data.latency.map(d => {
      const date = new Date(d.timestamp * 1000);
      if (hours <= 1)   return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      if (hours <= 24)  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' +
             date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const values = data.latency.map(d => d.latency_ms);

    const canvas = document.getElementById('hosts-latency-chart');
    if (!canvas) return;

    if (!hostsChartReady || !hostsChart) {
      if (hostsChart) { hostsChart.destroy(); hostsChart = null; }
      hostsChart = new Chart(canvas.getContext('2d'), {
        type: 'line',
        data: {
          labels,
          datasets: [{
            label: 'Latency (ms)',
            data: values,
            borderColor: '#58a6ff',
            backgroundColor: 'rgba(88,166,255,0.08)',
            borderWidth: 1.5,
            pointRadius: 2,
            pointHoverRadius: 4,
            tension: 0.3,
            fill: true,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 200 },
          scales: {
            x: {
              ticks: { color: '#8b949e', font: { family: 'IBM Plex Mono', size: 10 }, maxTicksLimit: 8 },
              grid:  { color: 'rgba(33,38,45,0.8)' }
            },
            y: {
              ticks: { color: '#8b949e', font: { family: 'IBM Plex Mono', size: 10 } },
              grid:  { color: 'rgba(33,38,45,0.8)' },
              beginAtZero: true
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#161b22',
              borderColor: '#21262d',
              borderWidth: 1,
              titleFont: { family: 'IBM Plex Mono' },
              bodyFont:  { family: 'IBM Plex Mono' },
              callbacks: { label: ctx => ` ${ctx.parsed.y} ms` }
            }
          }
        }
      });
      hostsChartReady = true;
    } else {
      hostsChart.data.labels              = labels;
      hostsChart.data.datasets[0].data    = values;
      hostsChart.update();
    }
  } catch (err) {
    console.error('Failed to load host history:', err);
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
