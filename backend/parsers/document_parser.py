"""
Phalanx Search - Document Parsers
Extracts text content from various document formats
100% Local processing - No data leaves your system
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime
import hashlib


@dataclass
class ParsedDocument:
    """Represents a parsed document with its content and metadata"""
    filename: str
    filepath: str
    content: str
    file_type: str
    file_size: int
    page_count: int
    created_at: datetime
    doc_hash: str
    metadata: Dict


class BaseParser:
    """Base class for document parsers"""
    
    def parse(self, filepath: str) -> ParsedDocument:
        raise NotImplementedError
    
    def _get_file_hash(self, filepath: str) -> str:
        """Generate MD5 hash of file for deduplication"""
        hasher = hashlib.md5()
        with open(filepath, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()
    
    def _get_file_info(self, filepath: str) -> Dict:
        """Get basic file information"""
        path = Path(filepath)
        stat = path.stat()
        return {
            "filename": path.name,
            "filepath": str(path.absolute()),
            "file_size": stat.st_size,
            "file_type": path.suffix.lower(),
            "created_at": datetime.fromtimestamp(stat.st_ctime),
            "doc_hash": self._get_file_hash(filepath)
        }


class PDFParser(BaseParser):
    """Parser for PDF documents using PyMuPDF"""
    
    def parse(self, filepath: str) -> ParsedDocument:
        import fitz  # PyMuPDF
        
        file_info = self._get_file_info(filepath)
        
        doc = fitz.open(filepath)
        text_content = []
        
        for page_num, page in enumerate(doc):
            text = page.get_text()
            if text.strip():
                text_content.append(f"[Page {page_num + 1}]\n{text}")
        
        page_count = len(doc)
        doc.close()
        
        return ParsedDocument(
            filename=file_info["filename"],
            filepath=file_info["filepath"],
            content="\n\n".join(text_content),
            file_type="pdf",
            file_size=file_info["file_size"],
            page_count=page_count,
            created_at=file_info["created_at"],
            doc_hash=file_info["doc_hash"],
            metadata={"source": "pdf", "pages": page_count}
        )


class WordParser(BaseParser):
    """Parser for Word documents (.docx)"""
    
    def parse(self, filepath: str) -> ParsedDocument:
        from docx import Document
        
        file_info = self._get_file_info(filepath)
        
        doc = Document(filepath)
        text_content = []
        
        # Extract paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                text_content.append(para.text)
        
        # Extract tables
        for table in doc.tables:
            table_text = []
            for row in table.rows:
                row_text = [cell.text.strip() for cell in row.cells]
                table_text.append(" | ".join(row_text))
            if table_text:
                text_content.append("\n[Table]\n" + "\n".join(table_text))
        
        return ParsedDocument(
            filename=file_info["filename"],
            filepath=file_info["filepath"],
            content="\n\n".join(text_content),
            file_type="docx",
            file_size=file_info["file_size"],
            page_count=len(doc.paragraphs) // 30 + 1,  # Estimate
            created_at=file_info["created_at"],
            doc_hash=file_info["doc_hash"],
            metadata={"source": "word", "paragraphs": len(doc.paragraphs)}
        )


class ExcelParser(BaseParser):
    """Parser for Excel spreadsheets (.xlsx)"""
    
    def parse(self, filepath: str) -> ParsedDocument:
        import pandas as pd
        
        file_info = self._get_file_info(filepath)
        
        # Read all sheets
        text_content = []
        
        with pd.ExcelFile(filepath) as xlsx:
            for sheet_name in xlsx.sheet_names:
                df = pd.read_excel(xlsx, sheet_name=sheet_name)
                
                # Convert to readable text
                sheet_text = f"[Sheet: {sheet_name}]\n"
                sheet_text += df.to_string(index=False)
                text_content.append(sheet_text)
        
        return ParsedDocument(
            filename=file_info["filename"],
            filepath=file_info["filepath"],
            content="\n\n".join(text_content),
            file_type="xlsx",
            file_size=file_info["file_size"],
            page_count=len(xlsx.sheet_names),
            created_at=file_info["created_at"],
            doc_hash=file_info["doc_hash"],
            metadata={"source": "excel", "sheets": xlsx.sheet_names}
        )


class PowerPointParser(BaseParser):
    """Parser for PowerPoint presentations (.pptx)"""
    
    def parse(self, filepath: str) -> ParsedDocument:
        from pptx import Presentation
        
        file_info = self._get_file_info(filepath)
        
        prs = Presentation(filepath)
        text_content = []
        
        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = [f"[Slide {slide_num}]"]
            
            for shape in slide.shapes:
                if hasattr(shape, "text") and shape.text.strip():
                    slide_text.append(shape.text)
            
            if len(slide_text) > 1:
                text_content.append("\n".join(slide_text))
        
        return ParsedDocument(
            filename=file_info["filename"],
            filepath=file_info["filepath"],
            content="\n\n".join(text_content),
            file_type="pptx",
            file_size=file_info["file_size"],
            page_count=len(prs.slides),
            created_at=file_info["created_at"],
            doc_hash=file_info["doc_hash"],
            metadata={"source": "powerpoint", "slides": len(prs.slides)}
        )


class TextParser(BaseParser):
    """Parser for plain text files (.txt, .md, .csv)"""
    
    def parse(self, filepath: str) -> ParsedDocument:
        file_info = self._get_file_info(filepath)
        
        # Try different encodings
        encodings = ['utf-8', 'utf-16', 'latin-1', 'cp1252']
        content = ""
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                break
            except UnicodeDecodeError:
                continue
        
        # Estimate page count (assuming ~3000 chars per page)
        page_count = max(1, len(content) // 3000)
        
        return ParsedDocument(
            filename=file_info["filename"],
            filepath=file_info["filepath"],
            content=content,
            file_type=file_info["file_type"].replace(".", ""),
            file_size=file_info["file_size"],
            page_count=page_count,
            created_at=file_info["created_at"],
            doc_hash=file_info["doc_hash"],
            metadata={"source": "text", "chars": len(content)}
        )


class DocumentParserFactory:
    """Factory to get the appropriate parser for a file type"""
    
    PARSERS = {
        ".pdf": PDFParser,
        ".docx": WordParser,
        ".doc": WordParser,
        ".xlsx": ExcelParser,
        ".xls": ExcelParser,
        ".pptx": PowerPointParser,
        ".txt": TextParser,
        ".md": TextParser,
        ".csv": TextParser,
    }
    
    @classmethod
    def get_parser(cls, filepath: str) -> Optional[BaseParser]:
        """Get the appropriate parser for a file"""
        ext = Path(filepath).suffix.lower()
        parser_class = cls.PARSERS.get(ext)
        
        if parser_class:
            return parser_class()
        return None
    
    @classmethod
    def parse_document(cls, filepath: str) -> Optional[ParsedDocument]:
        """Parse a document and return the result"""
        parser = cls.get_parser(filepath)
        if parser:
            return parser.parse(filepath)
        return None
    
    @classmethod
    def is_supported(cls, filepath: str) -> bool:
        """Check if a file type is supported"""
        ext = Path(filepath).suffix.lower()
        return ext in cls.PARSERS
