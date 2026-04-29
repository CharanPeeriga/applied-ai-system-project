from ai_coach import detect_glitch, retrieve_strategy_tool, _fallback_result, _parse_json_response


# --- detect_glitch ---

def test_no_glitch_clean_history():
    # 50 → Too Low (secret > 50), 75 → Too High (secret < 75), 62 → Too Low (secret > 62)
    # Implied range: 63–74. No contradiction.
    history = [50, 75, 62]
    hints = ["Too Low", "Too High", "Too Low"]
    assert detect_glitch(history, hints) is None


def test_glitch_contradictory_hints():
    # Told "Too Low" at 60 means secret > 60
    # Told "Too High" at 40 means secret < 40
    # Contradiction: secret > 60 AND secret < 40 is impossible
    history = [60, 40]
    hints = ["Too Low", "Too High"]
    result = detect_glitch(history, hints)
    assert result is not None
    assert "Contradictory" in result or "impossible" in result


def test_no_glitch_empty_history():
    assert detect_glitch([], []) is None


def test_no_glitch_single_guess():
    assert detect_glitch([50], ["Too High"]) is None


def test_glitch_skips_non_int_guesses():
    # Non-int guesses (parse failures) should be ignored
    history = ["abc", 50]
    hints = ["Too Low", "Too High"]
    # "abc" is skipped; only (50, "Too High") implies secret < 50 — no contradiction
    assert detect_glitch(history, hints) is None


# --- retrieve_strategy_tool ---

def test_retrieve_returns_string():
    result = retrieve_strategy_tool("opening move")
    assert isinstance(result, str)
    assert len(result) > 0


def test_retrieve_opening_includes_midpoint():
    result = retrieve_strategy_tool("opening midpoint binary search")
    assert "midpoint" in result.lower() or "binary" in result.lower() or "50" in result


def test_retrieve_glitch_query_includes_anomaly_content():
    result = retrieve_strategy_tool("contradictory hints glitch bug detected")
    assert any(word in result.lower() for word in ["contradict", "glitch", "bug", "anomaly", "string"])


# --- _parse_json_response ---

def test_parse_valid_json():
    raw = '{"plan":"test","recommendation":"42","reasoning":"mid","confidence":0.9,"self_critique":"none"}'
    result = _parse_json_response(raw, 1, 100)
    assert result["recommendation"] == "42"
    assert result["confidence"] == 0.9


def test_parse_out_of_range_recommendation_clamped():
    raw = '{"plan":"test","recommendation":"200","reasoning":"mid","confidence":0.8,"self_critique":"none"}'
    result = _parse_json_response(raw, 1, 100)
    assert result["recommendation"] == "50"  # clamped to midpoint


def test_parse_invalid_json_fallback():
    raw = "this is not json"
    result = _parse_json_response(raw, 1, 100)
    assert "recommendation" in result
    assert result["confidence"] == 0.5


def test_parse_strips_markdown_fences():
    raw = '```json\n{"plan":"p","recommendation":"30","reasoning":"r","confidence":0.7,"self_critique":"s"}\n```'
    result = _parse_json_response(raw, 1, 100)
    assert result["recommendation"] == "30"


# --- _fallback_result ---

def test_fallback_returns_midpoint():
    result = _fallback_result(10, 50, None, "test error")
    assert result["recommendation"] == "30"
    assert result["confidence"] == 0.3
    assert result["glitch_warning"] is None


def test_fallback_passes_glitch_warning():
    warning = "Contradictory hints detected"
    result = _fallback_result(1, 100, warning, "api error")
    assert result["glitch_warning"] == warning
