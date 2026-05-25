# Chapter 4: Agent Memory with Mem0

"The agents people trust are the ones who recognise them on the second visit."

## Overview

This chapter teaches how to build long-term memory layers for AI agents using Mem0. By the end, you'll have:

- A shopping agent that remembers user preferences across conversations
- A support agent that shares memories with the shopping agent
- Memory infrastructure running as a Docker service
- A dashboard for monitoring what agents remember

The agents recognize who you are, recall what you cared about, and shape their answers accordingly.

## Project Structure

```
chapter-04-memory/
├── README.md                         # This file
├── requirements.txt                  # Python dependencies
├── .env.example                      # Template for environment variables
├── .gitignore                        # Git ignore rules
├── docker-compose.yml                # Docker setup for Mem0 and ChromaDB
├── catalog_data.py                   # Product catalog (all stages use this)
├── memory_tools.py                   # Local Mem0 client and tools (Stages 1-3)
├── memory_tools_http.py              # HTTP-backed Mem0 client (Stage 4)
├── stage_1_session_state/            # Session state memory only
│   ├── __init__.py
│   └── agent.py
├── stage_2_long_term_memory/         # Mem0 long-term memory (local)
│   ├── __init__.py
│   └── agent.py
├── stage_3_support_agent/            # Cross-agent memory sharing
│   ├── __init__.py
│   └── agent.py
└── stage_4_docker/                   # REST API memory (Docker)
    ├── __init__.py
    └── agent.py
```

## Four Stages of the Build

### Stage 1: Session State Memory
**Location:** `stage_1_session_state/agent.py`

A shopping agent that remembers the last product you viewed within a single conversation. When the conversation ends, the memory dies.

**Key Concepts:**
- ADK's `session.state` dictionary
- `after_tool_callback` to update state
- `{placeholder?}` syntax for injecting state into prompts

**To run:**
```bash
adk web .
# Select "stage_1_session_state" from the dropdown
```

### Stage 2: Long-term Memory with Mem0
**Location:** `stage_2_long_term_memory/agent.py`

The shopping agent now uses Mem0 to remember user preferences across conversations and days. The agent:
1. Calls `search_memory` at the start of every conversation
2. Calls `save_memory` when the user states personal facts
3. Shares the same memory store with other agents

**Key Concepts:**
- Mem0's fact extraction and retrieval
- User scoping with `user_id`
- Hybrid retrieval combining semantic search, keyword matching, and entity linking
- Local ChromaDB vector store

**To run:**
```bash
adk web .
# Select "stage_2_long_term_memory" from the dropdown
# Have a conversation: "Hi, I'm Alice. I avoid peanuts."
# End the conversation and start a new one
# Ask: "Recommend me a product" - it remembers Alice
```

### Stage 3: Cross-Agent Memory
**Location:** `stage_3_support_agent/agent.py`

A support agent that uses the same Mem0 store as the shopping agent. It can answer questions about allergies that the shopping agent learned in a previous conversation.

**The Demo:**
1. In Stage 2: Tell the shopping agent you avoid peanuts
2. Switch to Stage 3: Ask if the "peanut granola bar" is safe to eat
3. The support agent recalls your allergy and warns you about the ingredients

**Key Concepts:**
- Multiple agents sharing one memory store
- Zero orchestration code between agents
- Lightweight multi-agent collaboration

**To run:**
```bash
# In a browser, open two tabs with the ADK web UI
# Tab 1: Stage 2 (shopping agent)
#   "Hi, I'm Alice. I avoid peanuts."
#
# Tab 2: Stage 3 (support agent)
#   User dropdown: Set to "alice"
#   "I ordered the peanut granola bar. Is it safe?"
#   Watch it recall your allergy and check ingredients
```

### Stage 4: Docker Service
**Location:** `stage_4_docker/agent.py`

Mem0 runs as a separate REST API service in Docker. The agent talks to it over HTTP. Same behavior as Stage 2, but production-ready.

**Services:**
- **Mem0 REST API** on port 8888 (memory operations)
- **ChromaDB** on port 8000 (vector storage)
- **Dashboard** on port 3000 (memory visualization)

