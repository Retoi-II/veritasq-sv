import logging
import streamlit as st

class StreamlitLogHandler(logging.Handler):
    """A logging handler that outputs logs directly to a Streamlit container."""
    def __init__(self, container):
        super().__init__()
        self.container = container

        if "session_logs" not in st.session_state:
            st.session_state.session_logs = []

    def emit(self, record):
        msg = self.format(record)
        # st.session_state.session_logs.append(msg) # Top to down log
        st.session_state.session_logs.insert(0, msg) # Down to top log

        if len(st.session_state.session_logs) > 100:
            st.session_state.session_logs.pop() # Removes the oldest item from the bottom
        full_history_text = "\n".join(st.session_state.session_logs)
        self.container.code(full_history_text, language="log")
