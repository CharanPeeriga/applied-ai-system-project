import sys
from unittest.mock import MagicMock


class _SessionState(dict):
    """Dict that also supports attribute access, matching Streamlit's session_state."""
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return False  # default: "key not in session_state" checks evaluate False

    def __setattr__(self, key, value):
        self[key] = value

    def __contains__(self, key):
        return super().__contains__(key)


# Build a streamlit mock that returns safe defaults for widget calls,
# preventing module-level st.* calls in app.py from raising errors during import.
mock_st = MagicMock()
mock_st.sidebar.selectbox.return_value = "Normal"
mock_st.sidebar.checkbox.return_value = True
mock_st.checkbox.return_value = True
mock_st.text_input.return_value = ""
mock_st.columns.return_value = (MagicMock(), MagicMock(), MagicMock())
mock_st.session_state = _SessionState()

sys.modules["streamlit"] = mock_st
