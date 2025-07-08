import requests

BASE_URL = "https://fantasy.premierleague.com/api"

def get_bootstrap_data():
    return requests.get(f"{BASE_URL}/bootstrap-static/").json()

def get_top_players(limit=10):
    data = get_bootstrap_data()
    sorted_players = sorted(data['elements'], key=lambda p: p['total_points'], reverse=True)
    return sorted_players[:limit]

def get_top_players_by_position(position: str, limit=5):
    data = get_bootstrap_data()
    position_map = {et['singular_name_short']: et['id'] for et in data['element_types']}
    pos_id = position_map.get(position.upper())
    if not pos_id:
        return []
    filtered = [p for p in data['elements'] if p['element_type'] == pos_id]
    sorted_players = sorted(filtered, key=lambda p: p['total_points'], reverse=True)
    return sorted_players[:limit]

def get_player_by_name(name: str):
    data = get_bootstrap_data()
    return [
        p for p in data['elements']
        if name.lower() in (p['first_name'] + ' ' + p['second_name']).lower()
    ]

def get_players_by_team(team_name: str):
    data = get_bootstrap_data()
    team_map = {t['name'].lower(): t['id'] for t in data['teams']}
    team_id = team_map.get(team_name.lower())
    if not team_id:
        return []
    return [p for p in data['elements'] if p['team'] == team_id]

def get_team_summary(team_id: int):
    data = get_bootstrap_data()
    for team in data['teams']:
        if team['id'] == team_id:
            return team
    return {}

def get_fixtures():
    return requests.get(f"{BASE_URL}/fixtures/").json()

def get_team_fixtures(team_id: int):
    fixtures = get_fixtures()
    return [f for f in fixtures if f["team_a"] == team_id or f["team_h"] == team_id]

def get_manager_info(team_id: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/").json()

def get_manager_history(team_id: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/history/").json()

def get_manager_picks(team_id: int, gw: int):
    return requests.get(f"{BASE_URL}/entry/{team_id}/event/{gw}/picks/").json()

def get_live_scores(gw: int):
    return requests.get(f"{BASE_URL}/event/{gw}/live/").json()

def resolve_player_picks(picks: list):
    data = get_bootstrap_data()
    players = {p['id']: p for p in data['elements']}
    teams = {t['id']: t['name'] for t in data['teams']}
    positions = {et['id']: et['singular_name_short'] for et in data['element_types']}

    resolved = []
    for pick in picks:
        p = players.get(pick['element'], {})
        resolved.append({
            "name": f"{p.get('first_name', '')} {p.get('second_name', '')}",
            "team": teams.get(p.get("team")),
            "position": positions.get(pick["element_type"]),
            "price": p.get("now_cost", 0) / 10,
            "multiplier": pick["multiplier"],
            "is_captain": pick["is_captain"],
            "is_vice_captain": pick["is_vice_captain"]
        })
    return resolved

def enrich_players(player_list: list):
    data = get_bootstrap_data()
    teams = {t["id"]: t["name"] for t in data["teams"]}
    positions = {et["id"]: et["singular_name_short"] for et in data["element_types"]}

    enriched = []
    for p in player_list:
        enriched.append({
            "name": f"{p['first_name']} {p['second_name']}",
            "team": teams.get(p["team"]),
            "position": positions.get(p["element_type"]),
            "points": p["total_points"],
            "price": p["now_cost"] / 10
        })
    return enriched

from datetime import datetime

def enrich_fixtures_for_team(team_id: int):
    fixtures = get_fixtures()
    data = get_bootstrap_data()
    teams = {t["id"]: t["name"] for t in data["teams"]}

    enriched = []
    for f in fixtures:
        if f["team_h"] != team_id and f["team_a"] != team_id:
            continue

        enriched.append({
            "gameweek": f["event"],
            "home_team": teams.get(f["team_h"]),
            "away_team": teams.get(f["team_a"]),
            "home_score": f.get("team_h_score"),
            "away_score": f.get("team_a_score"),
            "kickoff": datetime.fromisoformat(f["kickoff_time"].replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M"),
            "finished": f["finished"]
        })
    return enriched

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

from datetime import datetime

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
    picks = resolve_player_picks(raw.get("picks", []))

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
        "squad": picks
    }

def enrich_live_scores(raw: dict):
    bootstrap = get_bootstrap_data()
    players = {p['id']: p for p in bootstrap['elements']}
    teams = {t['id']: t['name'] for t in bootstrap['teams']}
    positions = {et['id']: et['singular_name_short'] for et in bootstrap['element_types']}

    enriched = []

    for e in raw.get("elements", []):
        player = players.get(e["id"], {})
        stats = e["stats"]

        enriched.append({
            "name": f"{player.get('first_name')} {player.get('second_name')}",
            "team": teams.get(player.get("team")),
            "position": positions.get(player.get("element_type")),
            "minutes": stats.get("minutes"),
            "goals": stats.get("goals_scored"),
            "assists": stats.get("assists"),
            "bps": stats.get("bps"),
            "ict_index": float(stats.get("ict_index", "0")),
            "xG": float(stats.get("expected_goals", "0")),
            "xA": float(stats.get("expected_assists", "0")),
            "points": stats.get("total_points"),
            "dream_team": stats.get("in_dreamteam")
        })

    return sorted(enriched, key=lambda x: x["points"], reverse=True)


def get_top_managers_from_league(league_id: int, page: int = 1):
    url = f"{BASE_URL}/leagues-classic/{league_id}/standings/?page_standings={page}"
    return requests.get(url).json()

def get_top_manager_ids(league_id: int, page_limit: int = 1, top_n: int = 5):
    all_entries = []
    for page in range(1, page_limit + 1):
        standings = get_top_managers_from_league(league_id, page)
        all_entries.extend(standings.get("standings", {}).get("results", []))
    return [entry["entry"] for entry in all_entries[:top_n]]

def summarize_top_manager_moves(league_id: int, gw: int, top_n: int = 5):
    ids = get_top_manager_ids(league_id, top_n=top_n)
    summary = {"captains": {}, "transfers_out": {}}
    for team_id in ids:
        picks = get_manager_picks(team_id, gw)
        captain = next((p for p in picks["picks"] if p["is_captain"]), {}).get("element")
        if captain:
            summary["captains"][captain] = summary["captains"].get(captain, 0) + 1

        history = picks.get("entry_history", {})
        if history.get("event_transfers", 0) > 0:
            summary["transfers_out"][team_id] = history.get("event_transfers")

    return summary

def get_template_team(league_id: int, gw: int, top_n: int = 5):
    ids = get_top_manager_ids(league_id, top_n=top_n)
    squad_counter = {}
    for team_id in ids:
        picks = get_manager_picks(team_id, gw)["picks"]
        for p in picks:
            element = p["element"]
            squad_counter[element] = squad_counter.get(element, 0) + 1
    return sorted(squad_counter.items(), key=lambda x: -x[1])
