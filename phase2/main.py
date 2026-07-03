from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from .session import SessionStore, DialogueSession
from .adaptive_engine import AdaptiveQuestionnaireEngine
from .voice import MockVoiceSTTService

# Reuse Phase 1 search and parsing engines!
try:
    from phase1.db import InMemoryVectorDB
    from phase1.nlp import MoodNLPParser
except ImportError:
    # Handle absolute import paths relative to parent
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from phase1.db import InMemoryVectorDB
    from phase1.nlp import MoodNLPParser

app = FastAPI(title="Spotify AI Mood Discovery API - Phase 2", version="2.0.0")

# Services Inits
session_store = SessionStore()
question_engine = AdaptiveQuestionnaireEngine()
voice_service = MockVoiceSTTService()
nlp_parser = MoodNLPParser()

# Resolve data path for track DB
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
tracks_path = os.path.join(os.path.dirname(current_dir), "phase1", "data", "tracks.json")
track_db = InMemoryVectorDB(data_path=tracks_path)


# Models
class StartSessionRequest(BaseModel):
    session_id: str
    phase: Optional[str] = "guided"

class AnswerSessionRequest(BaseModel):
    session_id: str
    answer_text: Optional[str] = None
    audio_stream_b64: Optional[str] = None # Base64 audio stream for hands-free voice search
    history: Optional[Dict[str, List[Any]]] = Field(
        default=None,
        description="User listening history mapping track_id -> [play_count, days_since_last_play]"
    )


@app.post("/api/v1/discovery/session/start")
async def start_session(request: StartSessionRequest):
    if session_store.exists(request.session_id):
        # Reset session
        session_store.delete(request.session_id)
        
    session = session_store.create(request.session_id, phase=request.phase)
    session.current_turn = 1
    
    # Compute initial question flow parameters
    next_step = question_engine.compute_next_step(session.slots)
    
    session.dialogue_history.append({
        "speaker": "system",
        "text": next_step["prompt_text"] if next_step else ""
    })
    session_store.save(session)
    
    return {
        "session_id": session.session_id,
        "current_turn": session.current_turn,
        "slots": session.slots,
        "next_step": next_step
    }


