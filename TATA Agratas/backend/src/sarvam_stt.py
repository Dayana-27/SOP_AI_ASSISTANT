from sarvam_client import sarvam_client, SARVAM_STT_URL
from logger_config import setup_logger, log_api_call, log_api_response, log_error
import requests
import io
import time

logger = setup_logger(__name__)

def transcribe_audio(audio_data, language_code=None):
    """
    Transcribe audio using Sarvam AI Speech-to-Text API
    
    Args:
        audio_data: Audio file bytes
        language_code: Optional (e.g., "hi-IN", "gu-IN")
    
    Returns:
        dict: Transcription result with text
    """
    start_time = time.time()
    logger.info(f"Starting audio transcription | Audio size: {len(audio_data)} bytes")
    
    try:
        # Create a file-like object from bytes
        audio_file = io.BytesIO(audio_data)
        
        files = {
            'file': ('audio.wav', audio_file, 'audio/wav')
        }
        
        #  NEW: Dynamic language handling
        data = {}
        if language_code:
            data["language_code"] = language_code
        
        logger.info(f"Language sent to STT: {language_code if language_code else 'AUTO'}")
        
        log_api_call(logger, "Sarvam STT", SARVAM_STT_URL, audio_size=len(audio_data))
        
        # Headers for API
        headers = {
            'api-subscription-key': sarvam_client.api_key
        }
        
        api_start = time.time()
        response = requests.post(
            SARVAM_STT_URL,
            headers=headers,
            files=files,
            data=data,
            timeout=(5, 30)
        )
        api_duration = (time.time() - api_start) * 1000
        
        log_api_response(logger, "Sarvam STT", response.status_code, api_duration)
        logger.debug(f"STT Response body: {response.text[:200]}...")
        
        if response.status_code == 200:
            result = response.json()
            detected_language = result.get('language_code', 'en-IN')
            transcript = result.get('transcript', '')
            total_duration = (time.time() - start_time) * 1000
            
            logger.info(
                f"Transcription successful | Detected: {detected_language} | "
                f"Transcript length: {len(transcript)} chars | Duration: {total_duration:.2f}ms"
            )
            logger.debug(f"Transcript: {transcript[:100]}...")
            
            
            return {
                'success': True,
                'transcript': transcript,
                'language_code': detected_language,
                'requested_language': language_code if language_code else "AUTO"
            }
        
        else:
            logger.error(f"STT API error | Status: {response.status_code} | Response: {response.text}")
            return {
                'success': False,
                'error': f"API Error: {response.status_code}",
                'message': response.text
            }
            
    except Exception as e:
        log_error(logger, e, "transcribe_audio")
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Test the function
    logger.info("Sarvam Speech-to-Text module loaded successfully")
    logger.info(f"API Key configured: {'Yes' if sarvam_client.api_key else 'No'}")
    logger.info("Supports: Auto detection + Forced language (hi-IN, gu-IN)")