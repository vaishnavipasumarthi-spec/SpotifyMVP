// ==========================================
// Spotify AI Mood Discovery — Frontend JS
// ==========================================

const API_BASE = "http://127.0.0.1:8005/api/v1/discovery/session";

// Views & Navigation
const viewHome = document.getElementById("view-home");
const viewSearch = document.getElementById("view-search");
const navHome = document.getElementById("nav-home");
const navSearch = document.getElementById("nav-search");
const homeFakeSearch = document.getElementById("home-fake-search");

// Search UI Elements
const searchInput = document.getElementById("search-input");
const micTriggerBtn = document.getElementById("mic-trigger-btn");
const searchDefaultState = document.getElementById("search-default-state");
const resultsContainer = document.getElementById("recommendation-results");
const tracksList = document.getElementById("tracks-list");
const playlistMode = document.getElementById("playlist-mode");
const moodPills = document.querySelectorAll(".mood-pill");
const feedbackSection = document.getElementById("feedback-section");
const feedbackBtns = document.querySelectorAll(".feedback-btn");

// Voice Elements
const voiceOverlay = document.getElementById("voice-overlay");
const transcriptEl = document.getElementById("voice-transcript-live");
const statusLabel = document.getElementById("voice-status-label");
const wave = document.getElementById("voice-wave");

const moodPromptSection = document.getElementById("mood-prompt-section");
const guidedQuestionsContainer = document.getElementById("guided-questions-container");
const guidedQTitle = document.getElementById("guided-q-title");
const guidedQOptions = document.getElementById("guided-q-options");
const mockSections = document.querySelectorAll("#search-default-state .section-block");

let currentSessionId = generateSessionId();
let recognition = null;
let liveTranscript = "";

function generateSessionId() {
    return "sess_" + Math.random().toString(36).substr(2, 9);
}

// ==========================================
// Navigation Logic
// ==========================================
function switchToView(viewName) {
    if (viewName === "home") {
        viewHome.classList.add("active");
        viewHome.classList.remove("hidden");
        viewSearch.classList.remove("active");
        viewSearch.classList.add("hidden");
        navHome.classList.add("active");
        navSearch.classList.remove("active");
    } else if (viewName === "search") {
        viewSearch.classList.add("active");
        viewSearch.classList.remove("hidden");
        viewHome.classList.remove("active");
        viewHome.classList.add("hidden");
        navSearch.classList.add("active");
        navHome.classList.remove("active");
    }
}

navHome.addEventListener("click", () => switchToView("home"));
navSearch.addEventListener("click", () => switchToView("search"));

// Clicking fake search on Home switches to Search view and focuses input
homeFakeSearch.addEventListener("click", () => {
    switchToView("search");
    setTimeout(() => {
        resetSearchState();
        searchInput.focus();
    }, 100);
});

// ==========================================
// Reset Search State
// ==========================================
function resetSearchState() {
    resultsContainer.classList.add("hidden");
    searchDefaultState.classList.remove("hidden");
    moodPromptSection.classList.remove("hidden");
    mockSections.forEach(sec => sec.classList.remove("hidden"));
    guidedQuestionsContainer.classList.add("hidden");
}

searchInput.addEventListener("focus", () => {
    resetSearchState();
    searchInput.value = ""; // Clear old query on click
});

// ==========================================
// Text & Pill Search
// ==========================================
searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        const text = searchInput.value.trim();
        if (!text) return;
        // Text search goes directly to AI (no questions)
        sendToGemini(text);
    }
});

// ==========================================
// Guided Discovery State Machine
// ==========================================
const guidedSteps = [
    {
        title: "What language?",
        options: ["Hindi", "English", "Punjabi", "K-Pop", "Global"],
        colors: ["bg-teal", "bg-blue", "bg-magenta", "bg-purple", "bg-indigo"]
    },
    {
        title: "What genre?",
        options: ["Pop", "Classical", "Hip-Hop", "Lo-Fi", "Surprise Me"],
        colors: ["bg-magenta", "bg-violet", "bg-blue-dark", "bg-indigo", "bg-teal"]
    },
    {
        title: "Playlist style?",
        options: ["Repetition", "Balanced", "Discovery"],
        colors: ["bg-blue", "bg-green", "bg-purple"]
    }
];

