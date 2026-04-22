// ── Config ───────────────────────────────────────────────────
const API_BASE        = 'http://localhost:7429';
const SUPABASE_URL    = 'https://qoxflvsmytpkbcxxpaxw.supabase.co';
const SUPABASE_ANON   = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFveGZsdnNteXRwa2JjeHhwYXh3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYyMTYzMTYsImV4cCI6MjA5MTc5MjMxNn0.AXmbjEdaka14XU29CdWPFlMLAIRuh6Tl8mwvb8XBW_k';
const FETCH_TIMEOUT   = 4000;

// Free tier polls every 10s; Premium/Pro every 5s.
function getPollInterval() {
  return userPlan === 'free' ? 10_000 : 5_000;
}
const LANE_ORDER      = ['top', 'mid', 'bot'];
const LANE_LABELS     = { top: 'TOP', mid: 'MID', bot: 'BOT' };

const PHASE_MESSAGES = {
  idle:    'Open League of Legends to begin',
  client:  'In client — enter a game',
  loading: 'Game loading…',
  in_game: 'Analysing…',
};

// ── State ────────────────────────────────────────────────────
let authToken     = null;
let userPlan      = 'free';
let pollTimer     = null;
const expandedLanes = new Set();
let lastData      = null;

// ── DOM ──────────────────────────────────────────────────────
const content    = document.getElementById('content');
const btnAccount = document.getElementById('btn-account');

function syncHeight() {
  const app = document.getElementById('app');
  const h = Math.ceil(app.getBoundingClientRect().height);
  window.electronAPI.setHeight(h + 2);
}

// ── Auth ─────────────────────────────────────────────────────
async function boot() {
  const stored = await window.electronAPI.getToken();
  if (stored) {
    const sub = await checkSubscription(stored);
    if (sub && sub.valid) {
      authToken = stored;
      userPlan  = sub.plan ?? 'free';
      showAccountBadge();
      startPolling();
    } else {
      await window.electronAPI.clearToken();
      renderLogin();
    }
  } else {
    renderLogin();
  }
}

async function checkSubscription(token) {
  try {
    // Decode the user ID from the JWT payload (no library needed — it's just base64url)
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    const userId  = payload.sub;
    if (!userId) return null;

    const res = await fetch(
      `${SUPABASE_URL}/rest/v1/subscriptions?user_id=eq.${userId}&select=plan,status,current_period_end&limit=1`,
      {
        headers: {
          apikey:        SUPABASE_ANON,
          Authorization: `Bearer ${token}`,
        },
        signal: AbortSignal.timeout(FETCH_TIMEOUT),
      }
    );
    if (!res.ok) return null;

    const rows = await res.json();
    const sub  = rows[0] ?? null;

    // If the JWT is valid (Supabase returned 200), the user can always use the overlay.
    // A cancelled/expired subscription degrades to free rather than blocking login.
    const activePlan = sub?.status === 'active' ? (sub.plan ?? 'free') : 'free';
    return {
      plan:       activePlan,
      valid:      true,
      expires_at: sub?.current_period_end ?? null,
    };
  } catch {
    return null;
  }
}

function showAccountBadge() {
  btnAccount.textContent = userPlan.toUpperCase();
  btnAccount.style.display = '';
}

async function handleSignOut() {
  await window.electronAPI.clearToken();
  authToken = null;
  userPlan  = 'free';
  btnAccount.style.display = 'none';
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  expandedLanes.clear();
  lastData = null;
  renderLogin();
}

btnAccount.addEventListener('click', handleSignOut);

// ── Login screen ─────────────────────────────────────────────
function renderLogin(error) {
  content.innerHTML = `
    <div class="login-form">
      <p class="login-label">Sign in to JungleCoach</p>
      ${error ? `<p class="login-error">${escapeHtml(error)}</p>` : ''}
      <input id="inp-email"    class="login-input" type="email"    placeholder="Email"    autocomplete="email" />
      <input id="inp-password" class="login-input" type="password" placeholder="Password" autocomplete="current-password" />
      <button id="btn-login" class="login-btn">Sign in</button>
    </div>`;
  syncHeight();

  const btnLogin   = document.getElementById('btn-login');
  const inpPassword = document.getElementById('inp-password');

  btnLogin.addEventListener('click', handleLogin);
  inpPassword.addEventListener('keydown', (e) => { if (e.key === 'Enter') handleLogin(); });
}

async function handleLogin() {
  const email    = document.getElementById('inp-email').value.trim();
  const password = document.getElementById('inp-password').value;
  const btn      = document.getElementById('btn-login');

  if (!email || !password) return;

  btn.textContent = 'Signing in…';
  btn.disabled    = true;

  try {
    const res  = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
      method: 'POST',
      headers: { apikey: SUPABASE_ANON, 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    const data = await res.json();

    if (!res.ok) {
      renderLogin(data.error_description || data.msg || 'Login failed — check your credentials');
      return;
    }

    authToken = data.access_token;
    await window.electronAPI.saveToken(authToken);

    const sub = await checkSubscription(authToken);
    userPlan  = sub?.plan ?? 'free';

    showAccountBadge();
    startPolling();
  } catch {
    renderLogin('Connection error — try again');
  }
}

// ── Polling ──────────────────────────────────────────────────
function startPolling() {
  fetchAnalysis();
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(fetchAnalysis, getPollInterval());
}

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
    renderPhase('idle');
  }
}

// ── Rendering ────────────────────────────────────────────────
function renderLanes(data) {
  lastData = data;
  const isPremium = userPlan === 'premium' || userPlan === 'pro';

  const lanesHTML = LANE_ORDER.map((lane) => {
    const info = data.lanes[lane];
    if (!info) return '';

    const priority   = (info.priority || 'low').toLowerCase();
    const isExpanded = expandedLanes.has(lane);
    const winPct     = info.matchup_winrate != null
      ? `${Math.round(info.matchup_winrate * 100)}%`
      : '';

    let reasonHTML = '';
    if (isExpanded) {
      if (isPremium && info.reason) {
        reasonHTML = `<div class="reason-text">${escapeHtml(info.reason)}</div>`;
      } else if (!isPremium) {
        reasonHTML = `<div class="reason-text upgrade-msg">Upgrade to Premium for AI reasoning</div>`;
      }
    }

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
        ${reasonHTML}
      </div>`;
  }).join('');

  const minuteHTML = data.game_minute != null
    ? `<span class="meta-item">Min&nbsp;${data.game_minute}</span>` : '';
  const patchHTML = data.patch
    ? `<span class="meta-item">Patch&nbsp;${escapeHtml(data.patch)}</span>` : '';
  const refreshHTML = `<span class="meta-item meta-refresh">${isPremium ? '5s' : '10s'}</span>`;

  const hintText = isPremium
    ? 'Click a lane for AI reasoning'
    : 'Upgrade for 5s refresh &amp; reasoning';

  content.innerHTML = `
    <div class="meta-row">${minuteHTML}${patchHTML}<span class="meta-spacer"></span>${refreshHTML}</div>
    <div class="lanes">${lanesHTML}</div>
    <div class="hint">${hintText}</div>
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

function renderPhase(phase) {
  const msg = PHASE_MESSAGES[phase] || 'Waiting…';
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
boot();
