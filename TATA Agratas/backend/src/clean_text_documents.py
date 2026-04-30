"""
Text Document Cleaner

This script processes converted text documents to:
- Remove excessive whitespace
- Clean up poorly formatted tables
- Remove redundant empty lines
- Preserve document structure and relevant information
"""

import re
from pathlib import Path
from typing import List


class TextDocumentCleaner:
    """Clean and format text documents"""
    
    def __init__(self, input_dir: str = "text", output_dir: str = "text"):
        """
        Initialize the cleaner
        
        Args:
            input_dir: Directory containing text files to clean
            output_dir: Directory to save cleaned text files
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def clean_table(self, table_text: str) -> str:
        """
        Clean up table and format as proper Markdown table
        
        Args:
            table_text: Raw table text
            
        Returns:
            Markdown formatted table
        """
        lines = table_text.strip().split('\n')
        
        # Identify content rows (rows with actual text, not just separators)
        content_rows = []
        for line in lines:
            # Skip pure separator lines (only +, -, =, |, and spaces)
            if re.match(r'^[\s\+\-\=\|]+$', line):
                continue
            
            # Check if line has actual content
            if '|' in line:
                # Extract cells
                cells = line.split('|')
                # Check if any cell has non-whitespace content
                has_content = any(cell.strip() for cell in cells)
                if has_content:
                    content_rows.append(line)
        
        if not content_rows:
            return ""
        
        # Parse all rows into cell arrays
        parsed_rows = []
        max_cols = 0
        for row in content_rows:
            cells = [cell.strip() for cell in row.split('|')]
            parsed_rows.append(cells)
            max_cols = max(max_cols, len(cells))
        
        # Identify which columns have any content
        has_content_col = [False] * max_cols
        for row in parsed_rows:
            for i, cell in enumerate(row):
                if cell:
                    has_content_col[i] = True
        
        # Filter out empty columns and rebuild rows
        cleaned_rows = []
        for row in parsed_rows:
            filtered_cells = []
            for i, cell in enumerate(row):
                if i < len(has_content_col) and has_content_col[i]:
                    filtered_cells.append(cell if cell else " ")
            
            if filtered_cells and any(cell.strip() for cell in filtered_cells):
                cleaned_rows.append(filtered_cells)
        
        if not cleaned_rows:
            return ""
        
        # Calculate column widths for proper alignment
        num_cols = len(cleaned_rows[0])
        col_widths = [0] * num_cols
        
        for row in cleaned_rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(cell))
        
        # Build Markdown table
        result = []
        
        # First row (header)
        header_cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(cleaned_rows[0])]
        result.append('| ' + ' | '.join(header_cells) + ' |')
        
        # Separator row
        separator_cells = ['-' * col_widths[i] for i in range(num_cols)]
        result.append('| ' + ' | '.join(separator_cells) + ' |')
        
        # Data rows
        for row in cleaned_rows[1:]:
            # Pad row to match number of columns
            while len(row) < num_cols:
                row.append('')
            data_cells = [cell.ljust(col_widths[i]) for i, cell in enumerate(row)]
            result.append('| ' + ' | '.join(data_cells) + ' |')
        
        return '\n'.join(result)
    
    def clean_document(self, content: str) -> str:
        """
        Clean the entire document
        
        Args:
            content: Raw document content
            
        Returns:
            Cleaned document content
        """
        lines = content.split('\n')
        cleaned_lines = []
        in_table = False
        table_buffer = []
        
        for line in lines:
            # Detect table start
            if '[TABLE' in line:
                in_table = True
                table_buffer = []
                continue
            
            # Collect table lines
            if in_table:
                table_buffer.append(line)
                # Detect table end (empty line after table content)
                if line.strip() == '' and len(table_buffer) > 5:
                    # Process the table
                    table_text = '\n'.join(table_buffer)
                    table_content = self.clean_table(table_text)
                    if table_content:
                        cleaned_lines.append('\n[TABLE]')
                        cleaned_lines.append(table_content)
                        cleaned_lines.append('')
                    in_table = False
                    table_buffer = []
                continue
            
            # Clean regular lines
            cleaned_line = line.strip()
            
            # Skip lines with only separators
            if re.match(r'^[\-\=]+$', cleaned_line):
                continue
            
            # Keep non-empty lines
            if cleaned_line:
                cleaned_lines.append(cleaned_line)
            # Keep single empty line for paragraph separation
            elif cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
        
        # Join lines and clean up multiple consecutive empty lines
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        # Clean up extra spaces
        result = re.sub(r' +', ' ', result)
        
        return result.strip() + '\n'
    
    def process_file(self, file_path: Path) -> None:
        """
        Process a single text file
        
        Args:
            file_path: Path to the text file
        """
        print(f"Processing: {file_path.name}")
        
        try:
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Clean the content
            cleaned_content = self.clean_document(content)
            
            # Save the cleaned file
            output_path = self.output_dir / file_path.name
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(cleaned_content)
            
            print(f"✓ Cleaned and saved: {output_path.name}")
            
        except Exception as e:
            print(f"✗ Error processing {file_path.name}: {str(e)}")
    
    def clean_all_files(self) -> None:
        """Clean all text files in the input directory"""
        text_files = list(self.input_dir.glob("*.txt"))
        
        if not text_files:
            print(f"No text files found in {self.input_dir}")
            return
        
        print(f"Found {len(text_files)} text file(s) to clean")
        print("=" * 80)
        
        for file_path in text_files:
            self.process_file(file_path)
            print()
        
        print("=" * 80)
        print("Cleaning complete!")
        print(f"Output directory: {self.output_dir}")


def main():
    """Main execution function"""
    print("Text Document Cleaner")
    print("=" * 80)
    
    # Initialize cleaner
    cleaner = TextDocumentCleaner(
        input_dir="text",
        output_dir="text"
    )
    
    # Clean all files
    cleaner.clean_all_files()


if __name__ == "__main__":
    main()

# Made with Bob
