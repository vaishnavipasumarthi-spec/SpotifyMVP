from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from .db import InMemoryVectorDB
from .nlp import MoodNLPParser

app = FastAPI(title="Spotify AI Mood Discovery API", version="1.0.0")

# Instantiate DB and NLP services
try:
    db = InMemoryVectorDB()
except Exception as e:
    # Resolve relative path fallback logic for test environments
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_path = os.path.join(current_dir, "data", "tracks.json")
    db = InMemoryVectorDB(data_path=data_path)

nlp_parser = MoodNLPParser()


# Request Models
class ContextModel(BaseModel):
    mood: Optional[str] = None
    activity: Optional[str] = None
    language: Optional[str] = None
    genre: Optional[str] = None
    mode: Optional[str] = "Balanced" # "Mostly New Discoveries" | "Hidden Artists" | "Familiar Favorites" | "Balanced"

class RuleConstraints(BaseModel):
    limit: Optional[int] = 5
    max_artist_skips: Optional[int] = 1
    avoid_tracks_played_within_days: Optional[int] = 14
    min_novelty_score: Optional[float] = 0.5

class RecommendationRequest(BaseModel):
    session_id: str
    prompt: Optional[str] = None # Unstructured user search prompt (e.g. "I'm feeling low...")
    context: Optional[ContextModel] = None # Guided AI Discovery context inputs
    history: Optional[Dict[str, List[Any]]] = Field(
        default=None, 
        description="Key is track_id, Value is list [play_count_last_30_days, days_since_last_play]"
    )
    constraints: Optional[RuleConstraints] = None


@app.post("/api/v1/discovery/recommend")
async def recommend(request: RecommendationRequest):
    history = request.history or {}
    constraints = request.constraints or RuleConstraints()
    limit = constraints.limit or 5
    
    # 1. Pipeline A: Natural Language Search Prompt
    if request.prompt:
        # Run natural language extractor
        query_context = nlp_parser.parse_query(request.prompt)
        
        # Override recommendation mode based on keywords in prompt
        mode = "Balanced"
        prompt_lower = request.prompt.lower()
        if "hidden" in prompt_lower or "emerging" in prompt_lower or "rare" in prompt_lower:
            mode = "Hidden Artists"
        elif "new" in prompt_lower or "discover" in prompt_lower:
            mode = "Mostly New Discoveries"
            
    # 2. Pipeline B: Guided AI Discovery Selection Context
    elif request.context:
        # Construct search factors based on selection matrices
        mode = request.context.mode or "Balanced"
        
        # Synthesize verbal criteria as prompt query to utilize parser maps
        synthetic_prompt = []
        if request.context.mood:
            synthetic_prompt.append(request.context.mood)
        if request.context.activity:
            synthetic_prompt.append(request.context.activity)
        if request.context.genre:
            synthetic_prompt.append(request.context.genre)
            
        synthetic_text = " ".join(synthetic_prompt)
        query_context = nlp_parser.parse_query(synthetic_text)
        
        # Append specific languages/genres if specified
        if request.context.language:
            query_context["tags"].append(request.context.language.lower())
    else:
        raise HTTPException(
            status_code=400, 
            detail="Invalid Request: Either 'prompt' or 'context' must be provided."
        )
        
    # Execute vector matching query (passing context parameters, play histories, and modes)
    try:
        recommendations = db.search(
            query_context=query_context,
            history=history,
            mode=mode,
            limit=limit
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database search failed: {str(e)}")
        
    # Format matches according to API Contracts
    formatted_tracks = []
    for match in recommendations:
        track = match["track"]
        is_hidden = track.get("popularity", 50) < 40
        
        formatted_tracks.append({
            "track_id": track["track_id"],
            "title": track["title"],
            "artist": {
                "name": track["artist"],
                "is_hidden_gem": is_hidden
            },
            "genres": track["genres"],
            "similarity_score": round(match["similarity_score"], 3),
            "repetition_penalty": round(match["repetition_penalty"], 3),
            "final_score": round(match["final_score"], 3)
        })
        
    return {
        "playlist_id": f"ai_discover_{request.session_id}",
        "name": f"AI Context Mix - {query_context.get('valence', 0.5)}Val",
        "query_parsed": query_context,
        "mode_applied": mode,
        "tracks": formatted_tracks
    }

@app.get("/api/v1/discovery/tracks")
async def get_tracks():
    """Lists all active reference tracks in the DB."""
    return {"count": len(db.tracks), "tracks": db.tracks}

@app.get("/api/v1/discovery/vocabulary")
async def get_vocabulary():
    """Lists indexing words used coordinates construction."""
    return {"vocabulary_size": len(db.vocabulary), "words": db.vocabulary}
