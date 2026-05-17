# AI Finance Companion Agent

A minimal AI finance agent that maintains memory across sessions,
uses provided finance tools, and demonstrates context-aware reasoning.

---

## Project Structure

```
finance_agent/
├── tools.py            # provided — do not modify
├── sessions.md         # provided — do not modify
│
├── agent.py            # core agent loop
├── memory_manager.py   # load/save/update memory.json
├── prompts.py          # all LLM prompts
├── tool_executor.py    # tool dispatch + all Python arithmetic
├── session_runner.py   # replays sessions from sessions.md
│
├── memory.json         # created automatically at runtime
├── requirements.txt
├── writeup_template.md
│
├── logs/
│   └── transcript.txt  # full log: tool calls, memory reads/writes, LLM output
│
└── outputs/
    ├── session1_output.txt   # clean turn-by-turn output
    └── session2_output.txt
```

---

## Setup

```bash
pip install -r requirements.txt

# Option A — .env file (recommended)
cp .env.example .env
# edit .env and paste your GROQ_API_KEY

# Option B — export directly
export GROQ_API_KEY="gsk_..."
```

---

## Running

### Session 1 (Monday, Nov 3, 2025)

Make sure `CURRENT_SESSION = 1` in `tools.py` (default), then:

```bash
python session_runner.py 1
```

This will:
- Run all 4 turns from Session 1
- Write memory to `memory.json`
- Write clean output to `outputs/session1_output.txt`
- Append full log to `logs/transcript.txt`

### Session 2 (Thursday, Nov 6, 2025)

Change `CURRENT_SESSION = 2` in `tools.py`, then:

```bash
python session_runner.py 2
```

The agent will load the memory saved from Session 1 and use it to reason about
the MacBook purchase question.

---

## Architecture

```
user message
  → load memory.json
  → LLM decides which tools to call     (judgment)
  → execute tools in Python             (deterministic)
  → compute summaries in Python         (deterministic — no LLM math)
  → LLM generates response              (reasoning + language)
  → LLM identifies new memory facts     (judgment)
  → save updated memory.json
  → log everything
```

**Two LLM calls per turn** (via Groq — `llama-3.3-70b-versatile`, fallback `llama3-8b-8192`)**:**
1. Tool decision  (TOOL_DECISION_PROMPT → JSON list of tools)
2. Response + memory update  (RESPONSE_PROMPT → JSON with response + memory_updates)

**Zero LLM math:**
All arithmetic (summing categories, computing targets, totaling bills) lives in
`tool_executor.compute_summaries()`. The LLM only cites pre-computed numbers.

---

## What is stored in memory

**Stored** (long-term facts only):
- User goals and commitments
- Behavioural patterns the user wants to change
- Actions the agent took (reminders set)

**Not stored** (always fetched live):
- Account balances
- Transaction totals
- Upcoming bill amounts

---

## Log format

```
[USER]
message text

[MEMORY READ]
  - fact 1
  - fact 2

[LLM TOOL DECISION]
{"tools": [{"name": "get_account_balance", "args": {}}]}

[TOOL CALL] get_account_balance({})
[TOOL RESULT]
{ "checking": 128000, ... }

[COMPUTED SUMMARIES (Python arithmetic)]
{ "checking_inr": 128000, ... }

[LLM RESPONSE]
{"response": "...", "memory_updates": [...]}

[MEMORY WRITE]
  + new fact stored

[ASSISTANT]
response text
```
