# tools/fpl_tools.py
"""
FPL MCP utility module
────────────────────────────────────────────────────────
Fast, documented Python helpers around the **free** Fantasy
Premier League API.  All heavy network calls are cached via
@lru_cache where safe.

Key public endpoints used
─────────────────────────
bootstrap-static/                 -> squads, teams, event meta
fixtures/                         -> full fixture list
event/{GW}/live/                  -> live GW stats
element-summary/{PID}/            -> per-player history
entry/{TEAM_ID}/history/          -> manager season + GW history
entry/{TEAM_ID}/event/{GW}/picks/ -> manager picks
entry/{TEAM_ID}/event/{GW}/transfers/ -> GW transfers
leagues-classic/{LID}/standings/  -> mini-league table
"""

from functools import lru_cache
from datetime import datetime
import statistics, requests

BASE_URL = "https://fantasy.premierleague.com/api"

# ───────────────────────────────────────────────────────
# Caching primitives
# ───────────────────────────────────────────────────────
@lru_cache(maxsize=1)
def get_bootstrap_data():
    """Global game-state: players, teams, element types, events."""
    return requests.get(f"{BASE_URL}/bootstrap-static/").json()

@lru_cache(maxsize=32)
def get_fixtures():
    """All PL fixtures (cached)."""
    return requests.get(f"{BASE_URL}/fixtures/").json()

# quick lookup maps
def _player_map():
    return {p["id"]: p for p in get_bootstrap_data()["elements"]}

_player_map_inv = {
    f"{p['first_name']} {p['second_name']}": p["id"]
    for p in get_bootstrap_data()["elements"]
}

def _team_map():
    return {t["id"]: t["name"] for t in get_bootstrap_data()["teams"]}

def _pos_map():
    return {e["id"]: e["singular_name_short"] for e in get_bootstrap_data()["element_types"]}


# ───────────────────────────────────────────────────────
# Basic player queries
# ───────────────────────────────────────────────────────
def get_top_players(limit=10):
    """Top N players overall by total points."""
    els = sorted(get_bootstrap_data()["elements"],
                 key=lambda p: p["total_points"],
                 reverse=True)
    return els[:limit]

def get_top_players_by_position(position: str, limit=5):
    """Top N players for a given position code (GK/DEF/MID/FWD)."""
    pos_id = {e["singular_name_short"]: e["id"]
              for e in get_bootstrap_data()["element_types"]}.get(position.upper())
    if not pos_id:
        return []
    players = [p for p in get_bootstrap_data()["elements"]
               if p["element_type"] == pos_id]
    return sorted(players, key=lambda p: p["total_points"], reverse=True)[:limit]

def get_player_by_name(name: str):
    """Case-insensitive substring search for player."""
    return [p for p in get_bootstrap_data()["elements"]
            if name.lower() in (p["first_name"] + " " + p["second_name"]).lower()]

def get_players_by_team(team_name: str):
    """All players belonging to a club (full team name required)."""
    team_id = {t["name"].lower(): t["id"]
               for t in get_bootstrap_data()["teams"]}.get(team_name.lower())
    return [p for p in get_bootstrap_data()["elements"] if p["team"] == team_id]


# ───────────────────────────────────────────────────────
# Teams & fixtures
# ───────────────────────────────────────────────────────
def get_team_summary(team_id: int):
    """Return static team record from bootstrap."""
    return next((t for t in get_bootstrap_data()["teams"] if t["id"] == team_id), {})

def get_team_fixtures(team_id: int):
    """Fixtures where given team is home or away."""
    return [f for f in get_fixtures()
            if f["team_h"] == team_id or f["team_a"] == team_id]

def enrich_fixtures_for_team(team_id: int):
    """Compact printable fixture list with KO & scores."""
    tm = _team_map()
    out = []
    for f in get_team_fixtures(team_id):
        out.append({
            "gw": f["event"],
            "home": tm[f["team_h"]],
            "away": tm[f["team_a"]],
            "h_score": f.get("team_h_score"),
            "a_score": f.get("team_a_score"),
            "ko": f["kickoff_time"][:16],
            "finished": f["finished"]
        })
    return out

