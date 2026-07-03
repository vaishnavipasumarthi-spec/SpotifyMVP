import unittest
from fastapi.testclient import TestClient
from .main import app, rl_optimizer, telemetry_store

class TestPhase4(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Reset telemetry store and default engine coefficients
        telemetry_store.clear()
        rl_optimizer.alpha_recent_decay = 0.50
        rl_optimizer.freq_penalty_weight = 0.20
        
    def test_log_playback_events(self):
        """Verify telemetry correctly ingests actions without errors."""
        response = self.client.post("/api/v1/telemetry/playback-event", json={
            "event_type": "TRACK_COMPLETED",
            "session_id": "sim_sess_01",
            "track_id": "trk_alpha99"
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)

    def test_rl_optimizer_increases_penalty_on_mass_skips(self):
        """
        Simulate a user skipping multiple heavily penalized songs. Prove the optimizer 
        hardens the penalty weight (increasing freq_penalty_weight) and decreases decay duration.
        """
        # Inject 3 skips where track was already heavily penalized (>0.2)
        for i in range(3):
            self.client.post("/api/v1/telemetry/playback-event", json={
                "event_type": "TRACK_SKIPPED",
                "session_id": "sim_sess_x",
                "track_id": f"trk_{i}",
                "context_meta": {
                    "repetition_penalty": 0.45 # A severe penalty but track was played anyway
                }
            })
            
        initial_stats = self.client.get("/api/v1/telemetry/stats").json()
        
        # Fire optimizer job
        job_res = self.client.post("/api/v1/telemetry/run-optimizer")
        self.assertEqual(job_res.status_code, 200)
        job_data = job_res.json()
        
        self.assertEqual(job_data["status"], "OPTIMIZATION_COMPLETE")
        self.assertEqual(job_data["evaluated_skips"], 3)
        
        # Final values should show increased friction rules
        final_stats = self.client.get("/api/v1/telemetry/stats").json()
        
        # We expect penalty_weight to be HIGHER (punish repeat tracks more heavily permanently)
        self.assertGreater(final_stats["freq_penalty_weight"], initial_stats["freq_penalty_weight"])
        
        # We expect alpha_recent_decay to be LOWER (penalty wears off slower over time)
        self.assertLess(final_stats["alpha_recent_decay"], initial_stats["alpha_recent_decay"])

if __name__ == "__main__":
    unittest.main()
