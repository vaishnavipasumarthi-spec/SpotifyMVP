import base64
import time
from typing import Dict, Any

class MockVoiceSTTService:
    """Simulates voice activity checks, speech-to-text, and audio conversions."""
    
    def transcribe_stream(self, base64_audio: str) -> Dict[str, Any]:
        """
        Receives base64 audio frames, detects voice volume levels (VAD), 
        and simulates low-latency Whisper translation transcription.
        """
        # 1. Handle mock empty inputs
        if not base64_audio or base64_audio.strip() == "":
            return {
                "transcription": "",
                "confidence": 0.0,
                "vad_status": "SILENT",
                "speaking_detected": False
            }
            
        # 2. Decode bytes check length to simulate VAD energy levels
        try:
            audio_bytes = base64.b64decode(base64_audio)
            byte_length = len(audio_bytes)
        except Exception:
            # Fallback if raw text bypass is used for testing
            audio_bytes = base64_audio.encode('utf-8')
            byte_length = len(audio_bytes)
            
        # If byte payload is too short, flag as silence (VAD threshold)
        if byte_length < 5:
            return {
                "transcription": "",
                "confidence": 0.0,
                "vad_status": "SILENT",
                "speaking_detected": False
            }
            
        # 3. Simulate processing time delay (150ms)
        time.sleep(0.15)
        
        # 4. Mock Speech-to-Text translation
        # Read text triggers sent inside mock payloads for testing (e.g. '[voice: happy study]')
        payload_str = ""
        try:
            payload_str = audio_bytes.decode('utf-8', errors='ignore')
        except Exception:
            pass
            
        transcription = "Calm studying vibe"
        confidence = 0.94
        
        if "[voice:" in payload_str:
            # Extract content between [voice: ...]
            start = payload_str.find("[voice:") + 7
            end = payload_str.find("]", start)
            if end != -1:
                transcription = payload_str[start:end].strip()
                confidence = 0.98
        elif "happy" in payload_str.lower():
            transcription = "Happy cheerful party"
            confidence = 0.90
            
        return {
            "transcription": transcription,
            "confidence": confidence,
            "vad_status": "ACTIVE_SPEECH",
            "speaking_detected": True
        }
