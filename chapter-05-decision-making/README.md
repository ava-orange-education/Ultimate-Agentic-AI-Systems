# Chapter 5: Decision-Making and Loops

This chapter extends the shopping agent from Chapter 4 with a menu of loop shapes, loop-control brakes, and multi-agent patterns — all built on the ADK 2.x `Workflow` primitive.

## Folder Structure

```
chapter-05-decision-making/
├── catalog_data.py                  # Shared product catalog (8 products)
├── returns_data.py                  # Mock orders table for Stage 4
├── requirements.txt
├── .env                             # GEMINI_API_KEY (create manually)
├── stage_1_react_with_brakes/
│   ├── __init__.py
│   └── agent.py                     # ReAct + tool-call cap + scratchpad cycle detection
├── stage_2_plan_and_execute/
│   ├── __init__.py
│   └── agent.py                     # Planner → Executor two-node Workflow chain
├── stage_3_evaluator_optimizer/
│   ├── __init__.py
│   └── agent.py                     # Generator → Critic → exit_check loop
└── stage_4_router/
    ├── __init__.py
    └── agent.py                     # Classifier → route_fn → specialist branch
```

## Setup

```bash
cd chapter-05-decision-making

# Create your .env file
echo "GEMINI_API_KEY=your-gemini-api-key-here" > .env

# Install dependencies
pip install -r requirements.txt

# Launch the ADK web UI (pick a stage from the dropdown)
adk web .
```

## The Four Stages

### Stage 1 — ReAct with Explicit Termination (`stage_1_react_with_brakes`)

**Agent name in UI:** `shopping_agent_with_brakes`

A standard ReAct shopping agent wrapped in three brakes:

| Brake | Mechanism | Threshold |
|---|---|---|
| Hard cap | `before_tool_callback` counts calls | 8 tool calls |
| Cycle detection | Scratchpad of normalized signatures + consecutive-empty counter | same sig = skip; 3 empty in a row = stop |
| Token budget | `before_model_callback` checks `tokens_used` | 20,000 tokens (stub; wired for Chapter 13) |

**Try these queries:**
1. `list me the food items` — normal path, one tool call
2. `list food items, then list them again, then again` — second call is skipped (same signature)
3. `find a product called Hyperion Stardust, then try other spellings` — 3 empty results trips the consecutive-empty brake

---

### Stage 2 — Plan-and-Execute (`stage_2_plan_and_execute`)

**Agent name in UI:** `plan_and_execute_shopper`

A two-node `Workflow` chain:

```
START → planner → executor
```

- **Planner**: no tools; writes a numbered plan into `session.state["plan"]` via `output_key`
- **Executor**: reads the plan through the `{plan}` placeholder and walks it with tools

**Try:** `what is the cheapest food item in the catalog?`

The planner writes the strategy up front; the executor follows it without thrashing.

---

### Stage 3 — Evaluator-Optimizer (`stage_3_evaluator_optimizer`)

**Agent name in UI:** `safety_message_writer`

A `Workflow` loop with a hard cap of 4 rounds:

```
START → generator → critic → exit_check
                    ↑             |
                    └── LOOP ─────┘
                                  └── STOP → finalize
```

- **Generator**: calls `get_product_details`, writes a safety message; reads `{critic_feedback?}` on subsequent rounds
- **Critic**: judges SAFETY / TONE / LENGTH; outputs `PASS` or `FAIL: <bullets>`
- **exit_check**: plain function node; routes `LOOP` (back to generator) or `STOP` (to terminal)

**Try:** `Alice avoids peanuts. Is product p005 safe for her?`

Watch the trace panel — typical run is 2 rounds; critic fires on tone in round 1.

---

### Stage 4 — Router (`stage_4_router`)

**Agent name in UI:** `triage_workflow`

A hybrid routing `Workflow`: LLM classifies, Python routes:

