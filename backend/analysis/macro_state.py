"""Macro game-state classifier and prompt context builder.

Once any outer tower falls (or the game passes 20 minutes), the jungler's
optimal decisions shift from gank priority to objective control and vision.
This module determines the current mode and builds the structured context
block that the cloud API feeds to Claude for macro awareness hints.

Riot compliance note: hints are framed as awareness and context, never as
direct instructions. Players make their own decisions.
"""

from capture.live_client import GameSnapshot, MacroSnapshot


def is_macro_mode(snapshot: GameSnapshot) -> bool:
    """Return True when the game has left the laning phase.

    Macro mode activates when any outer tower has fallen on either side, or
    when the game clock passes 20 minutes (baron spawns regardless of towers).
    """
    if snapshot.game_time_seconds >= 20 * 60:
        return True
    macro = snapshot.macro
    return any(macro.ally_outer_down.values()) or any(macro.enemy_outer_down.values())


def macro_state_key(snapshot: GameSnapshot) -> str:
    """Build a compact string key used for cache invalidation.

    The key changes whenever a tower falls, a dragon or baron is killed, or
    the baron countdown crosses a meaningful threshold — triggering a fresh
    cloud API call for updated hints.
    """
    m = snapshot.macro
    # Round baron_spawn_in to nearest 30s so minor clock drift doesn't bust the cache.
    baron_bucket = (
        int((m.baron_spawn_in or 0) // 30) if m.baron_spawn_in is not None else -1
    )
    dragon_bucket = (
        int((m.dragon_spawn_in or 0) // 30) if m.dragon_spawn_in is not None else -1
    )
    return (
        f"ao:{m.ally_outer_down}|eo:{m.enemy_outer_down}"
        f"|ad:{m.ally_dragon_stacks}|ed:{m.enemy_dragon_stacks}"
        f"|db:{dragon_bucket}|bb:{baron_bucket}"
    )


def build_macro_context(snapshot: GameSnapshot) -> str:
    """Build the structured game-state block sent to Claude as the user message.

    Keeps raw data (timers, stacks, tower states) tightly formatted so the
    prompt stays within token limits while giving Claude enough context to
    produce specific, non-generic awareness points.
    """
    macro = snapshot.macro
    game_sec = snapshot.game_time_seconds
    game_min = int(game_sec // 60)
    game_s   = int(game_sec % 60)

    lines: list[str] = [
        f"Game time: {game_min:02d}:{game_s:02d}",
        f"Your side: {snapshot.ally_team}",
        "",
        "Tower status (outer towers only):",
    ]

    for lane in ("top", "mid", "bot"):
        ally_status  = "DOWN" if macro.ally_outer_down[lane]  else "standing"
        enemy_status = "DOWN" if macro.enemy_outer_down[lane] else "standing"
        lines.append(f"  {lane.title()}: yours {ally_status}, enemy {enemy_status}")

    lines += ["", "Objectives:"]

    # Dragon
    if macro.dragon_spawn_in is None:
        dragon_line = "Dragon is alive on the map now"
    elif macro.dragon_spawn_in < 1:
        dragon_line = "Dragon just spawned"
    else:
        dm, ds = int(macro.dragon_spawn_in // 60), int(macro.dragon_spawn_in % 60)
        dragon_line = f"Dragon spawns in {dm}:{ds:02d}"
    lines.append(
        f"  Dragon: {dragon_line} | Stacks — you: {macro.ally_dragon_stacks}, "
        f"enemy: {macro.enemy_dragon_stacks}"
    )

    # Baron
    if game_sec < 20 * 60:
        remaining = (20 * 60) - game_sec
        bm, bs = int(remaining // 60), int(remaining % 60)
        baron_line = f"Baron not yet spawned — spawns in {bm}:{bs:02d}"
    elif macro.baron_spawn_in is None:
        baron_line = "Baron is alive on the map now"
    elif macro.baron_spawn_in < 1:
        baron_line = "Baron just respawned"
    else:
        bm, bs = int(macro.baron_spawn_in // 60), int(macro.baron_spawn_in % 60)
        baron_line = f"Baron respawns in {bm}:{bs:02d}"
    lines.append(f"  Baron: {baron_line}")

    # Herald
    herald_line = (
        "Rift Herald available"
        if macro.herald_available
        else "Rift Herald not available"
    )
    lines.append(f"  Herald: {herald_line}")

    # Rotation context — deterministic notes about likely lane assignments
    rotation_notes = _build_rotation_notes(macro)
    if rotation_notes:
        lines += ["", "Lane context:"]
        for note in rotation_notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)


def _build_rotation_notes(macro: MacroSnapshot) -> list[str]:
    """Return structured notes about likely lane assignments from tower state.

    These are hard rules that are always true when the tower condition holds,
    so they are pre-computed rather than left to Claude to infer.
    """
    notes: list[str] = []

    if macro.enemy_outer_down["bot"] and not macro.ally_outer_down["bot"]:
        notes.append(
            "Enemy bot outer is down — bot/support have more map freedom "
            "and may rotate toward mid or objectives"
        )

    if macro.ally_outer_down["bot"] and not macro.enemy_outer_down["bot"]:
        notes.append(
            "Your bot outer is down — enemy has easier access to bot-side jungle "
            "and dragon pit"
        )

    if macro.ally_outer_down["bot"] and macro.enemy_outer_down["bot"]:
        notes.append(
            "Both bot outers are gone — bot lane has dissolved into mid and objectives"
        )

    if macro.enemy_outer_down["mid"] and not macro.ally_outer_down["mid"]:
        notes.append(
            "Enemy mid outer is down — enemy mid laner has more roam freedom"
        )

    if macro.ally_outer_down["mid"] and not macro.enemy_outer_down["mid"]:
        notes.append(
            "Your mid outer is down — your mid laner is under pressure; "
            "mid priority may be harder to establish"
        )

    return notes
