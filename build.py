"""Turn the raw JSON from fetch.py into clean tables in data/fpl.db.

Run: python build.py  (after python fetch.py)
Each build_* function makes one table: right columns, right types, consistent names,
so everything downstream (FDR model, xP, optimizer, agent) can trust the data.
"""
import json
import sqlite3
from pathlib import Path

import pandas as pd

# Columns to keep from bootstrap["elements"] (one row per player, current state)
PLAYER_COLS = [
    "id", "code", "web_name", "first_name", "second_name", "team", "element_type",
    "now_cost", "selected_by_percent", "total_points",
    "status", "chance_of_playing_next_round", "news", "news_added",
    "penalties_order", "corners_and_indirect_freekicks_order", "direct_freekicks_order",
    "ep_next",
]
# FPL sends these as text ("12.3"), so they must be converted to numbers
FLOAT_COLS = ["selected_by_percent", "ep_next"]

# Columns to keep from element-summary "history" (one row per player per match)
GW_COLS = [
    "element", "fixture", "round", "opponent_team", "was_home",
    "minutes", "starts",
    "goals_scored", "assists", "clean_sheets", "goals_conceded", "own_goals",
    "penalties_saved", "penalties_missed", "yellow_cards", "red_cards",
    "saves", "bonus", "bps", "total_points",
    "expected_goals", "expected_assists", "expected_goals_conceded",
    "defensive_contribution", "clearances_blocks_interceptions", "recoveries", "tackles",
    "value",
]
GW_FLOAT_COLS = ["expected_goals", "expected_assists", "expected_goals_conceded"]  # text in the API

RAW = Path("data/raw")
DB = Path("data/fpl.db")  # in data/, which is gitignored: it can always be rebuilt from RAW


def latest_run():
    # Run folders are named by UTC timestamp (start with "2"), so max() = newest.
    # Skips the old non-timestamp folders (bootstrap/, fixtures/, understat/)
    return max(p for p in RAW.iterdir() if p.name.startswith("2"))


def build_teams(bootstrap):
    # bootstrap["teams"] -> one row per team
    return pd.DataFrame(bootstrap["teams"])[["id", "code", "name", "short_name"]]


def build_players(bootstrap):
    df = pd.DataFrame(bootstrap["elements"])[PLAYER_COLS]

    # element_type is a number (1-4); map it to GKP/DEF/MID/FWD via bootstrap["element_types"]
    positions = {t["id"]: t["singular_name_short"] for t in bootstrap["element_types"]}
    df["pos"] = df["element_type"].map(positions)
    df["price"] = df["now_cost"] / 10  # FPL stores £5.5m as 55
    df[FLOAT_COLS] = df[FLOAT_COLS].astype(float)

    # FPL leaves chance empty for available players; empty there means 100
    df.loc[(df["status"] == "a") & df["chance_of_playing_next_round"].isna(), "chance_of_playing_next_round"] = 100

    # team -> team_id: makes clear it is an id pointing at teams.id, not a name
    df = df.drop(columns=["element_type", "now_cost"]).rename(columns={"team": "team_id"})
    assert set(df["pos"]) <= {"GKP", "DEF", "MID", "FWD"}, "new element type, check bootstrap"
    return df


def build_fixtures(fixtures):
    # fixtures.json is already a list of matches (not a dict like bootstrap)
    df = pd.DataFrame(fixtures)[["id", "event", "kickoff_time", "team_h", "team_a", "team_h_score", "team_a_score", "finished"]]
    df["kickoff_time"] = pd.to_datetime(df["kickoff_time"])  # text -> real datetime, so dates sort/compare
    # "Int64" (capital I) = whole numbers that may be empty: unplayed matches have no score,
    # and a postponed match has no event. Plain int64 can't hold empty values.
    df[["event", "team_h_score", "team_a_score"]] = df[["event", "team_h_score", "team_a_score"]].astype("Int64")
    return df


def build_player_gw(run, fixtures):
    """The core table: one row per player per match. fixtures = output of build_fixtures."""
    # One file per player; collect a DataFrame per file, then stack them all once
    # (concat inside the loop would copy the growing table every time)
    frames = []
    for f in (run / "element_summary").glob("*.json"):
        summary = json.loads(f.read_text())
        frames.append(pd.DataFrame(summary["history"]))
    # ignore_index: every player's frame starts at 0; renumber 0..n so the index is unique
    df = pd.concat(frames, ignore_index=True)[GW_COLS]
    df[GW_FLOAT_COLS] = df[GW_FLOAT_COLS].astype(float)
    df["price"] = df["value"] / 10  # price that GW, stored like now_cost

    # The team a player played for in each match: home side if was_home, else away.
    # Per match, not players.team_id, so a January transfer still gets the right team.
    # how="left" keeps every row; a missing fixture shows up as an empty team, not a lost row
    df = df.merge(fixtures[["id", "team_h", "team_a"]], left_on="fixture", right_on="id", how="left")
    df["team"] = df["team_h"].where(df["was_home"], df["team_a"])  # pandas if/else per row

    # id/team_h/team_a were only needed to find team. round -> event so the gameweek
    # has the same name as in fixtures, and the tables join on it directly
    df = df.drop(columns=["value", "id", "team_h", "team_a"]).rename(columns={"round": "event"})
    return df

def build_team_gw(player_gw):
    """One row per team per match: xG for and against"""
    #sum the players xG per team per match -> get the teams xG
    df = (player_gw
            .groupby(["fixture", "event", "team", "opponent_team", "was_home"], as_index=False)
            .agg(xg_for=("expected_goals", "sum"))
            .rename(columns={"opponent_team": "opponent"}))
    
    opp = df[["fixture", "team", "xg_for"]].rename(columns={"team": "opponent", "xg_for": "xg_against"})
    return df.merge(opp, on=["fixture", "opponent"], how="left")

    
    


if __name__ == "__main__":
    # Only runs on `python build.py`, not when another file imports these functions
    run = latest_run()
    bootstrap = json.loads((run / "bootstrap.json").read_text())
    fixtures = json.loads((run / "fixtures.json").read_text())

    fx = build_fixtures(fixtures)  # built first: build_player_gw needs it
    pgw = build_player_gw(run, fx)
    tables = {  # table name in the database -> DataFrame
        "teams": build_teams(bootstrap),
        "players": build_players(bootstrap),
        "fixtures": fx,
        "player_gw": pgw,
        "team_gw": build_team_gw(pgw)
        
    }
    # A duplicate row would silently double a player's xG and points in every model
    assert not tables["player_gw"].duplicated(["element", "fixture"]).any(), "duplicate player-fixture rows"

    # `with` commits the changes when the block ends
    with sqlite3.connect(DB) as con:
        for name, df in tables.items():
            # replace: each build overwrites the table with fresh data instead of appending duplicates
            # index=False: pandas row numbers are not data, don't store them
            df.to_sql(name, con, if_exists="replace", index=False)
            print(f"{name}: {len(df)} rows")
        # Smoke test: a real SQL query against the new database
        print(pd.read_sql("SELECT web_name, total_points FROM players ORDER BY total_points DESC LIMIT 10", con))
    print(f"Built {DB} from {run.name}")
