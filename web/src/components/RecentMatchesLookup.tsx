"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  fetchMatchHistory,
  requestAnalysis,
  type MatchEntry,
  type ParticipantSummary,
  type PlayerProfile,
} from "@/lib/cloud-api";

// ─── Constants ───────────────────────────────────────────────────────────────

const REGIONS = [
  { value: "europe", label: "EU" },
  { value: "americas", label: "NA/BR" },
  { value: "asia", label: "KR/JP" },
  { value: "sea", label: "SEA/OCE" },
];

const SPELL_KEYS: Record<number, string> = {
  1: "SummonerBoost", 3: "SummonerExhaust", 4: "SummonerFlash",
  6: "SummonerHaste", 7: "SummonerHeal", 11: "SummonerSmite",
  12: "SummonerTeleport", 13: "SummonerMana", 14: "SummonerDot",
  21: "SummonerBarrier", 32: "SummonerSnowball",
};

const ROLE_ABBR: Record<string, string> = {
  TOP: "TOP", JUNGLE: "JGL", MIDDLE: "MID", BOTTOM: "BOT", UTILITY: "SUP",
};

const TIER_COLOR: Record<string, string> = {
  IRON: "#8a8a8a", BRONZE: "#c08050", SILVER: "#a8b8c8",
  GOLD: "#d4a017", PLATINUM: "#39b8ae", EMERALD: "#50c878",
  DIAMOND: "#7ec8e3", MASTER: "#a560cf", GRANDMASTER: "#e05c5c",
  CHALLENGER: "#f4c842",
};

// ─── URL helpers ─────────────────────────────────────────────────────────────

const champTile = (n: string) =>
  `https://ddragon.leagueoflegends.com/cdn/img/champion/tiles/${n}_0.jpg`;
const itemImg = (v: string, id: number) =>
  `https://ddragon.leagueoflegends.com/cdn/${v}/img/item/${id}.png`;
const spellImg = (v: string, id: number) => {
  const k = SPELL_KEYS[id];
  return k ? `https://ddragon.leagueoflegends.com/cdn/${v}/img/spell/${k}.png` : null;
};
const profileIconImg = (v: string, id: number) =>
  `https://ddragon.leagueoflegends.com/cdn/${v}/img/profileicon/${id}.png`;
const rankEmblemImg = (v: string, tier: string) => {
  const t = tier.charAt(0) + tier.slice(1).toLowerCase();
  return `https://ddragon.leagueoflegends.com/cdn/${v}/img/emblem/Emblem_${t}.png`;
};

// ─── Formatters ──────────────────────────────────────────────────────────────

const fmtDur = (s: number) => `${Math.floor(s / 60)}:${(s % 60).toString().padStart(2, "0")}`;
const fmtDate = (ms: number) =>
  new Date(ms).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
const fmtK = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
const kda = (k: number, d: number, a: number) =>
  d === 0 ? "Perfect" : ((k + a) / d).toFixed(2);

// ─── Tiny atoms ──────────────────────────────────────────────────────────────

function DDImg({
  src, alt = "", w, h, className = "", dim = false,
}: { src: string; alt?: string; w: number; h: number; className?: string; dim?: boolean }) {
  return (
    <div
      className={`overflow-hidden flex-shrink-0${dim ? " opacity-50" : ""} ${className}`}
      style={{ width: w, height: h, background: "rgba(26,26,74,0.9)" }}
    >
      <img
        src={src} alt={alt} className="w-full h-full object-cover"
        onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
      />
    </div>
  );
}

function EmptySlot({ w, h, dim }: { w: number; h: number; dim?: boolean }) {
  return (
    <div
      className={`rounded flex-shrink-0${dim ? " opacity-30" : " opacity-40"}`}
      style={{ width: w, height: h, background: "rgba(26,26,74,0.5)" }}
    />
  );
}

function SpellPair({ sp1, sp2, ddv, size }: { sp1: number; sp2: number; ddv: string; size: number }) {
  return (
    <div className="flex flex-col gap-0.5 flex-shrink-0">
      {[sp1, sp2].map((id, i) => {
        const src = spellImg(ddv, id);
        return src
          ? <DDImg key={i} src={src} w={size} h={size} className="rounded-sm" />
          : <EmptySlot key={i} w={size} h={size} />;
      })}
    </div>
  );
}

