"""
Phalanx Search - FastAPI Backend
REST API for the document search engine
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import tempfile
import shutil
from pathlib import Path
import sys

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from config.settings import DOCUMENTS_DIR, SUPPORTED_EXTENSIONS, MAX_FILE_SIZE_MB
from backend.search import search_engine

# Initialize FastAPI app
app = FastAPI(
    title="🔍 Phalanx Search API",
    description="100% Local AI-Powered Document Search Engine. No data leaves your system.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============== Pydantic Models ==============

class SearchRequest(BaseModel):
    query: str
    top_k: int = 10
    file_type: Optional[str] = None
    filename: Optional[str] = None


class SearchResult(BaseModel):
    id: str
    content: str
    score: float
    filename: str
    file_type: str
    chunk_index: int


class IndexedDocument(BaseModel):
    filename: str
    filepath: str
    file_type: str
    chunk_count: int
    indexed_at: str


class SystemStats(BaseModel):
    total_chunks: int
    total_documents: int
    embedding_model: str
    supported_file_types: List[str]


# ============== API Endpoints ==============

@app.get("/", tags=["Info"])
async def root():
    """Welcome endpoint"""
    return {
        "message": "🔍 Welcome to Phalanx Search",
        "description": "100% Local AI Document Search Engine",
        "privacy": "All data stays on your machine - no cloud services used",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", tags=["Info"])
async def health_check():
    """Health check endpoint"""
    stats = search_engine.get_stats()
    return {
        "status": "healthy",
        "engine": "ready",
        "stats": stats
    }


@app.get("/stats", response_model=SystemStats, tags=["Info"])
async def get_stats():
    """Get system statistics"""
    stats = search_engine.get_stats()
    return stats


@app.post("/search", tags=["Search"])
async def search_documents(request: SearchRequest):
    """
    Search for documents matching the query
    
    - **query**: Natural language search query
    - **top_k**: Number of results to return (default: 10)
    - **file_type**: Filter by file type (pdf, docx, xlsx, etc.)
    - **filename**: Filter by filename (partial match)
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    results = search_engine.search(
        query=request.query,
        top_k=request.top_k,
        file_type_filter=request.file_type,
        filename_filter=request.filename
    )
    
    # Format results
    formatted_results = []
    for result in results:
        formatted_results.append({
            "id": result["id"],
            "content": result["content"],
            "score": result["score"],
            "filename": result["metadata"].get("filename", "Unknown"),
            "file_type": result["metadata"].get("file_type", "unknown"),
            "chunk_index": result["metadata"].get("chunk_index", 0),
            "filepath": result["metadata"].get("filepath", ""),
            "page_count": result["metadata"].get("page_count", 1)
        })
    
    return {
        "query": request.query,
        "total_results": len(formatted_results),
        "results": formatted_results
    }


@app.get("/search", tags=["Search"])
async def search_documents_get(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(10, description="Number of results"),
    file_type: Optional[str] = Query(None, description="Filter by file type")
):
    """Search using GET request (for easy browser testing)"""
    request = SearchRequest(query=q, top_k=top_k, file_type=file_type)
    return await search_documents(request)


@app.post("/upload", tags=["Documents"])
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and index a document
    
    Supported formats: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), Text files
    """
    # Check file extension
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file_ext}. Supported: {list(SUPPORTED_EXTENSIONS.keys())}"
        )
    
    # Check file size
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Seek back to start
    
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB"
        )
    
    # Save to temp file then process
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        
        # Index the document
        result = search_engine.index_document(tmp_path)
        
        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)
        
        if result["success"]:
            return {
                "status": "success",
                "message": f"Document '{file.filename}' indexed successfully",
                "details": result
            }
        else:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index-directory", tags=["Documents"])
async def index_directory(directory_path: str):
    """Index all documents in a directory"""
    result = search_engine.index_directory(directory_path)
    
    if result.get("success") == False:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@app.get("/documents", tags=["Documents"])
async def list_documents():
    """List all indexed documents"""
    documents = search_engine.get_indexed_documents()
    return {
        "total_documents": len(documents),
        "documents": documents
    }


@app.delete("/documents/{filename}", tags=["Documents"])
async def delete_document(filename: str):
    """Delete a document from the index"""
    result = search_engine.delete_document(filename)
    
    if not result["success"]:
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found")
    
    return {
        "status": "success",
        "message": f"Document '{filename}' deleted",
        "chunks_deleted": result["chunks_deleted"]
    }


@app.delete("/documents", tags=["Documents"])
async def clear_all_documents():
    """Clear all documents from the index (use with caution!)"""
    success = search_engine.clear_index()
    
    if success:
        return {"status": "success", "message": "All documents cleared"}
    else:
        raise HTTPException(status_code=500, detail="Failed to clear documents")


@app.get("/supported-types", tags=["Info"])
async def get_supported_types():
    """Get list of supported file types"""
    return {
        "supported_extensions": SUPPORTED_EXTENSIONS
    }


# ============== Run Server ==============

if __name__ == "__main__":
    import uvicorn
    from config.settings import API_HOST, API_PORT
    
    print("\n" + "="*60)
    print("🔍 PHALANX SEARCH - Local AI Document Search Engine")
    print("="*60)
    print(f"🌐 API Server: http://{API_HOST}:{API_PORT}")
    print(f"📚 API Docs:   http://{API_HOST}:{API_PORT}/docs")
    print(f"🔒 Privacy:    100% Local - No data leaves your system")
    print("="*60 + "\n")
    
    uvicorn.run(
        "main:app",
        host=API_HOST,
        port=API_PORT,
        reload=True,
        log_level="info"
    )
