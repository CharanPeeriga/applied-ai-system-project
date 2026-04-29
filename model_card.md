# Model Card — Game Glitch Investigator AI Coach

## Model Details

- **Model used:** gemini-2.0-flash (Google)
- **Role:** Strategic game coach using RAG and agentic tool use
- **Input:** Structured game state (range, attempt count, guess/hint history)
- **Output:** JSON with plan, recommendation, confidence score, self-critique, and optional glitch alert

---

## AI Collaboration

### How AI Was Used During Development

Claude (claude-sonnet-4-6) was used throughout development for:
- Designing the agentic tool-use loop structure
- Drafting the knowledge base content
- Generating test cases for edge conditions
- Debugging the Streamlit rendering order issue with `st.rerun()`

### Helpful AI Suggestion
Gemini's automatic function calling was suggested as the mechanism for the RAG retrieval step — passing a plain Python function as a tool so the model decides when and what to retrieve. This was the right call: it made the agentic step genuinely observable (logged in `coach.log`) without manual loop boilerplate, and the docstring served directly as the tool description.

### Flawed AI Suggestion
Claude initially recommended calling `st.rerun()` after every guess (including wins and losses) to ensure the coach panel updated immediately. This broke the win experience: the balloons and success message disappeared instantly because the rerun replaced them with the "already won" status page. The fix was conditional: `st.rerun()` is only called when the game is still in progress.

---

## Biases and Limitations

- The knowledge base encodes a **binary search bias** — it treats midpoint guessing as universally optimal. In scoring systems that reward bold guesses, this may be suboptimal.
- The coach has no memory of previous games; it cannot learn from a player's typical mistakes.
- Keyword-based retrieval can miss relevant KB sections if query phrasing doesn't align with stored text.
- The model is prompted for structured JSON; if the model deviates, a fallback is used which has lower confidence (0.3) and no strategic nuance.

---

## Testing Results

| Test Category | Tests | Passed | Notes |
|---|---|---|---|
| Game logic (hints, reset) | 11 | 11 | All pass including string-secret paths |
| Glitch detection | 5 | 5 | Correctly identifies contradictions |
| KB retrieval | 3 | 3 | Returns relevant content for opening/glitch/endgame queries |
| JSON parsing + fallback | 5 | 5 | Handles invalid JSON, out-of-range recommendations, markdown fences |

**Confidence score distribution (manual testing):**
- Normal play (mid-game): 0.82–0.92
- Endgame (≤5 numbers): 0.70–0.85
- Glitch detected: 0.55–0.70 (lower due to uncertainty)
- Fallback (API error): 0.30

---

## Ethical Considerations

**Could the AI be misused?**
The coach is advisory — it explains its reasoning rather than just giving the answer. However, a player could follow it mechanically to win every game trivially. This undermines the challenge intent.

**Mitigation:** The coach's confidence score is displayed prominently; in glitch conditions, confidence drops and the recommendation may be wrong (since the game itself is broken). Players are incentivized to understand the reasoning, not just copy the number.

**Data privacy:** No user data is stored. Guess history exists only in Streamlit session state (browser memory) and is cleared on page refresh or new game. The coach.log file contains only game metrics (no PII).

---

## Reflection

Building this system taught me that **reliability engineering is where AI systems live or die in production**. The most interesting challenge wasn't getting the LLM to give good advice — it was making the system behave correctly when the game itself is broken. The glitch detector needed to be deterministic (not LLM-based) because you can't use an AI to reliably detect when another AI-adjacent system is producing hallucinated/corrupted outputs. You need ground truth.

The agentic tool-use pattern also revealed something non-obvious: giving the model agency over *what to retrieve* produces better results than pre-loading all context, because the model can tailor the retrieval to the specific situation (endgame vs opening, glitch vs normal play).
