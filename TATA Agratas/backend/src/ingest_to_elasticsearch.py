"""
Elasticsearch RAG Pipeline - Document Ingestion with ELSER

This script:
1. Connects to Elasticsearch using credentials from .env
2. Creates vector embeddings using .elser_model_2
3. Creates an index "agratas"
4. Ingests processed text documents
"""

import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
import json
import re


class ElasticsearchRAGPipeline:
    """RAG Pipeline for ingesting documents into Elasticsearch with ELSER embeddings"""
    
    def __init__(self, text_dir: str = "text"):
        """
        Initialize the pipeline
        
        Args:
            text_dir: Directory containing processed text files
        """
        self.text_dir = Path(text_dir)
        
        # Load environment variables
        load_dotenv()
        
        # Get Elasticsearch credentials
        self.username = os.getenv("WX_DISCOVERY_USERNAME")
        self.password = os.getenv("WX_DISCOVERY_PASSWORD")
        self.endpoint = os.getenv("WX_DISCOVERY_ENDPOINT")
        self.port = os.getenv("WX_DISCOVERY_PORT")
        
        # Construct Elasticsearch URL
        self.elasticsearch_url = f"{self.endpoint}:{self.port}"
        
        # Initialize Elasticsearch connection
        self.es_connection = None
        self.index_name = "agratas"
        self.elser_model = ".elser_model_2"
    
    def connect_to_elasticsearch(self) -> bool:
        """
        Establish connection to Elasticsearch
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            print("Connecting to Elasticsearch...")
            print(f"URL: {self.elasticsearch_url}")
            print(f"Username: {self.username}")
            
            self.es_connection = Elasticsearch(
                self.elasticsearch_url,
                verify_certs=False,
                basic_auth=(self.username, self.password),
                retry_on_timeout=True,
                max_retries=10,
                request_timeout=3600,
                headers={"Accept": "application/vnd.elasticsearch+json; compatible-with=8"}
            )
            
            # Test connection
            info = self.es_connection.info()
            print("✓ Successfully connected to Elasticsearch")
            print(f"Cluster: {info['cluster_name']}")
            print(f"Version: {info['version']['number']}")
            return True
            
        except Exception as e:
            print(f"✗ Failed to connect to Elasticsearch: {str(e)}")
            return False
    
    def create_index_with_elser(self) -> bool:
        """
        Create Elasticsearch index with ELSER model configuration
        
        Returns:
            True if index created successfully, False otherwise
        """
        try:
            # Check if index already exists
            if self.es_connection.indices.exists(index=self.index_name):
                print(f"Index '{self.index_name}' already exists")
                response = input("Do you want to delete and recreate it? (yes/no): ")
                if response.lower() == 'yes':
                    self.es_connection.indices.delete(index=self.index_name)
                    print(f"✓ Deleted existing index '{self.index_name}'")
                else:
                    print("Using existing index")
                    return True
            
            # Create index with ELSER configuration
            index_config = {
                "mappings": {
                    "properties": {
                        "document_name": {"type": "keyword"},
                        "page_number": {"type": "integer"},
                        "content": {"type": "text"},
                        "ml.tokens": {
                            "type": "rank_features"
                        },
                        "timestamp": {"type": "date"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0
                }
            }
            
            self.es_connection.indices.create(
                index=self.index_name,
                body=index_config
            )
            
            print(f"✓ Created index '{self.index_name}' with ELSER configuration")
            return True
            
        except Exception as e:
            print(f"✗ Failed to create index: {str(e)}")
            return False
    
    def create_ingest_pipeline(self) -> bool:
        """
        Create ingest pipeline with ELSER model
        
        Returns:
            True if pipeline created successfully, False otherwise
        """
        try:
            pipeline_id = "elser-ingest-pipeline"
            
            # Check if pipeline exists
            if self.es_connection.ingest.get_pipeline(id=pipeline_id, ignore=[404]):
                print(f"Pipeline '{pipeline_id}' already exists")
                return True
            
            # Create pipeline with ELSER inference
            pipeline_config = {
                "description": "Ingest pipeline for ELSER embeddings",
                "processors": [
                    {
                        "inference": {
                            "model_id": self.elser_model,
                            "input_output": {
                                "input_field": "content",
                                "output_field": "ml.tokens"
                            }
                        }
                    }
                ]
            }
            
            self.es_connection.ingest.put_pipeline(
                id=pipeline_id,
                body=pipeline_config
            )
            
            print(f"✓ Created ingest pipeline '{pipeline_id}'")
            return True
            
        except Exception as e:
            print(f"✗ Failed to create ingest pipeline: {str(e)}")
            print("Note: Make sure ELSER model is deployed in your Elasticsearch cluster")
            return False
    
    def parse_document(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Parse a text document into chunks by page
        
        Args:
            file_path: Path to the text file
            
        Returns:
            List of document chunks
        """
        chunks = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Split by PAGE markers
            pages = re.split(r'PAGE \d+', content)
            
            # Extract document name and total pages from header
            doc_name = file_path.stem
            
            page_num = 1
            for page_content in pages:
                page_content = page_content.strip()
                
                if not page_content:
                    continue
                
                # Skip the header section
                if page_content.startswith("DOCUMENT:"):
                    continue
                
                chunk = {
                    "document_name": doc_name,
                    "page_number": page_num,
                    "content": page_content,
                    "timestamp": "2026-04-01T00:00:00Z"
                }
                
                chunks.append(chunk)
                page_num += 1
        
        except Exception as e:
            print(f"Error parsing {file_path.name}: {str(e)}")
        
        return chunks
    
    def ingest_documents(self) -> bool:
        """
        Ingest all text documents into Elasticsearch
        
        Returns:
            True if ingestion successful, False otherwise
        """
        try:
            text_files = list(self.text_dir.glob("*.txt"))
            
            if not text_files:
                print(f"No text files found in {self.text_dir}")
                return False
            
            print(f"\nFound {len(text_files)} document(s) to ingest")
            print("=" * 80)
            
            total_chunks = 0
            pipeline_id = "elser-ingest-pipeline"
            
            for file_path in text_files:
                print(f"\nProcessing: {file_path.name}")
                
                # Parse document into chunks
                chunks = self.parse_document(file_path)
                
                if not chunks:
                    print(f"  No chunks extracted from {file_path.name}")
                    continue
                
                print(f"  Extracted {len(chunks)} page(s)")
                
                # Ingest chunks with ELSER pipeline
                for i, chunk in enumerate(chunks, 1):
                    try:
                        self.es_connection.index(
                            index=self.index_name,
                            document=chunk,
                            pipeline=pipeline_id
                        )
                        total_chunks += 1
                        
                        if i % 5 == 0:
                            print(f"  Ingested {i}/{len(chunks)} pages...")
                    
                    except Exception as e:
                        print(f"  ✗ Error ingesting page {i}: {str(e)}")
                
                print(f"  ✓ Completed {file_path.name}")
            
            print("\n" + "=" * 80)
            print(f"✓ Ingestion complete!")
            print(f"Total chunks ingested: {total_chunks}")
            
            # Refresh index
            self.es_connection.indices.refresh(index=self.index_name)
            
            return True
            
        except Exception as e:
            print(f"✗ Failed to ingest documents: {str(e)}")
            return False
    
    def verify_ingestion(self) -> None:
        """Verify documents were ingested successfully"""
        try:
            # Get document count
            count = self.es_connection.count(index=self.index_name)
            print(f"\nIndex '{self.index_name}' contains {count['count']} documents")
            
            # Get a sample document
            result = self.es_connection.search(
                index=self.index_name,
                body={
                    "size": 1,
                    "query": {"match_all": {}}
                }
            )
            
            if result['hits']['hits']:
                print("\nSample document:")
                doc = result['hits']['hits'][0]['_source']
                print(f"  Document: {doc.get('document_name', 'N/A')}")
                print(f"  Page: {doc.get('page_number', 'N/A')}")
                print(f"  Content preview: {doc.get('content', '')[:100]}...")
                print(f"  Has embeddings: {'ml.tokens' in doc}")
        
        except Exception as e:
            print(f"Error verifying ingestion: {str(e)}")
    
    def run_pipeline(self) -> bool:
        """
        Run the complete RAG pipeline
        
        Returns:
            True if pipeline completed successfully, False otherwise
        """
        print("=" * 80)
        print("Elasticsearch RAG Pipeline - Document Ingestion")
        print("=" * 80)
        
        # Step 1: Connect to Elasticsearch
        if not self.connect_to_elasticsearch():
            return False
        
        print()
        
        # Step 2: Create ingest pipeline with ELSER
        if not self.create_ingest_pipeline():
            return False
        
        print()
        
        # Step 3: Create index
        if not self.create_index_with_elser():
            return False
        
        print()
        
        # Step 4: Ingest documents
        if not self.ingest_documents():
            return False
        
        # Step 5: Verify ingestion
        self.verify_ingestion()
        
        print("\n" + "=" * 80)
        print("Pipeline completed successfully!")
        print("=" * 80)
        
        return True


def main():
    """Main execution function"""
    pipeline = ElasticsearchRAGPipeline(text_dir="text")
    pipeline.run_pipeline()


if __name__ == "__main__":
    main()

# Made with Bob