let userSelections = {};
let currentStepIndex = 0;

const guidedBackBtn = document.getElementById("guided-back-btn");
const resultsBackBtn = document.getElementById("results-back-btn");

if (guidedBackBtn) {
    guidedBackBtn.addEventListener("click", () => {
        guidedQuestionsContainer.classList.add("hidden");
        moodPromptSection.classList.remove("hidden");
        mockSections.forEach(sec => sec.classList.remove("hidden"));
    });
}

if (resultsBackBtn) {
    resultsBackBtn.addEventListener("click", () => {
        resetSearchState();
        searchInput.value = "";
    });
}

moodPills.forEach(pill => {
    pill.addEventListener("click", () => {
        userSelections = {};
        userSelections.mood = pill.textContent.trim();
        searchInput.value = userSelections.mood;
        startGuidedFlow();
    });
});

function startGuidedFlow() {
    // Hide mood prompt and static browse sections
    moodPromptSection.classList.add("hidden");
    mockSections.forEach(sec => sec.classList.add("hidden"));
    
    // Show follow-up questions container
    guidedQuestionsContainer.classList.remove("hidden");
    currentStepIndex = 0;
    renderGuidedStep();
}

function renderGuidedStep() {
    if (currentStepIndex >= guidedSteps.length) {
        // We are done! Construct the query and send.
        guidedQuestionsContainer.classList.add("hidden");
        const finalQuery = `Mood: ${userSelections.mood}, Language: ${userSelections.lang}, Genre: ${userSelections.genre}, Style: ${userSelections.style}`;
        searchInput.value = finalQuery;
        sendToGemini(finalQuery);
        return;
    }

    const step = guidedSteps[currentStepIndex];
    guidedQTitle.textContent = step.title;
    guidedQOptions.innerHTML = "";

    step.options.forEach((opt, i) => {
        const btn = document.createElement("button");
        btn.className = `mood-pill ${step.colors[i % step.colors.length]}`;
        btn.textContent = opt;
        btn.addEventListener("click", () => {
            // Save answer based on step index
            if (currentStepIndex === 0) userSelections.lang = opt;
            else if (currentStepIndex === 1) userSelections.genre = opt;
            else if (currentStepIndex === 2) userSelections.style = opt;
            
            currentStepIndex++;
            renderGuidedStep();
        });
        guidedQOptions.appendChild(btn);
    });
}

// ==========================================
// Voice Search — Web Speech API
// ==========================================
micTriggerBtn.addEventListener("click", startVoice);

function startVoice() {
    resetSearchState();
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        alert("Voice search requires Chrome or Edge browser.");
        return;
    }

    liveTranscript = "";
    transcriptEl.textContent = "speak now...";
    transcriptEl.style.color = "var(--text-secondary)";
    statusLabel.textContent = "Listening...";
    wave.style.opacity = "1";
    voiceOverlay.classList.remove("hidden");

    recognition = new SpeechRecognition();
    recognition.lang = "en-IN";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (e) => {
        let interim = "";
        liveTranscript = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
            const t = e.results[i][0].transcript;
            if (e.results[i].isFinal) {
                liveTranscript += t;
            } else {
                interim += t;
            }
        }
        if (liveTranscript) {
            transcriptEl.textContent = liveTranscript;
            transcriptEl.style.color = "#ffffff";
        } else {
            transcriptEl.textContent = interim;
            transcriptEl.style.color = "var(--text-secondary)";
        }
    };

    recognition.onspeechend = () => recognition.stop();

    recognition.onend = () => {
        wave.style.opacity = "0.3";
        const query = liveTranscript.trim();
        if (query) {
            statusLabel.textContent = `"${query}"`;
            transcriptEl.textContent = "Processing...";
            setTimeout(() => {
                voiceOverlay.classList.add("hidden");
                switchToView("search");
                searchInput.value = query;
                // Voice search goes directly to AI (no questions)
                sendToGemini(query);
            }, 800);
        } else {
            statusLabel.textContent = "Nothing heard. Tap mic to try again.";
            setTimeout(() => voiceOverlay.classList.add("hidden"), 2000);
        }
    };

    recognition.onerror = (e) => {
        wave.style.opacity = "0.3";
        if (e.error === "no-speech") {
            statusLabel.textContent = "No speech detected.";
        } else if (e.error === "not-allowed") {
            statusLabel.textContent = "Mic access denied.";
        } else {
            statusLabel.textContent = `Error: ${e.error}`;
        }
        setTimeout(() => voiceOverlay.classList.add("hidden"), 2500);
    };

    recognition.start();
}