```
START → classifier → route_fn → SHOPPING → shopping_specialist
                              ↘ RETURNS  → returns_specialist
```

- **Classifier**: emits one of `SHOPPING` or `RETURNS`
- **route_fn**: deterministic function; sets `ctx.route` and forwards the original user message
- **shopping_specialist**: `list_products` + `get_product_details`
- **returns_specialist**: `get_order_status` + `initiate_return`

**Try these queries:**
1. `Show me the food items in the catalog` → routed to shopping
2. `I want to return order o1003` → routed to returns, return initiated
3. `Try to return order o1002` → routed to returns, rejected (past 30-day window), escalates to human

---

## Pattern Reference

### Table 1: When to use each loop shape

| Pattern | Failure mode it fixes | Cost vs. ReAct | Fits | Avoid for |
|---|---|---|---|---|
| **ReAct** (default) | — | 1× | Emergent tasks, under ~30 steps | Known fixed paths; quality-critical output |
| **Chain of Thought** | Shallow single-call reasoning | ~1× | Pure reasoning, no tools | Anything needing a tool lookup |
| **Plan-and-Execute** | One-step-at-a-time misrouting | 1.3×–2.0× | Multi-step, path knowable up front | Contingent paths that depend on results |
| **Reflection / Evaluator-Optimizer** | Model confidently wrong | ~1.5× typical | Measurable quality bar | Cheap, low-stakes answers |
| **Tree of Thoughts** | Linear search gets stuck | branching × depth | Scoreable search spaces | Fuzzy business tasks |
| **Router** | One agent with too many tools | +1 small call | Distinct request types | A single coherent task |
| **Orchestrator-Worker** | One agent juggling subtasks | sum of workers + integrator | Decomposable, parallelisable work | Simple single-specialist requests |
| **Multi-Agent Debate** | Unchallenged reasoning | 3×+ | Correctness over speed | Latency-sensitive paths |

### Table 2: Workflow building blocks

| Pattern | Workflow building block |
|---|---|
| ReAct | A single `LlmAgent` (brakes in callbacks) |
| Plan-and-Execute | Chain: `(START, planner, executor)` |
| Reflection / Evaluator-Optimizer | Loop: body nodes + conditional edge back + terminal exit node |
| Orchestrator-Worker | Fan-out tuple of workers → `JoinNode` → integrator |
| Router | Classifier node + route function node + routing-map edge |
| Hierarchical | A node that is itself a nested `Workflow` |

---

## Loop-Control Brakes

Every stage uses at least one of these mechanisms:

| Brake | Where it lives | Stage |
|---|---|---|
| Tool-call cap | `before_tool_callback` counter | Stage 1 |
| Scratchpad cycle detection | `before_tool_callback` + `after_tool_callback` | Stage 1 |
| Token budget | `before_model_callback` counter | Stage 1 (stub) |
| Graph termination | conditional edge → terminal node | Stage 3 |
| Round cap | `exit_check` function node | Stage 3 |
| Human override | human-in-the-loop node | Chapter 12 |

---

## Key Concepts

**`_signature(tool_name, args)`** — normalizes tool arguments (lowercase, sorted) so trivial rephrasings collapse to one scratchpad entry.

**`output_key`** — an `LlmAgent` parameter that writes the agent's final text into `session.state[key]`, making it available as `{key}` in downstream prompts.

**`{placeholder?}`** — the `?` form tells ADK not to raise if the key is absent in state (used for `{critic_feedback?}` in round 1 of Stage 3).

**`ctx.route`** — set by a function node to pick the outgoing edge from a routing-map `(node, {"LABEL": target, ...})`.

**Terminal node** — a node with no outgoing edges; control stops there and its return value is the workflow's final output.

---

## Next: Chapter 6

Stage 4's router works because both specialists live in the same Python process. Chapter 6 lifts the returns specialist into a separate A2A service so the two teams can develop, deploy, and scale independently.
