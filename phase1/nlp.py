import os
import json
import re
import time
from dotenv import load_dotenv

try:
    from groq import Groq
    groq_available = True
except ImportError:
    groq_available = False


class MoodNLPParser:
    """
    Uses Groq LLM (llama-3.3-70b-versatile) to:
    1. Deeply understand the user's intent — mood, language, activity, context
    2. Generate 5 REAL song recommendations with artist names and per-track reasoning
    3. Output acoustic parameters as fallback for vector matching
    4. Automatically rotates across 3 API keys when rate limits are hit
    """

    MODEL = "llama-3.3-70b-versatile"   # Fast, smart, generous free tier

    def __init__(self):
        load_dotenv()

        # Load all 3 Groq API keys
        self.api_keys = [
            k for k in [
                os.getenv("GROQ_API_KEY_1"),
                os.getenv("GROQ_API_KEY_2"),
                os.getenv("GROQ_API_KEY_3"),
            ] if k and not k.startswith("your_groq_key")
        ]

        self.current_key_index = 0
        self.use_live = len(self.api_keys) > 0

        if self.use_live:
            print(f"[OK] Groq NLP Parser ready - {len(self.api_keys)} API key(s) loaded.")
        else:
            print("[WARN] No valid Groq API keys found. Using keyword fallback mode.")

        # Keyword fallback mappings for offline mode
        self.mood_map = {
            "sad":       {"valence": 0.20, "energy": 0.25, "tags": ["sad", "melancholy"]},
            "happy":     {"valence": 0.85, "energy": 0.80, "tags": ["happy", "cheerful"]},
            "calm":      {"valence": 0.70, "energy": 0.25, "tags": ["calm", "relaxing"]},
            "relaxed":   {"valence": 0.70, "energy": 0.20, "tags": ["chill", "peaceful"]},
            "gym":       {"valence": 0.50, "energy": 0.95, "tags": ["workout", "gym"]},
            "study":     {"valence": 0.60, "energy": 0.30, "tags": ["focus", "study"]},
            "driving":   {"valence": 0.65, "energy": 0.72, "tags": ["driving"]},
            "party":     {"valence": 0.90, "energy": 0.90, "tags": ["party", "dance"]},
            "romantic":  {"valence": 0.75, "energy": 0.35, "tags": ["romantic", "love"]},
            "hindi":     {"valence": 0.65, "energy": 0.60, "tags": ["hindi", "bollywood"]},
            "bollywood": {"valence": 0.70, "energy": 0.65, "tags": ["bollywood", "hindi"]},
        }

    def _get_client(self):
        """Returns a Groq client using the current active API key."""
        return Groq(api_key=self.api_keys[self.current_key_index])

    def _rotate_key(self):
        """Rotate to the next available API key."""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            print(f"[INFO] Rotated to Groq API key #{self.current_key_index + 1}")
            return True
        return False

    def _fallback_parse(self, text: str, error_msg: str = ""):
        """Keyword-based fallback when all Groq keys are unavailable."""
        valence_scores, energy_scores, tags = [], [], []
        text_lower = text.lower()

        for key, config in self.mood_map.items():
            if re.search(r'\b' + re.escape(key) + r'\b', text_lower):
                valence_scores.append(config["valence"])
                energy_scores.append(config["energy"])
                tags.extend(config["tags"])

        reasoning = f"Offline fallback mode — keyword matched from: '{text}'"
        if error_msg:
            reasoning += f" | (Error: {error_msg})"

        return {
            "thought_process": reasoning,
            "valence": round(sum(valence_scores) / len(valence_scores), 2) if valence_scores else 0.5,
            "energy": round(sum(energy_scores) / len(energy_scores), 2) if energy_scores else 0.5,
            "danceability": 0.5,
            "tags": list(set(tags)),
            "genres": [],
            "ai_tracks": []
        }

    def parse_query(self, query_text: str):
        """
        Main entry point. Sends the user query to Groq LLM and returns
        structured JSON with real song recommendations + reasoning.
        Automatically rotates API keys on rate limit errors.
        """
        if not self.use_live:
            return self._fallback_parse(query_text, error_msg="No valid API keys found in environment.")

        prompt = f"""You are a world-class music curator with deep knowledge of all genres, languages, moods, artists, and global music trends — including Bollywood, Hollywood, K-Pop, Punjabi, Tamil, Telugu, and more.

A user wants music for: "{query_text}"

Your job:
1. UNDERSTAND the query deeply — detect language preferences, mood, activity, cultural context
2. Recommend exactly 5 REAL songs with real artist names that perfectly fit
3. For each track, write a short reason WHY it fits this exact query
4. Write a thought_process explaining your curation logic

IMPORTANT RULES:
- If user mentions "Hindi" or "Bollywood" → recommend ONLY Hindi/Bollywood songs
- If user mentions "English" → recommend ONLY English songs
- If user mentions "Tamil/Telugu/Punjabi/K-Pop" etc → match that language/genre
- Always use REAL artist names and REAL song titles
- Never hallucinate fake songs

Respond with ONLY valid JSON, no markdown, no extra text:
{{
    "thought_process": "2-3 sentences explaining your understanding and curation strategy",
    "valence": 0.0,
    "energy": 0.0,
    "danceability": 0.0,
    "tags": ["tag1", "tag2"],
    "genres": ["genre1"],
    "ai_tracks": [
        {{
            "title": "Song Title",
            "artist": "Artist Name",
            "genre": "Genre",
            "why": "One sentence on why this perfectly fits the query",
            "valence": 0.0,
            "energy": 0.0
        }}
    ]
}}"""

        # Try each key up to 2 rotations
        attempts = 0
        max_attempts = len(self.api_keys) * 2

        while attempts < max_attempts:
            attempts += 1
            try:
                client = self._get_client()
                response = client.chat.completions.create(
                    model=self.MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=1024,
                )

                raw = response.choices[0].message.content.strip()

                # Strip markdown fences if present
                if raw.startswith("```"):
                    raw = re.sub(r'^```[a-z]*\n?', '', raw)
                    raw = re.sub(r'\n?```$', '', raw.strip())

                parsed = json.loads(raw)
                print(f"[OK] Groq response received using key #{self.current_key_index + 1}")

                return {
                    "thought_process": parsed.get("thought_process", ""),
                    "valence":         float(parsed.get("valence", 0.5)),
                    "energy":          float(parsed.get("energy", 0.5)),
                    "danceability":    float(parsed.get("danceability", 0.5)),
                    "tags":            parsed.get("tags", []),
                    "genres":          parsed.get("genres", []),
                    "ai_tracks":       parsed.get("ai_tracks", [])
                }

            except Exception as e:
                err = str(e)
                if "rate_limit" in err.lower() or "429" in err or "quota" in err.lower():
                    print(f"[WARN] Rate limit on key #{self.current_key_index + 1} - rotating...")
                    if not self._rotate_key():
                        print("[ERROR] All keys exhausted. Using fallback.")
                        break
                    time.sleep(1)
                else:
                    print(f"[ERROR] Groq API Error: {err[:150]}")
                    return self._fallback_parse(query_text, error_msg=err[:150])

        print("[WARN] All Groq keys failed. Using keyword fallback.")
        return self._fallback_parse(query_text, error_msg="All keys rate limited.")
