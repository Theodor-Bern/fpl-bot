Building an AI-powered FPL assisant for my own FPL team. 

**Why I want to build this**
I play fantasy premier league every year. Each week I ponder how I should format my team. How do I optimize my 15 player team with a budget of 100 million both short and long term. Should I make a transfer/s, or should I keep them? Should I play a chip or not? All these decisions are decicions I have to make every week. Furthermore, I mostly ground my decisions on data and on how they look when playing, do they have high xG, xGI, and do they look active and involved alot in attacks. Or if its a defender, is their team good in defense xGA, GA, do they get defcons. How are the minutes for the players? Do they start every game that they are available? I could keep going. In conclusion I want to build this assisant to help me navigate through this and make smart decisions. 


**What it should do**
The end result should be an AI-assistant that can reason and keep an conversation.
- It builds an optimal 15-player squad under a constrained budget. For this we should make som real optimize mathematic methods. 
- Suggest transfers based on my current team, and on projected points over the next gameweeks.
- Mode for finding great performing players with low ownership
-Calculates its own FDR since FPL's FDR is not updated quickly and does not really tell how good the teams are.
- Answers natural language questions through an agent that calls tools over the stored FPL data (SQLite). RAG only later, for unstructured text like news.

**Tech stack**
Live FPL API + historical archive, data pipeline with pandas to SQLite. Team-strength model (own FDR), xP model, optimizer (PuLP + CBC), Gemini agent with tool calling, Streamlit UI.

---

## Architecture

```
┌──────────────── Streamlit UI (chat + squad view) ────────────────┐
│   Gemini agent  ── function calling ──┐                           │
│                                       ▼                           │
│   Tools: get_my_team · projected_points · best_transfers ·        │
│          optimal_squad · differentials · fixture_ratings ·        │
│          player_stats(name)                                       │
└───────────────────────────────┬───────────────────────────────────┘
                                ▼
  ┌──────────────┐   ┌──────────────────┐   ┌──────────────────┐
  │ Team-strength│──▶│ xP model         │──▶│ Optimizer (PuLP) │
  │ model = own  │   │ P(plays) × pts|  │   │ squad / transfers│
  │ FDR          │   │ plays            │   │ / chips          │
  └──────▲───────┘   └────────▲─────────┘   └──────────────────┘
         └────────── SQLite ◀─┴── pipeline (pandas) ◀── data sources
```

### Why tools instead of RAG for stats
RAG retrieves text chunks by similarity, it can't sort, filter or do math. "Highest xGI under £7m" needs a query over the whole table. The agent calls Python functions that query SQLite / run the models, and Gemini explains the exact results.

### Components
1. **Data pipeline → SQLite**
   - Tables: `players`, `teams`, `fixtures`, `player_gw` (one row per player per GW, the core table), `my_team`.
   - Keep the timestamped raw JSON snapshots.
2. **Team-strength model (own FDR)**
   - Fit attack/defence strength per team from xG/xGA, recent games weighted more, plus home advantage (Poisson, later Dixon-Coles).
   - Output per fixture: expected goals for/against → FDR buckets, clean-sheet probability (e^-xGA), attacking multiplier.
   - One model, used three ways. Inspiration: AIrsenal's team model.
3. **xP model**
   - P(starts): recent minutes, `starts_per_90`, `chance_of_playing_next_round`, `news`.
   - Points if plays: xG/90, xA/90, clean-sheet odds, defcons (`defensive_contribution_per_90`), bonus, set pieces (`penalties_order`).
   - Start with a hand-written formula, add ML (XGBoost like OpenFPL) only if backtests show it beats the formula.
   - Baseline to beat: FPL's own `ep_next`.
4. **Optimizer (PuLP + CBC)**
   - Single GW: 15 players, £100m, 2/5/5/3, max 3 per club, best XI, captain ×2.
   - Multi GW: free transfers, banking (max 5), −4 hits, bench weights.
   - Chips: Wildcard = unlimited FTs in one GW, Bench Boost = bench scores.
   - Reference: sertalpbilal `FPL-Optimization-Tools`, FPL Review solver docs.
5. **Differentials mode**: a filter, not a system. `selected_by_percent < 5` sorted by xP over the next 5 GWs.
6. **Agent**
   - First: a raw tool-calling loop with the Gemini SDK (~30 lines), to learn how agents work underneath.
   - Then: rebuild it in LangGraph (state, branching, human approval), e.g. a weekly-review workflow: fetch → update xP → optimize → draft advice → I approve.
   - Tools are plain Python functions, so they work in both versions.
7. **Streamlit UI**: `st.chat_message` for chat, a table/pitch view for the squad.

### Data sources
| Source | What | Use |
|---|---|---|
| FPL API `bootstrap-static`, `fixtures` | Players, teams, prices, xG/xA/xGC, defcons, `ep_next`, news | Live data |
| FPL API `element-summary/{id}/` | Per-GW history per player | `player_gw` |
| FPL API `entry/{id}/event/{gw}/picks/` | My team | Transfers |
| [vaastav/Fantasy-Premier-League](https://github.com/vaastav/Fantasy-Premier-League) | Per-GW data since 2016 | Training + backtests |
| Understat | Team/player xG history | Team-strength model |
| [OpenFPL](https://github.com/daniegr/OpenFPL) | Open-source xP | Early xP so the optimizer works before my own model exists, and a second model to compare against |
| Bookmaker odds (Odds-API.io / The Odds API free tiers) | Goalscorer, match and totals odds | Strong xP input, later |
| [Onside Arena](https://onsidearena.com) benchmark | Accuracy of projection sources | Sanity check for my model |

Unverified: free-tier limits of the odds APIs, whether chips come in two sets per season.

### Build order (each step is useful on its own)
1. Pipeline → SQLite (refactor `main.py`)
2. Team-strength model → own FDR + CS odds
3. xP model + backtest vs last season and `ep_next` (OpenFPL as stopgap)
4. Optimizer: single GW → multi GW → chips
5. Gemini agent, raw loop with ~6 tools
6. Streamlit UI
7. Rebuild agent in LangGraph
8. *(Optional)* bookmaker odds, RAG over news
