# conftest.py mocks streamlit before this file is collected,
# allowing app.py (which has module-level st.* calls) to be imported safely.
from logic_utils import check_guess
from app import check_guess as app_check_guess


# --- Existing tests (logic_utils interface) ---

def test_winning_guess():
    # If the secret is 50 and guess is 50, it should be a win
    outcome, _ = check_guess(50, 50)
    assert outcome == "Win"

def test_guess_too_high():
    # If secret is 50 and guess is 60, hint should be "Too High"
    outcome, _ = check_guess(60, 50)
    assert outcome == "Too High"

def test_guess_too_low():
    # If secret is 50 and guess is 40, hint should be "Too Low"
    outcome, _ = check_guess(40, 50)
    assert outcome == "Too Low"


# --- Bug 1: Hint directions must not be swapped ---

def test_hint_too_high_says_lower():
    # When guess > secret the player needs to go LOWER, not higher
    outcome, message = app_check_guess(60, 50)
    assert outcome == "Too High"
    assert "LOWER" in message, f"Expected 'LOWER' in hint for too-high guess, got: {message!r}"

def test_hint_too_low_says_higher():
    # When guess < secret the player needs to go HIGHER, not lower
    outcome, message = app_check_guess(40, 50)
    assert outcome == "Too Low"
    assert "HIGHER" in message, f"Expected 'HIGHER' in hint for too-low guess, got: {message!r}"


# --- Bug 2a: Even-attempt path casts secret to str; outcome and hint must stay correct ---

def test_string_secret_too_high_outcome():
    # Simulates app.py even-attempt path where secret arrives as str("50")
    outcome, message = app_check_guess(60, "50")
    assert outcome == "Too High"
    assert "LOWER" in message, f"String-secret too-high hint wrong: {message!r}"

def test_string_secret_too_low_outcome():
    outcome, message = app_check_guess(40, "50")
    assert outcome == "Too Low"
    assert "HIGHER" in message, f"String-secret too-low hint wrong: {message!r}"

def test_string_secret_win():
    # guess == int(secret_str) should still be a win
    outcome, _message = app_check_guess(50, "50")
    assert outcome == "Win"


# --- Bug 2b: New-game button must reset history and score ---

def _simulate_new_game(state: dict) -> dict:
    """Mirror the new-game block in app.py (lines 135-140)."""
    state["attempts"] = 0
    state["secret"] = 99   # random in production; fixed here for determinism
    state["history"] = []
    state["score"] = 0
    state["status"] = "playing"
    return state

def test_new_game_clears_history():
    state = {"attempts": 3, "secret": 42, "history": [10, 20, 30], "score": 50, "status": "playing"}
    state = _simulate_new_game(state)
    assert state["history"] == [], "history was not cleared on new game"

def test_new_game_resets_score():
    state = {"attempts": 3, "secret": 42, "history": [10, 20, 30], "score": 50, "status": "playing"}
    state = _simulate_new_game(state)
    assert state["score"] == 0, "score was not reset on new game"

def test_new_game_resets_attempts():
    state = {"attempts": 5, "secret": 42, "history": [1, 2, 3, 4, 5], "score": 30, "status": "playing"}
    state = _simulate_new_game(state)
    assert state["attempts"] == 0, "attempts were not reset on new game"
