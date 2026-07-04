# Spotify AI Mood Discovery: System Architecture

This document outlines the architecture for the Spotify AI Mood Discovery MVP, deployed as a full-stack Serverless application on Vercel.

---

## 1. High-Level Architecture Overview

The system is built as a monolithic repository that leverages Vercel's hybrid hosting: serving static assets (HTML/CSS/JS) for the frontend, and Serverless Python Functions for the FastAPI backend.

```mermaid
graph TD
    subgraph Client Layer [Client Layer (Web Browser)]
        UI[Spotify Native UI Clone<br/>HTML/CSS/JS]
        Voice[Web Speech API<br/>Voice Input]
        Text[Search Input]
        Pills[Mood Pills<br/>Guided Flow]
    end

    subgraph Vercel Routing Layer [Vercel CDN & Routing]
        Router{vercel.json Router}
    end

    subgraph Serverless Backend [Vercel Python Serverless / FastAPI]
        API[FastAPI App Wrapper<br/>api/index.py]
        NLP[MoodNLPParser<br/>Groq LLM Integration]
        VDB[InMemoryVectorDB<br/>NumPy Matching]
    end

    subgraph External AI Services
        Groq[Groq API<br/>llama-3.3-70b]
    end

    %% Input paths
    Voice --> UI
    Text --> UI
    Pills --> UI

    %% HTTP Requests
    UI -->|Static Asset Requests /| Router
    UI -->|API Requests /api/*| Router

    %% Routing
    Router -->|Serves Static Files| UI
    Router -->|Forwards to Python| API

    %% Backend Processing
    API --> NLP
    NLP <-->|Real-time Inference| Groq
    API --> VDB
    NLP -->|Fallback Acoustic Params| VDB
    VDB --> API

    %% Response
    API -->|Ranked Playlist JSON| UI
```

---

## 2. Dual-Path Interaction Flow

The frontend supports two distinct interaction models to reduce friction and handle both explicit and implicit user intents.

### Path A: Direct NLP (Text & Voice)
- **Input**: User types "play sad songs" or clicks the microphone and speaks.
- **Flow**: The query is sent directly to the `POST /api/v1/discovery/session/answer` endpoint.
- **Processing**: The `MoodNLPParser` sends the query to Groq LLM. Groq understands the intent and generates 5 highly relevant song recommendations with contextual reasoning.
- **UI Render**: The generated songs are instantly displayed.

### Path B: Guided Discovery (Mood Pills)
- **Input**: User clicks a Mood Pill (e.g., "Relaxed") on the Search page.
- **Flow**: The UI enters a state-machine driven guided flow.
- **Steps**:
  1. Ask for Language (Hindi, English, etc.)
  2. Ask for Genre (Pop, Classical, etc.)
  3. Ask for Playlist Style (Balanced, Discovery, etc.)
- **Processing**: The answers are concatenated into a synthetic prompt (e.g., "Mood: Relaxed, Language: English, Genre: Pop") and sent to the same NLP endpoint.

---

## 3. Backend Subsystems

### A. FastAPI Serverless Wrapper (`api/index.py`)
Because Vercel serverless functions are ephemeral, we use `api/index.py` to expose the FastAPI ASGI app to Vercel's `@vercel/python` builder. The `vercel.json` file routes all `/api/*` traffic to this function.

### B. NLP Orchestrator (`phase1/nlp.py`)
- **Primary Engine**: Integrates with Groq API using `llama-3.3-70b-versatile` for blazing-fast inference.
- **Key Rotation**: Automatically rotates across 3 API keys (`GROQ_API_KEY_1`, `2`, `3`) to bypass rate limits.
- **Graceful Fallback**: If all keys are rate-limited, or if the Vercel environment is missing the API keys, the system catches the exception and falls back to a deterministic keyword-mapping dictionary.
- **UI Error Exposure**: If the API fails for non-rate-limit reasons (like invalid proxies or auth errors), the error is appended to the fallback `thought_process` and displayed in the UI for easy debugging.

### C. Vector Database (`phase1/db.py`)
- **Technology**: NumPy-based in-memory vector store.
- **Purpose**: Serves as the fallback engine. It calculates cosine similarity between the target acoustic features (valence, energy, danceability) and the pre-computed track embeddings in `tracks.json`.

---

## 4. Frontend UI/UX

- **Design System**: A pixel-perfect clone of the native Spotify mobile app, implemented in vanilla HTML/CSS. Features bottom navigation, glassmorphism, and dynamic hover/active states.
- **State Management**: The UI toggles visibility of the `Home` and `Search` views. 
- **Feedback Loop**: Each generated playlist includes a Thumbs Up/Thumbs Down section. Clicking these updates the UI instantly, preparing the ground for future Reinforcement Learning models.
