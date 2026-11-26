import pandas as pd

PLAYER_COLS = [
      "id", "code", "web_name", "first_name", "second_name", "team", "element_type",
      "now_cost", "selected_by_percent",
      "status", "chance_of_playing_next_round", "news", "news_added",
      "penalties_order", "corners_and_indirect_freekicks_order",
  "direct_freekicks_order",
      "ep_next",
  ]
FLOAT_COLS = ["selected_by_percent", "ep_next"]

def build_teams(bootstrap):
    #bootstrap["teams"] -> one row per team
    return pd.DataFrame(bootstrap["teams"])[["id", "code", "name", "short_name"]]

def build_players(bootstrap):
    df = pd.DataFrame(bootstrap["elements"])[PLAYER_COLS]
    
    positions = {t["id"]: t["singular_name_short"] for t in bootstrap["element_types"]}
    df["pos"] = df["element_type"].map(positions)
    df["price"] = df["now_cost"] / 10
    df[FLOAT_COLS] = df[FLOAT_COLS].astype(float)

    # FPL leaves chance empty for available players; empty there means 100
    df.loc[(df["status"] == "a") & df["chance_of_playing_next_round"].isna(), "chance_of_playing_next_round"] = 100

    df = df.drop(columns=["element_type", "now_cost"]).rename(columns={"team": "team_id"})
    assert set(df["pos"]) <= {"GKP", "DEF", "MID", "FWD"}, "new element type, check bootstrap"
    return df

def build_fixtures(fixtures):
    df = pd.DataFrame(fixtures)[["id", "event", "kickoff_time", "team_h", "team_a", "team_h_score", "team_a_score", "finished" ]]
    df["kickoff_time"] = pd.to_datetime(df["kickoff_time"])
    df[["event", "team_h_score", "team_a_score"]] = df[["event", "team_h_score", "team_a_score"]].astype("Int64")
    return df
    