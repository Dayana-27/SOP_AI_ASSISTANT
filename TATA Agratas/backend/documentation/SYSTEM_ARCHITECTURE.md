# TATA Agratas Multi-Language Voice RAG System - Architecture & Flow

## System Overview

This document describes the complete architecture and data flow of the TATA Agratas Multi-Language Voice RAG (Retrieval-Augmented Generation) System with Speech-to-Text and Text-to-Speech capabilities.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React + Carbon)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Voice Input  │  │ Text Input   │  │ Chat Display │              │
│  │ (Microphone) │  │ (TextArea)   │  │ (Messages)   │              │
│  └──────┬───────┘  └──────┬───────┘  └──────▲───────┘              │
│         │                 │                  │                       │
└─────────┼─────────────────┼──────────────────┼───────────────────────┘
          │                 │                  │
          ▼                 ▼                  │
┌─────────────────────────────────────────────┼───────────────────────┐
│                    BACKEND (FastAPI)         │                       │
│                                              │                       │
│  ┌──────────────────────────────────────────┼────────────────────┐  │
│  │              API ENDPOINTS                │                    │  │
│  │                                           │                    │  │
│  │  /transcribe          /process_voice     │    /query          │  │
│  │  (STT only)           (Full Pipeline)    │    (RAG only)      │  │
│  └──────┬────────────────────┬──────────────┼────────┬───────────┘  │
│         │                    │               │        │              │
│         ▼                    ▼               ▼        ▼              │
│  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐       │
│  │  Sarvam AI  │  │  Translation     │  │  Elasticsearch   │       │
│  │  STT API    │  │  (Sarvam API)    │  │  Hybrid Search   │       │
│  └─────────────┘  └──────────────────┘  └────────┬─────────┘       │
│                                                    │                 │
│                                          ┌─────────▼─────────┐       │
│                                          │   WatsonX AI      │       │
│                                          │   (LLM)           │       │
│                                          └─────────┬─────────┘       │
│                                                    │                 │
│                    ┌───────────────────────────────┘                 │
│                    ▼                                                 │
│         ┌──────────────────┐                                         │
│         │  Sarvam AI TTS   │                                         │
│         │  (Text-to-Speech)│                                         │
│         └──────────────────┘                                         │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Detailed Flow Diagrams

### Flow 1: Voice Query Processing (Multi-Language)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    USER SPEAKS (Any Language)                        │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: Audio Recording (Frontend)                                 │
│  - MediaRecorder API captures audio                                 │
│  - Audio stored as Blob (WAV format)                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: Speech-to-Text (Backend: /transcribe)                      │
│  - Audio sent to Sarvam AI STT API                                  │
│  - Returns: transcript + detected language_code                     │
│  - Example: "બેટરી કેવી રીતે કામ કરે છે?" → language: gu-IN         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: Display Transcript (Frontend)                              │
│  - Transcript shown in text input box                               │
│  - Language code saved: detectedLanguage = 'gu-IN'                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: Send to /process_voice (Backend)                           │
│  - POST { query: "બેટરી...", source_language: "gu-IN", top_k: 3 }  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: Translation to English (if needed)                         │
│  - If language != English: Sarvam Translate API                     │
│  - Gujarati → English: "How does a battery work?"                   │
│  - If English: Skip translation                                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 6: RAG Processing (Internal /query call)                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ 6a. Elasticsearch Hybrid Search                              │  │
│  │     - Semantic search (embeddings)                           │  │
│  │     - Keyword search (BM25)                                  │  │
│  │     - Reranking for best results                             │  │
│  │     - Returns top_k documents                                │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │ 6b. WatsonX AI Generation                                    │  │
│  │     - Query + Retrieved docs → LLM                           │  │
│  │     - Generates contextual answer in English                 │  │
│  │     - Example: "A battery works by..."                       │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 7: Translation Back to Original Language                      │
│  - If language != English: Sarvam Translate API                     │
│  - English → Gujarati: "બેટરી કામ કરે છે..."                        │
│  - If English: translated_answer = english_answer                   │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 8: Text-to-Speech Generation                                  │
│  - Sarvam AI TTS API (Bulbul V3 model)                              │
│  - Input: translated_answer + language_code                         │
│  - Speaker: 'priya' (female voice)                                  │
│  - Returns: Base64 encoded audio (WAV)                              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 9: Response to Frontend                                       │
│  - JSON: { original_query, english_query, english_answer,           │
│           translated_answer, audio_base64, sources }                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 10: Display & Play (Frontend)                                 │
│  - Display translated_answer in chat                                │
│  - Convert Base64 → Audio Blob                                      │
│  - Auto-play audio response                                         │
│  - User hears answer in their language                              │
└─────────────────────────────────────────────────────────────────────┘
```

---

### Flow 2: Text Query Processing (English Only via /query)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    USER TYPES ENGLISH QUERY                          │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: Send to /query (Backend)                                   │
│  - POST { query: "What is battery safety?", top_k: 3 }              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: Elasticsearch Hybrid Search                                │
│  - Semantic + Keyword search                                        │
│  - Reranking                                                         │
│  - Returns top_k relevant documents                                 │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: WatsonX AI Generation                                      │
│  - Query + Retrieved docs → LLM                                     │
│  - Generates English answer                                         │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: Response to Frontend                                       │
│  - JSON: { query, answer, sources }                                 │
│  - No translation, No TTS                                           │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: Display Answer (Frontend)                                  │
│  - Show English answer in chat                                      │
│  - No audio playback                                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## API Endpoints

### 1. `/transcribe` - Speech-to-Text Only

**Purpose:** Convert audio to text with language detection

**Request:**
```
POST /transcribe
Content-Type: multipart/form-data

