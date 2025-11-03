# infra/stores/session_state_store.py
from dataclasses import dataclass
import streamlit as st
from dataclasses import dataclass, field
from typing import Dict
from git import List


SESSION_KEYS = {
    "code": "code",
    "language": "language",
    "review_md": "review_md",
    "fixed_code": "fixed_code",
    "chat_messages": "chat_messages",
}

@dataclass
class SessionState:
    code: str = ""
    language: str = "text"
    review_md: str = ""
    fixed_code: str = ""
    chat_messages: List[Dict[str, str]] = field(default_factory=list)

    @property
    def has_review(self) -> bool:
        return bool(self.review_md.strip())
    
class SessionStateStore:
    def get(self) -> SessionState:
        return SessionState(
            code=st.session_state.get(SESSION_KEYS["code"], ""),
            language=st.session_state.get(SESSION_KEYS["language"], "text"),
            review_md=st.session_state.get(SESSION_KEYS["review_md"], ""),
            fixed_code=st.session_state.get(SESSION_KEYS["fixed_code"], ""),
            chat_messages=st.session_state.get(SESSION_KEYS["chat_messages"], []),
        )

    def set(self, state: SessionState) -> None:
        st.session_state[SESSION_KEYS["code"]] = state.code
        st.session_state[SESSION_KEYS["language"]] = state.language
        st.session_state[SESSION_KEYS["review_md"]] = state.review_md
        st.session_state[SESSION_KEYS["fixed_code"]] = state.fixed_code
        st.session_state[SESSION_KEYS["chat_messages"]] = state.chat_messages
