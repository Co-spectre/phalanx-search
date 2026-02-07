"""
Phalanx Search - Simple Local Document Search
A minimal, private, local AI document search engine.
"""

import streamlit as st
import sys
from pathlib import Path
import tempfile

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.settings import SUPPORTED_EXTENSIONS
from backend.search import search_engine

# ============== Page Configuration ==============
st.set_page_config(
    page_title="Phalanx Search",
    page_icon="🔍",
    layout="centered"
)

# ============== Simple CSS ==============
st.markdown("""
<style>
    .stApp {
        background-color: #ffffff;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ============== Helper Functions ==============

@st.cache_resource
def get_search_engine():
    """Get search engine instance"""
    return search_engine

# ============== Main App ==============

st.title("🔍 Phalanx Search")
st.caption("Private local document search - your data never leaves this machine")

# ============== Search Section ==============
st.subheader("Search Documents")

search_query = st.text_input(
    "Enter your search query",
    placeholder="Search for documents..."
)

if search_query:
    with st.spinner("Searching..."):
        engine = get_search_engine()
        results = engine.search(search_query, top_k=10)
    
    if results:
        st.success(f"Found {len(results)} results")
        
        for i, result in enumerate(results, 1):
            meta = result.get("metadata", {})
            filename = meta.get("filename", "Unknown")
            content = result.get("content", "")
            score = result.get("score", 0)
            
            with st.expander(f"{i}. {filename} ({score*100:.0f}% match)"):
                st.text(content[:500] + ("..." if len(content) > 500 else ""))
    else:
        st.info("No results found. Try different search terms.")

st.divider()

# ============== Upload Section ==============
st.subheader("Upload Documents")

uploaded_files = st.file_uploader(
    "Choose files to upload",
    type=[ext.replace(".", "") for ext in SUPPORTED_EXTENSIONS.keys()],
    accept_multiple_files=True
)

if uploaded_files and st.button("Upload & Index"):
    progress_bar = st.progress(0)
    engine = get_search_engine()
    success_count = 0
    
    for i, file in enumerate(uploaded_files):
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp:
            tmp.write(file.getvalue())
            tmp_path = tmp.name
        
        try:
            res = engine.index_document(tmp_path)
            if res.get("success"):
                success_count += 1
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        
        progress_bar.progress((i + 1) / len(uploaded_files))
    
    progress_bar.empty()
    
    if success_count > 0:
        st.success(f"Successfully uploaded {success_count} documents")
        st.rerun()
    else:
        st.error("Failed to upload documents")

st.divider()

# ============== Stats Section ==============
try:
    engine = get_search_engine()
    stats = engine.get_stats()
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Documents", stats.get("total_documents", 0))
    with col2:
        st.metric("Indexed Chunks", stats.get("total_chunks", 0))
except:
    st.info("System initializing...")
