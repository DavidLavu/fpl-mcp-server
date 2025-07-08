from fastapi import FastAPI, Query
from fastapi.responses import FileResponse

from tools.fpl_tools import (
    get_top_players, get_top_players_by_position, get_player_by_name,
    get_players_by_team, get_team_summary, get_team_fixtures,
    get_manager_info, get_manager_history, get_manager_picks,
    get_live_scores, resolve_player_picks,
    enrich_players, enrich_fixtures_for_team, enrich_manager_info,
    enrich_manager_history, enrich_manager_picks, enrich_live_scores,
    get_fdr, top_value_picks, ownership_trend, chip_usage_summary,
    suggest_captain, suggest_transfers,
    get_template_team, get_top_manager_ids, get_bootstrap_data
)

app = FastAPI(
    title="FPL MCP Server",
    version="1.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    servers=[{"url": "https://fpl-mcp-server.onrender.com"}]
)

@app.get("/tools/get_top_players", summary="Top Players", description="Get top N players ranked by total points")
def top_players(limit: int = Query(5, ge=1, le=50, description="Number of players to return")):
    return enrich_players(get_top_players(limit))

@app.get("/tools/get_top_players_by_position", summary="Top By Position", description="Get top players filtered by position (GK, DEF, MID, FWD)")
def top_by_position(
    position: str = Query(..., description="Player position: GK, DEF, MID, or FWD"),
    limit: int = Query(5, description="Number of players to return")
):
    return enrich_players(get_top_players_by_position(position, limit))

@app.get("/tools/get_player_by_name", summary="Player Search", description="Search for player by name (case-insensitive substring match)")
def player_search(name: str = Query(..., description="Full or partial player name")):
    return enrich_players(get_player_by_name(name))

@app.get("/tools/get_players_by_team", summary="Players By Team", description="Get all players from a given team name")
def players_by_team(team_name: str = Query(..., description="Full team name (e.g., Arsenal)")):
    return enrich_players(get_players_by_team(team_name))

@app.get("/tools/get_team_summary", summary="Team Summary", description="Static team metadata and strength from FPL bootstrap")
def team_summary(team_id: int = Query(..., description="FPL team ID (1–20)")):
    return get_team_summary(team_id)

@app.get("/tools/get_team_fixtures", summary="Team Fixtures", description="Upcoming and past fixtures for a given FPL team")
def team_fixtures(team_id: int = Query(..., description="FPL team ID (1–20)")):
    return enrich_fixtures_for_team(team_id)

@app.get("/tools/get_manager_info", summary="Manager Info", description="FPL manager info based on team ID")
def manager_info(team_id: int = Query(..., description="FPL team ID")):
    return enrich_manager_info(get_manager_info(team_id))

@app.get("/tools/get_manager_history", summary="Manager History", description="FPL manager season history and gameweek summary")
def manager_history(team_id: int = Query(..., description="FPL team ID")):
    return enrich_manager_history(get_manager_history(team_id))

@app.get("/tools/get_manager_picks", summary="Manager Picks", description="Picks for a given manager and gameweek")
def manager_picks(
    team_id: int = Query(..., description="FPL team ID"),
    gw: int = Query(..., description="Gameweek number (1–38)")
):
    return enrich_manager_picks(get_manager_picks(team_id, gw))

@app.get("/tools/get_resolved_manager_picks", summary="Resolved Picks", description="Enriched squad with roles (C, VC, points)")
def resolved_picks(
    team_id: int = Query(..., description="FPL team ID"),
    gw: int = Query(..., description="Gameweek number (1–38)")
):
    return resolve_player_picks(get_manager_picks(team_id, gw)["picks"])

@app.get("/tools/get_live_scores", summary="Live Scores", description="Current FPL live stats for all players in a given gameweek")
def live_scores(gw: int = Query(..., description="Gameweek number (1–38)")):
    return enrich_live_scores(get_live_scores(gw))

@app.get("/tools/get_fdr", summary="Fixture Difficulty", description="Get next N opponent difficulty ratings for a team")
def fdr(
    team_id: int = Query(..., description="FPL team ID"),
    next_n: int = Query(5, description="How many future fixtures to check")
):
    return get_fdr(team_id, next_n)

@app.get("/tools/get_value_picks", summary="Top Value Picks", description="Return best points-per-million players")
def value_picks(
    limit: int = Query(10, description="Max players to return"),
    min_mins: int = Query(900, description="Minimum minutes played")
):
    return top_value_picks(limit, min_mins)

@app.get("/tools/ownership_trend", summary="Ownership Trend", description="Check player selection frequency across custom team IDs")
def own_trend(
    team_ids: str = Query(..., description="Comma-separated FPL team IDs (e.g. 1234,5678)"),
    gw: int = Query(..., description="Gameweek number")
):
    ids = [int(x) for x in team_ids.split(",")]
    return ownership_trend(ids, gw)

@app.get("/tools/chip_usage_summary", summary="Chip Usage", description="Aggregate chip usage (Triple Captain, Bench Boost, etc.)")
def chips(team_ids: str = Query(..., description="Comma-separated FPL team IDs")):
    ids = [int(x) for x in team_ids.split(",")]
    return chip_usage_summary(ids)

@app.get("/tools/suggest_captain", summary="Suggest Captain", description="Suggest best captain pick based on live scores")
def captain(
    team_id: int = Query(..., description="FPL team ID"),
    gw: int = Query(..., description="Gameweek number")
):
    return suggest_captain(team_id, gw)

@app.get("/tools/suggest_transfers", summary="Suggest Transfers", description="Suggest 1–3 transfer moves based on recent form and value")
def transfers(
    team_id: int = Query(..., description="FPL team ID"),
    gw: int = Query(..., description="Gameweek number"),
    budget: float = Query(2.0, description="Extra budget available in millions")
):
    return suggest_transfers(team_id, gw, budget)

@app.get("/tools/get_template_team", summary="Template Team", description="Most common squad across top N managers in a league")
def template_team(
    league_id: int = Query(314, description="League ID (default: Official FPL)"),
    gw: int = Query(38, description="Gameweek"),
    top_n: int = Query(5, description="How many top managers to check")
):
    return get_template_team(league_id, gw, top_n)

@app.get("/tools/get_top_manager_ids", summary="Top Managers in League", description="List top N manager team IDs from a league")
def league_top_ids(
    league_id: int = Query(..., description="Mini-league ID"),
    top_n: int = Query(5, description="Number of top managers to return")
):
    return get_top_manager_ids(league_id, top_n)

@app.get("/openapi.json", summary="Get OpenAPI Spec", description="Expose schema for external tools like GPT to use")
def openapi_spec():
    return FileResponse("openapi.json")

@app.get("/", summary="Root", description="Health check")
def root():
    return {"message": "FPL MCP Server is running"}
