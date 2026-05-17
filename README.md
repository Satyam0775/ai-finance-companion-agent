# AI Finance Companion Agent

A minimal AI finance companion agent built for the Reach AI Engineer assignment.

The agent maintains persistent memory across sessions, intelligently uses financial tools, and combines long-term user context with fresh live data to make contextual financial decisions.

---

# Objective

The goal of this project was to build a lightweight AI agent that can:

* maintain memory across conversations
* decide when tools are needed
* avoid stale memory for changing financial data
* reason contextually about financial trade-offs
* remain simple and framework-light

The implementation intentionally avoids:

* LangChain
* CrewAI
* vector databases
* embeddings
* complex orchestration frameworks

The focus is on:

* memory engineering
* tool discipline
* context management
* deterministic computation
* conversational reasoning

---

# Tech Stack

* Python 3.10+
* Groq API
* llama-3.3-70b-versatile
* JSON persistence
* Deterministic Python arithmetic

---

# Project Structure

```text
finance_agent/
│
├── agent.py
├── prompts.py
├── memory_manager.py
├── tool_executor.py
├── session_runner.py
├── tools.py
├── sessions.md
├── requirements.txt
├── writeup_template.md
├── memory.json
│
├── outputs/
│   ├── session1_output.txt
│   └── session2_output.txt
│
├── logs/
│   └── transcript.txt
│
├── .gitignore
└── README.md
```

---

# Core Architecture

```text
User Input
    ↓
Memory Read
    ↓
LLM Tool Decision
    ↓
Deterministic Tool Execution
    ↓
Python Arithmetic Summaries
    ↓
LLM Response Generation
    ↓
Memory Extraction
    ↓
Memory Persistence
```

---

# Design Decisions

## 1. Memory vs Live Financial State

One of the most important architectural decisions was separating:

### Persistent Memory

Stored:

* long-term goals
* behavioral intentions
* user commitments
* financial preferences

Examples:

* save ₹15 lakh for house down payment
* reduce food delivery spending
* allocate ₹30,000 to house fund

### NOT Stored

Not persisted:

* account balances
* transaction totals
* upcoming bills
* temporary cash-flow data

These values become stale quickly and are always fetched live using tools.

---

## 2. Deterministic Arithmetic

The LLM is never responsible for:

* arithmetic
* totals
* filtering
* computations
* date calculations

All calculations are handled in Python inside:

```python
tool_executor.compute_summaries()
```

This avoids arithmetic hallucination and improves reliability.

---

## 3. Minimal Tool Usage

The agent is prompted to call only the minimum necessary tools.

Examples:

* spending question → transactions only
* affordability question → balances + upcoming bills
* reminder request → reminder tool only

This keeps the agent disciplined and efficient.

---

# Session Design

## Session 1

The agent:

* analyzes salary and savings
* evaluates food delivery spending
* discusses savings goals
* stores long-term financial intentions
* sets a reminder

## Session 2

The agent:

* recalls the earlier house-fund goal
* remembers spending-reduction goals
* fetches fresh balances and bills
* reasons about the ₹80,000 MacBook purchase
* gives contextual advice instead of simplistic yes/no answers

This demonstrates:

* persistent memory
* contextual reasoning
* live-state revalidation
* tool discipline

---

# Running The Project

## 1. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 2. Create `.env`

```env
GROQ_API_KEY=your_groq_api_key
```

---

## 3. Run Session 1

Set in `tools.py`:

```python
CURRENT_SESSION = 1
```

Then run:

```bash
python session_runner.py 1
```

---

## 4. Run Session 2

Set in `tools.py`:

```python
CURRENT_SESSION = 2
```

Then run:

```bash
python session_runner.py 2
```

---

# Output Files

## Clean Outputs

Located in:

```text
outputs/
```

Contains:

* clean assistant responses
* final conversational outputs

---

## Full Internal Logs

Located in:

```text
logs/transcript.txt
```

Contains:

* memory reads
* memory writes
* tool decisions
* tool calls
* computed summaries
* raw LLM responses

---

# Example Memory State

```json
{
  "facts": [
    "Committed to saving ₹15 lakh in 2 years for a house down payment",
    "Aim to allocate ₹30,000 to the house fund this month",
    "wants to reduce food delivery expenses"
  ]
}
```

---

# LLM Usage Philosophy

The LLM is used ONLY for:

* conversational reasoning
* contextual judgment
* tool selection
* response generation
* memory extraction

Python code handles:

* arithmetic
* financial calculations
* deterministic logic
* persistence
* date handling

---

# Assignment Alignment

This implementation directly addresses the assignment goals:

* memory engineering
* tool orchestration
* context management
* reasoning across sessions
* persistent state
* lightweight agent architecture

---

# Future Improvements

With additional time, possible improvements include:

* typed memory categories
* contradiction resolution in memory
* memory relevance ranking
* better reminder date parsing
* affordability scoring system
* lightweight memory retrieval heuristics

---

# Author

Satyam Kumar
