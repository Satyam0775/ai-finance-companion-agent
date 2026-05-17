"""
agent.py

The core agent loop. One function per stage, called in sequence.

Flow for each user turn:
  1. Load memory from disk              (memory_manager)
  2. Log memory context                 (visible in transcript)
  3. Ask LLM which tools to call        (LLM judgment — prompts.TOOL_DECISION_PROMPT)
  4. Fix reminder dates deterministically(Python — LLM must NOT hallucinate dates)
  5. Execute tools in Python            (tool_executor.execute_tool — deterministic)
  6. Compute numeric summaries          (tool_executor.compute_summaries — no LLM math)
  7. Ask LLM to generate response       (LLM reasoning — prompts.RESPONSE_PROMPT)
  8. Extract memory updates from reply  (LLM judgment)
  9. Save updated memory to disk        (memory_manager)
 10. Log everything

LLM is used ONLY for steps 3, 7, and 8 — judgment and language, never arithmetic.
LLM provider: Groq  (llama-3.3-70b-versatile, fallback: llama3-8b-8192)
"""

import os
import re
import json
from datetime import date, timedelta

from dotenv import load_dotenv
from groq import Groq, APIError, APIConnectionError, AuthenticationError

from memory_manager import load_memory, save_memory, add_facts
from tool_executor import execute_tool, compute_summaries
from prompts import SYSTEM_PROMPT, TOOL_DECISION_PROMPT, RESPONSE_PROMPT

# Load .env file — searches current directory and all parents.
# Must be called before any os.getenv() so the key is available.
load_dotenv(override=True)

# ─── Logging setup ────────────────────────────────────────────────────────────
# Logs go to both stdout and logs/transcript.txt (appended so both sessions
# accumulate in a single file).

os.makedirs("logs",    exist_ok=True)
os.makedirs("outputs", exist_ok=True)

_log_fh = open("logs/transcript.txt", "a", encoding="utf-8")


def _log(msg: str) -> None:
    """Write to stdout and the transcript file."""
    print(msg)
    _log_fh.write(msg + "\n")
    _log_fh.flush()


# ─── Groq API key — load, debug, validate ────────────────────────────────────

def _load_and_validate_api_key() -> str:
    """
    Load GROQ_API_KEY from environment (populated by load_dotenv above),
    print safe diagnostics, and validate the key format before returning it.
    Raises a clear EnvironmentError if anything looks wrong.
    """
    raw_key = os.getenv("GROQ_API_KEY", "")
    api_key = raw_key.strip()          # remove accidental whitespace / newlines

    # ── Safe debug output (never prints the full key) ──────────────────────
    key_loaded  = "YES" if api_key else "NO"
    key_prefix  = api_key[:8] if len(api_key) >= 8 else "(too short)"
    key_length  = len(api_key)

    print(f"[DEBUG] GROQ_API_KEY loaded : {key_loaded}")
    print(f"[DEBUG] Key prefix          : {key_prefix}")
    print(f"[DEBUG] Key length          : {key_length}")

    # ── Validation ──────────────────────────────────────────────────────────
    if not api_key:
        raise EnvironmentError(
            "\n[ERROR] GROQ_API_KEY is not set.\n"
            "  1. Rename .env.example  →  .env\n"
            "  2. Open .env and replace the placeholder with your real key.\n"
            "  3. Get a free key at: https://console.groq.com → API Keys\n"
        )

    if not api_key.startswith("gsk_"):
        raise EnvironmentError(
            f"\n[ERROR] GROQ_API_KEY looks wrong — Groq keys start with 'gsk_'.\n"
            f"  Got prefix : '{api_key[:8]}'\n"
            f"  Check your .env file for typos or copy-paste errors.\n"
            f"  Regenerate at: https://console.groq.com → API Keys\n"
        )

    if key_length < 40:
        raise EnvironmentError(
            f"\n[ERROR] GROQ_API_KEY looks too short (got {key_length} chars).\n"
            f"  A valid Groq key is typically 50–80 characters.\n"
            f"  Regenerate at: https://console.groq.com → API Keys\n"
        )

    print(f"[DEBUG] Key validation      : PASSED\n")
    return api_key


_GROQ_API_KEY = _load_and_validate_api_key()

# ─── Groq client ──────────────────────────────────────────────────────────────

_client = Groq(api_key=_GROQ_API_KEY)
_MODEL_PRIMARY  = "llama-3.3-70b-versatile"
_MODEL_FALLBACK = "llama3-8b-8192"


# ─── Session date resolution (deterministic, no LLM) ─────────────────────────
# Import CURRENT_SESSION from tools to stay in sync with the session flag.
from tools import CURRENT_SESSION

_SESSION_TODAY: dict[int, date] = {
    1: date(2025, 11, 3),   # Monday
    2: date(2025, 11, 6),   # Thursday
}

# Keywords that indicate the user wants a reminder set.
_REMINDER_KEYWORDS = ("remind", "reminder", "don't forget", "dont forget", "alert me", "notify me")


