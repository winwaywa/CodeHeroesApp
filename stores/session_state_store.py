# infra/stores/session_state_store.py
from dataclasses import dataclass
import streamlit as st
from dataclasses import dataclass, field
from typing import Dict
from git import List


SESSION_KEYS = {
    "origin_code": "origin_code",
    "language": "language",
    "fixed_code": "fixed_code",
    "chat_messages": "chat_messages",
    "model": "model",
}

@dataclass
class SessionState:
    origin_code: str = ""
    language: str = "text"
    fixed_code: str = ""
    chat_messages: List[Dict[str, str]] = field(default_factory=list)
    model: str = ""  

    
class SessionStateStore:
    def get(self) -> SessionState:
        return SessionState(
            origin_code=st.session_state.get(SESSION_KEYS["origin_code"], ""),
            language=st.session_state.get(SESSION_KEYS["language"], "text"),
            fixed_code=st.session_state.get(SESSION_KEYS["fixed_code"], ""),
            chat_messages=st.session_state.get(SESSION_KEYS["chat_messages"], []),
            model=st.session_state.get(SESSION_KEYS["model"], ""),
        )

    def set(self, state: SessionState) -> None:
        st.session_state[SESSION_KEYS["origin_code"]] = state.origin_code
        st.session_state[SESSION_KEYS["language"]] = state.language
        st.session_state[SESSION_KEYS["fixed_code"]] = state.fixed_code
        st.session_state[SESSION_KEYS["chat_messages"]] = state.chat_messages
        st.session_state[SESSION_KEYS["model"]] = state.model
