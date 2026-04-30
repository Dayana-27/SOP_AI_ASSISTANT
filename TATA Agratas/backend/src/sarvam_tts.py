from sarvam_client import sarvam_client, SARVAM_TTS_URL
from logger_config import setup_logger, log_api_call, log_api_response, log_error
import time
import base64
import io
import wave

logger = setup_logger(__name__)

def split_text_into_chunks(text, max_length=500):
    """
    Split text into chunks at sentence boundaries, respecting max_length
    
    Args:
        text: Text to split
        max_length: Maximum characters per chunk
    
    Returns:
        list: List of text chunks
    """
    # Split by sentence endings
    sentences = []
    current = ""
    
    for char in text:
        current += char
        if char in '.!?।॥' and len(current.strip()) > 0:  # Include Hindi sentence endings
            sentences.append(current.strip())
            current = ""
    
    if current.strip():
        sentences.append(current.strip())
    
    # Combine sentences into chunks
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_length:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            # If single sentence is too long, split it
            if len(sentence) > max_length:
                words = sentence.split()
                temp_chunk = ""
                for word in words:
                    if len(temp_chunk) + len(word) + 1 <= max_length:
                        temp_chunk += (" " if temp_chunk else "") + word
                    else:
                        if temp_chunk:
                            chunks.append(temp_chunk)
                        temp_chunk = word
                if temp_chunk:
                    current_chunk = temp_chunk
                else:
                    current_chunk = ""
            else:
                current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def generate_tts_for_chunk(text, target_language_code, speaker):
    """
    Generate TTS for a single chunk of text
    
    Returns:
        bytes: WAV audio data or None if failed
    """
    try:
        payload = {
            'inputs': [text],
            'target_language_code': target_language_code,
            'speaker': speaker,
            'pace': 1.0,
            'speech_sample_rate': 8000,
            'enable_preprocessing': True,
            'model': 'bulbul:v3'
        }
        
        response = sarvam_client.post(
            SARVAM_TTS_URL,
            payload=payload,
            timeout=(5, 20)
        )
        
        if response.status_code == 200:
            result = response.json()
            audio_base64 = result.get('audios', [None])[0]
            if audio_base64:
                # Decode base64 to bytes
                return base64.b64decode(audio_base64)
        return None
    except Exception as e:
        logger.error(f"Error generating TTS for chunk: {str(e)}")
        return None


def concatenate_wav_files(wav_chunks):
    """
    Concatenate multiple WAV audio chunks into a single WAV file
    
    Args:
        wav_chunks: List of WAV audio data (bytes)
    
    Returns:
        bytes: Combined WAV audio data
    """
    if not wav_chunks:
        return None
    
    if len(wav_chunks) == 1:
        return wav_chunks[0]
    
    try:
        # Read first chunk to get parameters
        first_chunk = io.BytesIO(wav_chunks[0])
        with wave.open(first_chunk, 'rb') as first_wav:
            params = first_wav.getparams()
            frames = [first_wav.readframes(first_wav.getnframes())]
        
        # Read remaining chunks
        for chunk_data in wav_chunks[1:]:
            chunk_io = io.BytesIO(chunk_data)
            with wave.open(chunk_io, 'rb') as wav:
                frames.append(wav.readframes(wav.getnframes()))
        
        # Write combined audio
        output = io.BytesIO()
        with wave.open(output, 'wb') as output_wav:
            output_wav.setparams(params)
            output_wav.writeframes(b''.join(frames))
        
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error concatenating WAV files: {str(e)}")
        return None