file: <audio_blob> (WAV/MP3)
```

**Response:**
```json
{
  "success": true,
  "transcript": "બેટરી કેવી રીતે કામ કરે છે?",
  "language_code": "gu-IN"
}
```

**Use Case:** Voice input transcription

---

### 2. `/query` - Pure RAG (English Only)

**Purpose:** RAG processing without translation or TTS

**Request:**
```json
POST /query
{
  "query": "What is battery safety?",
  "top_k": 3
}
```

**Response:**
```json
{
  "query": "What is battery safety?",
  "answer": "Battery safety involves...",
  "sources": [
    {
      "document_name": "SoP_Battery_Waste_Management.txt",
      "page_number": 1,
      "content": "...",
      "score": 0.95
    }
  ],
  "retrieval_method": "hybrid",
  "timestamp": "2026-04-02T11:30:00Z",
  "processing_time_seconds": 1.23
}
```

**Use Case:** Direct English queries, API integrations

---

### 3. `/process_voice` - Full Multi-Language Pipeline

**Purpose:** Complete voice processing with translation and TTS

**Request:**
```json
POST /process_voice
{
  "query": "બેટરી કેવી રીતે કામ કરે છે?",
  "source_language": "gu-IN",
  "top_k": 3
}
```

**Response:**
```json
{
  "original_query": "બેટરી કેવી રીતે કામ કરે છે?",
  "english_query": "How does a battery work?",
  "english_answer": "A battery works by...",
  "translated_answer": "બેટરી કામ કરે છે...",
  "audio_base64": "UklGRiQAAABXQVZFZm10...",
  "sources": [...],
  "retrieval_method": "hybrid",
  "timestamp": "2026-04-02T11:30:00Z",
  "processing_time_seconds": 2.45
}
```

**Use Case:** Voice queries in any language, chatbot UI

---

## Technology Stack

### Frontend
- **Framework:** React 18 with Vite
- **UI Library:** IBM Carbon Design System
- **Voice Recording:** MediaRecorder API (Web Audio API)
- **Audio Playback:** HTML5 Audio API
- **Styling:** SCSS with Carbon themes

### Backend
- **Framework:** FastAPI (Python)
- **Search Engine:** Elasticsearch 8.x
  - Hybrid search (semantic + keyword)
  - Reranking with cross-encoder
- **LLM:** IBM WatsonX AI
  - Model: granite-13b-chat-v2
- **Speech Services:** Sarvam AI APIs
  - STT: Automatic language detection
  - Translation: 20+ Indian languages
  - TTS: Bulbul V3 model

### External APIs
1. **Sarvam AI Speech-to-Text**
   - Endpoint: `https://api.sarvam.ai/speech-to-text`
   - Auto language detection
   - Supports: Hindi, Tamil, Telugu, Kannada, Malayalam, Gujarati, etc.

2. **Sarvam AI Translation**
   - Endpoint: `https://api.sarvam.ai/translate`
   - Bidirectional translation (any language ↔ English)

3. **Sarvam AI Text-to-Speech**
   - Endpoint: `https://api.sarvam.ai/text-to-speech`
   - Model: bulbul:v3
   - Multiple speakers available

---

## Supported Languages

The system supports the following languages through Sarvam AI:

| Language | Code | STT | Translation | TTS |
|----------|------|-----|-------------|-----|
| English | en-IN | ✅ | ✅ | ✅ |
| Hindi | hi-IN | ✅ | ✅ | ✅ |
| Tamil | ta-IN | ✅ | ✅ | ✅ |
| Telugu | te-IN | ✅ | ✅ | ✅ |
| Kannada | kn-IN | ✅ | ✅ | ✅ |
| Malayalam | ml-IN | ✅ | ✅ | ✅ |
| Gujarati | gu-IN | ✅ | ✅ | ✅ |
| Marathi | mr-IN | ✅ | ✅ | ✅ |
| Bengali | bn-IN | ✅ | ✅ | ✅ |
| Punjabi | pa-IN | ✅ | ✅ | ✅ |
| Odia | or-IN | ✅ | ✅ | ✅ |

---

## Data Flow Summary

```
Voice Input → STT → Text (with language) → Translation (if needed) → 
RAG (Search + Generate) → Translation back → TTS → Audio Output
```

**Key Points:**
1. All RAG processing happens in English for consistency
2. Translation is bidirectional (user language ↔ English)
3. TTS is generated in the user's original language
4. `/query` endpoint remains pure for English-only use cases
5. `/process_voice` handles the complete multi-language pipeline

---

## Performance Considerations

- **Average Response Time:** 2-3 seconds (including TTS)
- **Elasticsearch Search:** ~200-300ms
- **WatsonX Generation:** ~800-1000ms
- **Translation:** ~200-300ms per call
- **TTS Generation:** ~500-800ms
- **Connection Pooling:** Elasticsearch and WatsonX use persistent connections

---

## Error Handling

The system includes comprehensive error handling at each stage:

1. **Audio Recording Errors:** Microphone permission issues
2. **STT Errors:** Invalid audio format, API failures
3. **Translation Errors:** Unsupported language pairs
4. **RAG Errors:** No relevant documents found
5. **TTS Errors:** Invalid speaker, model compatibility issues

All errors are logged and user-friendly messages are displayed in the UI.

---

## Future Enhancements

1. **Streaming Responses:** Real-time audio streaming for TTS
2. **Multi-turn Conversations:** Context-aware follow-up questions
3. **Custom Voice Training:** Organization-specific voice models
4. **Offline Mode:** Local STT/TTS for sensitive environments
5. **Analytics Dashboard:** Usage metrics and performance monitoring

---

*Last Updated: April 2, 2026*
*Version: 1.0.0*