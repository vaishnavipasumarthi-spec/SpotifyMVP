from typing import Dict, List, Any

class RLOptimizer:
    def __init__(self):
        # Default global constants used by Phase 1 Vector DB
        self.alpha_recent_decay = 0.5   # Controls how fast penalty drops over days
        self.freq_penalty_weight = 0.20 # Controls penalty for raw play count limits
        self.learning_rate = 0.05
        
    def get_current_constants(self) -> Dict[str, float]:
        """Expose current tuned parameters to the search engine."""
        return {
            "alpha_recent_decay": self.alpha_recent_decay,
            "freq_penalty_weight": self.freq_penalty_weight
        }

    def run_optimization_cycle(self, logs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyzes telemetry feedback and updates tuning constants using a simple 
        reinforcement heuristic.
        """
        if not logs:
            return {"status": "NO_LOGS", "metrics": self.get_current_constants()}

        # Metrics Collection
        total_skips = 0
        repetition_skip_penalty = 0.0
        discovery_skip_penalty = 0.0
        
        for item in logs:
            if item["event_type"] == "TRACK_SKIPPED":
                total_skips += 1
                meta = item.get("context_meta", {})
                
                # If a user skipped a track that had a heavy repetition penalty (meaning
                # the penalty wasn't strong ENOUGH to drop it from ranking), we need to
                # increase the global penalty weight.
                applied_penalty = meta.get("repetition_penalty", 0.0)
                if applied_penalty > 0.1:
                    repetition_skip_penalty += applied_penalty

        # Compute heuristic updates if sufficient skips occurred
        if total_skips > 0:
            avg_rep_penalty_on_skips = repetition_skip_penalty / total_skips
            
            # Simple RL update rule: 
            # If average skipped track had noticeable penalty, the penalty floor needs raising.
            if avg_rep_penalty_on_skips > 0.20:
                # User skipped despite penalty. Increase freq_penalty_weight slightly to punish more
                self.freq_penalty_weight = min(1.0, self.freq_penalty_weight + self.learning_rate)
                # Decrease alpha decay so tracks stay penalized longer across days
                self.alpha_recent_decay = max(0.1, self.alpha_recent_decay - (self.learning_rate / 2))

        return {
            "status": "OPTIMIZATION_COMPLETE",
            "evaluated_skips": total_skips,
            "metrics": self.get_current_constants()
        }
