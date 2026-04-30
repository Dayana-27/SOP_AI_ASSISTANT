"""
PDF to Text Converter with Structure Preservation

This script converts PDF documents to text format while maintaining:
- Page-wise information
- Table structure
- Document hierarchy
- Proper formatting

Dependencies: pdfplumber, tabulate (already in requirements.txt)
"""

import os
import pdfplumber
from pathlib import Path
from tabulate import tabulate
from typing import List, Dict, Any
import json


class PDFToTextConverter:
    """Convert PDF documents to structured text format"""
    
    def __init__(self, input_dir: str = "data", output_dir: str = "documentation"):
        """
        Initialize the converter
        
        Args:
            input_dir: Directory containing PDF files
            output_dir: Directory to save converted text files
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
    def extract_tables_from_page(self, page) -> List[str]:
        """
        Extract tables from a PDF page and format them
        
        Args:
            page: pdfplumber page object
            
        Returns:
            List of formatted table strings
        """
        tables = []
        extracted_tables = page.extract_tables()
        
        if extracted_tables:
            for idx, table in enumerate(extracted_tables, 1):
                if table and len(table) > 0:
                    # Clean up None values and empty strings
                    cleaned_table = []
                    for row in table:
                        cleaned_row = [cell if cell else "" for cell in row]
                        cleaned_table.append(cleaned_row)
                    
                    # Format table using tabulate
                    if len(cleaned_table) > 1:
                        # Use first row as headers if it looks like headers
                        headers = cleaned_table[0]
                        data = cleaned_table[1:]
                        table_str = tabulate(data, headers=headers, tablefmt="grid")
                    else:
                        table_str = tabulate(cleaned_table, tablefmt="grid")
                    
                    tables.append(f"\n[TABLE {idx}]\n{table_str}\n")
        
        return tables
    
    def extract_text_from_page(self, page) -> str:
        """
        Extract text from a PDF page, excluding table areas
        
        Args:
            page: pdfplumber page object
            
        Returns:
            Extracted text string
        """
        # Get the full text
        text = page.extract_text()
        
        if not text:
            return ""
        
        # Clean up the text
        text = text.strip()
        
        return text
    
    def convert_pdf_to_text(self, pdf_path: Path) -> Dict[str, Any] | None:
        """
        Convert a single PDF file to structured text
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Dictionary containing document metadata and content, or None if error
        """
        document = {
            "filename": pdf_path.name,
            "total_pages": 0,
            "pages": []
        }
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                document["total_pages"] = len(pdf.pages)
                
                for page_num, page in enumerate(pdf.pages, 1):
                    page_data = {
                        "page_number": page_num,
                        "content": "",
                        "tables": []
                    }
                    
                    # Extract text
                    text = self.extract_text_from_page(page)
                    
                    # Extract tables
                    tables = self.extract_tables_from_page(page)
                    
                    page_data["content"] = text
                    page_data["tables"] = tables
                    
                    document["pages"].append(page_data)
                    
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {str(e)}")
            return None
        
        return document
    
    def format_document_as_text(self, document: Dict[str, Any]) -> str:
        """
        Format the document dictionary as a readable text file
        
        Args:
            document: Document dictionary from convert_pdf_to_text
            
        Returns:
            Formatted text string
        """
        output = []
        
        # Header
        output.append("=" * 80)
        output.append(f"DOCUMENT: {document['filename']}")
        output.append(f"TOTAL PAGES: {document['total_pages']}")
        output.append("=" * 80)
        output.append("")
        
        # Process each page
        for page in document["pages"]:
            output.append("-" * 80)
            output.append(f"PAGE {page['page_number']}")
            output.append("-" * 80)
            output.append("")
            
            # Add text content
            if page["content"]:
                output.append(page["content"])
                output.append("")
            
            # Add tables
            if page["tables"]:
                for table in page["tables"]:
                    output.append(table)
                    output.append("")
            
            output.append("")
        
        return "\n".join(output)
    
    def save_as_text(self, document: Dict[str, Any], output_path: Path):
        """
        Save the document as a text file
        
        Args:
            document: Document dictionary
            output_path: Path to save the text file
        """
        formatted_text = self.format_document_as_text(document)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(formatted_text)
        
        print(f"✓ Saved: {output_path.name}")
    
    def save_as_json(self, document: Dict[str, Any], output_path: Path):
        """
        Save the document as a JSON file (optional structured format)
        
        Args:
            document: Document dictionary
            output_path: Path to save the JSON file
        """
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(document, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Saved: {output_path.name}")
    
    def convert_all_pdfs(self, save_json: bool = False):
        """
        Convert all PDF files in the input directory
        
        Args:
            save_json: If True, also save JSON format alongside text
        """
        pdf_files = list(self.input_dir.glob("*.pdf"))
        
        if not pdf_files:
            print(f"No PDF files found in {self.input_dir}")
            return
        
        print(f"Found {len(pdf_files)} PDF file(s) to convert")
        print("-" * 80)
        
        for pdf_path in pdf_files:
            print(f"\nProcessing: {pdf_path.name}")
            
            # Convert PDF to structured format
            document = self.convert_pdf_to_text(pdf_path)
            
            if document:
                # Generate output filename
                base_name = pdf_path.stem
                
                # Save as text
                text_output_path = self.output_dir / f"{base_name}.txt"
                self.save_as_text(document, text_output_path)
                
                # Optionally save as JSON
                if save_json:
                    json_output_path = self.output_dir / f"{base_name}.json"
                    self.save_as_json(document, json_output_path)
        
        print("\n" + "=" * 80)
        print("Conversion complete!")
        print(f"Output directory: {self.output_dir}")


def main():
    """Main execution function"""
    print("PDF to Text Converter")
    print("=" * 80)
    
    # Initialize converter
    converter = PDFToTextConverter(
        input_dir="data",
        output_dir="text"
    )
    
    # Convert all PDFs
    # Set save_json=True if you also want JSON format
    converter.convert_all_pdfs(save_json=False)


if __name__ == "__main__":
    main()

# Made with Bob
