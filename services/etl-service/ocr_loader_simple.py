#!/usr/bin/env python3
"""
Simplified OCR Loader for smoke testing
Works without heavy dependencies (PyMuPDF, ChromaDB, etc.)
"""

import argparse
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any
import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("ocr_loader.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class SimpleOCRLoader:
    """Simplified OCR Loader for smoke testing"""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        
    def extract_lot_id(self, filename: str) -> Optional[int]:
        """Extract lot ID from filename (e.g., 37971908.pdf -> 37971908)"""
        try:
            # Match numbers at the beginning of filename
            match = re.match(r'^(\d+)', Path(filename).stem)
            if match:
                return int(match.group(1))
        except (ValueError, AttributeError):
            pass
            
        logger.warning(f"Could not extract lot_id from filename: {filename}")
        return None
        
    def extract_text_from_mock_pdf(self, pdf_path: Path) -> str:
        """Extract text from mock PDF file (actually a text file)"""
        try:
            with open(pdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Remove mock header if present
            lines = content.split('\n')
            if lines and lines[0] == "MOCK PDF FILE FOR TESTING":
                # Skip header and separator line
                if len(lines) > 2:
                    return '\n'.join(lines[2:])
                    
            return content
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
            
    def store_in_postgres(self, lot_id: int, filename: str, file_type: str, content: str) -> Optional[int]:
        """Store extracted content in PostgreSQL"""
        try:
            with psycopg2.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    # Insert with ON CONFLICT DO NOTHING for lot_id + filename uniqueness
                    query = """
                        INSERT INTO attachments (lot_id, file_name, file_type, content)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (lot_id, file_name) DO NOTHING
                        RETURNING id
                    """
                    
                    cur.execute(query, (lot_id, filename, file_type, content))
                    result = cur.fetchone()
                    
                    if result:
                        logger.info(f"Stored content for lot {lot_id}, file {filename}")
                        return result[0]
                    else:
                        logger.info(f"Duplicate skipped: lot {lot_id}, file {filename}")
                        return None
                        
        except Exception as e:
            logger.error(f"Failed to store in PostgreSQL: {e}")
            return None
            
    def process_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Process a single mock PDF file"""
        try:
            lot_id = self.extract_lot_id(file_path.name)
            if not lot_id:
                return None
                
            logger.info(f"Processing {file_path.name} for lot {lot_id}")
            
            content = self.extract_text_from_mock_pdf(file_path)
            
            if content.strip():
                return {
                    'lot_id': lot_id,
                    'filename': file_path.name,
                    'file_type': 'pdf',
                    'content': content
                }
                    
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            
        return None
        
    def process_directory(self, path: Path) -> Dict[str, int]:
        """Process all PDF files in directory"""
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory does not exist: {path}")
            
        # Find all PDF files
        files = list(path.glob("*.pdf"))
        
        if not files:
            logger.warning(f"No PDF files found in {path}")
            return {"processed": 0, "stored": 0, "skipped": 0}
            
        logger.info(f"Found {len(files)} files to process")
        
        stats = {"processed": 0, "stored": 0, "skipped": 0}
        
        for file_path in files:
            stats["processed"] += 1
            
            try:
                result = self.process_file(file_path)
                
                if result:
                    # Store in PostgreSQL
                    attachment_id = self.store_in_postgres(
                        result['lot_id'],
                        result['filename'],
                        result['file_type'],
                        result['content']
                    )
                    
                    if attachment_id:
                        stats["stored"] += 1
                    else:
                        stats["skipped"] += 1
                else:
                    stats["skipped"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                stats["skipped"] += 1
                
        logger.info(
            f"Processing complete: {stats['processed']} files processed, "
            f"{stats['stored']} stored, {stats['skipped']} skipped"
        )
        
        return stats


def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description="Simple OCR Loader for smoke testing")
    parser.add_argument("--path", required=True, help="Path to directory containing PDF files")
    parser.add_argument("--db", required=True, help="PostgreSQL database URL")
    parser.add_argument("--embed", help="Ignored in simple version")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    try:
        path = Path(args.path)
        
        # Initialize and run Simple OCR Loader
        loader = SimpleOCRLoader(args.db)
        stats = loader.process_directory(path)
        
        logger.info("Simple OCR Loader completed successfully")
        print(f"Results: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Simple OCR Loader failed: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    try:
        stats = main()
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Simple OCR Loader interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Simple OCR Loader failed: {e}")
        sys.exit(1)