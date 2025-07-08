# main.py
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from collections import Counter
import requests

from tools.fpl_tools import (
    # core
    get_top_players, get_top_players_by_position, get_player_by_name,
    get_players_by_team, get_team_summary, get_team_fixtures,
    get_manager_info, get_manager_history, get_manager_picks,
    get_live_scores, resolve_player_picks,
    # enrichment
    enrich_players, enrich_fixtures_for_team, enrich_manager_info,
    enrich_manager_history, enrich_manager_picks, enrich_live_scores,
    # elite helpers
    get_fdr, top_value_picks, ownership_trend, chip_usage_summary,
    suggest_captain, suggest_transfers,
    # template / league
    get_template_team, get_top_manager_ids, get_bootstrap_data
)

app = FastAPI(
    title="FPL MCP Server",
    version="1.1.0",
    openapi_url="/openapi.json",
    docs_url="/docs",
    servers=[{"url": "https://fpl-mcp-server.onrender.com"}]
)

# ──────────────────────────────────────────────
# Basic player & team routes
# ──────────────────────────────────────────────
@app.get("/tools/get_top_players")
def top_players(limit: int = Query(5, ge=1, le=50)):
    return enrich_players(get_top_players(limit))

@app.get("/tools/get_top_players_by_position")
def top_by_position(position: str, limit: int = 5):
    return enrich_players(get_top_players_by_position(position, limit))

@app.get("/tools/get_player_by_name")
def player_search(name: str):
    return enrich_players(get_player_by_name(name))

@app.get("/tools/get_players_by_team")
def players_by_team(team_name: str):
    return enrich_players(get_players_by_team(team_name))

@app.get("/tools/get_team_summary")
def team_summary(team_id: int):
    return get_team_summary(team_id)

@app.get("/tools/get_team_fixtures")
def team_fixtures(team_id: int):
    return enrich_fixtures_for_team(team_id)

# ──────────────────────────────────────────────
# Manager routes
# ──────────────────────────────────────────────
@app.get("/tools/get_manager_info")
def manager_info(team_id: int):
    return enrich_manager_info(get_manager_info(team_id))

@app.get("/tools/get_manager_history")
def manager_history(team_id: int):
    return enrich_manager_history(get_manager_history(team_id))

@app.get("/tools/get_manager_picks")
def manager_picks(team_id: int, gw: int):
    return enrich_manager_picks(get_manager_picks(team_id, gw))

@app.get("/tools/get_resolved_manager_picks")
def resolved_picks(team_id: int, gw: int):
    return resolve_player_picks(get_manager_picks(team_id, gw)["picks"])

# ──────────────────────────────────────────────
# Live & analytics routes
# ──────────────────────────────────────────────
@app.get("/tools/get_live_scores")
def live_scores(gw: int):
    return enrich_live_scores(get_live_scores(gw))

@app.get("/tools/get_fdr")
def fdr(team_id: int, next_n: int = 5):
    return get_fdr(team_id, next_n)

@app.get("/tools/get_value_picks")
def value_picks(limit: int = 10, min_mins: int = 900):
    return top_value_picks(limit, min_mins)

@app.get("/tools/ownership_trend")
def own_trend(team_ids: str, gw: int):
    ids = [int(x) for x in team_ids.split(",")]
    return ownership_trend(ids, gw)

@app.get("/tools/chip_usage_summary")
def chips(team_ids: str):
    ids = [int(x) for x in team_ids.split(",")]
    return chip_usage_summary(ids)

@app.get("/tools/suggest_captain")
def captain(team_id: int, gw: int):
    return suggest_captain(team_id, gw)

@app.get("/tools/suggest_transfers")
def transfers(team_id: int, gw: int, budget: float = 2.0):
    return suggest_transfers(team_id, gw, budget)

# ──────────────────────────────────────────────
# League / template helpers
# ──────────────────────────────────────────────
@app.get("/tools/get_template_team")
def template_team(league_id: int = 314, gw: int = 38, top_n: int = 5):
    return get_template_team(league_id, gw, top_n)

@app.get("/tools/get_top_manager_ids")
def league_top_ids(league_id: int, top_n: int = 5):
    return get_top_manager_ids(league_id, top_n)

# ──────────────────────────────────────────────
# OpenAPI file
# ──────────────────────────────────────────────
@app.get("/openapi.json")
def openapi_spec():
    return FileResponse("openapi.json")

# Root health-check
@app.get("/")
def root():
    return {"message": "FPL MCP Server is running"}