**To run:**
```bash
# Start Docker services
docker compose up -d

# Bootstrap admin account and get API key
docker exec -it chapter4-mem0 make bootstrap \
    EMAIL=admin@example.com PASSWORD='change-me' NAME='Admin'

# Copy the m0sk_... API key to .env
# Add: MEM0_API_KEY=m0sk_your_key_here

# Start the agent
adk web .
# Select "shopping_agent_docker" from the dropdown

# Open the dashboard
# http://localhost:3000
# Log in with your admin account
```

## Setup Instructions

### 1. Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

### 3. Set Up Environment Variables

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
echo "GEMINI_API_KEY=your-key-here" >> .env
echo "GOOGLE_API_KEY=your-key-here" >> .env
```

### 4. For Stages 1-3 (Local): No extra setup needed
Just run `adk web .` and start exploring.

### 5. For Stage 4 (Docker)

```bash
# Generate JWT secret
echo "MEM0_JWT_SECRET=$(openssl rand -base64 48)" >> .env

# Start Docker services
docker compose up -d

# Verify services are running
curl http://localhost:8888/        # Mem0 API
curl http://localhost:8000/api/v2/heartbeat  # ChromaDB

# Bootstrap admin account
docker exec -it chapter4-mem0 make bootstrap \
    EMAIL=admin@example.com PASSWORD='change-me' NAME='Admin'

# Add the API key to .env
# MEM0_API_KEY=m0sk_your_key_here
```

## Key Files Explained

### catalog_data.py
In-memory product catalog with 8 items across 4 categories. Used by all stages.
- `list_products()` - Browse products
- `get_product_details()` - Get full product info

### memory_tools.py
Mem0 client configured for Gemini LLM and HuggingFace embeddings. Used by Stages 1-3.
- `save_memory()` - Store a user fact
- `search_memory()` - Retrieve relevant facts

### memory_tools_http.py
HTTP client for the Mem0 REST server. Used by Stage 4.
- Same interface as memory_tools.py
- Talks to Docker container instead of local library

### Agent Files
Each stage has an agent with different capabilities:
- **Stage 1:** Shopping agent only (remembers within session)
- **Stage 2:** Shopping agent + memory tools (remembers across sessions)
- **Stage 3:** Support agent + memory tools (recalls shopping memories)
- **Stage 4:** Shopping agent + HTTP memory tools (production architecture)

## How Memory Works

### Three Layers

1. **Working Memory:** What the model sees right now (the prompt context)
2. **Session Memory:** Facts within one conversation (ADK's `session.state`)
3. **Long-term Memory:** Facts across conversations (Mem0's vector store)

### Mem0 Pipeline

```
User says: "I avoid peanuts"
    ↓
Mem0 extracts: "User avoids peanuts"
    ↓
Embed + store in ChromaDB
    ↓
On next query:
    search("allergies") → returns "User avoids peanuts"
```

### User Scoping

All memories are scoped by `user_id`. Alice and Bob never see each other's memories.

```python
# When saving
save_memory("I avoid peanuts", user_id="alice")

