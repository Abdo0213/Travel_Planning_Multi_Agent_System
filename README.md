# ✈️ Travel Planning Multi-Agent System

An AI-powered travel planner built with **LangGraph**, **OpenRouter**, and the **MCP (Model Context Protocol)**. Specialized agents collaborate to search flights, check weather, find hotels, and discover activities — then synthesize everything into a personalized itinerary that you can approve or revise in a loop.

---

## 🏗️ Architecture

```
User Browser (HTML/JS)
       │  REST + SSE
FastAPI Server  (port 8000)
       │
LangGraph Supervisor Graph
       ├── ✈️  FlightAgent      → flight_mcp_server.py     (stdio MCP → Aviationstack)
       ├── 🌤️  WeatherAgent     → weather_mcp_server.py    (stdio MCP → OpenWeatherMap)
       ├── 🏨  HotelAgent       → npx tavily-mcp           (stdio MCP → Tavily official)
       ├── 🎯  ActivitiesAgent  → npx tavily-mcp           (stdio MCP → Tavily official)
       └── 📋  PlannerAgent     → OpenRouter LLM (synthesises all results)
                    ↓
           interrupt() ← Human-in-the-loop review
           User: Approve ✅  or  Request changes ✏️
                    ↓ (revision loop)
           PlannerAgent regenerates until approved
                    ↓
PostgreSQL  ← LangGraph checkpointing (persists state across API calls)
LangSmith   ← Full trace observability
```

### MCP Transport Strategy

| Agent | Server | Transport | Why |
|---|---|---|---|
| Flight | `flight_mcp_server.py` | **stdio** | Local Python script, Aviationstack API |
| Weather | `weather_mcp_server.py` | **stdio** | Local Python script, OpenWeatherMap API |
| Hotel | `npx tavily-mcp` | **stdio** | Official Tavily MCP — no manual server needed |
| Activities | `npx tavily-mcp` | **stdio** | Shared with Hotel via MCPManager |

All MCP servers are coordinated through a **single `MCPManager`** (`mcp_client/mcp_manager.py`). Graph nodes never touch MCP protocol directly.

---

## 📁 Project Structure

```
Travel_Planning_Multi_Agent_System/
│
├── 📄 main.py                        # Entry point (uvicorn server)
├── 📄 graph.py                       # LangGraph StateGraph definition
├── 📄 graphController.py             # Graph lifecycle & SSE streaming
├── 📄 Travel_State.py                # Shared TypedDict state
├── 📄 state_builder.py               # Build initial state from user input
├── 📄 prompts.py                     # All agent system prompts
│
├── 📂 config/
│   └── Config.py                     # Pydantic-settings (all keys from .env)
│
├── 📂 llm/
│   └── openrouter.py                 # LLM factory → OpenRouter via langchain-openai
│
├── 📂 mcp_client/                    # ← CENTRAL MCP COORDINATOR
│   └── mcp_manager.py                # MCPManager: routes all tool calls
│
├── 📂 MCP_Servers/
│   ├── flight_mcp_server.py          # stdio MCP → Aviationstack REST API
│   ├── weather_mcp_server.py         # stdio MCP → OpenWeatherMap API
│   │     └── tools: get_weather()
│   │                get_forecast_for_date()   ← per-day weather detail
│   └── tavily_mcp_server.py          # DEPRECATED — official npx used instead
│
├── 📂 graph_nodes/
│   ├── flight_node.py                # Calls mcp_manager.search_flights()
│   ├── weather_node.py               # Calls mcp_manager.get_weather() + get_forecast_for_date()
│   ├── hotel_node.py                 # Calls mcp_manager.search_hotels()
│   ├── activities_node.py            # Calls mcp_manager.search_activities()
│   └── planner_node.py               # OpenRouter LLM — synthesises the travel plan
│
├── 📂 db/
│   └── postgres_checkpointer.py      # AsyncPostgresSaver for LangGraph
│
├── 📂 app/
│   └── server.py                     # FastAPI app factory + lifespan
│
├── 📂 routes/
│   └── travel_routes.py              # API endpoints + SSE streaming
│
├── 📂 ui/
│   ├── index.html                    # 5-step wizard UI
│   ├── style.css                     # Dark glassmorphism design
│   └── app.js                        # SSE client + Markdown rendering
│
├── 📄 requirements.txt
├── 📄 .env.example                   # ← Copy this to .env and fill your keys
└── 📄 .gitignore
```

---

## ⚙️ Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| Node.js | 18+ | Required for `npx tavily-mcp` (official Tavily MCP) |
| PostgreSQL | 14+ | For LangGraph state checkpointing |

---

## 🚀 Setup & Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd Travel_Planning_Multi_Agent_System
```

### 2. Create and activate virtual environment

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install Python dependencies

```powershell
pip install -r requirements.txt
```

> **Note:** `mcp==1.9.4` is pinned — mcp 2.x renamed `FastMCP` which breaks our local servers.

### 4. Install Tavily MCP (official, Node.js)

```bash
npx -y tavily-mcp --help
```

This will auto-install `tavily-mcp` on first run. You just need Node.js installed.

### 5. Configure environment variables

```powershell
Copy-Item .env.example .env
```

Edit `.env` and fill in your API keys:

```env
# LLM — OpenRouter (https://openrouter.ai)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free   # free tier model