def get_fdr(team_id: int, next_n=5):
    """Simple fixture difficulty rating (bucketed 1-5)."""
    fdr_map = {1: "EASY", 2: "EASY", 3: "MED", 4: "HARD", 5: "HARD"}
    out = []
    for f in get_team_fixtures(team_id)[:next_n]:
        opp = f["team_a"] if f["team_h"] == team_id else f["team_h"]
        rating = fdr_map[(get_team_summary(opp)["strength"] // 100) or 1]
        out.append({"gw": f["event"], "opponent": _team_map()[opp], "fdr": rating})
    return out


# ───────────────────────────────────────────────────────
# Manager (entry) helpers
# ───────────────────────────────────────────────────────
def get_manager_info(team_id: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/").json()

def get_manager_history(team_id: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/history/").json()

def get_manager_picks(team_id: int, gw: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/event/{gw}/picks/").json()

def get_manager_transfers(team_id: int, gw: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/event/{gw}/transfers/").json()

def enrich_manager_history(raw: dict):
    simplified_current = [
        {
            "gameweek": gw["event"],
            "points": gw["points"],
            "overall_rank": gw["overall_rank"],
            "bench_points": gw["points_on_bench"],
            "team_value": gw["value"] / 10,
            "transfers": gw["event_transfers"],
            "transfer_cost": gw["event_transfers_cost"],
            "percentile": f"Top {gw['percentile_rank']}%"
        }
        for gw in raw.get("current", [])
    ]

    simplified_past = [
        {
            "season": season["season_name"],
            "total_points": season["total_points"],
            "final_rank": season["rank"]
        }
        for season in raw.get("past", [])
    ]

    simplified_chips = [
        {
            "chip": chip["name"],
            "gameweek": chip["event"],
            "date": datetime.fromisoformat(chip["time"].replace("Z", "+00:00")).strftime("%Y-%m-%d")
        }
        for chip in raw.get("chips", [])
    ]

    return {
        "gameweek_history": simplified_current,
        "season_history": simplified_past,
        "chip_usage": simplified_chips
    }

def enrich_manager_picks(raw: dict):
    entry = raw.get("entry_history", {})
    picks = raw.get("picks", [])
    live_scores = get_live_scores(entry.get("event"))

    live_data = {p["id"]: p for p in live_scores.get("elements", [])}
    bootstrap = get_bootstrap_data()
    players = {p["id"]: p for p in bootstrap["elements"]}
    teams = {t["id"]: t["name"] for t in bootstrap["teams"]}
    positions = {et["id"]: et["singular_name_short"] for et in bootstrap["element_types"]}

    resolved_picks = []
    for pick in picks:
        element_id = pick["element"]
        live = live_data.get(element_id, {}).get("stats", {})
        player = players.get(element_id, {})

        resolved_picks.append({
            "name": f"{player.get('first_name')} {player.get('second_name')}",
            "team": teams.get(player.get("team")),
            "position": positions.get(player.get("element_type")),
            "price": player.get("now_cost", 0) / 10,
            "multiplier": pick["multiplier"],
            "is_captain": pick["is_captain"],
            "is_vice_captain": pick["is_vice_captain"],
            "points": live.get("total_points", 0)
        })

    return {
        "gameweek": entry.get("event"),
        "points": entry.get("points"),
        "total_points": entry.get("total_points"),
        "overall_rank": entry.get("overall_rank"),
        "team_value": entry.get("value", 0) / 10,
        "bank": entry.get("bank", 0) / 10,
        "transfers": entry.get("event_transfers"),
        "transfer_cost": entry.get("event_transfers_cost"),
        "bench_points": entry.get("points_on_bench"),
        "chip_used": raw.get("active_chip"),
        "squad": resolved_picks
    }


def enrich_manager_info(raw: dict):
    data = get_bootstrap_data()
    teams = {t["id"]: t["name"] for t in data["teams"]}

    return {
        "manager_name": f"{raw['player_first_name']} {raw['player_last_name']}",
        "region": raw.get("player_region_name"),
        "team_name": teams.get(raw.get("favourite_team")),
        "overall_points": raw.get("summary_overall_points"),
        "overall_rank": raw.get("summary_overall_rank"),
        "gw_points": raw.get("summary_event_points"),
        "gw_rank": raw.get("summary_event_rank"),
        "years_played": raw.get("years_active"),
        "leagues": [
            {
                "name": league["name"],
                "rank": league.get("entry_rank"),
                "total_players": league.get("rank_count"),
                "percentile": league.get("entry_percentile_rank")
            }
            for league in raw.get("leagues", {}).get("classic", [])
        ]
    }



# ───────────────────────────────────────────────────────
# Live data & player form
# ───────────────────────────────────────────────────────
def get_live_scores(gw: int):
    return requests.get(f"{BASE_URL}/event/{gw}/live/").json()

def get_recent_form(pid: int, lookback=5):
    """Average points over last N appearances."""
    hist = requests.get(f"{BASE_URL}/element-summary/{pid}/").json()["history"][-lookback:]
    pts = [h["total_points"] for h in hist]
    return round(statistics.mean(pts), 2) if pts else 0


# ───────────────────────────────────────────────────────
# Enrichment helpers (pretty JSON ready for API)
# ───────────────────────────────────────────────────────
def _enrich_player(pid: int):
    p = _player_map()[pid]
    return {
        "id": pid,
        "name": f"{p['first_name']} {p['second_name']}",
        "team": _team_map()[p["team"]],
        "position": _pos_map()[p["element_type"]],
        "price": p["now_cost"] / 10
    }

def resolve_player_picks(picks):
    """Convert raw pick dicts into enriched squad list."""
    return [{**_enrich_player(p["element"]),
             "multiplier": p["multiplier"],
             "is_captain": p["is_captain"],
             "is_vice_captain": p["is_vice_captain"]} for p in picks]

def enrich_players(players):
    return [{**_enrich_player(p["id"]), "points": p["total_points"]} for p in players]

def enrich_live_scores(raw):
    points = []
    pm, tm, pos = _player_map(), _team_map(), _pos_map()
    for e in raw["elements"]:
        p, s = pm[e["id"]], e["stats"]
        points.append({
            "name": f"{p['first_name']} {p['second_name']}",
            "team": tm[p["team"]],
            "position": pos[p["element_type"]],
            "points": s["total_points"],
            "minutes": s["minutes"],
            "goals": s["goals_scored"],
            "assists": s["assists"]
        })
    return sorted(points, key=lambda x: -x["points"])


# ───────────────────────────────────────────────────────
# Elite analytics helpers
# ───────────────────────────────────────────────────────
def top_value_picks(limit=10, min_mins=900):
    """Best points-per-million players meeting a minutes floor."""
    els = [p for p in get_bootstrap_data()["elements"] if p["minutes"] >= min_mins]
    vals = sorted(els, key=lambda p: p["total_points"] / p["now_cost"], reverse=True)
    return [_enrich_player(p["id"]) | {
        "ppm": round(p["total_points"] / p["now_cost"], 2),
        "points": p["total_points"]
    } for p in vals[:limit]]

def get_top_manager_ids(league_id: int, top_n=5):
    res = requests.get(f"{BASE_URL}/leagues-classic/{league_id}/standings/").json()
    return [r["entry"] for r in res["standings"]["results"][:top_n]]

def get_template_team(league_id: int, gw: int, top_n=5):
    """Common XV among the league’s top N managers."""
    ids, counter = get_top_manager_ids(league_id, top_n), {}
    for tid in ids:
        for p in get_manager_picks(tid, gw)["picks"]:
            counter[p["element"]] = counter.get(p["element"], 0) + 1
    common = sorted(counter.items(), key=lambda x: -x[1])[:15]
    return [_enrich_player(pid) | {"selected_by": c} for pid, c in common]

def ownership_trend(team_ids, gw: int):
    """Player ownership frequency inside a custom manager set."""
    counter = {}
    for tid in team_ids:
        for p in get_manager_picks(tid, gw)["picks"]:
            counter[p["element"]] = counter.get(p["element"], 0) + 1
    total = len(team_ids)
    return [{**_enrich_player(pid),
             "pct": round(cnt * 100 / total, 1)}
            for pid, cnt in sorted(counter.items(), key=lambda x: -x[1])]

def chip_usage_summary(team_ids):
    """Aggregate chip deployments across managers."""
    chip_counter = {}
    for tid in team_ids:
        for chip in get_manager_history(tid).get("chips", []):
            key = f"{chip['chip']}_GW{chip['event']}"
            chip_counter[key] = chip_counter.get(key, 0) + 1
    return dict(sorted(chip_counter.items(), key=lambda x: -x[1]))

def suggest_captain(team_id: int, gw: int):
    """Choose highest live-points player in user’s XI."""
    squad = get_manager_picks(team_id, gw)["picks"]
    live = get_live_scores(gw)["elements"]
    pts = {e["id"]: e["stats"]["total_points"] for e in live}
    best = max(squad, key=lambda p: pts.get(p["element"], 0))
    return _enrich_player(best["element"])

def suggest_transfers(team_id: int, gw: int, budget=2.0):
    """
    Simple rule: sell players averaging <3 pts last 5 GWs, buy
    value picks of same position within budget.
    """
    entry = get_manager_picks(team_id, gw)
    bank = entry["entry_history"]["bank"] / 10 + budget
    squad = resolve_player_picks(entry["picks"])
    bad = [p for p in squad if get_recent_form(_player_map_inv[p["name"]]) < 3]

    replacements = top_value_picks(30)
    moves = []
    for b in bad:
        for r in replacements:
            if r["price"] <= b["price"] + bank and r["position"] == b["position"]:
                moves.append({"sell": b, "buy": r})
                break
    return moves[:3]
