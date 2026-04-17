// ── Config ───────────────────────────────────────────────────
const API_BASE = 'http://localhost:7429';
const POLL_INTERVAL = 5000;
const FETCH_TIMEOUT = 4000;
const LANE_ORDER = ['top', 'mid', 'bot'];
const LANE_LABELS = { top: 'TOP', mid: 'MID', bot: 'BOT' };

// ── State ────────────────────────────────────────────────────
const expandedLanes = new Set();
// Hold the last successful data so click-to-expand still works between polls
let lastData = null;

// ── DOM helpers ──────────────────────────────────────────────
const content = document.getElementById('content');

function syncHeight() {
  const app = document.getElementById('app');
  const h = Math.ceil(app.getBoundingClientRect().height);
  window.electronAPI.setHeight(h + 2); // +2 for border
}

// ── Rendering ────────────────────────────────────────────────
function renderLanes(data) {
  lastData = data;

  const lanesHTML = LANE_ORDER.map((lane) => {
    const info = data.lanes[lane];
    if (!info) return '';

    const priority = (info.priority || 'low').toLowerCase();
    const isExpanded = expandedLanes.has(lane);
    const winPct = info.matchup_winrate != null
      ? `${Math.round(info.matchup_winrate * 100)}%`
      : '';

    return `
      <div class="lane-card priority-${priority}${isExpanded ? ' expanded' : ''}" data-lane="${lane}">
        <div class="lane-row">
          <span class="lane-label">${LANE_LABELS[lane]}</span>
          <span class="matchup">
            <span class="ally">${escapeHtml(info.ally_champion)}</span>
            <span class="vs">vs</span>
            <span class="enemy">${escapeHtml(info.enemy_champion)}</span>
          </span>
          <span class="right-group">
            ${winPct ? `<span class="winrate">${winPct}</span>` : ''}
            <span class="priority-badge badge-${priority}">${priority.toUpperCase()}</span>
          </span>
        </div>
        ${isExpanded && info.reason
          ? `<div class="reason-text">${escapeHtml(info.reason)}</div>`
          : ''}
      </div>`;
  }).join('');

  const minuteHTML = data.game_minute != null
    ? `<span class="meta-item">Min&nbsp;${data.game_minute}</span>` : '';
  const patchHTML = data.patch
    ? `<span class="meta-item">Patch&nbsp;${escapeHtml(data.patch)}</span>` : '';

  content.innerHTML = `
    ${(minuteHTML || patchHTML) ? `<div class="meta-row">${minuteHTML}${patchHTML}</div>` : ''}
    <div class="lanes">${lanesHTML}</div>
    <div class="hint">Click a lane to see reasoning</div>
  `;

  // Attach click handlers after rendering
  content.querySelectorAll('.lane-card').forEach((card) => {
    card.addEventListener('click', () => {
      const lane = card.dataset.lane;
      if (expandedLanes.has(lane)) {
        expandedLanes.delete(lane);
      } else {
        expandedLanes.add(lane);
      }
      renderLanes(lastData);
    });
  });

  syncHeight();
}

function renderScanning() {
  content.innerHTML = `
    <div class="status-msg">
      <span class="ellipsis">Game detected &mdash; hold TAB to scan</span>
    </div>`;
  syncHeight();
}

function renderWaiting() {
  content.innerHTML = `
    <div class="status-msg">
      <span class="ellipsis">Waiting for game</span>
    </div>`;
  syncHeight();
}

function renderOffline() {
  content.innerHTML = `
    <div class="status-msg offline">
      Backend offline
      <small>Run <code>python backend/main.py</code> to start</small>
    </div>`;
  syncHeight();
}

// ── Polling ──────────────────────────────────────────────────
async function fetchAnalysis() {
  try {
    const res = await fetch(`${API_BASE}/analysis`, {
      signal: AbortSignal.timeout(FETCH_TIMEOUT),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    if (data.game_detected && data.lanes) {
      renderLanes(data);
    } else if (data.game_detected) {
      renderScanning();
    } else {
      renderWaiting();
    }
  } catch {
    renderOffline();
  }
}

// ── Window controls ──────────────────────────────────────────
document.getElementById('btn-close').addEventListener('click', () => {
  window.electronAPI.closeWindow();
});
document.getElementById('btn-minimize').addEventListener('click', () => {
  window.electronAPI.minimizeWindow();
});

// ── Utilities ────────────────────────────────────────────────
function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Boot ─────────────────────────────────────────────────────
fetchAnalysis();
setInterval(fetchAnalysis, POLL_INTERVAL);
