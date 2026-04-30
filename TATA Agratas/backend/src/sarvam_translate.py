from sarvam_client import sarvam_client, SARVAM_TRANSLATE_URL
from logger_config import setup_logger, log_api_call, log_api_response, log_error
import time
import re

logger = setup_logger(__name__)

# Sarvam API character limit for translation
MAX_CHARS_PER_REQUEST = 500  # Conservative limit for chunking

def smart_chunk_text(text, max_chars=MAX_CHARS_PER_REQUEST):
    """
    Split text into chunks at sentence boundaries, respecting max character limit.
    
    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk
        
    Returns:
        List of text chunks
    """
    if len(text) <= max_chars:
        return [text]
    
    # Split by sentences (periods, question marks, exclamation marks followed by space or newline)
    sentences = re.split(r'([.!?]\s+|\n+)', text)
    
    chunks = []
    current_chunk = ""
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i]
        separator = sentences[i + 1] if i + 1 < len(sentences) else ""
        
        # If adding this sentence exceeds limit, save current chunk and start new one
        if current_chunk and len(current_chunk) + len(sentence) + len(separator) > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + separator
        else:
            current_chunk += sentence + separator
    
    # Add the last chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # Handle edge case: if a single sentence is too long, split by words
    final_chunks = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            final_chunks.append(chunk)
        else:
            # Split long chunk by words
            words = chunk.split()
            temp_chunk = ""
            for word in words:
                if len(temp_chunk) + len(word) + 1 <= max_chars:
                    temp_chunk += word + " "
                else:
                    if temp_chunk:
                        final_chunks.append(temp_chunk.strip())
                    temp_chunk = word + " "
            if temp_chunk:
                final_chunks.append(temp_chunk.strip())
    
    return final_chunks

def translate_to_english(text, source_language_code='hi-IN'):
    """
    Translate text to English using Sarvam AI Translation API
    
    Args:
        text: Text to translate
        source_language_code: Source language code (default: 'hi-IN' for Hindi)
    
    Returns:
        dict: Translation result with English text
    """
    start_time = time.time()
    logger.info(f"Translating to English | Source: {source_language_code} | Text length: {len(text)} chars")
    logger.debug(f"Source text: {text[:100]}...")
    
    try:
        payload = {
            'input': text,
            'source_language_code': source_language_code,
            'target_language_code': 'en-IN'
        }
        
        log_api_call(logger, "Sarvam Translate", SARVAM_TRANSLATE_URL,
                    source=source_language_code, target='en-IN', text_length=len(text))
        
        # Use shared client with connection pooling
        api_start = time.time()
        response = sarvam_client.post(
            SARVAM_TRANSLATE_URL,
            payload=payload,
            timeout=(5, 15)
        )
        api_duration = (time.time() - api_start) * 1000
        
        log_api_response(logger, "Sarvam Translate", response.status_code, api_duration)
        
        if response.status_code == 200:
            result = response.json()
            translated_text = result.get('translated_text', text)
            total_duration = (time.time() - start_time) * 1000
            
            logger.info(f"Translation to English successful | Duration: {total_duration:.2f}ms | "
                       f"Output length: {len(translated_text)} chars")
            logger.debug(f"Translated text: {translated_text[:100]}...")
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_text': text
            }
        else:
            logger.error(f"Translation to English failed | Status: {response.status_code} | "
                        f"Response: {response.text}")
            # If translation fails, return original text
            return {
                'success': False,
                'translated_text': text,  # Fallback to original
                'original_text': text,
                'error': f"API Error: {response.status_code}"
            }
            
    except Exception as e:
        log_error(logger, e, "translate_to_english")
        # If translation fails, return original text
        return {
            'success': False,
            'translated_text': text,  # Fallback to original
            'original_text': text,
            'error': str(e)
        }

