"""
memory_manager.py

Handles all disk I/O for the agent's memory.

Design decision:
  Memory is a JSON file with a flat list of string "facts".
  This keeps it human-readable and easy to inspect between sessions.

What belongs in memory:
  - Long-term goals and commitments the user has expressed
  - Behavioral patterns the user wants to change
  - Decisions the user made in past sessions

What does NOT belong in memory:
  - Account balances (stale by next session)
  - Transaction totals (snapshots, not patterns)
  - Upcoming bill amounts (always fetch live)
"""

import json
import os

MEMORY_FILE = "memory.json"


def load_memory() -> dict:
    """Load memory from disk. Returns empty structure if file doesn't exist yet."""
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    # First-ever run: return empty memory
    return {"facts": []}


def save_memory(memory: dict) -> None:
    """Persist the memory dict to disk as formatted JSON."""
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def add_facts(memory: dict, new_facts: list[str]) -> dict:
    """
    Add new facts to memory, skipping empty strings and exact duplicates.
    Returns the updated memory dict.
    """
    existing = set(memory.get("facts", []))
    for fact in new_facts:
        fact = fact.strip()
        if fact and fact not in existing:
            memory["facts"].append(fact)
            existing.add(fact)
    return memory