# Aviationstack (https://aviationstack.com) — free tier works
AVIATIONSTACK_API_KEY=...

# OpenWeatherMap (https://openweathermap.org) — free tier works
OPENWEATHER_API_KEY=...

# Tavily (https://tavily.com) — free tier works
TAVILY_API_KEY=tvly-...

# PostgreSQL
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/travel_planner

# LangSmith — optional, for tracing (https://smith.langchain.com)
LANGSMITH_API_KEY=ls__...
LANGSMITH_PROJECT=travel-planning-agent
LANGCHAIN_TRACING_V2=true
```

### 6. Create the PostgreSQL database

```sql
-- In psql or pgAdmin:
CREATE DATABASE travel_planner;
```

---

## ▶️ Running the Application

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

Expected output:
```
12:00:00  INFO     main — Starting Travel Planning Agent...
12:00:00  INFO     main — MCPManager will spawn MCP servers on-demand:
                     • flight  → MCP_Servers/flight_mcp_server.py (stdio)
                     • weather → MCP_Servers/weather_mcp_server.py (stdio)
                     • tavily  → npx -y tavily-mcp (stdio, requires Node.js)
12:00:01  INFO     main — LangGraph compiled and ready.
12:00:01  INFO     uvicorn — Application startup complete.
```

Open your browser: **http://localhost:8000** 🌐

---

## 🧭 User Flow

```
Step 1: Trip Details
  → Enter: origin, destination, dates, number of travelers, budget

Step 2: Preferences
  → Choose activity types (museums, beaches, hiking, food tours, etc.)

Step 3: AI Agents Working (real-time SSE progress)
  ✈️  Flight Agent      [Running...] → [✓ Done]
  🌤️  Weather Agent     [Waiting...] → [Running...] → [✓ Done]
  🏨  Hotel Agent       [Waiting...] → [Running...] → [✓ Done]
  🎯  Activities Agent  [Waiting...] → [Running...] → [✓ Done]
  📋  Planner Agent     [Waiting...] → [Running...] → [✓ Done]

Step 4: Plan Review
  → Read your full Markdown travel itinerary
  → Click "✅ Approve This Plan"  — saves and finalises
  → OR click "✏️ Request Changes" — describe what to change → Planner revises

Step 5: Approved ✓
  → View final plan, print it
```

---

## 🔌 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/plan/start` | Register a new session, returns `thread_id` |
| `GET` | `/api/plan/stream/{thread_id}` | SSE stream — agent progress + final plan |
| `POST` | `/api/plan/feedback/{thread_id}` | SSE stream — revise plan with feedback |
| `POST` | `/api/plan/approve/{thread_id}` | Approve plan, finalises graph |
| `GET` | `/api/plan/status/{thread_id}` | Get current session state (JSON) |
| `GET` | `/api/health` | Health check |

### Example: Start a plan

```bash
curl -X POST http://localhost:8000/api/plan/start \
  -H "Content-Type: application/json" \
  -d '{
    "origin": "Cairo, Egypt",
    "destination": "Paris, France",
    "departure_date": "2025-12-15",
    "return_date": "2025-12-22",
    "num_travelers": 2,
    "activities": ["museums", "food tours", "art galleries"],
    "budget": 4000,
    "budget_currency": "USD"
  }'
```

Response:
```json
{ "thread_id": "a1b2c3d4-...", "status": "created" }
```

### Example: Stream agent progress (SSE)

```bash
curl -N http://localhost:8000/api/plan/stream/a1b2c3d4-...
```

Events received:
```
event: node_complete
data: {"event":"node_complete","node":"flight_agent","label":"Searching for flights","emoji":"✈️"}

event: node_complete
data: {"event":"node_complete","node":"weather_agent","label":"Checking weather forecast","emoji":"🌤️"}

...

event: plan_ready
data: {"event":"plan_ready","plan_draft":"# ✈️ Travel Plan: Cairo...","revision_count":0}
```

### Example: Submit revision feedback

```bash
curl -X POST http://localhost:8000/api/plan/feedback/a1b2c3d4-... \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Please find cheaper hotels under $100/night and add more museum visits"}'
```

### Example: Approve the plan

```bash
curl -X POST http://localhost:8000/api/plan/approve/a1b2c3d4-...
```

---

## 🧪 Testing Individual Components

### Test the Weather MCP server directly

```powershell
# Get weather for the full trip period
.\venv\Scripts\python.exe -c "
import asyncio, json
from mcp_client.mcp_manager import mcp_manager

async def test():
    result = await mcp_manager.get_weather('Paris', '2025-12-15', '2025-12-22')
    print(json.dumps(result, indent=2, ensure_ascii=False))

asyncio.run(test())
"
```

### Test the new per-day forecast tool

