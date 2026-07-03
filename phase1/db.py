import json
import os
import numpy as np

class InMemoryVectorDB:
    def __init__(self, data_path=None):
        if data_path is None:
            # Resolve relative data directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            data_path = os.path.join(current_dir, "data", "tracks.json")
        
        self.data_path = data_path
        self.tracks = []
        self.vocabulary = []
        self.track_vectors = {} # track_id -> normalized numpy array
        
        self.load_database()
        self.build_index()

    def load_database(self):
        """Loads track lists from tracks.json."""
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Track metadata database not found at {self.data_path}")
        
        with open(self.data_path, "r", encoding="utf-8") as f:
            self.tracks = json.load(f)

    def build_index(self):
        """Builds numerical and word-tag indexing profiles."""
        # 1. Establish the vocabulary of all unique tags
        all_tags = set()
        for track in self.tracks:
            for tag in track.get("tags", []):
                all_tags.add(tag.lower())
            for genre in track.get("genres", []):
                all_tags.add(genre.lower())
        
        self.vocabulary = sorted(list(all_tags))
        vocab_size = len(self.vocabulary)
        
        # 2. Vectorize each track
        for track in self.tracks:
            track_id = track["track_id"]
            
            # Numeric characteristics: [valence, energy, danceability, normalized_popularity]
            norm_pop = track.get("popularity", 50) / 100.0
            numeric_features = [
                track.get("valence", 0.5),
                track.get("energy", 0.5),
                track.get("danceability", 0.5),
                norm_pop
            ]
            
            # Semantic characteristics: multi-hot vector based on tags/genres
            tag_features = [0.0] * vocab_size
            track_tags = [t.lower() for t in track.get("tags", [])] + [g.lower() for g in track.get("genres", [])]
            for tag in track_tags:
                if tag in self.vocabulary:
                    idx = self.vocabulary.index(tag)
                    tag_features[idx] = 1.0
            
            # Concatenate numeric features and word embeddings
            combined_vector = np.array(numeric_features + tag_features, dtype=float)
            
            # L2 Normalize the track vector to ensure cosine similarity is a simple dot product
            norm = np.linalg.norm(combined_vector)
            if norm > 0:
                normalized_vector = combined_vector / norm
            else:
                normalized_vector = combined_vector
                
            self.track_vectors[track_id] = normalized_vector

    def search(self, query_context, history=None, mode="Balanced", limit=5):
        """
        Performs vector cosine similarity search and applies anti-repetition formulas.
        
        - query_context: dict containing target acoustic metrics and list of tags
        - history: dict mapping track_id to list containing [times_played_in_30_days, days_since_last_play]
        - mode: "Mostly New Discoveries", "Hidden Artists", "Familiar Favorites", "Balanced"
        """
        if history is None:
            history = {}
            
        # 1. Construct query vector
        target_valence = query_context.get("valence", 0.5)
        target_energy = query_context.get("energy", 0.5)
        target_danceability = query_context.get("danceability", 0.5)
        # Default query popularity target
        target_popularity = 0.5 
        if mode == "Hidden Artists":
            target_popularity = 0.15
        elif mode == "Familiar Favorites":
            target_popularity = 0.80
            
        query_numeric = [target_valence, target_energy, target_danceability, target_popularity]
        
        query_tags = [t.lower() for t in query_context.get("tags", [])]
        vocab_size = len(self.vocabulary)
        query_tag_features = [0.0] * vocab_size
        for tag in query_tags:
            if tag in self.vocabulary:
                idx = self.vocabulary.index(tag)
                query_tag_features[idx] = 2.0  # Apply higher weight booster for explicit tag query matches
                
        query_vector = np.array(query_numeric + query_tag_features, dtype=float)
        q_norm = np.linalg.norm(query_vector)
        if q_norm > 0:
            query_vector = query_vector / q_norm
            
        # 2. Iterate through tracks and apply scores
        scored_tracks = []
        for track in self.tracks:
            track_id = track["track_id"]
            track_vector = self.track_vectors[track_id]
            
            # Cosine similarity (dot product of L2 normalized vectors)
            cosine_similarity = float(np.dot(query_vector, track_vector))
            
            # A. CALCULATE REPETITION PENALTY
            # PR = lambda1 * e^(-alpha * days_since_play) + lambda2 * (count_30 / max_count)
            repetition_penalty = 0.0
            if track_id in history:
                count_30, days_since_play = history[track_id]
                
                # Decay factor over time elapsed
                lambda1 = 0.60
                alpha = 0.15 # Decay constant
                temporal_penalty = lambda1 * np.exp(-alpha * days_since_play)
                
                # Frequency penalty based on play count
                lambda2 = 0.25
                max_count = 10.0 # Assume 10 plays is maximum threshold
                frequency_penalty = lambda2 * (min(count_30, max_count) / max_count)
                
                repetition_penalty = temporal_penalty + frequency_penalty
                
            # B. CALCULATE DISCOVERY BOOST
            discovery_boost = 0.0
            is_hidden_gem = track.get("popularity", 50) < 40
            
            if mode == "Mostly New Discoveries":
                # High boost to long-tail tracks
                if is_hidden_gem:
                    discovery_boost = 0.25
                elif track_id not in history:
                    discovery_boost = 0.10
            elif mode == "Hidden Artists":
                if is_hidden_gem:
                    discovery_boost = 0.35
            elif mode == "Balanced":
                if is_hidden_gem and track_id not in history:
                    discovery_boost = 0.15
            elif mode == "Familiar Favorites":
                # Penalize non-history tracks if we want familiarity
                if track_id not in history:
                    discovery_boost = -0.20
            
            # Combine elements
            final_score = cosine_similarity - repetition_penalty + discovery_boost
            
            scored_tracks.append({
                "track": track,
                "similarity_score": cosine_similarity,
                "repetition_penalty": repetition_penalty,
                "discovery_boost": discovery_boost,
                "final_score": final_score
            })
            
        # 3. Sort by final score descending
        scored_tracks.sort(key=lambda x: x["final_score"], reverse=True)
        
        # 4. Format outputs
        return scored_tracks[:limit]