function Items({
  items, trinket, ddv, size,
}: { items: number[]; trinket: number | null; ddv: string; size: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {items.map((id, i) => (
        <DDImg key={i} src={itemImg(ddv, id)} w={size} h={size} className="rounded" />
      ))}
      {Array.from({ length: Math.max(0, 6 - items.length) }).map((_, i) => (
        <EmptySlot key={`e${i}`} w={size} h={size} />
      ))}
      <div className="w-px mx-1 self-stretch" style={{ background: "rgba(26,26,74,0.8)" }} />
      {trinket != null
        ? <DDImg src={itemImg(ddv, trinket)} w={size} h={size} className="rounded" dim />
        : <EmptySlot w={size} h={size} dim />}
    </div>
  );
}

// ─── Player profile card ─────────────────────────────────────────────────────

function PlayerProfileCard({ profile, ddv }: { profile: PlayerProfile; ddv: string }) {
  const r = profile.ranked_solo;
  const winRate = r ? Math.round((r.wins / (r.wins + r.losses)) * 100) : null;
  const tierColor = r ? (TIER_COLOR[r.tier] ?? "#7986cb") : "#7986cb";

  return (
    <div
      className="rounded-xl p-5 border flex items-center gap-5 flex-wrap"
      style={{
        background: "rgba(13,13,43,0.8)",
        borderColor: "rgba(80,90,180,0.3)",
        backdropFilter: "blur(16px)",
      }}
    >
      {/* Profile icon + level */}
      <div className="relative flex-shrink-0">
        <DDImg
          src={profileIconImg(ddv, profile.profile_icon_id)}
          alt="Profile icon"
          w={64} h={64}
          className="rounded-xl"
        />
        <span
          className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 sub-heading text-[9px] tracking-wide px-1.5 rounded-full border font-bold"
          style={{
            background: "rgba(8,8,24,0.95)",
            borderColor: "rgba(80,90,180,0.5)",
            color: "#c5cae9",
            whiteSpace: "nowrap",
          }}
        >
          {profile.summoner_level}
        </span>
      </div>

      {/* Name */}
      <div className="flex-shrink-0">
        <p className="text-base font-bold" style={{ color: "#f0f2ff" }}>
          {profile.summoner_name}
        </p>
        <p className="sub-heading text-[9px] tracking-widest mt-0.5" style={{ color: "#7986cb" }}>
          SUMMONER
        </p>
      </div>

      {/* Divider */}
      <div className="w-px self-stretch hidden sm:block" style={{ background: "rgba(80,90,180,0.2)" }} />

      {/* Rank */}
      {r ? (
        <div className="flex items-center gap-4">
          <DDImg
            src={rankEmblemImg(ddv, r.tier)}
            alt={r.tier}
            w={56} h={56}
            className="rounded-lg"
          />
          <div>
            <p className="text-sm font-bold" style={{ color: tierColor }}>
              {r.tier} {r.rank}
            </p>
            <p className="text-xs font-mono mt-0.5" style={{ color: "#c5cae9" }}>
              {r.lp} LP
            </p>
            <p className="text-xs mt-0.5" style={{ color: "#7986cb" }}>
              <span style={{ color: "#00e564" }}>{r.wins}W</span>
              {" · "}
              <span style={{ color: "#ff3366" }}>{r.losses}L</span>
              {" · "}
              <span style={{ color: winRate && winRate >= 50 ? "#00e564" : "#c5cae9" }}>
                {winRate}% WR
              </span>
            </p>
          </div>
        </div>
      ) : (
        <div>
          <p className="text-sm" style={{ color: "#7986cb" }}>Unranked</p>
          <p className="text-xs mt-0.5" style={{ color: "#7986cb" }}>Solo / Duo</p>
        </div>
      )}
    </div>
  );
}

// ─── Scoreboard participant row ───────────────────────────────────────────────

