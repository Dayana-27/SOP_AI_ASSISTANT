"""
Main Application - FastAPI Server for TATA Agratas RAG System
"""

from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
from contextlib import asynccontextmanager
import time
import json
import asyncio
from search_es import search_hybrid, get_es_connection
from watsonx_generation import generate_answer, generate_answer_stream, get_watsonx_model
from sarvam_stt import transcribe_audio
from sarvam_translate import translate_to_english, translate_from_english, smart_chunk_text
from sarvam_tts import text_to_speech
from logger_config import setup_logger, log_performance, log_error

# Setup logger
logger = setup_logger(__name__)

# Global connection objects (initialized at startup)
es_client = None
watsonx_model = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app
    Handles startup and shutdown events
    """
    # Startup: Initialize connections
    global es_client, watsonx_model
    
    logger.info("=" * 60)
    logger.info("TATA Agratas RAG System - Starting Up")
    logger.info("=" * 60)
    
    try:
        logger.info("Initializing Elasticsearch connection...")
        es_client = get_es_connection()
        logger.info("✓ Elasticsearch connection established successfully")
    except Exception as e:
        logger.warning(f"Could not connect to Elasticsearch: {str(e)}")
        es_client = None
    
    try:
        logger.info("Initializing WatsonX AI model...")
        watsonx_model = get_watsonx_model()
        logger.info("✓ WatsonX AI model initialized successfully")
    except Exception as e:
        logger.warning(f"Could not initialize WatsonX model: {str(e)}")
        watsonx_model = None
    
    logger.info("=" * 60)
    logger.info("✅ Application Ready - All systems operational")
    logger.info("=" * 60)
    
    yield  # Application runs here
    
    # Shutdown: Clean up connections
    logger.info("=" * 60)
    logger.info("Shutting down application...")
    logger.info("=" * 60)
    
    if es_client:
        try:
            es_client.close()
            logger.info("✓ Elasticsearch connection closed")
        except Exception as e:
            logger.error(f"Error closing Elasticsearch connection: {str(e)}")
    
    logger.info("✅ Shutdown complete")
    logger.info("=" * 60)


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="TATA Agratas RAG API",
    description="Retrieval-Augmented Generation API for Industrial Battery Manufacturing",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response Models
class QueryRequest(BaseModel):
    query: str  # English query only
    top_k: int = 3


class VoiceQueryRequest(BaseModel):
    query: str  # Query in any language
    source_language: str  # Language code (e.g., 'hi-IN', 'ta-IN', 'en-IN')
    top_k: int = 3


class SearchResult(BaseModel):
    document_name: str
    page_number: int
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    retrieval_method: str
    num_results: int
    timestamp: str
    processing_time_seconds: float


class Source(BaseModel):
    document_name: str
    page_number: int
    content: str
    score: float


class QueryResponse(BaseModel):
    query: str  # English query
    answer: str  # English answer
    sources: List[Source]
    retrieval_method: str
    timestamp: str
    processing_time_seconds: float


class VoiceQueryResponse(BaseModel):
    original_query: str  # Query in original language
    english_query: str  # Translated to English
    english_answer: str  # Answer in English
    translated_answer: str  # Answer in original language
    audio_base64: Optional[str] = None  # TTS audio
    sources: List[Source]
    retrieval_method: str
    timestamp: str
    processing_time_seconds: float


class TTSRequest(BaseModel):
    text: str
    language: str  # Language code (e.g., 'hi-IN', 'ta-IN', 'en-IN')


class TTSResponse(BaseModel):
    audio_base64: Optional[str] = None
    success: bool
    error: Optional[str] = None
    processing_time_seconds: float


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "TATA Agratas RAG API",
        "version": "1.0.0",
        "endpoints": {
            "/query": "POST - Full RAG (English only - search + answer generation)",
            "/process_voice": "POST - Voice query processing (any language with translation)",
            "/process_voice_stream": "POST - Streaming voice query with real-time text and audio",
            "/generate_tts": "POST - Generate Text-to-Speech audio",
            "/transcribe": "POST - Audio transcription",
            "/es_search": "POST - Elasticsearch hybrid search only",
            "/health": "GET - Health check"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "elasticsearch": "connected" if es_client else "disconnected",
        "watsonx": "connected" if watsonx_model else "disconnected",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/es_search", response_model=SearchResponse)
async def elasticsearch_search(request: QueryRequest):
    """
    Search Elasticsearch using hybrid search (semantic + keyword, reranked)
    
    Args:
        request: QueryRequest with query and top_k
        
    Returns:
        SearchResponse with retrieved and reranked documents
    """
    start_time = time.time()
    
    try:
        # Search Elasticsearch using hybrid search with pooled connection
        results = search_hybrid(request.query, top_k=request.top_k, es_client=es_client)
        
        processing_time = (time.time() - start_time)  # Convert to ms
        
        # Format response
        search_results = [
            SearchResult(
                document_name=doc['document_name'],
                page_number=doc['page_number'],
                content=doc['content'],
                score=doc['score']
            )
            for doc in results
        ]
        
        return SearchResponse(
            query=request.query,
            results=search_results,
            retrieval_method="hybrid",
            num_results=len(search_results),
            timestamp=datetime.utcnow().isoformat(),
            processing_time_seconds=round(processing_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching Elasticsearch: {str(e)}")


@app.post("/query", response_model=QueryResponse)
async def query_rag(request: QueryRequest):
    """
    Full RAG pipeline: Search + Answer Generation (English only)
    This endpoint accepts only English queries and returns English answers.
    For multi-language support, use /process_voice endpoint.
    
    Args:
        request: QueryRequest with English query and top_k
        
    Returns:
        QueryResponse with English answer and sources
    """
    start_time = time.time()
    
    try:
        # Step 1: Search Elasticsearch with English query
        retrieved_docs = search_hybrid(request.query, top_k=request.top_k, es_client=es_client)
        
        if not retrieved_docs:
            return QueryResponse(
                query=request.query,
                answer="No relevant information found in the knowledge base.",
                sources=[],
                retrieval_method="hybrid",
                timestamp=datetime.utcnow().isoformat(),
                processing_time_seconds=round((time.time() - start_time), 2)
            )
        
        # Step 2: Generate answer using WatsonX AI
        answer = generate_answer(request.query, retrieved_docs, model=watsonx_model)
        
        processing_time = (time.time() - start_time)
        
        # Step 3: Format response
        sources = [
            Source(
                document_name=doc['document_name'],
                page_number=doc['page_number'],
                content=doc['content'],
                score=doc['score']
            )
            for doc in retrieved_docs
        ]
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            retrieval_method="hybrid",
            timestamp=datetime.utcnow().isoformat(),
            processing_time_seconds=round(processing_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/process_voice", response_model=VoiceQueryResponse)
async def process_voice_query(request: VoiceQueryRequest):
    """
    Process voice query with full translation pipeline:
    1. Translate query to English (if not English)
    2. Call /query endpoint for RAG processing
    3. Translate answer back to original language (if not English)
    4. Generate TTS in original language (always, even for English)
    
    Args:
        request: VoiceQueryRequest with query in any language and source_language code
        
    Returns:
        VoiceQueryResponse with translated answer and audio
    """
    start_time = time.time()
    request_id = f"voice_{int(time.time() * 1000)}"
    
    logger.info(f"[{request_id}] Voice query request received | Language: {request.source_language} | "
               f"Query length: {len(request.query)} chars")
    logger.debug(f"[{request_id}] Query: {request.query[:100]}...")
    
    try:
        original_query = request.query
        source_lang = request.source_language
        
        # Step 1: Translate query to English if needed
        if source_lang.startswith('en'):
            english_query = original_query
            logger.info(f"[{request_id}] Query is in English, skipping translation")
        else:
            logger.info(f"[{request_id}] Step 1: Translating query from {source_lang} to English")
            translation_result = translate_to_english(original_query, source_lang)
            english_query = translation_result['translated_text']
            logger.debug(f"[{request_id}] Translated query: {english_query[:100]}...")
        
        # Step 2: Call /query endpoint for RAG processing
        logger.info(f"[{request_id}] Step 2: Processing RAG query")
        rag_start = time.time()
        query_request = QueryRequest(query=english_query, top_k=request.top_k)
        rag_response = await query_rag(query_request)
        rag_duration = (time.time() - rag_start) * 1000
        log_performance(logger, f"[{request_id}] RAG Processing", rag_duration)
        
        english_answer = rag_response.answer
        logger.debug(f"[{request_id}] English answer: {english_answer[:100]}...")
        
        # Step 3: Translate answer back to original language (if not English)
        translated_answer = english_answer
        
        if not source_lang.startswith('en'):
            logger.info(f"[{request_id}] Step 3: Translating answer back to {source_lang}")
            translation_result = translate_from_english(english_answer, source_lang)
            translated_answer = translation_result['translated_text']
            logger.info(f"[{request_id}] Translation success: {translation_result.get('success', False)}")
            logger.debug(f"[{request_id}] Translated answer: {translated_answer[:100]}...")
            
            # CRITICAL: Verify translation actually happened
            if translated_answer == english_answer:
                logger.warning(f"[{request_id}] ⚠️ WARNING: Translation returned same text as English! "
                             f"Translation may have failed. Check Sarvam API.")
        else:
            logger.info(f"[{request_id}] Step 3: Language is English ({source_lang}), skipping translation")
        
        # Return response immediately without TTS
        # Frontend will call /generate_tts separately
        processing_time = (time.time() - start_time)
        log_performance(logger, f"[{request_id}] Total Voice Query Processing (without TTS)", processing_time * 1000)
        
        return VoiceQueryResponse(
            original_query=original_query,
            english_query=english_query,
            english_answer=english_answer,
            translated_answer=translated_answer,
            audio_base64=None,  # TTS will be generated separately
            sources=rag_response.sources,
            retrieval_method=rag_response.retrieval_method,
            timestamp=datetime.utcnow().isoformat(),
            processing_time_seconds=round(processing_time, 2)
        )
        
    except Exception as e:
        log_error(logger, e, f"[{request_id}] process_voice_query")
        raise HTTPException(status_code=500, detail=f"Error processing voice query: {str(e)}")

@app.post("/generate_tts", response_model=TTSResponse)
async def generate_tts(request: TTSRequest):
    """
    Generate Text-to-Speech audio for given text
    
    Args:
        request: TTSRequest with text and language
        
    Returns:
        TTSResponse with audio_base64 or error
    """
    start_time = time.time()
    request_id = f"tts_{int(time.time() * 1000)}"
    
    logger.info(f"[{request_id}] TTS generation request | Language: {request.language} | "
               f"Text length: {len(request.text)} chars")
    logger.debug(f"[{request_id}] Text: {request.text[:100]}...")
    
    try:
        tts_result = text_to_speech(request.text, request.language)
        processing_time = (time.time() - start_time)
        
        if tts_result['success']:
            logger.info(f"[{request_id}] TTS generated successfully")
            log_performance(logger, f"[{request_id}] TTS Generation", processing_time * 1000)
            
            return TTSResponse(
                audio_base64=tts_result['audio_base64'],
                success=True,
                error=None,
                processing_time_seconds=round(processing_time, 2)
            )
        else:
            logger.warning(f"[{request_id}] TTS generation failed: {tts_result.get('error')}")
            return TTSResponse(
                audio_base64=None,
                success=False,
                error=tts_result.get('error', 'Unknown error'),
                processing_time_seconds=round(processing_time, 2)
            )
            
    except Exception as e:
        log_error(logger, e, f"[{request_id}] generate_tts")
        processing_time = (time.time() - start_time)
        return TTSResponse(
            audio_base64=None,
            success=False,
            error=str(e),
            processing_time_seconds=round(processing_time, 2)
        )



@app.post("/transcribe")
async def transcribe_speech(file: UploadFile = File(...)):
    """
    Transcribe audio to text using Sarvam AI Speech-to-Text
    
    Args:
        file: Audio file (wav, mp3, etc.)
        
    Returns:
        Transcription result with text
    """
    request_id = f"transcribe_{int(time.time() * 1000)}"
    start_time = time.time()
    
    try:
        logger.info(f"[{request_id}] Transcription request received | File: {file.filename} | "
                   f"Content-Type: {file.content_type}")
        
        # Read the uploaded file
        audio_content = await file.read()
        logger.info(f"[{request_id}] Audio file read | Size: {len(audio_content)} bytes")
        
        # Transcribe using Sarvam AI
        result = transcribe_audio(audio_content)
        
        processing_time = (time.time() - start_time) * 1000
        
        if result['success']:
            logger.info(f"[{request_id}] Transcription successful | Language: {result.get('language_code')} | "
                       f"Duration: {processing_time:.2f}ms")
            logger.debug(f"[{request_id}] Transcript: {result['transcript'][:100]}...")
            
            return {
                "success": True,
                "transcript": result['transcript'],
                "language_code": result.get('language_code', 'en-IN')
            }
        else:
            error_msg = result.get('message', result.get('error', 'Unknown error'))
            logger.error(f"[{request_id}] Transcription failed: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Transcription failed: {error_msg}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        log_error(logger, e, f"[{request_id}] transcribe_speech")
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")


@app.post("/process_voice_stream")
async def process_voice_query_stream(request: VoiceQueryRequest):
    """
    Process voice query with TRUE streaming:
    1. Stream text tokens as they're generated
    2. Translate chunks in parallel
    3. Generate TTS for chunks as they're ready
    4. Frontend plays audio while text is still streaming
    
    Returns Server-Sent Events (SSE) stream
    """
    request_id = f"stream_{int(time.time() * 1000)}"
    
    async def event_generator():
        try:
            original_query = request.query
            source_lang = request.source_language
            
            # Step 1: Translate query to English if needed
            if source_lang.startswith('en'):
                english_query = original_query
            else:
                translation_result = translate_to_english(original_query, source_lang)
                english_query = translation_result['translated_text']
            
            # Send query info
            yield f"data: {json.dumps({'type': 'query', 'english_query': english_query, 'original_query': original_query})}\n\n"
            
            # Step 2: Search Elasticsearch
            retrieved_docs = search_hybrid(english_query, top_k=request.top_k, es_client=es_client)
            
            if not retrieved_docs:
                yield f"data: {json.dumps({'type': 'error', 'message': 'No relevant information found'})}\n\n"
                return
            
            # Send sources
            sources_data = [
                {
                    'document_name': doc['document_name'],
                    'page_number': doc['page_number'],
                    'content': doc['content'],
                    'score': doc['score']
                }
                for doc in retrieved_docs
            ]
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources_data})}\n\n"
            
            # Step 3: Stream answer generation
            english_text_buffer = ""
            translated_text_buffer = ""
            chunk_counter = 0
            
            # Generate answer with streaming
            for token in generate_answer_stream(english_query, retrieved_docs, model=watsonx_model):
                english_text_buffer += token
                
                # Send English token immediately
                yield f"data: {json.dumps({'type': 'token_en', 'token': token})}\n\n"
                
                # When we have enough text (sentence or ~100 chars), translate and generate TTS
                if (len(english_text_buffer) >= 100 and token.strip().endswith(('.', '!', '?'))) or \
                   len(english_text_buffer) >= 200:
                    
                    chunk_text = english_text_buffer.strip()
                    english_text_buffer = ""
                    
                    if chunk_text:
                        # Translate chunk if not English
                        if not source_lang.startswith('en'):
                            translation_result = translate_from_english(chunk_text, source_lang)
                            translated_chunk = translation_result['translated_text']
                        else:
                            translated_chunk = chunk_text
                        
                        # Send translated chunk
                        yield f"data: {json.dumps({'type': 'chunk_translated', 'text': translated_chunk, 'chunk_id': chunk_counter})}\n\n"
                        
                        # Generate TTS for this chunk
                        tts_result = text_to_speech(translated_chunk, source_lang)
                        if tts_result['success']:
                            yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': tts_result['audio_base64'], 'chunk_id': chunk_counter})}\n\n"
                        
                        chunk_counter += 1
                        translated_text_buffer += translated_chunk + " "
            
            # Handle remaining text
            if english_text_buffer.strip():
                chunk_text = english_text_buffer.strip()
                
                if not source_lang.startswith('en'):
                    translation_result = translate_from_english(chunk_text, source_lang)
                    translated_chunk = translation_result['translated_text']
                else:
                    translated_chunk = chunk_text
                
                yield f"data: {json.dumps({'type': 'chunk_translated', 'text': translated_chunk, 'chunk_id': chunk_counter})}\n\n"
                
                tts_result = text_to_speech(translated_chunk, source_lang)
                if tts_result['success']:
                    yield f"data: {json.dumps({'type': 'audio_chunk', 'audio': tts_result['audio_base64'], 'chunk_id': chunk_counter})}\n\n"
                
                translated_text_buffer += translated_chunk
            
            # Send completion
            yield f"data: {json.dumps({'type': 'complete', 'full_text': translated_text_buffer.strip()})}\n\n"
            
        except Exception as e:
            logger.error(f"[{request_id}] Streaming error: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

if __name__ == "__main__":
    import uvicorn
    logger.info("=" * 60)
    logger.info("Starting TATA Agratas RAG API Server")
    logger.info("=" * 60)
    logger.info("API Server: http://localhost:8000")
    logger.info("API Documentation: http://localhost:8000/docs")
    logger.info("Interactive API: http://localhost:8000/redoc")
    logger.info("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

# Made with Bob
