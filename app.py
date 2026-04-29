import os
import random
from dotenv import load_dotenv
load_dotenv()
import streamlit as st
from logic_utils import get_range_for_difficulty, parse_guess, check_guess, update_score
from ai_coach import coach_agent


def _render_coach_panel(result: dict):
    st.subheader("🤖 AI Coach")

    glitch = result.get("glitch_warning")
    if glitch:
        st.error(f"⚠️ Glitch Detected: {glitch}")

    confidence = float(result.get("confidence", 0.5))
    rec = result.get("recommendation", "?")
    plan = result.get("plan", "")
    reasoning = result.get("reasoning", "")
    critique = result.get("self_critique", "")

    st.caption(f"_Plan: {plan}_")
    st.metric("Recommended next guess", rec)
    st.progress(confidence, text=f"Confidence: {confidence:.0%}")
    st.write(reasoning)

    with st.expander("Self-critique"):
        st.write(critique)

st.set_page_config(page_title="Glitchy Guesser", page_icon="🎮")

st.title("🎮 Game Glitch Investigator")
st.caption("An AI-generated guessing game. Something is off.")

st.sidebar.header("Settings")

difficulty = st.sidebar.selectbox(
    "Difficulty",
    ["Easy", "Normal", "Hard"],
    index=1,
)

attempt_limit_map = {
    "Easy": 6,
    "Normal": 8,
    "Hard": 5,
}
attempt_limit = attempt_limit_map[difficulty]

low, high = get_range_for_difficulty(difficulty)

st.sidebar.caption(f"Range: {low} to {high}")
st.sidebar.caption(f"Attempts allowed: {attempt_limit}")

if "secret" not in st.session_state:
    st.session_state.secret = random.randint(low, high)

if "attempts" not in st.session_state:
    st.session_state.attempts = 1

if "score" not in st.session_state:
    st.session_state.score = 0

if "status" not in st.session_state:
    st.session_state.status = "playing"

if "history" not in st.session_state:
    st.session_state.history = []

# AI Coach state
if "hints" not in st.session_state:
    st.session_state.hints = []
if "current_low" not in st.session_state:
    st.session_state.current_low = low
if "current_high" not in st.session_state:
    st.session_state.current_high = high
if "coach_result" not in st.session_state:
    st.session_state.coach_result = None
if "last_hint" not in st.session_state:
    st.session_state.last_hint = None

st.subheader("Make a guess")

st.info(
    f"Guess a number between 1 and 100. "
    f"Attempts left: {attempt_limit - st.session_state.attempts}"
)

with st.expander("Developer Debug Info"):
    st.write("Secret:", st.session_state.secret)
    st.write("Attempts:", st.session_state.attempts)
    st.write("Score:", st.session_state.score)
    st.write("Difficulty:", difficulty)
    st.write("History:", st.session_state.history)

if st.session_state.last_hint:
    st.warning(st.session_state.last_hint)

raw_guess = st.text_input(
    "Enter your guess:",
    key=f"guess_input_{difficulty}"
)

col1, col2, col3 = st.columns(3)
with col1:
    submit = st.button("Submit Guess 🚀")
with col2:
    new_game = st.button("New Game 🔁")
with col3:
    show_hint = st.checkbox("Show hint", value=True)

# FIX: added 3 lines to reset history, score, and status
if new_game:
    st.session_state.attempts = 0
    st.session_state.secret = random.randint(1, 100)
    st.session_state.history = []
    st.session_state.score = 0
    st.session_state.status = "playing"
    st.session_state.hints = []
    st.session_state.current_low = low
    st.session_state.current_high = high
    st.session_state.coach_result = None
    st.session_state.last_hint = None
    st.success("New game started.")
    st.rerun()

if st.session_state.status != "playing":
    if st.session_state.status == "won":
        st.success("You already won. Start a new game to play again.")
    else:
        st.error("Game over. Start a new game to try again.")
    if st.session_state.get("coach_result"):
        _render_coach_panel(st.session_state.coach_result)
    st.stop()

if submit:
    st.session_state.attempts += 1

    ok, guess_int, err = parse_guess(raw_guess)

    if not ok:
        st.session_state.history.append(raw_guess)
        st.error(err)
    else:
        st.session_state.history.append(guess_int)

        if st.session_state.attempts % 2 == 0:
            secret = str(st.session_state.secret)
        else:
            secret = st.session_state.secret

        outcome, message = check_guess(guess_int, secret)

        if show_hint:
            st.session_state.last_hint = message

        # Track outcome for coach's range narrowing and glitch detection
        if outcome == "Too High":
            st.session_state.hints.append("Too High")
            st.session_state.current_high = min(
                st.session_state.current_high, guess_int - 1
            )
        elif outcome == "Too Low":
            st.session_state.hints.append("Too Low")
            st.session_state.current_low = max(
                st.session_state.current_low, guess_int + 1
            )

        st.session_state.score = update_score(
            current_score=st.session_state.score,
            outcome=outcome,
            attempt_number=st.session_state.attempts,
        )

        if outcome == "Win":
            st.balloons()
            st.session_state.status = "won"
            st.success(
                f"You won! The secret was {st.session_state.secret}. "
                f"Final score: {st.session_state.score}"
            )
        else:
            if st.session_state.attempts >= attempt_limit:
                st.session_state.status = "lost"
                st.error(
                    f"Out of attempts! "
                    f"The secret was {st.session_state.secret}. "
                    f"Score: {st.session_state.score}"
                )

        # Call AI Coach if game is still in progress (not win/loss)
        if st.session_state.status == "playing" and os.getenv("GEMINI_API_KEY"):
            game_state = {
                "attempts": st.session_state.attempts,
                "history": [g for g in st.session_state.history if isinstance(g, int)],
                "hints": st.session_state.hints,
                "low": st.session_state.current_low,
                "high": st.session_state.current_high,
                "attempt_limit": attempt_limit,
            }
            with st.spinner("🤖 AI Coach analyzing..."):
                st.session_state.coach_result = coach_agent(game_state)
            st.rerun()

st.divider()

if not os.getenv("GEMINI_API_KEY"):
    st.info(
        "💡 Set GEMINI_API_KEY to enable the AI Coach. "
        "The game runs normally without it."
    )
elif st.session_state.coach_result:
    _render_coach_panel(st.session_state.coach_result)

st.caption("Built by an AI that claims this code is production-ready.")
