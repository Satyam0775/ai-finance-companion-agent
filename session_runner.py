"""
session_runner.py

Replays the exact user messages from sessions.md, in order.
Writes a clean output transcript to outputs/sessionN_output.txt.
The full detailed log (tool calls, memory reads/writes, LLM raw output)
goes to logs/transcript.txt via agent.py.

Usage:
    python session_runner.py 1   # Run Session 1 (set CURRENT_SESSION=1 in tools.py first)
    python session_runner.py 2   # Run Session 2 (set CURRENT_SESSION=2 in tools.py first)
"""

import sys
import os

from agent import process_turn, _log
from memory_manager import load_memory

# ─── Session messages (exact text from sessions.md) ──────────────────────────

SESSION_1_MESSAGES = [
    "I just got my salary credited. Help me figure out how much I can realistically save this month.",
    "I feel like I'm spending too much on food delivery. How much did I actually spend on it last month?",
    (
        "Okay that's worse than I thought. Let's say I want to cut that in half AND put aside " 
        "₹30,000 for my house fund this month — is that realistic given my upcoming bills?"
    ),
    "Got it. Remind me to actually transfer the ₹30,000 to my house fund on the 25th.",
]

SESSION_2_MESSAGES = [
    "Hey, my colleague is selling his MacBook for ₹80,000, barely used. I've been wanting to upgrade. Should I buy it?",
]


# ─── Runner ───────────────────────────────────────────────────────────────────

def run_session(session_num: int, messages: list[str], output_file: str) -> None:
    """
    Process all turns for a session.
    Memory is loaded once at the start; each turn may update it on disk.
    """
    os.makedirs("outputs", exist_ok=True)
    memory = load_memory()

    _log(f"\n{'#' * 60}")
    _log(f"# SESSION {session_num}")
    _log(f"{'#' * 60}")

    clean_turns: list[dict] = []

    for msg in messages:
        result     = process_turn(msg, memory)
        memory     = result["memory"]          # carry forward any updates
        clean_turns.append({
            "user":      msg,
            "assistant": result["response"],
        })

    # Write a human-readable clean output (no raw LLM / tool noise)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"SESSION {session_num} — Clean Output\n")
        f.write("=" * 60 + "\n\n")
        for i, turn in enumerate(clean_turns, 1):
            f.write(f"[Turn {i}]\n")
            f.write(f"USER:      {turn['user']}\n\n")
            f.write(f"ASSISTANT: {turn['assistant']}\n\n")
            f.write("-" * 60 + "\n\n")

    _log(f"\n✅  Session {session_num} complete.")
    _log(f"    Clean output  → {output_file}")
    _log(f"    Full log      → logs/transcript.txt")
    _log(f"    Memory state  → memory.json")


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("1", "2"):
        print("Usage:  python session_runner.py [1|2]")
        sys.exit(1)

    session = int(sys.argv[1])

    if session == 1:
        _log("\n🔵  SESSION 1 — Monday, Nov 3, 2025")
        _log("    Make sure CURRENT_SESSION = 1 in tools.py\n")
        run_session(1, SESSION_1_MESSAGES, "outputs/session1_output.txt")
        _log("\n→  Memory written to memory.json.")
        _log("→  Now set CURRENT_SESSION = 2 in tools.py, then run:")
        _log("   python session_runner.py 2\n")

    elif session == 2:
        _log("\n🟢  SESSION 2 — Thursday, Nov 6, 2025")
        _log("    Make sure CURRENT_SESSION = 2 in tools.py\n")
        run_session(2, SESSION_2_MESSAGES, "outputs/session2_output.txt")
