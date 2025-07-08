from fastapi import FastAPI, Query
import requests
from collections import Counter
from tools.fpl_tools import (
    get_top_players,
    get_top_players_by_position,
    get_player_by_name,
    get_players_by_team,
    get_team_summary,
    get_team_fixtures,
    get_manager_info,
    get_manager_history,
    get_manager_picks,
    get_live_scores,
    resolve_player_picks,
    enrich_players,
    enrich_fixtures_for_team,
    enrich_manager_info,
    enrich_manager_history,
    enrich_manager_picks,
    enrich_live_scores,
    summarize_top_manager_moves,
    get_template_team, get_bootstrap_data, get_manager_picks, get_manager_history
)


app = FastAPI()

@app.get("/")
def root():
    return {"message": "FPL MCP Server is running"}

@app.get("/tools/get_top_players")
def top_players(limit: int = Query(5, ge=1, le=50)):
    players = get_top_players(limit)
    return enrich_players(players)

@app.get("/tools/get_top_players_by_position")
def top_by_position(position: str = Query(..., description="GK, DEF, MID, FWD"), limit: int = 5):
    players = get_top_players_by_position(position, limit)
    return enrich_players(players)

@app.get("/tools/get_player_by_name")
def player_search(name: str):
    players = get_player_by_name(name)
    return enrich_players(players)

@app.get("/tools/get_players_by_team")
def players_by_team(team_name: str):
    players = get_players_by_team(team_name)
    return enrich_players(players)


@app.get("/tools/get_team_summary")
def team_summary(team_id: int):
    return get_team_summary(team_id)

@app.get("/tools/get_team_fixtures")
def team_fixtures(team_id: int):
    return enrich_fixtures_for_team(team_id)

@app.get("/tools/get_manager_info")
def manager_info(team_id: int):
    raw = get_manager_info(team_id)
    return enrich_manager_info(raw)

@app.get("/tools/get_manager_history")
def manager_history(team_id: int):
    raw = get_manager_history(team_id)
    return enrich_manager_history(raw)

@app.get("/tools/get_manager_picks")
def manager_picks(team_id: int, gw: int):
    raw = get_manager_picks(team_id, gw)
    return enrich_manager_picks(raw)

@app.get("/tools/get_live_scores")
def live_scores(gw: int):
    raw = get_live_scores(gw)
    return enrich_live_scores(raw)

@app.get("/tools/get_resolved_manager_picks")
def resolved_picks(team_id: int, gw: int):
    raw_data = get_manager_picks(team_id, gw)
    picks = raw_data.get("picks", [])
    return resolve_player_picks(picks)

@app.get("/tools/compare_top_manager_moves")
def compare_top_manager_moves(league_id: int, gw: int, top_n: int = Query(5, ge=1, le=100)):
    standings_url = f"https://fantasy.premierleague.com/api/leagues-classic/{league_id}/standings/"
    standings = requests.get(standings_url).json()
    managers = standings["standings"]["results"][:top_n]
    team_ids = [m["entry"] for m in managers]

    captain_counter = Counter()
    transfer_out_counter = Counter()

    for team_id in team_ids:
        try:
            # Get captain pick
            picks_data = get_manager_picks(team_id, gw)
            captain = next((p["element"] for p in picks_data["picks"] if p["is_captain"]), None)
            if captain:
                captain_counter[captain] += 1

            # Get transfers OUT
            transfers_url = f"https://fantasy.premierleague.com/api/entry/{team_id}/event/{gw}/transfers/"
            transfers = requests.get(transfers_url).json()
            if isinstance(transfers, list):
                out_ids = [t["element_out"] for t in transfers]
                transfer_out_counter.update(out_ids)

        except Exception as e:
            print(f"Error for manager {team_id}: {e}")
            continue

    # Enrichment
    bootstrap = get_bootstrap_data()
    player_map = {p["id"]: p for p in bootstrap["elements"]}
    teams = {t["id"]: t["name"] for t in bootstrap["teams"]}
    positions = {e["id"]: e["singular_name_short"] for e in bootstrap["element_types"]}

    def enrich(counter):
        return [
            {
                "name": f"{p['first_name']} {p['second_name']}",
                "team": teams.get(p["team"]),
                "position": positions.get(p["element_type"]),
                "count": count
            }
            for pid, count in counter.most_common()
            if (p := player_map.get(pid))
        ]

    return {
        "captains": enrich(captain_counter),
        "transfers_out": enrich(transfer_out_counter)
    }

@app.get("/tools/get_template_team")
def get_template_team_view(league_id: int = 314, gw: int = 38, top_n: int = 5):
    return get_template_team(league_id, gw, top_n)

from fastapi.responses import FileResponse

@app.get("/openapi.json")
def get_openapi_spec():
    return FileResponse("openapi.json")
  