```powershell
.\venv\Scripts\python.exe -c "
import asyncio, json
from mcp_client.mcp_manager import mcp_manager

async def test():
    result = await mcp_manager.get_forecast_for_date('Paris', '2025-12-17')
    print(json.dumps(result, indent=2, ensure_ascii=False))

asyncio.run(test())
"
```

### Test the Flight MCP server

```powershell
.\venv\Scripts\python.exe -c "
import asyncio, json
from mcp_client.mcp_manager import mcp_manager

async def test():
    result = await mcp_manager.search_flights(
        origin='Cairo', destination='Paris',
        departure_date='2025-12-15', return_date='2025-12-22',
        num_travelers=2, budget=4000
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

asyncio.run(test())
"
```

### Test hotel search via Tavily MCP

```powershell
.\venv\Scripts\python.exe -c "
import asyncio, json
from mcp_client.mcp_manager import mcp_manager

async def test():
    result = await mcp_manager.search_hotels(
        destination='Paris', check_in='2025-12-15', check_out='2025-12-22',
        num_travelers=2, budget=4000
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))

asyncio.run(test())
"
```

### Test the MCPManager server registry

```powershell
.\venv\Scripts\python.exe -c "
from mcp_client.mcp_manager import mcp_manager
import json
print(json.dumps(mcp_manager.list_servers(), indent=2))
"
```

### Run a full syntax check

```powershell
.\venv\Scripts\python.exe -m py_compile `
  Travel_State.py state_builder.py prompts.py `
  graph.py graphController.py main.py `
  config\Config.py llm\openrouter.py `
  mcp_client\mcp_manager.py `
  graph_nodes\flight_node.py graph_nodes\weather_node.py `
  graph_nodes\hotel_node.py graph_nodes\activities_node.py `
  graph_nodes\planner_node.py `
  MCP_Servers\flight_mcp_server.py `
  MCP_Servers\weather_mcp_server.py `
  app\server.py routes\travel_routes.py `
  db\postgres_checkpointer.py
echo "All files OK"
```

---

## 🔑 Getting API Keys

| Service | Free Tier | Sign-up Link |
|---|---|---|
| **OpenRouter** | ✅ Free models available | https://openrouter.ai |
| **Aviationstack** | ✅ 500 req/month | https://aviationstack.com |
| **OpenWeatherMap** | ✅ 1000 req/day | https://openweathermap.org/api |
| **Tavily** | ✅ 1000 req/month | https://tavily.com |
| **LangSmith** | ✅ Free for dev | https://smith.langchain.com |

---

## 🤖 Recommended OpenRouter Models

| Model | Speed | Quality | Notes |
|---|---|---|---|
| `meta-llama/llama-3.1-8b-instruct:free` | ⚡ Fast | ⭐⭐⭐ | **Default — free tier** |
| `meta-llama/llama-3.1-70b-instruct:free` | 🐢 Slower | ⭐⭐⭐⭐⭐ | Higher quality, free |
| `mistralai/mistral-7b-instruct:free` | ⚡ Fast | ⭐⭐⭐ | Lightweight alternative |
| `google/gemma-2-9b-it:free` | ⚡ Fast | ⭐⭐⭐ | Good instruction following |

Change the model in `.env`:
```env
OPENROUTER_MODEL=meta-llama/llama-3.1-70b-instruct:free
```

---

## 🐛 Troubleshooting

### `ModuleNotFoundError: No module named 'mcp.server.fastmcp'`
```powershell
pip install "mcp==1.9.4" --force-reinstall
```
mcp 2.x renamed FastMCP. This project is pinned to 1.9.4.

### `npx: command not found` (Tavily MCP fails)
Install Node.js from https://nodejs.org — then restart your terminal.

### `connection refused` on PostgreSQL
```sql
-- Ensure PostgreSQL is running, then:
CREATE DATABASE travel_planner;
```

### Graph never completes (stuck after planner)
Check LangSmith traces. Usually means the LLM returned an empty response — verify your `OPENROUTER_API_KEY` is valid.

### Weather forecast returns empty for dates
OpenWeatherMap free tier only provides a **5-day forecast window**. Use departure dates within the next 5 days for testing `get_forecast_for_date`.

---

## 📐 Key Design Decisions

### Why MCP for local scripts?
Flight and weather servers run as **stdio MCP subprocesses** — this decouples the API logic from the graph, making each server independently testable and replaceable.

### Why official Tavily MCP?
Tavily maintains their own MCP server (`npx tavily-mcp`). Using it means we get automatic updates and don't maintain dead code.

### Why one MCPManager?
All MCP connections are routed through [`mcp_client/mcp_manager.py`](mcp_client/mcp_manager.py). Adding a new data source means registering one entry in `_servers` — nodes stay clean.

### Why PostgreSQL checkpointing?
LangGraph's `interrupt()` pauses the graph mid-execution. PostgreSQL persists the state so the graph can resume across separate HTTP requests (user approval/feedback).

---

## 📜 License

MIT — feel free to use and adapt for learning purposes.
