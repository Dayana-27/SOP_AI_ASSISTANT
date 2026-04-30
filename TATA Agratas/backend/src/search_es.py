"""
Elasticsearch Search Functions
Simple functions to search documents from Elasticsearch
"""

import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()


def get_es_connection():
    """
    Create and return Elasticsearch connection
    
    Returns:
        Elasticsearch client object
    """
    username = os.getenv("WX_DISCOVERY_USERNAME")
    password = os.getenv("WX_DISCOVERY_PASSWORD")
    endpoint = os.getenv("WX_DISCOVERY_ENDPOINT")
    port = os.getenv("WX_DISCOVERY_PORT")
    
    elasticsearch_url = f"{endpoint}:{port}"
    
    es = Elasticsearch(
        [elasticsearch_url],
        basic_auth=(username, password),
        verify_certs=False,
        ssl_show_warn=False,
        request_timeout=30,
        max_retries=3,
        retry_on_timeout=True
    )
    
    return es


def search_semantic(query: str, top_k: int = 3, index_name: str = "agratas", es_client=None) -> List[Dict[str, Any]]:
    """
    Search using ELSER semantic search
    
    Args:
        query: Search query
        top_k: Number of results to return
        index_name: Elasticsearch index name
        es_client: Elasticsearch client (optional, creates new if None)
        
    Returns:
        List of documents with content, metadata, and scores
    """
    es = es_client if es_client else get_es_connection()
    
    search_query = {
        "query": {
            "text_expansion": {
                "ml.inference.content_expanded.predicted_value": {
                    "model_id": ".elser_model_2",
                    "model_text": query
                }
            }
        },
        "size": top_k,
        "_source": ["content", "document_name", "page_number"]
    }
    
    response = es.search(index=index_name, body=search_query)
    
    results = []
    for hit in response['hits']['hits']:
        results.append({
            'content': hit['_source']['content'],
            'document_name': hit['_source']['document_name'],
            'page_number': hit['_source']['page_number'],
            'score': hit['_score']
        })
    
    return results


def search_keyword(query: str, top_k: int = 3, index_name: str = "agratas", es_client=None) -> List[Dict[str, Any]]:
    """
    Search using BM25 keyword search
    
    Args:
        query: Search query
        top_k: Number of results to return
        index_name: Elasticsearch index name
        es_client: Elasticsearch client (optional, creates new if None)
        
    Returns:
        List of documents with content, metadata, and scores
    """
    es = es_client if es_client else get_es_connection()
    
    search_query = {
        "query": {
            "match": {
                "content": query
            }
        },
        "size": top_k,
        "_source": ["content", "document_name", "page_number"]
    }
    
    response = es.search(index=index_name, body=search_query)
    
    results = []
    for hit in response['hits']['hits']:
        results.append({
            'content': hit['_source']['content'],
            'document_name': hit['_source']['document_name'],
            'page_number': hit['_source']['page_number'],
            'score': hit['_score']
        })
    
    return results


def search_hybrid(query: str, top_k: int = 3, index_name: str = "agratas", es_client=None) -> List[Dict[str, Any]]:
    """
    Hybrid search: Run both semantic (ELSER) and keyword (BM25) search in parallel, then rerank results
    
    Args:
        query: Search query
        top_k: Number of results to return after reranking
        index_name: Elasticsearch index name
        es_client: Elasticsearch client (optional, creates new if None)
        
    Returns:
        List of reranked documents with content, metadata, and scores
    """
    # Get more results from each method for better reranking
    fetch_k = top_k * 2
    
    # Run both searches in parallel using ThreadPoolExecutor
    semantic_results = []
    keyword_results = []
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both search tasks with shared ES client
        future_semantic = executor.submit(search_semantic, query, fetch_k, index_name, es_client)
        future_keyword = executor.submit(search_keyword, query, fetch_k, index_name, es_client)
        
        # Get results as they complete
        for future in as_completed([future_semantic, future_keyword]):
            try:
                result = future.result()
                if future == future_semantic:
                    semantic_results = result
                else:
                    keyword_results = result
            except Exception as e:
                print(f"Error in parallel search: {str(e)}")
                # Continue with empty results for failed search
                if future == future_semantic:
                    semantic_results = []
                else:
                    keyword_results = []
    
    # Combine and deduplicate results
    combined = {}
    
    # Add semantic results with normalized scores
    max_semantic_score = max([r['score'] for r in semantic_results]) if semantic_results else 1.0
    for result in semantic_results:
        key = f"{result['document_name']}_{result['page_number']}"
        normalized_score = result['score'] / max_semantic_score
        combined[key] = {
            'content': result['content'],
            'document_name': result['document_name'],
            'page_number': result['page_number'],
            'semantic_score': normalized_score,
            'keyword_score': 0.0
        }
    
    # Add keyword results with normalized scores
    max_keyword_score = max([r['score'] for r in keyword_results]) if keyword_results else 1.0
    for result in keyword_results:
        key = f"{result['document_name']}_{result['page_number']}"
        normalized_score = result['score'] / max_keyword_score
        
        if key in combined:
            combined[key]['keyword_score'] = normalized_score
        else:
            combined[key] = {
                'content': result['content'],
                'document_name': result['document_name'],
                'page_number': result['page_number'],
                'semantic_score': 0.0,
                'keyword_score': normalized_score
            }
    
    # Calculate hybrid score (weighted combination)
    # Give more weight to semantic search (0.7) vs keyword (0.3)
    for key in combined:
        combined[key]['score'] = (
            0.7 * combined[key]['semantic_score'] +
            0.3 * combined[key]['keyword_score']
        )
    
    # Sort by hybrid score and return top_k
    reranked = sorted(combined.values(), key=lambda x: x['score'], reverse=True)[:top_k]
    
    # Clean up the response (remove intermediate scores)
    final_results = []
    for result in reranked:
        final_results.append({
            'content': result['content'],
            'document_name': result['document_name'],
            'page_number': result['page_number'],
            'score': result['score']
        })
    
    return final_results

# Made with Bob