def translate_from_english(text, target_language_code='hi-IN'):
    """
    Translate text from English to target language using Sarvam AI Translation API.
    Automatically chunks text if it exceeds 1000 character limit.
    
    Args:
        text: English text to translate
        target_language_code: Target language code (e.g., 'hi-IN', 'ta-IN', 'gu-IN')
    
    Returns:
        dict: Translation result with text in target language
    """
    start_time = time.time()
    logger.info(f"Translating from English | Target: {target_language_code} | Text length: {len(text)} chars")
    logger.debug(f"English text: {text[:100]}...")
    
    try:
        # Check if text exceeds API limit (1000 chars)
        if len(text) > 1000:
            logger.info(f"Text exceeds 1000 chars, chunking into smaller pieces...")
            chunks = smart_chunk_text(text, max_chars=900)  # Use 900 to be safe
            logger.info(f"Split into {len(chunks)} chunks")
            
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                logger.debug(f"Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                
                payload = {
                    'input': chunk,
                    'source_language_code': 'en-IN',
                    'target_language_code': target_language_code
                }
                
                api_start = time.time()
                response = sarvam_client.post(
                    SARVAM_TRANSLATE_URL,
                    payload=payload,
                    timeout=(5, 15)
                )
                api_duration = (time.time() - api_start) * 1000
                
                if response.status_code == 200:
                    result = response.json()
                    translated_chunk = result.get('translated_text', chunk)
                    translated_chunks.append(translated_chunk)
                    logger.debug(f"Chunk {i+1} translated successfully ({api_duration:.2f}ms)")
                else:
                    logger.error(f"Chunk {i+1} translation failed | Status: {response.status_code}")
                    # On failure, use original chunk
                    translated_chunks.append(chunk)
            
            # Combine all translated chunks
            translated_text = ' '.join(translated_chunks)
            total_duration = (time.time() - start_time) * 1000
            
            logger.info(f"Chunked translation completed | Total duration: {total_duration:.2f}ms | "
                       f"Output length: {len(translated_text)} chars")
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_text': text,
                'chunks_used': len(chunks)
            }
        
        # Single request for text under 1000 chars
        payload = {
            'input': text,
            'source_language_code': 'en-IN',
            'target_language_code': target_language_code
        }
        
        log_api_call(logger, "Sarvam Translate", SARVAM_TRANSLATE_URL,
                    source='en-IN', target=target_language_code, text_length=len(text))
        
        # Use shared client with connection pooling
        api_start = time.time()
        response = sarvam_client.post(
            SARVAM_TRANSLATE_URL,
            payload=payload,
            timeout=(5, 15)
        )
        api_duration = (time.time() - api_start) * 1000
        
        log_api_response(logger, "Sarvam Translate", response.status_code, api_duration)
        
        if response.status_code == 200:
            result = response.json()
            translated_text = result.get('translated_text', text)
            total_duration = (time.time() - start_time) * 1000
            
            logger.info(f"Translation from English successful | Duration: {total_duration:.2f}ms | "
                       f"Output length: {len(translated_text)} chars")
            logger.debug(f"Translated text: {translated_text[:100]}...")
            
            return {
                'success': True,
                'translated_text': translated_text,
                'original_text': text
            }
        else:
            logger.error(f"Translation from English failed | Status: {response.status_code} | "
                        f"Response: {response.text}")
            # If translation fails, return original text
            return {
                'success': False,
                'translated_text': text,  # Fallback to original
                'original_text': text,
                'error': f"API Error: {response.status_code} - {response.text}"
            }
            
    except Exception as e:
        log_error(logger, e, "translate_from_english")
        # If translation fails, return original text
        return {
            'success': False,
            'translated_text': text,  # Fallback to original
            'original_text': text,
            'error': str(e)
        }

if __name__ == "__main__":
    # Test the function
    logger.info("Sarvam Translation module loaded successfully")
    logger.info(f"API Key configured: {'Yes' if sarvam_client.api_key else 'No'}")
    logger.info("Using shared connection pool for translation requests")

# Made with Bob