def _today() -> date:
    """Return the canonical 'today' for the current session."""
    return _SESSION_TODAY.get(CURRENT_SESSION, date(2025, 11, 3))


def _resolve_reminder_date(user_message: str) -> str | None:
    """
    Deterministically infer the correct reminder date from the user message.

    Strategy (in priority order):
      1. Explicit ordinal/cardinal day-of-month  →  nearest future occurrence in Nov 2025
      2. "tomorrow"                              →  today + 1 day
      3. "next week"                             →  today + 7 days
      4. "end of month" / "month end"            →  last day of current month

    Returns a 'YYYY-MM-DD' string, or None if no reminder intent is detected
    (so the caller knows not to inject/override a set_reminder call).
    """
    msg = user_message.lower()

    # Gate: only proceed if the user actually wants a reminder.
    if not any(kw in msg for kw in _REMINDER_KEYWORDS):
        return None

    today = _today()

    # ── 1. Explicit day number: "25th", "the 10th", "on 15", etc. ────────────
    day_match = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\b", msg)
    if day_match:
        day = int(day_match.group(1))
        if 1 <= day <= 31:
            try:
                candidate = today.replace(day=day)
                # If the day has already passed this month, roll to next month.
                if candidate < today:
                    if today.month == 12:
                        candidate = candidate.replace(year=today.year + 1, month=1)
                    else:
                        candidate = candidate.replace(month=today.month + 1)
                return candidate.strftime("%Y-%m-%d")
            except ValueError:
                pass  # e.g. Feb 30 — fall through to other patterns

    # ── 2. Relative: tomorrow ─────────────────────────────────────────────────
    if "tomorrow" in msg:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    # ── 3. Relative: next week ────────────────────────────────────────────────
    if "next week" in msg:
        return (today + timedelta(weeks=1)).strftime("%Y-%m-%d")

    # ── 4. End of month ───────────────────────────────────────────────────────
    if "end of month" in msg or "month end" in msg:
        if today.month == 12:
            last_day = today.replace(day=31)
        else:
            last_day = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
        return last_day.strftime("%Y-%m-%d")

    # Reminder intent detected but no parseable date — fall back to today.
    _log("[DATE FALLBACK] Reminder intent detected but no date parsed; using today.")
    return today.strftime("%Y-%m-%d")


def _fix_reminder_dates(tool_calls: list[dict], user_message: str) -> list[dict]:
    """
    Post-process the LLM's tool-call list:
      • If the LLM decided to call set_reminder, override its `date` arg with the
        deterministically resolved date — the LLM must never own date arithmetic.
      • If the user clearly wants a reminder but the LLM forgot to include
        set_reminder, inject it automatically.

    This is purely deterministic Python — no LLM involvement.
    """
    resolved_date = _resolve_reminder_date(user_message)
    if resolved_date is None:
        # No reminder intent detected; nothing to do.
        return tool_calls

    fixed: list[dict] = []
    reminder_already_present = False

    for tc in tool_calls:
        if tc.get("name") == "set_reminder":
            reminder_already_present = True
            tc = dict(tc)                              # shallow copy — don't mutate
            tc["args"] = dict(tc.get("args", {}))
            original_date = tc["args"].get("date", "(none)")
            tc["args"]["date"] = resolved_date
            _log(
                f"[DATE FIX] set_reminder date overridden: "
                f"'{original_date}' → '{resolved_date}'"
            )
        fixed.append(tc)

    # Inject a set_reminder call if the LLM missed it despite clear user intent.
    if not reminder_already_present:
        # Try to extract reminder content from the message (best-effort).
        content_match = re.search(
            r"remind(?:\s+me)?\s+(?:to\s+|about\s+)?(.+?)(?:\s+on\b|$)",
            user_message,
            re.IGNORECASE,
        )
        content = content_match.group(1).strip() if content_match else user_message[:80]
        injected = {"name": "set_reminder", "args": {"date": resolved_date, "content": content}}
        fixed.append(injected)
        _log(
            f"[DATE FIX] set_reminder injected (LLM missed it): "
            f"date={resolved_date}, content='{content}'"
        )

    return fixed


