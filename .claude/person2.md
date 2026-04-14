# Person 2 — Frontend / Web / Auth / Payments

You are helping **Person 2** on the JungleCoach project.
Person 2 owns the Electron overlay UI, the Next.js web app, Supabase auth, Stripe payments, and all deployment infrastructure.

Read `CLAUDE.md` first for the full project context.

---

## Your current tasks (Phase 2 — overlay UI)

### In progress
- [ ] Build Electron overlay shell (transparent window, always-on-top)
- [ ] Design 3-lane card UI with priority colours (red/yellow/grey)
- [ ] Connect overlay to local Python API on port 7429

### Up next
- [ ] Make overlay draggable and resizable
- [ ] Add settings panel (opacity, toggle on/off)
- [ ] Test on 1080p, 1440p, and ultrawide resolutions

### Done


---

## Your ownership map

```
overlay/
├── main.js              ← Electron main process (window creation, always-on-top)
├── preload.js           ← Electron preload (secure bridge to Node)
├── renderer/
│   ├── index.html       ← overlay HTML shell
│   ├── overlay.js       ← polls /analysis every 5s, updates UI
│   └── overlay.css      ← overlay styles (dark, semi-transparent)
└── package.json

web/
├── src/
│   ├── app/
│   │   ├── page.tsx             ← landing page
│   │   ├── login/page.tsx       ← login
│   │   ├── signup/page.tsx      ← signup
│   │   ├── dashboard/page.tsx   ← user dashboard
│   │   ├── settings/page.tsx    ← account settings
│   │   └── billing/page.tsx     ← subscription management
│   │
│   ├── components/
│   │   ├── LaneCard.tsx         ← single lane priority card
│   │   ├── PriorityBadge.tsx    ← red/yellow/grey badge
│   │   └── SubscriptionStatus.tsx
│   │
│   ├── lib/
│   │   ├── supabase.ts          ← Supabase client
│   │   ├── stripe.ts            ← Stripe helpers
│   │   └── api.ts               ← wrapper for backend API calls
│   │
│   └── api/
│       ├── auth/route.ts        ← auth callbacks
│       ├── stripe/webhook/route.ts  ← Stripe webhook handler
│       └── subscription/route.ts    ← check user subscription status
│
└── package.json
```

---

## The overlay — how it should look and behave

### Visual design
- Dark semi-transparent background: `rgba(10, 10, 15, 0.85)`
- Always on top of the game window
- Default position: top-right corner
- Collapsed size: ~280px wide × 160px tall (3 lane rows)
- Expandable: click a lane to see full reasoning text

### Lane card states
```
HIGH priority  → left border: #E24B4A (red),  background: rgba(226,75,74,0.08)
MEDIUM priority → left border: #EF9F27 (amber), background: rgba(239,159,39,0.08)
LOW priority   → left border: #444441 (grey),  background: transparent
```

### Polling the backend
```javascript
// overlay/renderer/overlay.js
const API_BASE = 'http://localhost:7429';

async function fetchAnalysis() {
  try {
    const res = await fetch(`${API_BASE}/analysis`);
    if (!res.ok) throw new Error('Backend not ready');
    const data = await res.json();
    renderLanes(data);
  } catch (e) {
    showStatus('Waiting for game...');
  }
}

setInterval(fetchAnalysis, 5000);
fetchAnalysis(); // immediate first call
```

### What the API returns (from Person 1's backend)
```json
{
  "game_detected": true,
  "game_minute": 12,
  "lanes": {
    "top":  { "ally": "Riven", "enemy": "Gangplank", "priority": "high",   "reason": "Riven hard counters GP early. Strong kill pressure at level 6." },
    "mid":  { "ally": "Azir",  "enemy": "Zed",       "priority": "medium", "reason": "Azir struggles early but scales. Gank to set up a 30-min win condition." },
    "bot":  { "ally": "Jinx",  "enemy": "Caitlyn",   "priority": "low",    "reason": "Even matchup. Save pressure for top or mid." }
  }
}
```

Full spec in `.claude/api-contract.md`.

---

## Supabase schema (your database)

```sql
-- Users are created automatically by Supabase Auth

-- Subscription status table
create table subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  stripe_customer_id text unique,
  stripe_subscription_id text unique,
  plan text default 'free',           -- 'free' | 'premium' | 'pro'
  status text default 'active',       -- 'active' | 'cancelled' | 'past_due'
  current_period_end timestamptz,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- Usage events (for analytics)
create table usage_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete cascade,
  event_type text,                    -- 'game_analysed' | 'overlay_opened' etc.
  metadata jsonb,
  created_at timestamptz default now()
);
```

Full schema in `.claude/data-schema.md`.

---

## Stripe setup

### Plans
| Plan | Price | Stripe Price ID |
|---|---|---|
| Free | €0 | — |
| Premium | €7.99/month | `price_premium_monthly` |
| Premium Annual | €59.99/year | `price_premium_annual` |
| Pro | €18.99/month | `price_pro_monthly` |

### Webhook events you must handle
- `checkout.session.completed` → create/update subscription row
- `customer.subscription.updated` → update plan/status
- `customer.subscription.deleted` → downgrade to free
- `invoice.payment_failed` → set status to `past_due`, send email

### Webhook handler pattern
```typescript
// web/src/api/stripe/webhook/route.ts
export async function POST(req: Request) {
  const body = await req.text();
  const sig = req.headers.get('stripe-signature')!;

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(body, sig, process.env.STRIPE_WEBHOOK_SECRET!);
  } catch (err) {
    return new Response('Webhook signature failed', { status: 400 });
  }

  switch (event.type) {
    case 'checkout.session.completed':
      await handleCheckoutComplete(event.data.object as Stripe.CheckoutSession);
      break;
    // ... other cases
  }

  return new Response('ok', { status: 200 });
}
```

---

## Auth flow — how desktop app verifies subscription

When the user logs in on the desktop app:
1. Open a browser window to `https://junglecoach.gg/app-login`
2. User logs in with Supabase Auth
3. Web page sends the session token to the local app via deep link: `junglecoach://auth?token=XXX`
4. Desktop app stores token in local secure storage (Electron keytar)
5. On each game start, app calls `GET /api/subscription` with the token
6. API returns `{ plan: "premium", valid: true }` — app unlocks premium features

---

## Running your code

```bash
# Overlay (Electron)
cd overlay
npm install
npm run dev        # starts Electron in dev mode
npm run build      # builds distributable

# Web app (Next.js)
cd web
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npm run start      # serve production build

# Test Stripe webhooks locally
stripe listen --forward-to localhost:3000/api/stripe/webhook
```

---

## How to ask Claude for help on this codebase

Good prompts:
- "I'm working on `overlay/renderer/overlay.js`. The lane cards need to animate in when priority changes from low to high. Help me add a smooth CSS transition."
- "I need to handle the `customer.subscription.deleted` Stripe webhook in `web/src/api/stripe/webhook/route.ts`. Write the handler that updates the subscriptions table in Supabase."
- "The desktop app needs to open a browser for login and receive the token back via deep link. Help me implement this in Electron's `main.js`."

Always paste the relevant file/function when asking for help — Claude has no memory between sessions.