function ParticipantRow({
  p, ddv, maxDmg,
}: { p: ParticipantSummary; ddv: string; maxDmg: number }) {
  const dmgPct = maxDmg > 0 ? (p.damage_dealt / maxDmg) * 100 : 0;
  const pos = ROLE_ABBR[p.position] ?? "—";

  return (
    <div
      className="flex items-center rounded-lg"
      style={
        p.is_self
          ? { background: "rgba(0,200,255,0.07)", borderLeft: "3px solid #00e5ff" }
          : { background: "rgba(255,255,255,0.03)", borderLeft: "3px solid transparent" }
      }
    >
      {/* Champion + name + role */}
      <div className="flex items-center gap-2.5 px-3 py-2.5 w-[210px] flex-shrink-0">
        <DDImg src={champTile(p.champion)} alt={p.champion} w={36} h={36} className="rounded-md flex-shrink-0" />
        <div className="min-w-0">
          <div
            className="text-sm font-medium truncate leading-snug"
            style={{ color: p.is_self ? "#67e8f9" : "#e8eaf6", maxWidth: 110 }}
            title={p.summoner_name}
          >
            {p.summoner_name.split("#")[0]}
          </div>
          <div className="text-xs leading-snug mt-0.5" style={{ color: "#6b7280" }}>
            {pos}
          </div>
        </div>
      </div>

      {/* KDA */}
      <div className="w-[110px] flex-shrink-0 px-3">
        <div className="text-sm font-semibold leading-snug">
          <span style={{ color: "#e8eaf6" }}>{p.kills}</span>
          <span style={{ color: "#374151" }}> / </span>
          <span style={{ color: "#f87171" }}>{p.deaths}</span>
          <span style={{ color: "#374151" }}> / </span>
          <span style={{ color: "#e8eaf6" }}>{p.assists}</span>
        </div>
        <div className="text-xs mt-0.5 leading-snug" style={{ color: "#6b7280" }}>
          {kda(p.kills, p.deaths, p.assists)} KDA
        </div>
      </div>

      {/* CS */}
      <div className="w-[72px] flex-shrink-0 px-3">
        <div className="text-sm font-semibold leading-snug" style={{ color: "#e8eaf6" }}>{p.cs}</div>
        <div className="text-xs mt-0.5 leading-snug" style={{ color: "#6b7280" }}>CS</div>
      </div>

      {/* Damage + bar */}
      <div className="w-[130px] flex-shrink-0 px-3">
        <div className="text-sm font-medium leading-snug" style={{ color: "#e8eaf6" }}>
          {fmtK(p.damage_dealt)}
        </div>
        <div className="h-1.5 rounded-full mt-1" style={{ background: "rgba(255,255,255,0.07)" }}>
          <div className="h-full rounded-full" style={{ width: `${dmgPct}%`, background: "#f87171" }} />
        </div>
      </div>

      {/* Items */}
      <div className="flex-1 px-3 py-2.5 min-w-0">
        <Items items={p.items} trinket={p.trinket} ddv={ddv} size={22} />
      </div>
    </div>
  );
}

// ─── Scoreboard ──────────────────────────────────────────────────────────────

