# Chapter 2 — Setting Up Your Agent Workshop

This chapter takes you from an empty folder to a real, running agent, and then to a containerised version of it. The code is split into two stages that share the same tools and goal, so you can read the progression clearly.

## What You Will Build

A small agent that:
- Takes a question in plain English
- Decides on its own which tool can answer it (arithmetic or weather)
- Runs the tool, reads the result, and decides what to say next
- Can be chatted with from the terminal **or** through ADK's browser UI
- Ships as a Docker image without changing a line of code

## Prerequisites

| Tool | Check | Install |
|---|---|---|
| Python 3.10+ | `python3 --version` | [python.org/downloads](https://python.org/downloads) |
| Git | `git --version` | [git-scm.com/downloads](https://git-scm.com/downloads) |
| Docker Desktop | `docker --version` | [docs.docker.com/get-started/get-docker](https://docs.docker.com/get-started/get-docker) |
| A Gemini API key | — | [aistudio.google.com](https://aistudio.google.com) |

## Project Layout

```
chapter_2/
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── stage-1-raw-loop/
│   ├── __init__.py
│   └── raw_loop.py          # ~30-line perception–action loop, no framework
└── stage-2-adk-agent/
    ├── __init__.py
    └── agent.py             # Same agent rewritten with Google ADK
```

## Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\Activate.ps1       # Windows PowerShell

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API key
cp .env.example .env
# Open .env and replace the placeholder with your real Gemini API key
```

## Stage 1 — Raw Loop (no framework)

`stage-1-raw-loop/raw_loop.py` implements the perception–action loop directly with `google-genai`. It defines two async tools, builds the tool schema by hand, and drives the model in a `for` loop with a `max_steps` safety brake.

### Tools

| Tool | What it does |
|---|---|
| `calculator` | Evaluates arithmetic expressions (`21 * 7`, `(3 + 4) * 2`) |
| `get_weather` | Looks up the current temperature in Celsius via Open-Meteo (no API key needed) |

### Run

```bash
# from chapter-02-agent-workshop/
python -m stage-1-raw-loop.raw_loop
python -m stage-1-raw-loop.raw_loop "What is the temperature in Bengaluru?"
python -m stage-1-raw-loop.raw_loop "If it is 27 in Bengaluru and 14 in London, what is the difference?"
```

The third command makes two weather tool calls and one arithmetic call, all chosen by the model.

## Stage 2 — ADK Agent

`stage-2-adk-agent/agent.py` rewrites the same agent using `google-adk`. The behaviour is identical; the code is shorter and more declarative. The `eval`-based calculator is replaced with three typed primitives (`add`, `subtract`, `multiply`) and the weather function returns a structured dict.

### Tools

| Tool | What it does |
|---|---|
| `add(a, b)` | Returns `a + b` |
| `subtract(a, b)` | Returns `a - b` |
| `multiply(a, b)` | Returns `a * b` |
| `get_weather(city)` | Returns current temperature in Celsius for the named city |

### Run in the browser (ADK web UI)

```bash
# from chapter-02-agent-workshop/
adk web .
```

Open [http://localhost:8000](http://localhost:8000), pick `stage-2-adk-agent` from the dropdown, and ask the same questions. The right-hand panel shows every reasoning step, tool call, and tool response.

### Experiment with the instruction string

Open `stage-2-adk-agent/agent.py`, change the `instruction` field, save, and rerun `adk web .`. The agent's tone and behaviour will shift immediately — the system prompt is the policy layer.

## Docker

The Dockerfile packages the Stage 2 agent. The Compose file injects your Gemini key from `.env` at run time so the secret is never baked into the image.

```bash
# Build and start
docker compose up --build

# Stop
docker compose down
```

Open [http://localhost:8000](http://localhost:8000) — the same ADK web UI, running inside a container. The image runs unchanged on a laptop, on Cloud Run, or on a Kubernetes pod.

> **Note:** If you edit `agent.py` while the container is running, restart with `docker compose up --build` to pick up the change. The running container serves the image it was built from, not your live source files.

## How the Loop Works

```
user message
     │
     ▼
 model call  ──►  function_call?  ──yes──►  run tool  ──►  append result  ──► (repeat)
     │                                                                              │
     └── no ──► return plain text answer  ◄──────────────────────────────────────┘
```

The model never touches your filesystem or APIs directly. It sends a structured request naming a tool and its arguments; your code runs the function and feeds the result back. This indirection is the safety story of tool use.

## Key Concepts from This Chapter

- **Tool**: a typed Python function the model can request by name. ADK reads the signature and docstring to build the JSON Schema the model sees.
- **Agent loop**: call model → if tool call, run function and append result, repeat; if text, return.
- **max_steps**: the safety brake that prevents infinite loops when the model never decides it is done.
- **Instruction string**: the system prompt — the policy layer of the agent. No retraining, no redeploy; one paragraph of English.
- **root_agent**: the variable name ADK's web UI looks for when discovering agents in a directory.

## What Comes Next

- **Chapter 3** — The tools in this chapter live in the same process as the agent. The Model Context Protocol gives tools a network boundary and a discovery mechanism so any agent can call any tool without sharing a process.
- **Chapter 4** — Durable memory across sessions.
- **Chapter 6** — Multi-agent collaboration across an A2A boundary.
- **Chapter 10** — Redis for semantic caching (added as a second service in `docker-compose.yml`).
- **Chapter 11** — Langfuse tracing (added the same way).