def text_to_speech(text, target_language_code='hi-IN', speaker='simran'):
    """
    Convert text to speech using Sarvam AI Text-to-Speech API
    Handles long text by splitting into chunks and concatenating audio
    
    Args:
        text: Text to convert to speech
        target_language_code: Target language code (e.g., 'hi-IN', 'en-IN')
        speaker: Voice speaker name (default: 'priya' - female voice)
    
    Returns:
        dict: Audio data in base64 format
    """
    start_time = time.time()
    original_length = len(text)
    
    logger.info(f"Generating TTS | Language: {target_language_code} | Speaker: {speaker} | "
               f"Text length: {original_length} chars")
    logger.debug(f"TTS text: {text[:100]}...")
    
    try:
        # Split text into chunks if needed
        MAX_TTS_LENGTH = 500
        chunks = split_text_into_chunks(text, MAX_TTS_LENGTH)
        
        if len(chunks) > 1:
            logger.info(f"Text split into {len(chunks)} chunks for TTS generation")
        
        # Generate TTS for each chunk
        wav_chunks = []
        for i, chunk in enumerate(chunks):
            log_api_call(logger, "Sarvam TTS", SARVAM_TTS_URL,
                        language=target_language_code, speaker=speaker,
                        text_length=len(chunk), model='bulbul:v3', chunk=f"{i+1}/{len(chunks)}")
            
            api_start = time.time()
            wav_data = generate_tts_for_chunk(chunk, target_language_code, speaker)
            api_duration = (time.time() - api_start) * 1000
            
            if wav_data:
                wav_chunks.append(wav_data)
                log_api_response(logger, f"Sarvam TTS Chunk {i+1}/{len(chunks)}", 200, api_duration)
            else:
                logger.warning(f"Failed to generate TTS for chunk {i+1}/{len(chunks)}")
                log_api_response(logger, f"Sarvam TTS Chunk {i+1}/{len(chunks)}", 400, api_duration)
        
        if not wav_chunks:
            logger.error("TTS failed: No audio chunks generated")
            return {
                'success': False,
                'error': 'No audio chunks generated'
            }
        
        # Concatenate chunks if multiple
        if len(wav_chunks) > 1:
            logger.info(f"Concatenating {len(wav_chunks)} audio chunks")
            combined_wav = concatenate_wav_files(wav_chunks)
        else:
            combined_wav = wav_chunks[0]
        
        if not combined_wav:
            logger.error("TTS failed: Could not concatenate audio chunks")
            return {
                'success': False,
                'error': 'Could not concatenate audio chunks'
            }
        
        # Encode to base64
        audio_base64 = base64.b64encode(combined_wav).decode('utf-8')
        total_duration = (time.time() - start_time) * 1000
        
        logger.info(f"TTS generation successful | Duration: {total_duration:.2f}ms | "
                   f"Audio size: {len(audio_base64)} bytes (base64) | Chunks: {len(chunks)}")
        
        return {
            'success': True,
            'audio_base64': audio_base64,
            'language': target_language_code
        }
        payload = {
            'inputs': [text],
            'target_language_code': target_language_code,
            'speaker': speaker,
            'pace': 1.0,
            'speech_sample_rate': 8000,
            'enable_preprocessing': True,
            'model': 'bulbul:v3'
        }
        
        log_api_call(logger, "Sarvam TTS", SARVAM_TTS_URL,
                    language=target_language_code, speaker=speaker,
                    text_length=len(text), model='bulbul:v3')
        
        # Use shared client with connection pooling
        api_start = time.time()
        response = sarvam_client.post(
            SARVAM_TTS_URL,
            payload=payload,
            timeout=(5, 20)  # 5s connect, 20s read for TTS generation
        )
        api_duration = (time.time() - api_start) * 1000
        
        log_api_response(logger, "Sarvam TTS", response.status_code, api_duration)
        
        if response.status_code == 200:
            result = response.json()
            # Sarvam returns audio in base64 format
            audio_base64 = result.get('audios', [None])[0]
            total_duration = (time.time() - start_time) * 1000
            
            if audio_base64:
                audio_size = len(audio_base64)
                logger.info(f"TTS generation successful | Duration: {total_duration:.2f}ms | "
                           f"Audio size: {audio_size} bytes (base64)")
                return {
                    'success': True,
                    'audio_base64': audio_base64,
                    'language': target_language_code
                }
            else:
                logger.error("TTS failed: No audio data in response")
                return {
                    'success': False,
                    'error': 'No audio data in response'
                }
        else:
            logger.error(f"TTS API error | Status: {response.status_code} | Response: {response.text}")
            return {
                'success': False,
                'error': f"API Error: {response.status_code}",
                'message': response.text
            }
            
    except Exception as e:
        log_error(logger, e, "text_to_speech")
        return {
            'success': False,
            'error': str(e)
        }

if __name__ == "__main__":
    # Test the function
    logger.info("Sarvam Text-to-Speech module loaded successfully")
    logger.info(f"API Key configured: {'Yes' if sarvam_client.api_key else 'No'}")
    logger.info("Using shared connection pool for TTS requests")
    logger.info("TTS Model: bulbul:v3 | Default speaker: priya")
    logger.info("Supports text chunking and concatenation for responses > 500 characters")

# Made with Bob
