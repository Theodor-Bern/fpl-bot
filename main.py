import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests



URL = "https://fantasy.premierleague.com/api/bootstrap-static/"

r = requests.get("https://fantasy.premierleague.com/api/bootstrap-static/",
                 headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
r.raise_for_status()
data = r.json()

#Save a raw dir, timestamped snapshot
raw_dir=Path("data/raw/bootstrap")
raw_dir.mkdir(parents=True, exist_ok=True)
ts=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
(raw_dir / f"{ts}.json").write_text(json.dumps(data))

players = pd.DataFrame(data["elements"]) #fetch players
teams = pd.DataFrame(data["teams"])[["id", "short_name"]] #fetch teams and keep only shortname
positions = pd.DataFrame(data["element_types"])[["id", "singular_name_short"]] #fetch positions and keep shortname

#Merge the teamname and position name to the player´s row. Instead of Haaland team=13 pos=4, it says Haaland team=MCI pos=FWD
players = (
    players
    .merge(teams, left_on="team", right_on="id", suffixes=("", "_team"))
    .merge(positions, left_on="element_type", right_on="id", suffixes=("", "_pos"))
)
players["price"] = players["now_cost"] / 10 #create new price column in players. now_cost is stored as 55 for 5.5m


xcols = [
    "expected_goals", "expected_assists", "expected_goal_involvements",
    "expected_goals_per_90", "expected_assists_per_90", "expected_goal_involvements_per_90",
]
players[xcols] = players[xcols].astype(float)

cols = ["web_name", "short_name", "singular_name_short", "price", "total_points", "minutes", "expected_assists", "expected_goals", "expected_goal_involvements"]

#print(players[cols].sort_values("total_points", ascending=False).head(15))

fx = requests.get("https://fantasy.premierleague.com/api/fixtures/",
                  headers={"User-Agent": "Mozilla/5.0"}, timeout=30).json()
fixtures = pd.DataFrame(fx)

# Save raw snapshot like you do for bootstrap
fx_dir = Path("data/raw/fixtures")
fx_dir.mkdir(parents=True, exist_ok=True)
(fx_dir / f"{ts}.json").write_text(json.dumps(fx))

# One row per team per fixture
home = fixtures.rename(columns={"team_h": "team", "team_a": "opponent",
                                "team_h_difficulty": "fdr"}).assign(is_home=True)
away = fixtures.rename(columns={"team_a": "team", "team_h": "opponent",
                                "team_a_difficulty": "fdr"}).assign(is_home=False)
team_fx = pd.concat([home, away])[["event", "team", "opponent", "is_home", "fdr", "finished"]]

# Add short names
names = teams.set_index("id")["short_name"]
team_fx["team_name"] = team_fx["team"].map(names)
team_fx["opp_name"] = team_fx["opponent"].map(names)


upcoming = team_fx[~team_fx["finished"] & team_fx["event"].notna()]
next_gw = upcoming["event"].min()
next5 = upcoming[upcoming["event"] < next_gw + 5]

#print(next5.groupby("team_name")["fdr"].mean().sort_values().round(2))
print(players[cols].sort_values("expected_goals", ascending=False).head(30))
