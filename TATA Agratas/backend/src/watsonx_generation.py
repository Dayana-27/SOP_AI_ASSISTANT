"""
WatsonX AI Response Generation
Simple functions to generate answers using IBM WatsonX AI
"""

import os
from dotenv import load_dotenv
from ibm_watsonx_ai.foundation_models import ModelInference
from ibm_watsonx_ai.metanames import GenTextParamsMetaNames as GenParams
from typing import List, Dict, Any

# Load environment variables
load_dotenv()


def get_watsonx_model(streaming=False):
    """
    Initialize and return WatsonX AI model
    
    Args:
        streaming: If True, configure for streaming mode
    
    Returns:
        ModelInference object
    """
    from ibm_watsonx_ai import Credentials
    
    api_key = os.getenv("WX_AI_API_KEY")
    project_id = os.getenv("WX_AI_PROJECT_ID")
    url = os.getenv("WX_AI_ENDPOINT")
    model_id = os.getenv("WX_AI_MODEL_ID")
    
    # Create credentials object
    credentials = Credentials(
        api_key=api_key,
        url=url
    )
    
    # Initialize model with credentials
    model = ModelInference(
        model_id=model_id,
        credentials=credentials,
        project_id=project_id,
        params={
            GenParams.MAX_NEW_TOKENS: 4000,
            GenParams.DECODING_METHOD: "greedy"
        }
    )
    
    return model


def create_prompt(query: str, retrieved_docs: List[Dict[str, Any]]) -> str:
    """
    Create prompt for LLM with retrieved context
    
    Args:
        query: User's question
        retrieved_docs: List of retrieved documents from Elasticsearch
        
    Returns:
        Formatted prompt string
    """
    # Format context from retrieved documents
    context_parts = []
    for i, doc in enumerate(retrieved_docs, 1):
        context_parts.append(
            f"Document {i}: {doc['document_name']} (Page {doc['page_number']})\n"
            f"{doc['content']}\n"
        )
    
    context_text = "\n".join(context_parts)
    
    # Create prompt
    prompt = f"""You are an AI assistant for TATA Agratas Gigafactory workers. Answer questions based ONLY on the provided context documents.

INSTRUCTIONS:
1. Answer based ONLY on the provided context
2. Be specific and actionable - workers need clear guidance
3. If information is not in the context, say "I don't have information about this in the available documents"
4. For safety questions: Be extra clear and emphasize safety protocols
5. For procedures: List steps clearly and in order
6. For troubleshooting: Provide systematic diagnostic steps
7. DO NOT mention document names or page numbers in your answer - just provide the information
8. Use simple language - avoid unnecessary jargon
9. For prohibitions or "can I" questions: Start with YES or NO clearly

CONTEXT DOCUMENTS:
{context_text}

WORKER'S QUESTION: {query}

ANSWER (be crisp, clear, and actionable - DO NOT include source citations in the answer):"""
    
    return prompt


def generate_answer(query: str, retrieved_docs: List[Dict[str, Any]], model=None, max_retries: int = 3) -> str:
    """
    Generate answer using WatsonX AI with retry logic for empty responses
    
    Args:
        query: User's question
        retrieved_docs: List of retrieved documents from Elasticsearch
        model: WatsonX model instance (optional, creates new if None)
        max_retries: Number of retries if answer is empty (default: 1)
        
    Returns:
        Generated answer string
    """
    if model is None:
        model = get_watsonx_model()
    prompt = create_prompt(query, retrieved_docs)
    
    answer = ""
    attempt = 0
    
    while attempt <= max_retries:
        try:
            response = model.generate_text(prompt=prompt)
            
            # Handle different response types
            if isinstance(response, str):
                answer = response.strip()
            elif isinstance(response, dict):
                answer = response.get('generated_text', str(response)).strip()
            elif isinstance(response, list) and len(response) > 0:
                answer = str(response[0]).strip()
            else:
                answer = str(response).strip()
            
            # Check if answer is empty and retry
            if answer and len(answer) > 0:
                break  # Success - got a non-empty answer
            else:
                attempt += 1
                if attempt <= max_retries:
                    print(f"Warning: Empty response on attempt {attempt}. Retrying...")
                else:
                    print(f"Warning: Empty response after {max_retries + 1} attempts for query: {query[:50]}...")
                    answer = "Unable to generate answer. Please try rephrasing your question."
                    
        except Exception as e:
            print(f"Error generating answer (attempt {attempt + 1}): {str(e)}")
            import traceback
            traceback.print_exc()
            
            attempt += 1
            if attempt > max_retries:
                answer = f"Error generating answer: {str(e)}"
                break
    
    return answer


def generate_answer_stream(query: str, retrieved_docs: List[Dict[str, Any]], model=None):
    """
    Generate answer using WatsonX AI with streaming support.
    Since WatsonX doesn't support true token-by-token streaming in the Python SDK,
    we simulate it by generating the full response and yielding it word-by-word.
    
    Args:
        query: User's question
        retrieved_docs: List of retrieved documents from Elasticsearch
        model: WatsonX model instance (optional, creates new if None)
        
    Yields:
        Text words as they are "streamed"
    """
    if model is None:
        model = get_watsonx_model()
    
    prompt = create_prompt(query, retrieved_docs)
    
    try:
        # Check if model has generate_text_stream method
        if hasattr(model, 'generate_text_stream'):
            # Try true streaming if available
            for chunk in model.generate_text_stream(prompt=prompt):
                if chunk:
                    yield chunk
        else:
            # Fallback: Generate full text and stream word-by-word
            print("WatsonX streaming not available, simulating word-by-word streaming...")
            response = model.generate_text(prompt=prompt)
            
            # Handle different response types
            if isinstance(response, str):
                answer = response.strip()
            elif isinstance(response, dict):
                answer = response.get('generated_text', str(response)).strip()
            elif isinstance(response, list) and len(response) > 0:
                answer = str(response[0]).strip()
            else:
                answer = str(response).strip()
            
            # Stream word by word with small delay for better UX
            import time
            words = answer.split()
            for i, word in enumerate(words):
                # Add space after word (except last word)
                if i < len(words) - 1:
                    yield word + " "
                else:
                    yield word
                # Small delay to simulate streaming (optional, can be removed)
                time.sleep(0.01)
                
    except Exception as e:
        print(f"Error in streaming generation: {str(e)}")
        import traceback
        traceback.print_exc()
        yield f"Error generating answer: {str(e)}"

# Made with Bob