# ─── LLM helpers ──────────────────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    """
    Single Groq chat-completion call with the shared system prompt.
    Only called for judgment/reasoning — never for arithmetic.
    Tries the primary model first; falls back to the smaller model on error.
    """
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": prompt},
    ]

    for model in (_MODEL_PRIMARY, _MODEL_FALLBACK):
        try:
            response = _client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1200,
                temperature=0.3,   # lower = more consistent JSON output
            )
            return response.choices[0].message.content.strip()

        except AuthenticationError:
            raise EnvironmentError(
                "\n[ERROR] Groq authentication failed — the API key was rejected.\n"
                "  Possible causes:\n"
                "    • Key was deleted or rotated on the Groq dashboard\n"
                "    • You copied the key with extra spaces or a missing character\n"
                "    • The .env file was not saved after editing\n"
                "  Steps to fix:\n"
                "    1. Go to https://console.groq.com → API Keys\n"
                "    2. Delete the old key and create a new one\n"
                "    3. Paste the new key into your .env file\n"
                "    4. Save .env, then re-run the session\n"
            )
        except APIConnectionError as exc:
            _log(f"[WARNING] Could not reach Groq API ({model}): {exc}")
            if model == _MODEL_FALLBACK:
                raise
        except APIError as exc:
            _log(f"[WARNING] Groq API error with {model}: {exc} — trying fallback.")
            if model == _MODEL_FALLBACK:
                raise

    # Should never reach here; the loop always raises on the fallback
    raise RuntimeError("All Groq model attempts failed.")


def _parse_json(raw: str) -> dict:
    """
    Robustly parse JSON from an LLM response.
    Strips markdown fences (```json … ```) if present.
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop the opening fence (```json or ```) and the closing fence (```)
        inner = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(inner).strip()
    return json.loads(text)


# ─── Stage helpers ────────────────────────────────────────────────────────────

def _format_facts(memory: dict) -> str:
    facts = memory.get("facts", [])
    return "\n".join(f"  - {f}" for f in facts) if facts else "  (none yet)"


def _decide_tools(user_message: str, memory: dict) -> list[dict]:
    """
    Stage 3 — LLM decides which tools to call.
    Returns a list of {"name": ..., "args": {...}} dicts.
    """
    prompt = TOOL_DECISION_PROMPT.format(
        user_message=user_message,
        memory_facts=_format_facts(memory),
    )
    raw = _call_llm(prompt)
    _log(f"\n[LLM TOOL DECISION]\n{raw}")
    try:
        return _parse_json(raw).get("tools", [])
    except json.JSONDecodeError:
        _log("[WARNING] Could not parse tool decision JSON — skipping tools this turn.")
        return []


def _run_tools(tool_calls: list[dict]) -> dict:
    """
    Stage 5 — Execute each tool call, log inputs and outputs.
    Returns {tool_name: raw_result}.
    """
    results: dict = {}
    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("args", {})
        _log(f"\n[TOOL CALL] {name}({json.dumps(args)})")
        result = execute_tool(name, args)
        _log(f"[TOOL RESULT]\n{json.dumps(result, indent=2, ensure_ascii=False)}")
        results[name] = result
    return results


def _generate_response(
    user_message: str,
    memory: dict,
    tool_results: dict,
    summaries: dict,
) -> tuple[str, list[str]]:
    """
    Stage 7+8 — LLM generates the reply and identifies what to remember.
    Returns (response_text, list_of_new_memory_facts).
    """
    prompt = RESPONSE_PROMPT.format(
        user_message=user_message,
        memory_facts=_format_facts(memory),
        tool_results=(
            json.dumps(tool_results, indent=2, ensure_ascii=False)
            if tool_results else "No tools were called."
        ),
        computed_summaries=(
            json.dumps(summaries, indent=2, ensure_ascii=False)
            if summaries else "No computations."
        ),
    )
    raw = _call_llm(prompt)
    _log(f"\n[LLM RESPONSE]\n{raw}")
    try:
        parsed = _parse_json(raw)
        return parsed["response"], parsed.get("memory_updates", [])
    except (json.JSONDecodeError, KeyError):
        # Fallback: treat the whole output as the response, no memory updates
        _log("[WARNING] Could not parse response JSON — using raw text.")
        return raw, []


# ─── Public interface ─────────────────────────────────────────────────────────

def process_turn(user_message: str, memory: dict) -> dict:
    """
    Run one full agent turn and return {"response": str, "memory": dict}.

    The caller is responsible for passing in the current memory and for
    threading the returned memory into the next turn.
    """
    _log(f"\n{'=' * 60}")
    _log(f"[USER]\n{user_message}")

    # Stage 1+2: display memory context
    _log(f"\n[MEMORY READ]\n{_format_facts(memory)}")

    # Stage 3: LLM decides tools (judgment)
    tool_calls = _decide_tools(user_message, memory)

    # Stage 4: fix reminder dates deterministically — LLM must not own date logic
    tool_calls = _fix_reminder_dates(tool_calls, user_message)

    # Stage 5: execute tools (deterministic Python)
    tool_results = _run_tools(tool_calls)

    # Stage 6: compute numeric summaries (deterministic Python — no LLM math)
    summaries = compute_summaries(tool_results)
    if summaries:
        _log(
            f"\n[COMPUTED SUMMARIES (Python arithmetic)]\n"
            f"{json.dumps(summaries, indent=2, ensure_ascii=False)}"
        )

    # Stage 7+8: LLM generates response and identifies memory updates
    response, memory_updates = _generate_response(
        user_message, memory, tool_results, summaries
    )

    # Stage 9: persist new memory facts
    if memory_updates:
        memory = add_facts(memory, memory_updates)
        save_memory(memory)
        _log(f"\n[MEMORY WRITE]")
        for fact in memory_updates:
            _log(f"  + {fact}")

    _log(f"\n[ASSISTANT]\n{response}")
    return {"response": response, "memory": memory}