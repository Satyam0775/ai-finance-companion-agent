"""
tool_executor.py

Two responsibilities:
  1. execute_tool()     — dispatches tool calls to tools.py functions
  2. compute_summaries() — ALL arithmetic lives here, never in the LLM

Design decision:
  Filtering transactions by date is deterministic Python code, not LLM work.
  Summing categories, totaling bills, computing targets — all code, not LLM.
  The LLM only receives pre-computed numbers and uses them in its prose.
"""

import json
from datetime import date, timedelta

from tools import (
    get_recent_transactions,
    get_account_balance,
    get_upcoming_bills,
    set_reminder,
    CURRENT_SESSION,
)

# "Today" for each session — mirrors the mock data in tools.py
SESSION_TODAY: dict[int, date] = {
    1: date(2025, 11, 3),  # Monday — salary just credited
    2: date(2025, 11, 6),  # Thursday — rent paid, a few more food orders
}


def _today() -> date:
    """Return the logical 'today' for whichever session is active."""
    return SESSION_TODAY.get(CURRENT_SESSION, date.today())


# ─── Tool dispatcher ──────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict):
    """
    Execute a named tool with given arguments and return its raw result.
    Date-based filtering for transactions is done here (deterministic Python).
    """
    if name == "get_recent_transactions":
        days = int(args.get("days", 33))
        all_txns = get_recent_transactions(days)
        # Filter to the requested window — left to caller per tools.py spec
        cutoff = _today() - timedelta(days=days)
        return [t for t in all_txns if date.fromisoformat(t["date"]) >= cutoff]

    elif name == "get_account_balance":
        return get_account_balance()

    elif name == "get_upcoming_bills":
        days = int(args.get("days", 30))
        return get_upcoming_bills(days)

    elif name == "set_reminder":
        return set_reminder(args["date"], args["content"])

    else:
        return {"error": f"Unknown tool: {name}"}


# ─── Deterministic computations — NEVER done by LLM ─────────────────────────

def _sum_category(transactions: list[dict], category: str) -> int:
    """Sum absolute debit amounts for a spending category."""
    return sum(abs(t["amount"]) for t in transactions if t["category"] == category)


def _total_bills(bills: list[dict]) -> int:
    """Sum all upcoming bill amounts."""
    return sum(b["amount"] for b in bills)


def compute_summaries(tool_results: dict) -> dict:
    """
    Run all arithmetic on raw tool outputs.
    Returns a flat dict of pre-computed numbers for the LLM to cite in its response.

    The LLM must use these numbers as-is — it does zero math of its own.
    """
    summaries: dict = {}

    if "get_recent_transactions" in tool_results:
        txns = tool_results["get_recent_transactions"]
        food_spend = _sum_category(txns, "food_delivery")
        summaries["food_delivery_spend_inr"]       = food_spend
        summaries["food_delivery_halved_target_inr"] = food_spend // 2
        summaries["shopping_spend_inr"]            = _sum_category(txns, "shopping")
        summaries["total_debits_inr"]              = sum(
            abs(t["amount"]) for t in txns if t["amount"] < 0
        )
        summaries["transaction_window_days"]       = (
            (_today() - date.fromisoformat(txns[0]["date"])).days if txns else 0
        )

    if "get_upcoming_bills" in tool_results:
        bills = tool_results["get_upcoming_bills"]
        summaries["total_upcoming_bills_inr"] = _total_bills(bills)

    if "get_account_balance" in tool_results:
        bal = tool_results["get_account_balance"]
        summaries["checking_inr"]      = bal.get("checking", 0)
        summaries["savings_inr"]       = bal.get("savings", 0)
        summaries["house_fund_inr"]    = bal.get("house_fund", 0)
        summaries["mutual_funds_inr"]  = bal.get("mutual_funds", 0)
        summaries["liquid_total_inr"]  = bal.get("checking", 0) + bal.get("savings", 0)

    # If we have both balances and bills, compute what's left after committed outflows
    if "total_upcoming_bills_inr" in summaries and "checking_inr" in summaries:
        summaries["checking_after_bills_inr"] = (
            summaries["checking_inr"] - summaries["total_upcoming_bills_inr"]
        )

    return summaries
