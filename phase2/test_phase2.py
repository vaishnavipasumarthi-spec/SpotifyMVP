import unittest
import base64
from fastapi.testclient import TestClient
from .main import app
from .session import SessionStore, DialogueSession
from .adaptive_engine import AdaptiveQuestionnaireEngine
from .voice import MockVoiceSTTService

class TestPhase2(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.session_store = SessionStore()
        self.question_engine = AdaptiveQuestionnaireEngine()
        self.voice_service = MockVoiceSTTService()

    def test_session_lifecycle_guided_flow(self):
        """Tests starting a session, answering step-by-step, slot filling, and final playlist extraction."""
        session_id = "test_guided_life_01"
        
        # 1. Start Session
        response = self.client.post("/api/v1/discovery/session/start", json={
            "session_id": session_id,
            "phase": "guided"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["session_id"], session_id)
        self.assertEqual(data["current_turn"], 1)
        self.assertEqual(data["next_step"]["slot_target"], "mood")
        
        # 2. Answer mood: Happy
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "answer_text": "Happy"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots"]["mood"], "Happy")
        self.assertEqual(data["next_step"]["slot_target"], "activity")
        # Assert adaptive question injection
        self.assertIn("Awesome vibe", data["next_step"]["prompt_text"])
        
        # 3. Answer activity: Studying
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "answer_text": "Studying"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots"]["activity"], "Studying")
        self.assertEqual(data["next_step"]["slot_target"], "language")
        
        # 4. Answer language: English
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "answer_text": "English"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots"]["language"], "English")
        self.assertEqual(data["next_step"]["slot_target"], "genre")
        
        # 5. Answer genre: Pop
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "answer_text": "Pop"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots"]["genre"], "Pop")
        self.assertEqual(data["next_step"]["slot_target"], "mode")
        
        # 6. Answer mode: Mostly New Discoveries (Completes slots -> triggers recommendations)
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "answer_text": "Mostly New Discoveries"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertIn("recommendations", data)
        self.assertTrue(len(data["recommendations"]["tracks"]) > 0)
        # Check that it filtered out based on context
        top_genre = data["recommendations"]["tracks"][0]["genres"]
        # Pop is matching genres list
        self.assertTrue(any("pop" in g.lower() for g in top_genre))

    def test_voice_activity_transcription_api(self):
        """Tests sending audio stream payloads and extracting text transcription details."""
        session_id = "test_voice_session"
        
        # Start session
        self.client.post("/api/v1/discovery/session/start", json={
            "session_id": session_id
        })
        
        # Construct base64 speech matching '[voice: Energetic]'
        raw_msg = "[voice: Energetic]"
        b64_audio = base64.b64encode(raw_msg.encode('utf-8')).decode('utf-8')
        
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "audio_stream_b64": b64_audio
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["slots"]["mood"], "Energetic")
        self.assertEqual(data["speech_metadata"]["vad_status"], "ACTIVE_SPEECH")
        self.assertEqual(data["speech_metadata"]["transcription"], "Energetic")

    def test_voice_silence_retrigger(self):
        """Tests system response when silent voice buffer (empty data) is transmitted."""
        session_id = "test_silent_session"
        self.client.post("/api/v1/discovery/session/start", json={
            "session_id": session_id
        })
        
        # Silent voice simulation payload (too short)
        short_payload = base64.b64encode(b"nil").decode('utf-8')
        
        response = self.client.post("/api/v1/discovery/session/answer", json={
            "session_id": session_id,
            "audio_stream_b64": short_payload
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Verify slots has NOT been filled
        self.assertIsNone(data["slots"]["mood"])
        # Verify speech metadata marks as silent
        self.assertEqual(data["speech_metadata"]["vad_status"], "SILENT")
        self.assertIn("Sorry, I couldn't hear you", data["next_step"]["prompt_text"])

if __name__ == "__main__":
    unittest.main()
