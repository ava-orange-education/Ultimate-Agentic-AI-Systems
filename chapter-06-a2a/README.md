# Chapter 6: Agent-to-Agent Communication with A2A

This chapter takes the router from Chapter 5 and gives its returns branch a
network boundary. The returns specialist is lifted out of the shopping
router's process, wrapped as an ADK `Workflow` graph, and exposed as its own
A2A service. The router is then rewired to reach it over HTTP through a
`RemoteA2aAgent` node instead of importing it as a local object.

## Folder Structure

```
chapter-06-a2a/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── docker-compose.yml
├── catalog_data.py          # shared product catalog, carried from Chapter 3/5
├── returns_data.py          # mock orders table, carried from Chapter 5
├── probe.py                 # tiny raw A2A client — see the protocol on the wire
├── returns_service/         # the A2A server
│   ├── __init__.py
│   ├── agent.py             # returns graph + to_a2a -> a2a_app
│   └── Dockerfile
└── shopping_desk/           # the A2A client (the router)
    ├── __init__.py
    ├── agent.py             # router graph with a RemoteA2aAgent node
    └── Dockerfile
```

## Setup

```bash
cd chapter-06-a2a
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux / WSL
# .venv\Scripts\Activate.ps1      # Windows PowerShell
pip install -r requirements.txt
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

## Stage 1 — The Returns Specialist as an A2A Service

The returns specialist from Chapter 5 (an `LlmAgent` with `get_order_status`
and `initiate_return`) is wrapped in a one-node `Workflow` called
`returns_desk`, given an explicit `AgentCard`, and turned into a running ASGI
app with a single call to `to_a2a`. Start it with uvicorn:

```bash
# from chapter-06-a2a/
uvicorn returns_service.agent:a2a_app --host 0.0.0.0 --port 8080
```

The returns desk is now a live A2A agent, reachable over the network,
independent of the shopping process.

## Stage 2 — Looking at the Wire

With the returns service running, fetch its Agent Card at the well-known
path:

```bash
curl http://localhost:8080/.well-known/agent-card.json
```

Then send it real work with the raw A2A client probe:

```bash
# from chapter-06-a2a/ (returns service must be running)
python probe.py
```

The response is a `Task`, not a bare string — you will see a task id, a
context id, a status of `TASK_STATE_COMPLETED`, and an artifact carrying the
specialist's answer.

## Stage 3 — Consuming the Returns Service from the Router

`shopping_desk/agent.py` is the Chapter 5 router with one change: the
`RETURNS` branch now points at `returns_remote`, a `RemoteA2aAgent` that
resolves the returns service's Agent Card and forwards work to it, instead
of a local `returns_specialist` object. Everything else — the classifier,
`route_fn`, and the local `shopping_specialist` — is unchanged.

Run both services in two terminals:

```bash
# terminal 1: the returns service
# from chapter-06-a2a/
uvicorn returns_service.agent:a2a_app --host 0.0.0.0 --port 8080

# terminal 2: the shopping desk web UI
# from chapter-06-a2a/
adk web .
```

Open the ADK web UI at http://localhost:8000, pick `shopping_desk`, and try:

1. `Show me the books in the catalog` → routed to `SHOPPING`, answered
   locally by `shopping_specialist`.
2. `I want to return order o1001, it was the wrong size` → routed to
   `RETURNS`, answered by the remote returns service over A2A.
3. `Try to return order o1002` → routed to `RETURNS`, rejected (past the
   30-day window), escalates to a human agent.

## Stage 4 — Both Agents Under Docker Compose

`docker-compose.yml` builds and runs both services on a shared network, with
the shopping desk reaching the returns agent by its Compose service name
(`returns-agent`) rather than a hard-coded IP.

```bash
# from chapter-06-a2a/
docker compose up --build
```

Open http://localhost:8000 and ask the same two questions. The shopping
answer is produced inside the `shopping-agent` container; the returns answer
crosses the Compose network to the `returns-agent` container, discovered
through the Agent Card it publishes at its well-known path.

```bash
docker compose down
```
