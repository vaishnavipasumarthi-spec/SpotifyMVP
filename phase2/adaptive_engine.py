from typing import Dict, List, Optional, Any

class AdaptiveQuestionnaireEngine:
    def __init__(self):
        # 1. Define question templates with adaptive builders
        self.question_configs = {
            "mood": {
                "choices": ["Happy", "Sad", "Energetic", "Calm", "Relaxed"],
                "default_text": "What is your mood now?"
            },
            "activity": {
                "choices": ["Studying", "Workout", "Driving", "Cooking", "Relaxing"],
                "default_text": "What are you doing?"
            },
            "language": {
                "choices": ["English", "Hindi", "Spanish", "Punjabi", "Other"],
                "default_text": "Your Preferred Language?"
            },
            "genre": {
                "choices": ["Rock", "Pop", "Hip-Hop", "Folk", "Indie", "Classical"],
                "default_text": "Preferred Genre?"
            },
            "mode": {
                "choices": ["Mostly New Discoveries", "Hidden Artists", "Familiar Favorites", "Balanced"],
                "default_text": "Your Preference?"
            }
        }

    def compute_next_step(self, slots: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Evaluates the session slots, identifies the next priority slot to fill,
        and constructs an adaptive question.
        Returns a dictionary detailing the next slot, prompt text, and choices, or None if complete.
        """
        # Define priority order for slot filling
        slot_order = ["mood", "activity", "language", "genre", "mode"]
        
        next_slot = None
        for slot in slot_order:
            if slots.get(slot) is None:
                next_slot = slot
                break
                
        if next_slot is None:
            return None # All slot targets are filled, transition to recommendation
            
        config = self.question_configs[next_slot]
        choices = config["choices"]
        prompt_text = config["default_text"]
        
        # Apply ADAPTIVE CONTEXT prompts depending on already filled values!
        if next_slot == "activity" and slots.get("mood"):
            mood = slots["mood"].lower()
            if mood in ["sad", "low", "relaxed"]:
                prompt_text = f"I see you're feeling {mood}. What are you doing right now?"
            elif mood in ["happy", "energetic"]:
                prompt_text = f"Awesome vibe! What are you doing now?"
                
        elif next_slot == "genre" and slots.get("activity"):
            activity = slots["activity"].lower()
            prompt_text = f"What genre sets the best tone for {activity}?"
            
        elif next_slot == "mode" and slots.get("mood"):
            prompt_text = f"For this mood, how should we build your playlist?"
            
        return {
            "slot_target": next_slot,
            "prompt_text": prompt_text,
            "choices": choices
        }
