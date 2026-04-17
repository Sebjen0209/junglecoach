// ── Config ───────────────────────────────────────────────────
const API_BASE = 'http://localhost:7429';
const POLL_INTERVAL = 5000;
const FETCH_TIMEOUT = 4000;
const LANE_ORDER = ['top', 'mid', 'bot'];
const LANE_LABELS = { top: 'TOP', mid: 'MID', bot: 'BOT' };

// Phase → human-readable status message
const PHASE_MESSAGES = {
  idle:    'Open League of Legends to begin',
  client:  'In client \u2014 enter a game',
  loading: 'Game loading\u2026',
  in_game: 'Analysing\u2026',
};

// ── State ────────────────────────────────────────────────────
const expandedLanes = new Set();
let lastData = null;

// ── DOM helpers ──────────────────────────────────────────────
const content = document.getElementById('content');

function syncHeight() {
  const app = document.getElementById('app');
  const h = Math.ceil(app.getBoundingClientRect().height);
  window.electronAPI.setHeight(h + 2);
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

// Render a phase-aware status message (no TAB instructions needed anymore —
// the backend reads data via Riot's Live Client API automatically).
function renderPhase(phase) {
  const msg = PHASE_MESSAGES[phase] || 'Waiting\u2026';
  const cls = phase === 'loading' ? ' loading' : '';
  content.innerHTML = `
    <div class="status-msg${cls}">
      <span class="ellipsis">${msg}</span>
    </div>`;
  syncHeight();
}

function renderOffline() {
  content.innerHTML = `
    <div class="status-msg offline">
      Backend offline
      <small>Run <code>python main.py</code> in <code>backend/</code></small>
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
    } else {
      // No lane data — fetch /status for a precise phase message.
      fetchStatus();
    }
  } catch {
    renderOffline();
  }
}

async function fetchStatus() {
  try {
    const res = await fetch(`${API_BASE}/status`, {
      signal: AbortSignal.timeout(FETCH_TIMEOUT),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderPhase(data.lol_phase);
  } catch {
    // /status unreachable — fall back to a generic waiting message
    renderPhase('idle');
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
