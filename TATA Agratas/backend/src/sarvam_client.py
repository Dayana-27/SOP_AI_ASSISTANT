"""
Sarvam AI API Client with Connection Pooling
Shared client for STT, Translation, and TTS operations
"""

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from logger_config import setup_logger

load_dotenv()
logger = setup_logger(__name__)

class SarvamAPIClient:
    """
    Singleton client for Sarvam AI API with connection pooling and retry logic.
    Improves performance by reusing connections across multiple API calls.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SarvamAPIClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.api_key = os.getenv('SARVAM_API_KEY')
        if not self.api_key:
            raise ValueError("SARVAM_API_KEY environment variable is not set")
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,  # Total number of retries
            backoff_factor=0.3,  # Wait 0.3s, 0.6s, 1.2s between retries
            status_forcelist=[429, 500, 502, 503, 504],  # Retry on these status codes
            allowed_methods=["POST"]  # Only retry POST requests
        )
        
        # Configure connection pooling adapter
        adapter = HTTPAdapter(
            pool_connections=10,  # Number of connection pools to cache
            pool_maxsize=20,  # Maximum number of connections to save in the pool
            max_retries=retry_strategy
        )
        
        # Mount adapter for HTTPS
        self.session.mount('https://', adapter)
        
        # Set default headers
        self.session.headers['api-subscription-key'] = self.api_key
        self.session.headers['Content-Type'] = 'application/json'
        
        self._initialized = True
        logger.info("Sarvam API Client initialized with connection pooling (pool_size=20, max_retries=3)")
    
    def post(self, url, payload, timeout=(5, 15)):
        """
        Make a POST request with connection pooling
        
        Args:
            url: API endpoint URL
            payload: JSON payload
            timeout: Tuple of (connect_timeout, read_timeout) in seconds
        
        Returns:
            Response object
        """
        return self.session.post(url, json=payload, timeout=timeout)
    
    def close(self):
        """Close the session and release connections"""
        if hasattr(self, 'session'):
            self.session.close()
            logger.info("Sarvam API Client connections closed")


# Global singleton instance
sarvam_client = SarvamAPIClient()

# API Endpoints
SARVAM_STT_URL = "https://api.sarvam.ai/speech-to-text"
SARVAM_TRANSLATE_URL = "https://api.sarvam.ai/translate"
SARVAM_TTS_URL = "https://api.sarvam.ai/text-to-speech"


if __name__ == "__main__":
    logger.info("Sarvam API Client module loaded")
    logger.info(f"API Key configured: {'Yes' if sarvam_client.api_key else 'No'}")
    logger.info("Connection pool size: 20")
    logger.info("Retry strategy: 3 attempts with exponential backoff")

# Made with Bob