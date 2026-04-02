// State
let latencyChart = null;
let selectedHost = null;
let statusInterval = null;

// ── Chart setup ──────────────────────────────────────────────
function initChart() {
  const ctx = document.getElementById('latency-chart').getContext('2d');
  latencyChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [{
        label: 'Latency (ms)',
        data: [],
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
      animation: { duration: 300 },
      scales: {
        x: {
          ticks: { color: '#8b949e', font: { family: 'IBM Plex Mono', size: 10 }, maxTicksLimit: 8 },
          grid: { color: 'rgba(33,38,45,0.8)' }
        },
        y: {
          ticks: { color: '#8b949e', font: { family: 'IBM Plex Mono', size: 10 } },
          grid: { color: 'rgba(33,38,45,0.8)' },
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
          bodyFont: { family: 'IBM Plex Mono' },
          callbacks: {
            label: ctx => ` ${ctx.parsed.y} ms`
          }
        }
      }
    }
  });
}

// ── Scan ─────────────────────────────────────────────────────
async function runScan() {
  const subnet = document.getElementById('subnet-input').value.trim() || '192.168.1.0/24';
  const btn = document.getElementById('scan-btn');

  btn.disabled = true;
  btn.textContent = 'Scanning...';
  showOverlay();

  try {
    const res = await fetch(`/api/scan?subnet=${encodeURIComponent(subnet)}`);
    const data = await res.json();
    renderHosts(data.hosts);
    updateStats(data.hosts);
    startStatusPolling();
  } catch (err) {
    console.error('Scan failed:', err);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Scan Network';
    hideOverlay();
  }
}

// ── Host table ───────────────────────────────────────────────
function renderHosts(hosts) {
  const tbody = document.getElementById('host-table-body');

  if (!hosts || hosts.length === 0) {
    tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No hosts found on that subnet</td></tr>';
    return;
  }

  tbody.innerHTML = hosts.map(host => `
    <tr onclick="selectHost('${host.ip}', this)" data-ip="${host.ip}">
      <td>${host.ip}</td>
      <td>${host.hostname !== host.ip ? host.hostname : '<span style="color:var(--muted)">—</span>'}</td>
      <td><span class="status-badge status-${host.status}">${host.status}</span></td>
      <td>${host.latency_ms != null ? host.latency_ms + ' ms' : '<span style="color:var(--muted)">—</span>'}</td>
      <td>${renderPorts(host.open_ports)}</td>
    </tr>
  `).join('');
}

function renderPorts(ports) {
  if (!ports || ports.length === 0) return '<span style="color:var(--muted)">none</span>';
  return ports.slice(0, 4).map(p => `<span class="port-tag">${p.port}/${p.service}</span>`).join('') +
    (ports.length > 4 ? ` <span style="color:var(--muted);font-size:0.68rem">+${ports.length - 4}</span>` : '');
}

// ── Stats bar ────────────────────────────────────────────────
function updateStats(hosts) {
  const up = hosts.filter(h => h.status === 'up').length;
  const down = hosts.filter(h => h.status === 'down').length;
  const latencies = hosts.filter(h => h.latency_ms != null).map(h => h.latency_ms);
  const avg = latencies.length ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(1) : '--';

  document.getElementById('hosts-up').textContent = up;
  document.getElementById('hosts-down').textContent = down;
  document.getElementById('avg-latency').textContent = avg !== '--' ? avg + ' ms' : '--';
  document.getElementById('total-hosts').textContent = hosts.length;
}

// ── Host selection + latency chart ───────────────────────────
async function selectHost(ip, row) {
  selectedHost = ip;

  document.querySelectorAll('.host-table tbody tr').forEach(r => r.classList.remove('selected'));
  row.classList.add('selected');

  document.getElementById('chart-title').textContent = `Latency — ${ip}`;

  await loadLatencyChart(ip);
}

async function loadLatencyChart(ip) {
  try {
    const res = await fetch(`/api/latency/${ip}`);
    const data = await res.json();

    const labels = data.latency.map(d => {
      const date = new Date(d.timestamp * 1000);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    });
    const values = data.latency.map(d => d.latency_ms);

    latencyChart.data.labels = labels;
    latencyChart.data.datasets[0].data = values;
    latencyChart.update();
  } catch (err) {
    console.error('Failed to load latency:', err);
  }
}

// ── Live status polling ───────────────────────────────────────
function startStatusPolling() {
  if (statusInterval) clearInterval(statusInterval);
  statusInterval = setInterval(async () => {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.hosts && data.hosts.length > 0) {
        updateStats(data.hosts);
        updateTableStatus(data.hosts);
        if (selectedHost) await loadLatencyChart(selectedHost);
      }
      document.getElementById('last-updated').textContent =
        new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (err) {
      console.error('Status poll failed:', err);
    }
  }, 30000);
}

function updateTableStatus(hosts) {
  hosts.forEach(host => {
    const row = document.querySelector(`tr[data-ip="${host.ip}"]`);
    if (!row) return;
    const badge = row.querySelector('.status-badge');
    const latencyCell = row.cells[3];
    if (badge) {
      badge.className = `status-badge status-${host.status}`;
      badge.textContent = host.status;
    }
    if (latencyCell) {
      latencyCell.textContent = host.latency_ms != null ? host.latency_ms + ' ms' : '—';
    }
  });
}

// ── Overlay ───────────────────────────────────────────────────
function showOverlay() {
  let overlay = document.getElementById('scan-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'scan-overlay';
    overlay.className = 'scanning-overlay';
    overlay.innerHTML = '<div class="spinner"></div><span>Scanning network...</span>';
    document.body.appendChild(overlay);
  }
  overlay.classList.add('active');
}

function hideOverlay() {
  const overlay = document.getElementById('scan-overlay');
  if (overlay) overlay.classList.remove('active');
}

// ── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initChart();
  document.getElementById('subnet-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') runScan();
  });
});