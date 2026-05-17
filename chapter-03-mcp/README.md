# Chapter 3 – Giving Agents Tools with MCP

This chapter builds the same MCP catalog server in four progressive stages.

## Folder structure

```
chapter-03-mcp/
├── README.md
├── requirements.txt
├── .env                          # shared by every stage (create from .env.example)
├── .env.example
├── .gitignore
├── docker-compose.yml
├── catalog_data.py               # shared catalog — imported by all stages
├── stage_1_stdio/
│   ├── __init__.py
│   ├── agent.py                  # shopping_agent (stdio transport)
│   └── catalog_server.py
├── stage_2_http/
│   ├── __init__.py
│   ├── catalog_server.py         # server only, no agent
│   └── Dockerfile
└── stage_3_adk/
    ├── __init__.py
    ├── agent.py                  # shopping_agent (HTTP transport)
    └── catalog_server.py
```

## Setup

```bash
cd chapter-03-mcp
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux / WSL
# .venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

## Stage 1 – stdio server + agent

The agent spawns the catalog server as a subprocess (stdio). Both run together
when you launch ADK Web.

```bash
# from chapter-03-mcp/
adk web --port 8002
```

Open http://localhost:8002 and select **stage_1_stdio** from the dropdown.

Test the server independently with MCP Inspector:

```bash
# macOS / Linux / WSL
npx @modelcontextprotocol/inspector .venv/bin/python stage_1_stdio/catalog_server.py

# Windows native
npx @modelcontextprotocol/inspector .venv\Scripts\python.exe stage_1_stdio\catalog_server.py
```

> **Windows note:** set `CATALOG_SERVER_PYTHON=.venv\Scripts\python.exe` in `.env`
> so the agent spawns the right interpreter.

## Stage 2 – Streamable HTTP server (no agent)

```bash
# from chapter-03-mcp/
python stage_2_http/catalog_server.py
```

Inspector → Streamable HTTP → `http://localhost:8000/mcp`

Docker:

```bash
docker compose up --build catalog
docker compose down
```

## Stage 3 – HTTP server + ADK agent

```bash
# Terminal 1 — catalog server on port 8001
# from chapter-03-mcp/
python stage_3_adk/catalog_server.py

# Terminal 2 — ADK web UI on port 8002
# from chapter-03-mcp/
adk web --port 8002
```

Open http://localhost:8002. The dropdown shows both **stage_1_stdio** and
**stage_3_adk** — compare them side by side. Stage 2 has no agent so it does
not appear.

## Port map

| Service              | Port |
|----------------------|------|
| Stage 2 catalog      | 8000 |
| Stage 3 catalog      | 8001 |
| ADK web UI           | 8002 |
| MCP Inspector        | 6274 |
