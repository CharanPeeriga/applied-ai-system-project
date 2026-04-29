import json
import logging
import os
from pathlib import Path

import google.generativeai as genai

logging.basicConfig(
    filename="coach.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

KNOWLEDGE_BASE_PATH = Path("knowledge_base.txt")
_KB_CACHE: str | None = None


def load_knowledge_base() -> str:
    global _KB_CACHE
    if _KB_CACHE is not None:
        return _KB_CACHE
    if not KNOWLEDGE_BASE_PATH.exists():
        logger.warning("Knowledge base not found at %s", KNOWLEDGE_BASE_PATH)
        return ""
    _KB_CACHE = KNOWLEDGE_BASE_PATH.read_text(encoding="utf-8")
    logger.info("Knowledge base loaded: %d chars", len(_KB_CACHE))
    return _KB_CACHE


def retrieve_strategy_tool(query: str) -> str:
    """Retrieve relevant chunks from the knowledge base for a given query."""
    kb = load_knowledge_base()
    if not kb:
        return "Knowledge base unavailable."

    sections = [s.strip() for s in kb.split("\n\n") if s.strip()]
    query_lower = query.lower()

    keywords_map = {
        "opening": ["opening", "start", "first", "initial"],
        "narrowing": ["narrow", "range", "update", "midpoint", "binary"],
        "endgame": ["endgame", "end game", "few", "remaining", "last", "close"],
        "pattern": ["pattern", "contradict", "anomaly", "glitch", "bug", "inconsistent"],
        "risk": ["risk", "pressure", "attempts left", "few attempts"],
        "difficulty": ["easy", "hard", "normal", "difficulty"],
    }

    scored: list[tuple[int, str]] = []
    for section in sections:
        score = 0
        section_lower = section.lower()
        for category, words in keywords_map.items():
            if any(w in query_lower for w in words) and any(w in section_lower for w in words):
                score += 3
            elif any(w in section_lower for w in words):
                score += 1
        scored.append((score, section))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [s for _, s in scored[:3] if s]
    result = "\n\n".join(top)
    logger.info("retrieve_strategy(query=%r) returned %d chars", query, len(result))
    return result


def _retrieve_strategy_for_model(query: str) -> str:
    """Retrieve relevant number-guessing game strategy from the knowledge base.

    Args:
        query: Describe what strategy you need, e.g. 'opening move',
               'endgame with few numbers left', or 'contradictory hints detected'.

    Returns:
        Relevant strategy text from the knowledge base.
    """
    return retrieve_strategy_tool(query)


def detect_glitch(history: list, hints: list) -> str | None:
    """
    Detect logical contradictions in hint history.
    If hints imply impossible bounds (implied_low > implied_high), the game has a bug.
    """
    implied_low = 0
    implied_high = float("inf")

    valid_pairs = [
        (g, h)
        for g, h in zip(history, hints)
        if isinstance(g, int) and h in ("Too High", "Too Low")
    ]

    for i, (guess, hint) in enumerate(valid_pairs):
        if hint == "Too High":
            implied_high = min(implied_high, guess - 1)
        elif hint == "Too Low":
            implied_low = max(implied_low, guess + 1)

        if implied_low > implied_high:
            logger.warning(
                "Glitch detected after pair %d: implied_low=%s implied_high=%s",
                i,
                implied_low,
                implied_high,
            )
            return (
                f"Contradictory hints after guess {guess}: "
                f"hints imply secret > {int(implied_low) - 1} AND secret < {int(implied_high) + 1}, "
                f"which is impossible. The game has a bug (likely string vs integer comparison)."
            )

    return None


def coach_agent(game_state: dict) -> dict:
    """
    Agentic RAG workflow using Gemini:
    1. Plan     — model receives game state, decides what to retrieve
    2. Retrieve — model calls _retrieve_strategy_for_model tool (RAG step)
    3. Act      — model synthesizes advice from retrieved context
    4. Verify   — model self-critiques and assigns confidence score

    Returns a dict with keys: plan, recommendation, reasoning,
    confidence, self_critique, glitch_warning (str | None).
    """
    glitch_warning = detect_glitch(
        game_state.get("history", []), game_state.get("hints", [])
    )

    attempts = game_state.get("attempts", 0)
    low = game_state.get("low", 1)
    high = game_state.get("high", 100)
    history = game_state.get("history", [])
    hints = game_state.get("hints", [])
    attempt_limit = game_state.get("attempt_limit", 8)

    logger.info(
        "coach_agent called: attempts=%d range=%d-%d history=%s hints=%s glitch=%s",
        attempts, low, high, history, hints, bool(glitch_warning),
    )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not set")
        return _fallback_result(low, high, glitch_warning, "GEMINI_API_KEY not set.")

    if not (1 <= low <= high):
        logger.error("Invalid range: low=%d high=%d", low, high)
        return _fallback_result(low, high, glitch_warning, "Invalid range provided.")

    system_prompt = (
        "You are a strategic AI coach for a number guessing game called 'Game Glitch Investigator.'\n"
        "Your job is to:\n"
        "1. Call the retrieve_strategy tool to get expert knowledge before advising.\n"
        "2. Analyze the current game state including guess history and hints.\n"
        "3. Detect game anomalies if hints are contradictory.\n"
        "4. Respond ONLY with a valid JSON object (no markdown fences) with these exact keys:\n"
        '   "plan": one sentence on your reasoning approach,\n'
        '   "recommendation": the specific number to guess next (integer as string),\n'
        '   "reasoning": 2-3 sentences explaining the choice,\n'
        '   "confidence": float 0.0-1.0 (how certain you are),\n'
        '   "self_critique": one sentence identifying any weakness in your advice.\n'
        "Do not include any text outside the JSON object."
    )

    glitch_note = f"\nANOMALY DETECTED: {glitch_warning}" if glitch_warning else ""
    user_content = (
        f"Current game state:\n"
        f"- Number range: {low} to {high}\n"
        f"- Attempts used: {attempts} of {attempt_limit}\n"
        f"- Guess history: {history}\n"
        f"- Hints received: {hints}\n"
        f"{glitch_note}\n\n"
        "First call retrieve_strategy, then give your JSON advice."
    )

    try:
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=system_prompt,
            tools=[_retrieve_strategy_for_model],
        )

        # Automatic function calling: Gemini handles the retrieve → respond loop
        chat = model.start_chat(enable_automatic_function_calling=True)
        response = chat.send_message(user_content)

        logger.info("Gemini response received, parsing JSON")
        raw = response.text.strip()
        result = _parse_json_response(raw, low, high)
        result["glitch_warning"] = glitch_warning
        logger.info(
            "Coach result: confidence=%.2f recommendation=%s",
            result.get("confidence", 0),
            result.get("recommendation", "?"),
        )
        return result

    except Exception as exc:  # noqa: BLE001
        logger.error("Coach agent error: %s", exc)
        return _fallback_result(low, high, glitch_warning, str(exc))


