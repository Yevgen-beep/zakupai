#!/usr/bin/env python3
"""
OCR Loader for ZakupAI ETL Service
Processes PDF/ZIP files, extracts text content, and stores in PostgreSQL + ChromaDB
"""

import argparse
import asyncio
import logging
import os
import re
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional, Tuple, List, Dict, Any
import io

import psycopg2
import psycopg2.extras
from psycopg2 import sql
import fitz  # PyMuPDF for PDF text extraction
import pytesseract  # OCR for scanned PDFs
from PIL import Image
import chromadb
from chromadb.config import Settings
import sentence_transformers
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


class OCRLoader:
    """OCR Loader for processing PDF/ZIP files and extracting text content"""
    
    def __init__(self, database_url: str, chroma_url: Optional[str] = None):
        self.database_url = database_url
        self.chroma_url = chroma_url or "http://localhost:8000"
        self.chroma_client = None
        self.collection = None
        self.sentence_model = None
        
        # Initialize sentence transformer for embeddings
        if chroma_url:
            try:
                self.sentence_model = sentence_transformers.SentenceTransformer(
                    'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
                )
                logger.info("Initialized sentence transformer model")
            except Exception as e:
                logger.warning(f"Failed to initialize sentence transformer: {e}")
                
    async def __aenter__(self):
        """Async context manager entry"""
        await self.connect_chroma()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.chroma_client:
            # ChromaDB client doesn't need explicit closing
            pass
            
    async def connect_chroma(self):
        """Initialize ChromaDB connection"""
        if not self.chroma_url:
            return
            
        try:
            # Initialize ChromaDB client
            self.chroma_client = chromadb.HttpClient(
                host=self.chroma_url.split("://")[1].split(":")[0],
                port=int(self.chroma_url.split(":")[-1]),
                settings=Settings(allow_reset=True)
            )
            
            # Get or create attachments collection
            self.collection = self.chroma_client.get_or_create_collection(
                name="attachments",
                metadata={"description": "OCR'd content from lot attachments"}
            )
            logger.info(f"Connected to ChromaDB at {self.chroma_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
            self.chroma_client = None
            
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
        
    def extract_text_from_pdf(self, pdf_path: Path) -> str:
        """Extract text from PDF using PyMuPDF with OCR fallback"""
        try:
            # Check if this is actually a mock PDF (text file)
            with open(pdf_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if first_line == "MOCK PDF FILE FOR TESTING":
                    logger.info(f"Processing mock PDF file: {pdf_path.name}")
                    f.seek(0)
                    content = f.read()
                    # Remove mock header
                    lines = content.split('\n')
                    if len(lines) > 2 and lines[0] == "MOCK PDF FILE FOR TESTING":
                        return '\n'.join(lines[2:])  # Skip header and separator
                    return content
        except:
            pass  # Continue with normal PDF processing
            
        try:
            doc = fitz.open(str(pdf_path))
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # First try to extract text directly
                text = page.get_text()
                
                if text.strip():
                    text_content.append(text)
                else:
                    # If no text found, use OCR on page image
                    logger.info(f"Using OCR for page {page_num + 1} of {pdf_path.name}")
                    try:
                        # Convert page to image
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better OCR
                        img_data = pix.tobytes("png")
                        img = Image.open(io.BytesIO(img_data))
                        
                        # Use Tesseract OCR with Russian language
                        ocr_text = pytesseract.image_to_string(
                            img, 
                            lang='rus+eng',  # Russian + English
                            config='--psm 6'  # Assume uniform block of text
                        )
                        
                        if ocr_text.strip():
                            text_content.append(ocr_text)
                            
                    except Exception as ocr_error:
                        logger.warning(f"OCR failed for page {page_num + 1}: {ocr_error}")
                        
            doc.close()
            return '\n\n'.join(text_content)
            
        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {e}")
            return ""
            
    def extract_from_zip(self, zip_path: Path) -> List[Tuple[str, str]]:
        """Extract text from all PDF files in ZIP archive"""
        extracted_files = []
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.filelist:
                    if file_info.filename.lower().endswith('.pdf'):
                        try:
                            # Extract PDF to memory
                            pdf_data = zip_ref.read(file_info.filename)
                            
                            # Create temporary PDF document
                            doc = fitz.open(stream=pdf_data, filetype="pdf")
                            text_content = []
                            
                            for page_num in range(len(doc)):
                                page = doc.load_page(page_num)
                                text = page.get_text()
                                
                                if text.strip():
                                    text_content.append(text)
                                else:
                                    # OCR fallback for scanned pages
                                    try:
                                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                                        img_data = pix.tobytes("png")
                                        img = Image.open(io.BytesIO(img_data))
                                        
                                        ocr_text = pytesseract.image_to_string(
                                            img, lang='rus+eng', config='--psm 6'
                                        )
                                        if ocr_text.strip():
                                            text_content.append(ocr_text)
                                            
                                    except Exception:
                                        continue
                                        
                            doc.close()
                            
                            if text_content:
                                extracted_files.append((
                                    file_info.filename, 
                                    '\n\n'.join(text_content)
                                ))
                                
                        except Exception as e:
                            logger.warning(f"Failed to process {file_info.filename} in ZIP: {e}")
                            
        except Exception as e:
            logger.error(f"Failed to process ZIP file {zip_path}: {e}")
            
        return extracted_files
        
    def store_in_postgres(self, lot_id: int, filename: str, file_type: str, content: str):
        """Store extracted content in PostgreSQL"""
        try:
            with psycopg2.connect(self.database_url) as conn:
                with conn.cursor() as cur:
                    # Insert with ON CONFLICT DO NOTHING for lot_id + filename uniqueness
                    query = sql.SQL("""
                        INSERT INTO attachments (lot_id, file_name, file_type, content)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (lot_id, file_name) DO NOTHING
                        RETURNING id
                    """)
                    
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
            
    async def store_in_chroma(self, attachment_id: int, lot_id: int, filename: str, content: str):
        """Store content in ChromaDB for semantic search"""
        if not self.collection or not self.sentence_model:
            return
            
        try:
            # Create embedding
            embedding = self.sentence_model.encode(content[:1000])  # Limit to first 1000 chars
            
            # Store in ChromaDB
            self.collection.add(
                documents=[content],
                embeddings=[embedding.tolist()],
                metadatas=[{
                    "attachment_id": attachment_id,
                    "lot_id": lot_id,
                    "filename": filename,
                    "content_length": len(content)
                }],
                ids=[f"attachment_{attachment_id}"]
            )
            
            logger.info(f"Stored in ChromaDB: attachment_id {attachment_id}")
            
        except Exception as e:
            logger.error(f"Failed to store in ChromaDB: {e}")
            
    def process_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Process a single file and extract content"""
        try:
            lot_id = self.extract_lot_id(file_path.name)
            if not lot_id:
                return None
                
            logger.info(f"Processing {file_path.name} for lot {lot_id}")
            
            if file_path.suffix.lower() == '.pdf':
                content = self.extract_text_from_pdf(file_path)
                file_type = 'pdf'
                
                if content.strip():
                    return {
                        'lot_id': lot_id,
                        'filename': file_path.name,
                        'file_type': file_type,
                        'content': content
                    }
                    
            elif file_path.suffix.lower() == '.zip':
                extracted_files = self.extract_from_zip(file_path)
                results = []
                
                for pdf_filename, content in extracted_files:
                    if content.strip():
                        results.append({
                            'lot_id': lot_id,
                            'filename': f"{file_path.stem}_{pdf_filename}",
                            'file_type': 'pdf',
                            'content': content
                        })
                        
                return results if results else None
                
        except Exception as e:
            logger.error(f"Failed to process {file_path}: {e}")
            
        return None
        
    async def process_directory(self, path: Path, enable_embedding: bool = False) -> Dict[str, int]:
        """Process all PDF/ZIP files in directory with parallel processing"""
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Directory does not exist: {path}")
            
        # Find all PDF and ZIP files
        files = list(path.glob("*.pdf")) + list(path.glob("*.zip"))
        
        if not files:
            logger.warning(f"No PDF/ZIP files found in {path}")
            return {"processed": 0, "stored": 0, "skipped": 0}
            
        logger.info(f"Found {len(files)} files to process")
        
        stats = {"processed": 0, "stored": 0, "skipped": 0}
        
        # Process files in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as executor:
            # Submit all file processing tasks
            future_to_file = {
                executor.submit(self.process_file, file_path): file_path 
                for file_path in files
            }
            
            # Process completed tasks
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                stats["processed"] += 1
                
                try:
                    result = future.result()
                    
                    if result:
                        # Handle both single results and lists (for ZIP files)
                        results = result if isinstance(result, list) else [result]
                        
                        for item in results:
                            # Store in PostgreSQL
                            attachment_id = self.store_in_postgres(
                                item['lot_id'],
                                item['filename'],
                                item['file_type'],
                                item['content']
                            )
                            
                            if attachment_id:
                                stats["stored"] += 1
                                
                                # Store in ChromaDB if enabled
                                if enable_embedding:
                                    await self.store_in_chroma(
                                        attachment_id,
                                        item['lot_id'],
                                        item['filename'],
                                        item['content']
                                    )
                            else:
                                stats["skipped"] += 1
                    else:
                        stats["skipped"] += 1
                        
                    # Progress logging
                    if stats["processed"] % 10 == 0:
                        logger.info(
                            f"Progress: {stats['processed']}/{len(files)} files processed, "
                            f"{stats['stored']} stored, {stats['skipped']} skipped"
                        )
                        
                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    stats["skipped"] += 1
                    
        logger.info(
            f"Processing complete: {stats['processed']} files processed, "
            f"{stats['stored']} stored, {stats['skipped']} skipped"
        )
        
        return stats


async def main():
    """Main function with command line argument parsing"""
    parser = argparse.ArgumentParser(description="OCR Loader for ZakupAI ETL Service")
    parser.add_argument("--path", required=True, help="Path to directory containing PDF/ZIP files")
    parser.add_argument("--db", required=True, help="PostgreSQL database URL")
    parser.add_argument("--embed", help="ChromaDB URL for embeddings (optional)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        
    try:
        path = Path(args.path)
        
        # Initialize and run OCR Loader
        async with OCRLoader(args.db, args.embed) as loader:
            stats = await loader.process_directory(path, enable_embedding=bool(args.embed))
            
        logger.info("OCR Loader completed successfully")
        return stats
        
    except Exception as e:
        logger.error(f"OCR Loader failed: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    try:
        stats = asyncio.run(main())
        print(f"\nResults: {stats}")
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("OCR Loader interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"OCR Loader failed: {e}")
        sys.exit(1)