# When searching
search_memory("allergies", filters={"user_id": "alice"})
```

## Common Tasks

### Test Session Memory (Stage 1)
```
1. Ask about product p007
2. Say "What was the last book I looked at?"
3. Agent answers correctly
4. Close the conversation
5. Start a new one and ask the same question
6. Agent forgets (session state is gone)
```

### Test Long-term Memory (Stage 2)
```
1. "Hi, I'm Alice. I love sci-fi books."
2. Close the conversation
3. Start a fresh conversation
4. "Recommend me a book"
5. Agent recalls your preference (memories survived the conversation boundary)
```

### Test Cross-Agent Memory (Stage 3)
```
1. Stage 2 (shopping): "I'm seriously allergic to peanuts"
2. Stage 3 (support): Set user to "alice"
3. Stage 3: "Is the peanut granola bar safe?"
4. Watch it recall the allergy and check ingredients
```

### Monitor in Dashboard (Stage 4)
```
1. Open http://localhost:3000
2. Log in with admin account
3. Requests page: See API calls in real-time
4. Memories page: See extracted facts, one per row
5. Entities page: See all users, their memory counts, delete data
```

## Architecture Insights

### Why Mem0?

- **Fact Extraction:** The LLM extracts "User avoids peanuts" from loose conversation
- **Embedding:** Facts are embedded into a vector space for semantic search
- **Hybrid Retrieval:** Combines semantic + keyword + entity matching
- **User Scoping:** Per-user memory isolation built-in
- **No Graph DB:** Modern Mem0 uses entity linking instead of a separate Neo4j instance

### When to Save vs Search

**Call `save_memory` when:**
- User states their name
- User mentions allergies or dietary restrictions
- User expresses preferences ("I love sci-fi")
- User reveals explicit dislikes

**Do NOT save:**
- Questions the user asks
- Products they merely browsed
- Transient curiosity ("I'm wondering about...")

**Call `search_memory` when:**
- Starting a new conversation (always)
- User asks for recommendations
- User refers to past interactions
- You need context to answer

## Failure Modes & Fixes

### Memory Pollution
**Problem:** Agent saves "User is asking about laptops" instead of "User loves laptops"

**Fix:**
- Tighten agent instruction with explicit examples
- Use Mem0's `custom_instructions` config

### Embedder Dimension Mismatch
**Problem:** Change embedder model → search throws dimension error

**Fix:**
```bash
# Drop and recreate the vector store
docker compose down -v
docker compose up -d
```

Always pick your embedder at the start and plan for migration if you change it.

## Extending to Production

### Single Machine → Multi-Agent
```
Multiple agent replicas → shared Mem0 server → shared ChromaDB
```

### Add Ingress
```
External traffic → reverse proxy (nginx/Caddy) → Mem0 server
```

### Multi-Tenant
```
One Mem0 stack per tenant, each with its own namespace and data
```

## What's Next

- **Chapter 5:** Agent termination and budget controls
- **Chapter 6:** Agent-to-agent communication
- **Chapter 7:** Supervisor patterns for multi-agent routing
- **Chapter 11:** Instrument memory calls with Langfuse
- **Chapter 15:** Credential management and security
- **Chapter 16:** Full e-commerce swarm with MCP-fronted catalog

## Useful Links

- Mem0 docs: https://docs.mem0.ai/open-source/overview
- ChromaDB setup: https://cookbook.chromadb.dev/running/running-chroma
- ADK sessions: https://google.github.io/adk-docs/sessions/memory
- HuggingFace embeddings: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2

## Tips & Tricks

1. **Check What's in Memory:** Open `http://localhost:3000/memories` after running Stage 4
2. **See All API Calls:** The Requests page shows every memory operation in real-time
3. **Delete Bad Memories:** Click a user on the Entities page to cascade-delete all their data
4. **Test Multi-User:** Open the dashboard Entities page while switching between Alice and Bob
5. **Monitor Extraction Quality:** If weird facts appear in the Memories page, check your agent instruction
6. **Verify Service Health:** `curl http://localhost:8888/` and `curl http://localhost:8000/api/v2/heartbeat`

## Troubleshooting

**"OPENAI_API_KEY not found"**
- You're still using Memory() without .from_config()
- Make sure to import from memory_tools, not directly from mem0

**"Missing en_core_web_sm"**
- Run: `python -m spacy download en_core_web_sm`
- This enables entity linking for hybrid retrieval

**Docker containers don't start**
- Check logs: `docker compose logs mem0` and `docker compose logs chromadb`
- WSL users: Remove `credsStore` from `~/.docker/config.json`

**Agent doesn't remember between conversations**
- Check dashboard Memories page to see if facts were saved
- Check dashboard Requests page to see the save_memory call
- Verify user_id stays the same across conversations

**"Connection refused" on localhost:8888**
- Are the Docker containers running? `docker ps`
- Try `docker compose up -d` again
- Check port binding: `netstat -an | grep 8888`

## Learning Path

1. Start with **Stage 1** to understand ADK's session state
2. Move to **Stage 2** to see Mem0's extraction and retrieval
3. Go to **Stage 3** to experience cross-agent collaboration
4. End with **Stage 4** to see production architecture

Each stage builds on the previous one. The code is designed to be self-contained—you can run any stage on its own.

---

**Remember:** "The agents people trust are the ones who recognise them on the second visit."