// ==========================================
// Core API Integration
// ==========================================
async function sendToGemini(text) {
    if (!text) return;
    
    // Switch UI state in Search View
    searchDefaultState.classList.add("hidden");
    resultsContainer.classList.remove("hidden");
    
    // Loading state
    document.getElementById("ai-reasoning-box").classList.add("hidden");
    if (feedbackSection) feedbackSection.classList.add("hidden");
    tracksList.innerHTML = `
        <div class="loading-state">
            <div class="loading-spinner"></div>
            <p>Curating your playlist for <em>"${text}"</em>...</p>
        </div>`;
    document.getElementById("playlist-title").textContent = `AI Mix: ${text.slice(0, 30)}`;

    currentSessionId = generateSessionId();

    try {
        await fetch(`${API_BASE}/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: currentSessionId, phase: "manual" })
        });

        const res = await fetch(`${API_BASE}/answer`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: currentSessionId, answer_text: text })
        });

        if (!res.ok) {
            const err = await res.text();
            tracksList.innerHTML = `<p class="error-msg">Server error ${res.status}: ${err}</p>`;
            return;
        }

        const data = await res.json();
        renderResults(data);

    } catch (err) {
        console.error(err);
        tracksList.innerHTML = `<p class="error-msg">Network error — is the backend running?</p>`;
    }
}

// ==========================================
// Render Results
// ==========================================
function renderResults(data) {
    const recs = data.recommendations;
    if (!recs) return;

    document.getElementById("playlist-title").textContent = recs.name || "AI Mix";
    playlistMode.textContent = data.slots?.mode || "Balanced";

    // AI Reasoning
    const reasoningBox = document.getElementById("ai-reasoning-box");
    const reasoningText = document.getElementById("ai-reasoning-text");
    if (recs.thought_process) {
        reasoningText.textContent = recs.thought_process;
        reasoningBox.classList.remove("hidden");
    } else {
        reasoningBox.classList.add("hidden");
    }

    // Tracks
    tracksList.innerHTML = "";
    if (!recs.tracks || recs.tracks.length === 0) {
        tracksList.innerHTML = `<p class="error-msg">No tracks found. Try a different query.</p>`;
        return;
    }

    recs.tracks.forEach((track, i) => {
        const card = document.createElement("div");
        card.className = "track-card result-card";
        if (i === 0) card.classList.add("top-pick");

        const isHidden = track.artist?.is_hidden_gem;
        const artistLabel = isHidden
            ? `${track.artist.name} <span class="gem-tag">Discovery</span>`
            : (track.artist?.name || "Unknown Artist");

        const matchPct = Math.round((track.similarity_score || 0) * 100);
        const whyHtml = track.why
            ? `<div class="track-why">${track.why}</div>`
            : "";

        card.innerHTML = `
            <div class="track-info">
                <div class="track-title">${track.title}</div>
                <div class="track-artist">${artistLabel}</div>
                <div class="track-genres">${(track.genres || []).slice(0, 2).join(" · ")}</div>
                ${whyHtml}
            </div>
            <div class="track-stats">
                <div class="stat-score">${matchPct}%</div>
                <div class="stat-subtext">match</div>
            </div>`;

        tracksList.appendChild(card);
    });

    if (feedbackSection) {
        feedbackSection.classList.remove("hidden");
        // Reset feedback buttons
        feedbackBtns.forEach(b => b.classList.remove("active"));
    }
}

// ==========================================
// Feedback Handlers
// ==========================================
if (feedbackBtns) {
    feedbackBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            // Remove active from all
            feedbackBtns.forEach(b => b.classList.remove("active"));
            // Add active to clicked
            btn.classList.add("active");
            // Here you would normally send an API request to log the feedback
            console.log("Feedback recorded for session:", currentSessionId);
        });
    });
}
