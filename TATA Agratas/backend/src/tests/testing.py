"""
RAG Pipeline Testing Script
Runs test questions through the RAG pipeline and generates output
"""

import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any
from datetime import datetime

# Add parent directory to path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.search_es import search_hybrid, get_es_connection
from src.watsonx_generation import generate_answer, get_watsonx_model


def load_test_questions() -> List[Dict[str, Any]]:
    """
    Load test questions from both JSON files
    
    Returns:
        List of test questions with category and question fields
    """
    questions = []
    
    # Load rag_tests.json
    try:
        with open('tests/rag_tests.json', 'r') as f:
            rag_data = json.load(f)
            for item in rag_data.get('test_questions', []):
                questions.append({
                    'id': item.get('id'),
                    'category': item.get('category', 'Unknown'),
                    'question': item.get('question', ''),
                    'original_answer': item.get('answer', '')
                })
    except Exception as e:
        print(f"Error loading rag_tests.json: {str(e)}")
    
    # Load industry_tests.json
    try:
        with open('tests/industry_tests.json', 'r') as f:
            industry_data = json.load(f)
            for item in industry_data.get('industry_test_questions', []):
                questions.append({
                    'id': item.get('id'),
                    'category': item.get('category', 'Unknown'),
                    'question': item.get('question', ''),
                    'original_answer': item.get('answer', '')
                })
    except Exception as e:
        print(f"Error loading industry_tests.json: {str(e)}")
    
    return questions


def process_single_question(question_data: Dict[str, Any], es_client, watsonx_model) -> Dict[str, Any]:
    """
    Process a single question through the RAG pipeline
    
    Args:
        question_data: Dictionary with id, category, question, and original_answer
        es_client: Elasticsearch client
        watsonx_model: WatsonX model instance
        
    Returns:
        Dictionary with id, category, question, original_answer, llm_answer, context, and processing_time
    """
    start_time = datetime.now()
    
    try:
        question_id = question_data.get('id')
        question = question_data['question']
        category = question_data['category']
        original_answer = question_data.get('original_answer', '')
        
        # Step 1: Search for relevant documents
        retrieved_docs = search_hybrid(question, top_k=3, es_client=es_client)
        
        if not retrieved_docs:
            processing_time = (datetime.now() - start_time).total_seconds()
            return {
                'id': question_id,
                'category': category,
                'question': question,
                'original_answer': original_answer,
                'llm_answer': 'No relevant information found in the knowledge base.',
                'context': '',
                'processing_time_seconds': round(processing_time, 2)
            }
        
        # Step 2: Generate answer
        llm_answer = generate_answer(question, retrieved_docs, model=watsonx_model)
        
        # Step 3: Format context - join content with newlines
        context_paragraphs = [doc['content'] for doc in retrieved_docs]
        context = '\n'.join(context_paragraphs)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'id': question_id,
            'category': category,
            'question': question,
            'original_answer': original_answer,
            'llm_answer': llm_answer,
            'context': context,
            'processing_time_seconds': round(processing_time, 2)
        }
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        print(f"Error processing question '{question_data.get('question', 'Unknown')}': {str(e)}")
        return {
            'id': question_data.get('id'),
            'category': question_data.get('category', 'Unknown'),
            'question': question_data.get('question', ''),
            'original_answer': question_data.get('original_answer', ''),
            'llm_answer': f'Error: {str(e)}',
            'context': '',
            'processing_time_seconds': round(processing_time, 2)
        }


def run_tests_parallel(questions: List[Dict[str, Any]], max_workers: int = 5, output_file: str = 'tests/output.json') -> List[Dict[str, Any]]:
    """
    Run all test questions in parallel and update output file incrementally
    
    Args:
        questions: List of question dictionaries
        max_workers: Maximum number of parallel workers
        output_file: Path to output JSON file
        
    Returns:
        List of results
    """
    print(f"Initializing connections...")
    
    # Initialize connections once
    es_client = get_es_connection()
    watsonx_model = get_watsonx_model()
    
    print(f"✓ Connections initialized")
    print(f"Processing {len(questions)} questions with {max_workers} workers...\n")
    
    results = []
    completed = 0
    
    # Initialize output file
    save_results_incremental(results, len(questions), output_file)
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_question = {
            executor.submit(process_single_question, q, es_client, watsonx_model): q
            for q in questions
        }
        
        # Process results as they complete
        for future in as_completed(future_to_question):
            completed += 1
            try:
                result = future.result()
                results.append(result)
                print(f"[{completed}/{len(questions)}] Completed: {result['question'][:60]}... ({result['processing_time_seconds']}s)")
                
                # Update output file incrementally
                save_results_incremental(results, len(questions), output_file)
                
            except Exception as e:
                question = future_to_question[future]
                print(f"[{completed}/{len(questions)}] Failed: {question.get('question', 'Unknown')[:60]}... - {str(e)}")
                error_result = {
                    'id': question.get('id'),
                    'category': question.get('category', 'Unknown'),
                    'question': question.get('question', ''),
                    'original_answer': question.get('original_answer', ''),
                    'llm_answer': f'Error: {str(e)}',
                    'context': '',
                    'processing_time_seconds': 0.0
                }
                results.append(error_result)
                
                # Update output file incrementally
                save_results_incremental(results, len(questions), output_file)
    
    return results


def save_results_incremental(results: List[Dict[str, Any]], total_questions: int, output_file: str = 'tests/output.json'):
    """
    Save results to JSON file incrementally (updates after each completion)
    
    Args:
        results: List of result dictionaries
        total_questions: Total number of questions being processed
        output_file: Output file path
    """
    # Calculate average processing time
    processing_times = [r.get('processing_time_seconds', 0) for r in results if r.get('processing_time_seconds', 0) > 0]
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    output_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'total_questions': total_questions,
        'completed_questions': len(results),
        'average_processing_time_seconds': round(avg_processing_time, 2),
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)


def save_results(results: List[Dict[str, Any]], output_file: str = 'tests/output.json'):
    """
    Save final results to JSON file
    
    Args:
        results: List of result dictionaries
        output_file: Output file path
    """
    # Calculate average processing time
    processing_times = [r.get('processing_time_seconds', 0) for r in results if r.get('processing_time_seconds', 0) > 0]
    avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
    
    output_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'total_questions': len(results),
        'completed_questions': len(results),
        'average_processing_time_seconds': round(avg_processing_time, 2),
        'results': results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Results saved to {output_file}")


def main():
    """Main execution function"""
    print("="*80)
    print("RAG Pipeline Testing")
    print("="*80)
    print()
    
    # Load test questions
    print("Loading test questions...")
    questions = load_test_questions()
    print(f"✓ Loaded {len(questions)} questions")
    print()
    
    if not questions:
        print("No questions found. Exiting.")
        return
    
    # Run tests in parallel
    start_time = datetime.now()
    results = run_tests_parallel(questions, max_workers=5)
    end_time = datetime.now()
    
    # Save results
    save_results(results)
    
    # Print summary
    print()
    print("="*80)
    print("Summary")
    print("="*80)
    print(f"Total questions: {len(results)}")
    print(f"Successful: {sum(1 for r in results if not r['llm_answer'].startswith('Error'))}")
    print(f"Failed: {sum(1 for r in results if r['llm_answer'].startswith('Error'))}")
    print(f"Total time: {(end_time - start_time).total_seconds():.2f} seconds")
    print(f"Average time per question: {(end_time - start_time).total_seconds() / len(results):.2f} seconds")
    print("="*80)


if __name__ == "__main__":
    main()

# Made with Bob
