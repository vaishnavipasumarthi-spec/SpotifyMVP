import unittest
import os
import json
from fastapi.testclient import TestClient
from .nlp import MoodNLPParser
from .db import InMemoryVectorDB

# Use correct import path structure depending on test runner environment
from .main import app

class TestPhase1(unittest.TestCase):
    def setUp(self):
        # Resolve data path relative to this script
        self.current_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_path = os.path.join(self.current_dir, "data", "tracks.json")
        self.db = InMemoryVectorDB(data_path=self.data_path)
        self.nlp = MoodNLPParser()
        self.client = TestClient(app)

    def test_nlp_parsing_sad_rainy(self):
        """Verify natural language mappings compute expected mood contexts."""
        result = self.nlp.parse_query("feeling low on this rainy day")
        self.assertLess(result["valence"], 0.40)
        self.assertLess(result["energy"], 0.40)
        self.assertIn("sad", result["tags"])

    def test_nlp_parsing_workout(self):
        """Verify high arousal matches for active fitness queries."""
        result = self.nlp.parse_query("give me upbeat songs for my gym session")
        self.assertGreaterEqual(result["energy"], 0.80)
        self.assertIn("gym", result["tags"])

    def test_vector_search_matching(self):
        """Verify in-memory similarity matching outputs matching track parameters."""
        query_context = {
            "valence": 0.20,
            "energy": 0.25,
            "danceability": 0.35,
            "tags": ["sad"]
        }
        results = self.db.search(query_context, limit=3)
        self.assertTrue(len(results) > 0)
        # Top result should be the melancholic track
        top_track = results[0]["track"]
        self.assertIn("sad", top_track["tags"])

    def test_anti_repetition_penalty(self):
        """Verify play history values apply a penalty and re-rank candidate plays."""
        query_context = {
            "valence": 0.85,
            "energy": 0.80,
            "danceability": 0.75,
            "tags": ["happy"]
        }
        
        # 1. Search without history
        results_no_history = self.db.search(query_context, history={}, limit=3)
        top_track_no_history_id = results_no_history[0]["track"]["track_id"]
        
        # 2. Search with the top track marked as heavily played today
        # Format: {track_id: [play_count_30_days, days_since_last_play]}
        history = {
            top_track_no_history_id: [8, 0] # played 8 times, and played today (0 days ago)
        }
        results_with_history = self.db.search(query_context, history=history, limit=15)
        
        # Verify the track received a heavy penalty and is no longer the top choice
        penalized_match = next(x for x in results_with_history if x["track"]["track_id"] == top_track_no_history_id)
        self.assertGreater(penalized_match["repetition_penalty"], 0.40)
        
        # Check if the list ordering changed (re-ranked due to penalty)
        new_top_track_id = results_with_history[0]["track"]["track_id"]
        self.assertNotEqual(top_track_no_history_id, new_top_track_id)

    def test_discovery_boost_hidden_gems(self):
        """Verify mostly new discoveries modes boost low popularity artists."""
        query_context = {
            "valence": 0.70,
            "energy": 0.75,
            "danceability": 0.75,
            "tags": ["happy"]
        }
        
        # Standard balanced matches
        results_balanced = self.db.search(query_context, mode="Balanced", limit=5)
        # Discovery matches
        results_discovery = self.db.search(query_context, mode="Mostly New Discoveries", limit=5)
        
        # Find item that is a hidden gem (popularity < 40)
        discovery_gems = [x for x in results_discovery if x["track"]["popularity"] < 40]
        for gem in discovery_gems:
            self.assertGreater(gem["discovery_boost"], 0.0)

    def test_api_recommend_endpoint(self):
        """Test API POST request endpoint parsing flows."""
        payload = {
            "session_id": "test_session_99ab",
            "prompt": "study and relax",
            "constraints": {
                "limit": 3
            }
        }
        response = self.client.post("/api/v1/discovery/recommend", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["mode_applied"], "Balanced")
        self.assertEqual(len(data["tracks"]), 3)
        self.assertIn("study", data["query_parsed"]["tags"])

if __name__ == "__main__":
    unittest.main()
