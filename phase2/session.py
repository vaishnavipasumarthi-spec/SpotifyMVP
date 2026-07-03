import threading
import json
from typing import Dict, List, Optional, Any

class DialogueSession:
    def __init__(self, session_id: str, phase: str = "guided"):
        self.session_id = session_id
        self.phase = phase
        self.current_turn = 0
        self.slots = {
            "mood": None,
            "activity": None,
            "language": None,
            "genre": None,
            "mode": None
        }
        self.dialogue_history: List[Dict[str, str]] = []
        self.engine_parameters: Dict[str, Any] = {
            "novelty_weight": 0.85,
            "gem_only_bias": False
        }

    def to_dict(self) -> Dict[str, Any]:
        """Serializes session state to a JSON-compatible directory structure."""
        return {
            "session_id": self.session_id,
            "phase": self.phase,
            "current_turn": self.current_turn,
            "slots": self.slots,
            "dialogue_history": self.dialogue_history,
            "engine_parameters": self.engine_parameters
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DialogueSession":
        """Reconstructs session state from a directory structure (Redis replication mock)."""
        session = cls(session_id=data["session_id"], phase=data.get("phase", "guided"))
        session.current_turn = data.get("current_turn", 0)
        session.slots = data.get("slots", {})
        session.dialogue_history = data.get("dialogue_history", [])
        session.engine_parameters = data.get("engine_parameters", {})
        return session


class SessionStore:
    """Thread-safe session cache storing dialogue states, mimicking Redis caching."""
    def __init__(self):
        self._store: Dict[str, str] = {} # Simulates storing JSON string dumps
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Optional[DialogueSession]:
        with self._lock:
            data_str = self._store.get(session_id)
            if not data_str:
                return None
            return DialogueSession.from_dict(json.loads(data_str))

    def save(self, session: DialogueSession) -> None:
        with self._lock:
            self._store[session.session_id] = json.dumps(session.to_dict())

    def create(self, session_id: str, phase: str = "guided") -> DialogueSession:
        session = DialogueSession(session_id=session_id, phase=phase)
        self.save(session)
        return session

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._store

    def delete(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