@app.post("/api/v1/discovery/session/answer")
async def answer_session(request: AnswerSessionRequest):
    session = session_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Dialogue Session not found.")
        
    session.current_turn += 1
    
    # 1. Identify which slot target is currently active
    next_step = question_engine.compute_next_step(session.slots)
    if not next_step:
        raise HTTPException(
            status_code=400, 
            detail="Session slots are already complete. Recommendations are ready."
        )
        
    active_slot = next_step["slot_target"]
    user_speech_meta = None
    
    # 2. Extract answer text: either direct String or Audio streaming STT
    if request.audio_stream_b64:
        # Stream decode
        voice_result = voice_service.transcribe_stream(request.audio_stream_b64)
        if not voice_result.get("speaking_detected"):
            if session.phase == "manual":
                raise HTTPException(status_code=400, detail="Silence detected.")
            # Return silence reminder question
            return {
                "session_id": session.session_id,
                "current_turn": session.current_turn,
                "slots": session.slots,
                "next_step": {
                    "slot_target": active_slot,
                    "prompt_text": f"Sorry, I couldn't hear you. {next_step['prompt_text']}",
                    "choices": next_step["choices"]
                },
                "speech_metadata": voice_result
            }
        answer_raw = voice_result["transcription"]
        user_speech_meta = voice_result
    elif request.answer_text:
        answer_raw = request.answer_text
    else:
        raise HTTPException(
            status_code=400, 
            detail="Requires either 'answer_text' or 'audio_stream_b64' parameters."
        )

    # 3. IF Phase is Manual, BYPASS Slot Filling — use Gemini directly!
    if session.phase == "manual":
        query_context = nlp_parser.parse_query(answer_raw)
        ai_tracks = query_context.get("ai_tracks", [])
        
        formatted_tracks = []
        if ai_tracks:
            # PRIMARY: Use Gemini-generated real song recommendations
            for i, t in enumerate(ai_tracks[:5]):
                formatted_tracks.append({
                    "track_id": f"ai_{i}",
                    "title": t.get("title", "Unknown"),
                    "artist": {"name": t.get("artist", "Unknown"), "is_hidden_gem": False},
                    "genres": [t.get("genre", "")] if t.get("genre") else [],
                    "why": t.get("why", ""),
                    "similarity_score": round(1.0 - (i * 0.05), 3),
                    "repetition_penalty": 0.0,
                    "final_score": round(1.0 - (i * 0.05), 3)
                })
        else:
            # FALLBACK: Use static vector DB if Gemini returned no tracks
            recommendations = track_db.search(
                query_context=query_context, history=request.history or {}, mode="Balanced", limit=5
            )
            for match in recommendations:
                track = match["track"]
                is_hidden = track.get("popularity", 50) < 40
                formatted_tracks.append({
                    "track_id": track["track_id"],
                    "title": track["title"],
                    "artist": {"name": track["artist"], "is_hidden_gem": is_hidden},
                    "genres": track["genres"],
                    "why": "",
                    "similarity_score": round(match["similarity_score"], 3),
                    "repetition_penalty": round(match["repetition_penalty"], 3),
                    "final_score": round(match["final_score"], 3)
                })

        session_store.delete(session.session_id)
        return {
            "session_id": session.session_id,
            "slots": {},
            "status": "COMPLETED",
            "recommendations": {
                "playlist_id": f"ai_discover_{session.session_id}",
                "name": f"AI Mix: {answer_raw[:30]}",
                "tracks": formatted_tracks,
                "thought_process": query_context.get("thought_process", "")
            },
            "speech_metadata": user_speech_meta
        }
        
    # 4. Categorize slot values
    # Match against valid choices to normalize (case-insensitive fuzzy checks)
    normalized_value = answer_raw
    valid_choices = next_step["choices"]
    for choice in valid_choices:
        if choice.lower() in answer_raw.lower():
            normalized_value = choice
            break
            
    # Assign slot
    session.slots[active_slot] = normalized_value
    session.dialogue_history.append({"speaker": "user", "text": answer_raw})
    
    # 5. Check next step parameters
    new_next_step = question_engine.compute_next_step(session.slots)
    
    if new_next_step:
        # Log system question
        session.dialogue_history.append({
            "speaker": "system",
            "text": new_next_step["prompt_text"]
        })
        session_store.save(session)
        
        return {
            "session_id": session.session_id,
            "current_turn": session.current_turn,
            "slots": session.slots,
            "next_step": new_next_step,
            "speech_metadata": user_speech_meta
        }
    else:
        # All slots filled! Compile final recommendations via Gemini
        session_store.save(session)
        mode = session.slots.get("mode", "Balanced")
        
        # Build a rich natural language prompt from slots for Gemini
        lang = session.slots.get('language', '')
        synthetic_prompt = (
            f"I'm feeling {session.slots.get('mood', '')} and I'm {session.slots.get('activity', '')}. "
            f"I want {session.slots.get('genre', '')} music"
            + (f" in {lang}" if lang and lang.lower() != 'other' else "") + "."
        )
        query_context = nlp_parser.parse_query(synthetic_prompt)
        
        ai_tracks = query_context.get("ai_tracks", [])
        formatted_tracks = []
        
        if ai_tracks:
            # PRIMARY: Gemini-curated real songs
            for i, t in enumerate(ai_tracks[:5]):
                formatted_tracks.append({
                    "track_id": f"ai_{i}",
                    "title": t.get("title", "Unknown"),
                    "artist": {"name": t.get("artist", "Unknown"), "is_hidden_gem": False},
                    "genres": [t.get("genre", "")] if t.get("genre") else [],
                    "why": t.get("why", ""),
                    "similarity_score": round(1.0 - (i * 0.05), 3),
                    "repetition_penalty": 0.0,
                    "final_score": round(1.0 - (i * 0.05), 3)
                })
        else:
            # FALLBACK: static vector DB
            if session.slots.get("language"):
                query_context["tags"].append(session.slots["language"].lower())
            recommendations = track_db.search(
                query_context=query_context, history=request.history or {}, mode=mode, limit=5
            )
            for match in recommendations:
                track = match["track"]
                is_hidden = track.get("popularity", 50) < 40
                formatted_tracks.append({
                    "track_id": track["track_id"],
                    "title": track["title"],
                    "artist": {"name": track["artist"], "is_hidden_gem": is_hidden},
                    "genres": track["genres"],
                    "why": "",
                    "similarity_score": round(match["similarity_score"], 3),
                    "repetition_penalty": round(match["repetition_penalty"], 3),
                    "final_score": round(match["final_score"], 3)
                })

        return {
            "session_id": session.session_id,
            "slots": session.slots,
            "status": "COMPLETED",
            "recommendations": {
                "playlist_id": f"ai_discover_{session.session_id}",
                "name": f"AI Mix — {session.slots.get('mood', 'Custom')} {session.slots.get('activity', '')}".strip(),
                "tracks": formatted_tracks,
                "thought_process": query_context.get("thought_process", "")
            },
            "speech_metadata": user_speech_meta
        }

@app.get("/api/v1/discovery/session/{session_id}")
async def get_session(session_id: str):
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return session.to_dict()