def _parse_json_response(raw: str, low: int, high: int) -> dict:
    """Parse the model's JSON response with fallback."""
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.lstrip("json").strip()
            if part.startswith("{"):
                raw = part
                break

    try:
        data = json.loads(raw)
        rec_str = str(data.get("recommendation", ""))
        try:
            rec_int = int(rec_str)
            if not (low <= rec_int <= high):
                data["recommendation"] = str((low + high) // 2)
                data["self_critique"] = (
                    data.get("self_critique", "")
                    + " (recommendation out of range; clamped to midpoint)"
                )
        except ValueError:
            data["recommendation"] = str((low + high) // 2)
        return data
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed: %s | raw=%r", exc, raw[:200])
        return {
            "plan": "JSON parse error — using binary search fallback.",
            "recommendation": str((low + high) // 2),
            "reasoning": "Binary search: guess the midpoint to eliminate half the remaining range.",
            "confidence": 0.5,
            "self_critique": "Fallback advice due to JSON parse error.",
        }


def _fallback_result(low: int, high: int, glitch_warning: str | None, reason: str) -> dict:
    return {
        "plan": f"Fallback: {reason}",
        "recommendation": str((low + high) // 2),
        "reasoning": "Binary search fallback: guess the midpoint to eliminate half the remaining range.",
        "confidence": 0.3,
        "self_critique": "Operating without AI coach due to an error.",
        "glitch_warning": glitch_warning,
    }