function Scoreboard({
  participants, ddv, userTeamId, userWon,
}: { participants: ParticipantSummary[]; ddv: string; userTeamId: number; userWon: boolean }) {
  const teams = [
    { id: userTeamId, won: userWon, label: "Your Team" },
    { id: userTeamId === 100 ? 200 : 100, won: !userWon, label: "Enemy Team" },
  ];

  return (
    <div className="space-y-5">
      {teams.map(({ id, won, label }) => {
        const members = participants.filter(p => p.team_id === id);
        const maxDmg = Math.max(...members.map(p => p.damage_dealt), 1);
        const teamAccent = won ? "#4ade80" : "#f87171";

        return (
          <div key={id}>
            {/* Team label */}
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold uppercase tracking-wide" style={{ color: teamAccent }}>
                {label}
              </span>
              <span className="text-xs" style={{ color: "#4b5563" }}>
                — {won ? "Victory" : "Defeat"}
              </span>
            </div>

            {/* Column headers */}
            <div className="flex items-center text-xs mb-1.5" style={{ color: "#6b7280" }}>
              <div className="w-[3px] flex-shrink-0" />
              <div className="w-[210px] flex-shrink-0 pl-3">Player</div>
              <div className="w-[110px] flex-shrink-0 pl-3">KDA</div>
              <div className="w-[72px] flex-shrink-0 pl-3">CS</div>
              <div className="w-[130px] flex-shrink-0 pl-3">Damage</div>
              <div className="flex-1 pl-3">Items</div>
            </div>

            <div className="overflow-x-auto">
              <div className="space-y-0.5" style={{ minWidth: 580 }}>
                {members.map((p, i) => (
                  <ParticipantRow key={i} p={p} ddv={ddv} maxDmg={maxDmg} />
                ))}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─── Match card ───────────────────────────────────────────────────────────────

function MatchCard({
  match, ddv, onAnalyse, analysing,
}: { match: MatchEntry; ddv: string; onAnalyse: (id: string) => void; analysing: string | null }) {
  const [expanded, setExpanded] = useState(false);
  const win = match.win;
  const accent = win ? "#00e564" : "#ff3366";
  const csPerMin = (match.cs / (match.game_duration_seconds / 60)).toFixed(1);
  const kpPct = Math.round(match.kill_participation * 100);
  const isAnalysing = analysing === match.match_id;
  const userTeamId = match.participants.find(p => p.is_self)?.team_id ?? 100;

  return (
    <div
      className="rounded-xl overflow-hidden"
      style={{
        background: win ? "rgba(0,35,18,0.85)" : "rgba(38,0,15,0.85)",
        border: `1px solid ${win ? "rgba(0,229,100,0.25)" : "rgba(255,51,102,0.25)"}`,
        backdropFilter: "blur(12px)",
      }}
    >
      {/* ── Main row ── */}
      <div className="flex items-center gap-4 px-4" style={{ minHeight: 68 }}>

        {/* Champion + spells */}
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <DDImg src={champTile(match.champion)} alt={match.champion} w={48} h={48} className="rounded-lg" />
          <SpellPair sp1={match.summoner_spell_1} sp2={match.summoner_spell_2} ddv={ddv} size={21} />
        </div>

        {/* Champion name + outcome + time */}
        <div className="w-[160px] flex-shrink-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm font-semibold leading-tight" style={{ color: "#e8eaf6" }}>{match.champion}</span>
            {match.position && (
              <span className="text-xs px-1.5 py-px rounded font-medium" style={{ background: "rgba(121,134,203,0.15)", color: "#9ca3af" }}>
                {ROLE_ABBR[match.position] ?? match.position}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-sm font-semibold" style={{ color: accent }}>{win ? "Victory" : "Defeat"}</span>
            <span className="text-xs" style={{ color: "#6b7280" }}>{fmtDur(match.game_duration_seconds)} · {fmtDate(match.game_start_timestamp)}</span>
          </div>
        </div>

        {/* KDA */}
        <div className="w-[140px] flex-shrink-0">
          <div className="leading-tight">
            <span className="text-lg font-bold" style={{ color: "#e8eaf6" }}>{match.kills}</span>
            <span className="text-base mx-0.5" style={{ color: "#374151" }}>/</span>
            <span className="text-lg font-bold" style={{ color: "#f87171" }}>{match.deaths}</span>
            <span className="text-base mx-0.5" style={{ color: "#374151" }}>/</span>
            <span className="text-lg font-bold" style={{ color: "#e8eaf6" }}>{match.assists}</span>
          </div>
          <div className="text-xs mt-0.5" style={{ color: "#6b7280" }}>{kda(match.kills, match.deaths, match.assists)} KDA</div>
        </div>

        {/* CS + KP */}
        <div className="flex gap-5 flex-shrink-0">
          <div>
            <div className="text-sm font-semibold" style={{ color: "#e8eaf6" }}>{match.cs}</div>
            <div className="text-xs" style={{ color: "#6b7280" }}>{csPerMin}/m</div>
          </div>
          <div>
            <div className="text-sm font-semibold" style={{ color: win ? "#4ade80" : "#9ca3af" }}>{kpPct}%</div>
            <div className="text-xs" style={{ color: "#6b7280" }}>KP</div>
          </div>
        </div>

        {/* Items */}
        <div className="flex-1 min-w-0">
          <Items items={match.items} trinket={match.trinket} ddv={ddv} size={26} />
        </div>

        {/* Action + expand toggle */}
        <div className="flex-shrink-0 flex flex-col items-center gap-1.5 pr-1">
          {match.has_analysis ? (
            <a
              href={`/dashboard/post-analysis/${encodeURIComponent(match.match_id)}`}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border whitespace-nowrap"
              style={{ background: "rgba(0,229,255,0.06)", borderColor: "rgba(0,229,255,0.2)", color: "#67e8f9" }}
            >
              View ↗
            </a>
          ) : (
            <button
              onClick={() => onAnalyse(match.match_id)}
              disabled={analysing !== null}
              className="text-xs font-medium px-3 py-1.5 rounded-lg border disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 whitespace-nowrap"
              style={{ background: "rgba(0,229,255,0.06)", borderColor: "rgba(0,229,255,0.2)", color: "#67e8f9" }}
            >
              {isAnalysing
                ? <><span className="w-2.5 h-2.5 border border-[#67e8f9]/30 border-t-[#67e8f9] rounded-full animate-spin" />Analysing…</>
                : "Analyse"}
            </button>
          )}
          <button
            onClick={() => setExpanded(v => !v)}
            className="flex items-center justify-center w-full transition-opacity hover:opacity-100 opacity-50"
            aria-label={expanded ? "Hide scoreboard" : "Show scoreboard"}
          >
            <span style={{ color: "#9ca3af", fontSize: 10 }}>{expanded ? "▲" : "▼"}</span>
          </button>
        </div>
      </div>

      {/* Scoreboard */}
      {expanded && (
        <div className="px-3 pt-3 pb-4 border-t" style={{ borderColor: "rgba(255,255,255,0.06)", background: "rgba(0,0,0,0.3)" }}>
          <Scoreboard participants={match.participants} ddv={ddv} userTeamId={userTeamId} userWon={win} />
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export function RecentMatchesLookup() {
  const router = useRouter();
  const [summonerName, setSummonerName] = useState("");
  const [region, setRegion] = useState("europe");
  const [loading, setLoading] = useState(false);
  const [analysing, setAnalysing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{
    matches: MatchEntry[];
    ddVersion: string;
    profile: PlayerProfile | null;
  } | null>(null);
  const [resolvedSummoner, setResolvedSummoner] = useState("");

  async function handleLookup(e: React.FormEvent) {
    e.preventDefault();
    if (!summonerName.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await fetchMatchHistory(summonerName.trim(), region);
      setResult({
        matches: data.matches,
        ddVersion: data.ddragon_version,
        profile: data.player_profile,
      });
      setResolvedSummoner(summonerName.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load match history");
    } finally {
      setLoading(false);
    }
  }

  async function handleAnalyse(matchId: string) {
    setAnalysing(matchId);
    setError(null);
    try {
      await requestAnalysis(matchId, resolvedSummoner);
      router.push(`/dashboard/post-analysis/${encodeURIComponent(matchId)}`);
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
      setAnalysing(null);
    }
  }

  return (
    <div className="space-y-4">
      {/* Search */}
      <form onSubmit={handleLookup} className="flex gap-3 flex-wrap items-end">
        <div className="flex-1 min-w-[200px] space-y-1.5">
          <label className="sub-heading text-[10px] tracking-widest" style={{ color: "#7986cb" }}>RIOT ID</label>
          <input
            type="text"
            value={summonerName}
            onChange={e => setSummonerName(e.target.value)}
            placeholder="Name#EUW"
            disabled={loading}
            className="w-full rounded-lg px-3 py-2.5 text-sm focus:outline-none"
            style={{ background: "rgba(8,8,24,0.8)", border: "1px solid rgba(26,26,74,0.8)", color: "#e8eaf6" }}
            onFocus={e => (e.currentTarget.style.borderColor = "rgba(0,229,255,0.4)")}
            onBlur={e => (e.currentTarget.style.borderColor = "rgba(26,26,74,0.8)")}
          />
        </div>
        <div className="space-y-1.5">
          <label className="sub-heading text-[10px] tracking-widest" style={{ color: "#7986cb" }}>REGION</label>
          <select
            value={region}
            onChange={e => setRegion(e.target.value)}
            disabled={loading}
            className="rounded-lg px-3 py-2.5 text-sm focus:outline-none"
            style={{ background: "rgba(8,8,24,0.8)", border: "1px solid rgba(26,26,74,0.8)", color: "#e8eaf6" }}
          >
            {REGIONS.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
          </select>
        </div>
        <button
          type="submit"
          disabled={loading || !summonerName.trim()}
          className="btn-arcane disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
        >
          {loading
            ? <><span className="w-3.5 h-3.5 border-2 border-[#080818]/30 border-t-[#080818] rounded-full animate-spin" />Loading…</>
            : "Look up"}
        </button>
      </form>

      {error && <p className="text-sm" style={{ color: "#ff3366" }}>{error}</p>}

      {/* Profile card */}
      {result?.profile && (
        <PlayerProfileCard profile={result.profile} ddv={result.ddVersion} />
      )}

      {/* Match list */}
      {result !== null && result.matches.length === 0 && (
        <p className="text-sm" style={{ color: "#7986cb" }}>No recent ranked matches found.</p>
      )}
      {result !== null && result.matches.length > 0 && (
        <div className="space-y-2">
          {result.matches.map(match => (
            <MatchCard
              key={match.match_id}
              match={match}
              ddv={result.ddVersion}
              onAnalyse={handleAnalyse}
              analysing={analysing}
            />
          ))}
        </div>
      )}
    </div>
  );
}
