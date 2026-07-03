import json
import threading
from typing import Dict, List, Any

class TelemetryStore:
    def __init__(self):
        # Store for local logging
        self.logs: List[Dict[str, Any]] = []
        self._lock = threading.Lock()

    def log_action(self, event_type: str, session_id: str, track_id: str, context_meta: Dict[str, Any]) -> None:
        """
        Logs an interaction event. Common events:
        - TRACK_SKIPPED (Skipped fast = negative signal)
        - TRACK_COMPLETED (Played long = positive signal)
        """
        with self._lock:
            self.logs.append({
                "event_type": event_type,
                "session_id": session_id,
                "track_id": track_id,
                "context_meta": context_meta
            })
            
    def get_logs(self) -> List[Dict[str, Any]]:
        with self._lock:
            # Return a copy to safely analyze
            return list(self.logs)
            
    def dump_logs(self) -> str:
        with self._lock:
            return json.dumps(self.logs, indent=2)

    def clear(self):
        with self._lock:
            self.logs.clear()
