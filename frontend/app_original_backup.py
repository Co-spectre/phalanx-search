"""
Phalanx Search - Enterprise Document Intelligence
A modern, private, local AI document search engine.
"""

import streamlit as st
import sys
from pathlib import Path
import time
import os
import subprocess
import re

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from config.settings import SUPPORTED_EXTENSIONS, DOCUMENTS_DIR
from backend.search import search_engine

# ============== Page Configuration ==============
st.set_page_config(
    page_title="Phalanx",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============== Modern Minimal CSS ==============
st.markdown("""
<style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    /* Root variables */
    :root {
        --bg-primary: #09090b;
        --bg-secondary: #18181b;
        --bg-tertiary: #27272a;
        --bg-hover: #3f3f46;
        --text-primary: #fafafa;
        --text-secondary: #a1a1aa;
        --text-muted: #71717a;
        --accent: #3b82f6;
        --accent-hover: #2563eb;
        --border: #27272a;
        --success: #22c55e;
        --warning: #eab308;
        --error: #ef4444;
    }
    
    /* Global styles */
    .stApp {
        background-color: var(--bg-primary);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1400px;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--bg-secondary);
        border-right: 1px solid var(--border);
    }
    
    [data-testid="stSidebar"] .stMarkdown {
        color: var(--text-secondary);
    }
    
    /* Typography */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-weight: 600;
        letter-spacing: -0.02em;
    }
    
    p, span, label {
        color: var(--text-secondary);
    }
    
    /* Header */
    .app-header {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 0 0 2rem 0;
        border-bottom: 1px solid var(--border);
        margin-bottom: 2rem;
    }
    
    .app-logo {
        width: 48px;
        height: 48px;
        background: linear-gradient(135deg, var(--accent) 0%, #8b5cf6 100%);
        border-radius: 12px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.2);
    }
    
    .app-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--text-primary);
        letter-spacing: -0.03em;
    }
    
    .app-subtitle {
        font-size: 0.875rem;
        color: var(--text-muted);
        margin-left: auto;
        font-weight: 500;
    }
    
    /* Search container */
    .search-container {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
    }
    
    /* Input styling */
    .stTextInput > div > div > input {
        background-color: var(--bg-tertiary) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        color: var(--text-primary) !important;
        font-size: 1rem !important;
        padding: 0.875rem 1rem !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: var(--accent) !important;
        color: white !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.625rem 1.25rem !important;
        font-weight: 500 !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.2s ease !important;
    }
    
    .stButton > button:hover {
        background: var(--accent-hover) !important;
        transform: translateY(-1px);
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background: var(--bg-tertiary) !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Result cards */
    .result-card {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        transition: all 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    
    .result-card:hover {
        border-color: var(--bg-hover);
        background: var(--bg-tertiary);
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    
    .result-header {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        margin-bottom: 1rem;
    }
    
    .result-icon-wrapper {
        flex-shrink: 0;
        width: 48px;
        height: 48px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--bg-tertiary);
        border: 1px solid var(--border);
    }
    
    .icon-pdf { color: #ef4444; background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.2); }
    .icon-doc { color: #3b82f6; background: rgba(59, 130, 246, 0.1); border-color: rgba(59, 130, 246, 0.2); }
    .icon-xls { color: #22c55e; background: rgba(34, 197, 94, 0.1); border-color: rgba(34, 197, 94, 0.2); }
    .icon-ppt { color: #f97316; background: rgba(249, 115, 22, 0.1); border-color: rgba(249, 115, 22, 0.2); }
    .icon-txt { color: #a1a1aa; background: rgba(161, 161, 170, 0.1); border-color: rgba(161, 161, 170, 0.2); }
    
    .result-info {
        flex: 1;
        min-width: 0;
    }
    
    .result-filename {
        font-weight: 600;
        color: var(--text-primary);
        font-size: 1rem;
        margin-bottom: 0.25rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    .result-path {
        font-size: 0.75rem;
        color: var(--text-muted);
        display: flex;
        align-items: center;
        gap: 6px;
    }
    
    .result-score {
        flex-shrink: 0;
        background: rgba(59, 130, 246, 0.1);
        color: var(--accent);
        padding: 0.375rem 0.75rem;
        border-radius: 8px;
        font-size: 0.875rem;
        font-weight: 600;
        border: 1px solid rgba(59, 130, 246, 0.2);
    }
    
    .result-content {
        color: var(--text-secondary);
        font-size: 0.9375rem;
        line-height: 1.6;
        padding: 1rem;
        background: var(--bg-primary);
        border-radius: 8px;
        border: 1px solid var(--border);
        margin-top: 0.5rem;
    }
    
    /* Privacy indicator */
    .privacy-indicator {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(34, 197, 94, 0.1);
        color: var(--success);
        padding: 0.5rem 1rem;
        border-radius: 20px;
        font-size: 0.8125rem;
        font-weight: 500;
        border: 1px solid rgba(34, 197, 94, 0.2);
    }
    
    .privacy-dot {
        width: 8px;
        height: 8px;
        background: var(--success);
        border-radius: 50%;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.4);
    }
    
    /* Document list */
    .doc-item {
        display: flex;
        align-items: center;
        gap: 16px;
        padding: 1rem;
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        margin-bottom: 0.75rem;
        transition: all 0.2s ease;
    }
    
    .doc-item:hover {
        background: var(--bg-tertiary);
        border-color: var(--bg-hover);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--bg-secondary);
        border-radius: 12px;
        padding: 6px;
        gap: 6px;
        border: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        background: transparent;
        border-radius: 8px;
        color: var(--text-secondary);
        font-weight: 500;
        padding: 0.625rem 1.25rem;
        border: none;
    }
    
    .stTabs [aria-selected="true"] {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Empty state */
    .empty-state {
        text-align: center;
        padding: 6rem 2rem;
        color: var(--text-muted);
    }
    
    .empty-state-icon {
        width: 80px;
        height: 80px;
        background: var(--bg-tertiary);
        border-radius: 24px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 2rem;
        color: var(--text-muted);
        border: 1px solid var(--border);
    }
    
    /* Stats */
    .stat-box {
        background: var(--bg-secondary);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1rem;
        transition: all 0.2s ease;
    }
    
    .stat-box:hover {
        border-color: var(--bg-hover);
    }
</style>
""", unsafe_allow_html=True)


# ============== SVG Icons ==============
# High quality SVG icons for file types and UI elements
ICONS = {
    "logo": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>""",
    "pdf": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M9 15l3 3 3-3"></path><path d="M12 18V12"></path></svg>""",
    "doc": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>""",
    "xls": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M8 13h8"></path><path d="M8 17h8"></path><path d="M10 9h4"></path></svg>""",
    "ppt": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><path d="M12 18v-6"></path><path d="M9 15h6"></path></svg>""",
    "txt": """<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line></svg>""",
    "search": """<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>""",
    "upload": """<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>""",
    "empty": """<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>""",
    "check": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>""",
    "error": """<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>""",
}

# ============== Helper Functions ==============

@st.cache_resource
def get_search_engine():
    """Cached access to search engine to prevent re-initialization"""
    return search_engine

@st.cache_data(ttl=300)
def perform_search(query: str, top_k: int, file_type_filter: str = None, search_mode: str = "hybrid"):
    """Cached search results for better performance"""
    engine = get_search_engine()
    return engine.search(query, top_k=top_k, file_type_filter=file_type_filter, search_mode=search_mode)

def highlight_keywords(text: str, query: str) -> str:
    """Highlight matching keywords in text"""
    if not query:
        return text
    words = re.findall(r'\b\w{2,}\b', query.lower())
    highlighted = text
    for word in words:
        pattern = re.compile(f'({re.escape(word)})', re.IGNORECASE)
        highlighted = pattern.sub(r'<mark style="background: rgba(59, 130, 246, 0.3); color: #fafafa; padding: 0 2px; border-radius: 2px;">\1</mark>', highlighted)
    return highlighted

def open_file_location(filepath: str):
    """Open the file location in Windows Explorer"""
    try:
        path = Path(filepath)
        if path.exists():
            # Open Explorer and select the file
            subprocess.run(['explorer', '/select,', str(path)])
            return True
        elif path.parent.exists():
            # Open the parent folder if file doesn't exist
            os.startfile(str(path.parent))
            return True
    except Exception as e:
        st.error(f"Could not open location: {e}")
    return False

def get_file_content(filepath: str) -> bytes:
    """Get file content for download"""
    try:
        with open(filepath, 'rb') as f:
            return f.read()
    except:
        return None

def get_file_icon_html(file_type: str) -> str:
    """Get SVG icon for file type"""
    type_map = {
        "pdf": ("icon-pdf", ICONS["pdf"]),
        "docx": ("icon-doc", ICONS["doc"]),
        "doc": ("icon-doc", ICONS["doc"]),
        "xlsx": ("icon-xls", ICONS["xls"]),
        "xls": ("icon-xls", ICONS["xls"]),
        "pptx": ("icon-ppt", ICONS["ppt"]),
        "ppt": ("icon-ppt", ICONS["ppt"]),
        "txt": ("icon-txt", ICONS["txt"]),
        "md": ("icon-txt", ICONS["txt"]),
        "csv": ("icon-xls", ICONS["xls"])
    }
    css_class, svg = type_map.get(file_type.lower(), ("icon-txt", ICONS["txt"]))
    return f'<div class="result-icon-wrapper {css_class}">{svg}</div>'

def format_score(score: float) -> str:
    return f"{score * 100:.0f}% Match"

def truncate_text(text: str, max_length: int = 300) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(' ', 1)[0] + "..."

# ============== Sidebar ==============

with st.sidebar:
    # Logo Area
    st.markdown(f"""
    <div style="padding: 1rem 0 2rem 0; border-bottom: 1px solid #27272a; margin-bottom: 2rem;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="width: 40px; height: 40px; background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%); border-radius: 10px; display: flex; align-items: center; justify-content: center; color: white; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);">
                {ICONS['logo']}
            </div>
            <div>
                <div style="font-size: 1.125rem; font-weight: 700; color: #fafafa; letter-spacing: -0.02em; line-height: 1.2;">Phalanx</div>
                <div style="font-size: 0.75rem; color: #71717a; font-weight: 500;">Enterprise Search</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Privacy Indicator
    st.markdown(f"""
    <div class="privacy-indicator">
        <div class="privacy-dot"></div>
        100% Private & Local
    </div>
    <p style="font-size: 0.75rem; color: #71717a; margin-top: 0.75rem; line-height: 1.5;">
        Your documents are processed locally. No data ever leaves this machine.
    </p>
    """, unsafe_allow_html=True)
    
    st.markdown("<div style='height: 2rem'></div>", unsafe_allow_html=True)
    
    # Settings
    st.markdown("<p style='font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #71717a; margin-bottom: 1rem; font-weight: 600;'>Search Configuration</p>", unsafe_allow_html=True)
    
    search_mode = st.selectbox(
        "Search Mode",
        ["Hybrid (Recommended)", "Semantic Only", "Keyword Only"],
        help="Hybrid combines AI understanding with exact keyword matching"
    )
    search_mode_map = {"Hybrid (Recommended)": "hybrid", "Semantic Only": "semantic", "Keyword Only": "keyword"}
    selected_search_mode = search_mode_map[search_mode]
    
    top_k = st.slider("Results limit", 1, 50, 10)
    
    file_types = ["All Formats"] + list(SUPPORTED_EXTENSIONS.keys())
    selected_type = st.selectbox("File type", file_types)
    
    st.markdown("<div style='height: 2rem'></div>", unsafe_allow_html=True)
    
    # Stats
    st.markdown("<p style='font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #71717a; margin-bottom: 1rem; font-weight: 600;'>System Status</p>", unsafe_allow_html=True)
    
    try:
        engine = get_search_engine()
        stats = engine.get_stats()
        
        st.markdown(f"""
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
            <div class="stat-box">
                <div style="font-size: 1.5rem; font-weight: 700; color: #fafafa;">{stats.get("total_documents", 0)}</div>
                <div style="font-size: 0.75rem; color: #71717a; font-weight: 500;">Documents</div>
            </div>
            <div class="stat-box">
                <div style="font-size: 1.5rem; font-weight: 700; color: #fafafa;">{stats.get("total_chunks", 0)}</div>
                <div style="font-size: 0.75rem; color: #71717a; font-weight: 500;">Chunks</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.error("System initializing...")

# ============== Main Content ==============

# Header
st.markdown(f"""
<div class="app-header">
    <div>
        <h1 class="app-title">Document Intelligence</h1>
        <p class="app-subtitle">Search across your enterprise knowledge base with AI</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Tabs
tab_search, tab_upload, tab_manage = st.tabs(["Search", "Upload", "Manage"])

# ============== Search Tab ==============
with tab_search:
    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    
    # Search Input
    search_query = st.text_input(
        "Search",
        placeholder="Ask a question or search for keywords...",
        label_visibility="collapsed"
    )
    
    st.markdown("<div style='height: 1.5rem'></div>", unsafe_allow_html=True)
    
    if search_query:
        with st.spinner("Searching knowledge base..."):
            # Filter
            ft_filter = None
            if selected_type and selected_type != "All Formats":
                ft_filter = selected_type.replace(".", "")
            
            results = perform_search(search_query, top_k, ft_filter, selected_search_mode)
        
        if results:
            # Results header with mode indicator
            mode_label = {"hybrid": "Hybrid", "semantic": "Semantic", "keyword": "Keyword"}[selected_search_mode]
            st.markdown(f"""
            <div style="margin-bottom: 1.5rem; display: flex; align-items: center; gap: 12px;">
                <span style="color: #22c55e;">{ICONS['check']}</span>
                <span style="color: #fafafa; font-weight: 500;">Found {len(results)} relevant results</span>
                <span style="background: rgba(59, 130, 246, 0.1); color: #3b82f6; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">{mode_label} Search</span>
            </div>
            """, unsafe_allow_html=True)
            
            for i, result in enumerate(results):
                meta = result.get("metadata", {})
                filename = meta.get("filename", "Unknown")
                file_type = meta.get("file_type", "txt")
                score = result.get("score", 0)
                content = result.get("content", "")
                filepath = meta.get("filepath", "")
                keywords = meta.get("keywords", "")
                summary = meta.get("summary", "")
                exact_match = result.get("exact_match", False)
                keyword_matches = result.get("keyword_matches", 0)
                
                icon_html = get_file_icon_html(file_type)
                highlighted_content = highlight_keywords(truncate_text(content, 400), search_query)
                
                # Exact match badge
                match_badge = ""
                if exact_match:
                    match_badge = '<span style="background: rgba(34, 197, 94, 0.1); color: #22c55e; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 8px;">Exact Match</span>'
                elif keyword_matches > 0:
                    match_badge = f'<span style="background: rgba(249, 115, 22, 0.1); color: #f97316; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.7rem; margin-left: 8px;">{keyword_matches} Keywords</span>'
                
                st.markdown(f"""
                <div class="result-card">
                    <div class="result-header">
                        {icon_html}
                        <div class="result-info">
                            <div class="result-filename">{filename}{match_badge}</div>
                            <div class="result-path">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
                                {filepath}
                            </div>
                        </div>
                        <div class="result-score">{format_score(score)}</div>
                    </div>
                    <div class="result-content">
                        {highlighted_content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # Action buttons row
                col1, col2, col3, col4 = st.columns([2, 2, 2, 4])
                
                with col1:
                    if filepath and Path(filepath).exists():
                        file_data = get_file_content(filepath)
                        if file_data:
                            st.download_button(
                                label="Download",
                                data=file_data,
                                file_name=filename,
                                mime="application/octet-stream",
                                key=f"dl_{i}_{filename}",
                                use_container_width=True
                            )
                
                with col2:
                    if st.button("Open Location", key=f"loc_{i}_{filename}", use_container_width=True):
                        open_file_location(filepath)
                
                with col3:
                    if st.button("View Details", key=f"info_{i}_{filename}", use_container_width=True):
                        st.session_state[f"show_details_{i}"] = not st.session_state.get(f"show_details_{i}", False)
                
                # Show document details if toggled
                if st.session_state.get(f"show_details_{i}", False):
                    with st.container():
                        st.markdown(f"""
                        <div style="background: #18181b; border: 1px solid #27272a; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                            <p style="font-size: 0.75rem; text-transform: uppercase; color: #71717a; margin-bottom: 0.5rem;">Document Summary</p>
                            <p style="color: #a1a1aa; font-size: 0.875rem; line-height: 1.6;">{summary if summary else 'No summary available'}</p>
                            <p style="font-size: 0.75rem; text-transform: uppercase; color: #71717a; margin: 1rem 0 0.5rem 0;">Keywords</p>
                            <div style="display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                {''.join([f'<span style="background: #27272a; color: #a1a1aa; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem;">{kw.strip()}</span>' for kw in keywords.split(",")[:10] if kw.strip()])}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                
                with st.expander("View full content"):
                    st.text(content)
                
                st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="empty-state">
                <div class="empty-state-icon">{ICONS['search']}</div>
                <h3 style="color: #fafafa; font-weight: 600; margin-bottom: 0.5rem;">No results found</h3>
                <p>Try adjusting your search terms or filters.</p>
            </div>
            """, unsafe_allow_html=True)
            
    else:
        st.markdown(f"""
        <div class="empty-state">
            <div class="empty-state-icon">{ICONS['logo']}</div>
            <h3 style="color: #fafafa; font-weight: 600; margin-bottom: 0.5rem;">Ready to search</h3>
            <p>Enter a query above to find documents using semantic search.</p>
        </div>
        """, unsafe_allow_html=True)

# ============== Upload Tab ==============
with tab_upload:
    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    
    uploaded_files = st.file_uploader(
        "Upload documents",
        type=[ext.replace(".", "") for ext in SUPPORTED_EXTENSIONS.keys()],
        accept_multiple_files=True,
        label_visibility="collapsed"
    )
    
    if uploaded_files:
        st.markdown(f"""
        <div style="background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 1rem; margin: 1rem 0; display: flex; align-items: center; gap: 12px;">
            <div style="width: 32px; height: 32px; background: rgba(59, 130, 246, 0.1); border-radius: 8px; display: flex; align-items: center; justify-content: center; color: #3b82f6;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
            </div>
            <span style="color: #fafafa; font-weight: 500;">{len(uploaded_files)} files ready to index</span>
        </div>
        """, unsafe_allow_html=True)
        
        if st.button("Start Indexing", type="primary"):
            progress_bar = st.progress(0)
            status_area = st.empty()
            
            engine = get_search_engine()
            results = []
            
            for i, file in enumerate(uploaded_files):
                status_area.text(f"Processing {file.name}...")
                
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.name).suffix) as tmp:
                    tmp.write(file.getvalue())
                    tmp_path = tmp.name
                
                try:
                    res = engine.index_document(tmp_path)
                    res["filename"] = file.name
                    results.append(res)
                finally:
                    Path(tmp_path).unlink(missing_ok=True)
                
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            status_area.empty()
            progress_bar.empty()
            
            success_count = sum(1 for r in results if r.get("success"))
            
            if success_count > 0:
                st.success(f"Successfully indexed {success_count} documents")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Failed to index documents")

    st.markdown("<div style='height: 2rem'></div>", unsafe_allow_html=True)
    st.markdown("### Index Local Folder")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        dir_path = st.text_input("Folder Path", placeholder="C:\\Documents", label_visibility="collapsed")
    with col2:
        if st.button("Index Folder", type="secondary", use_container_width=True):
            if dir_path:
                with st.spinner("Indexing folder..."):
                    engine = get_search_engine()
                    res = engine.index_directory(dir_path)
                    if res.get("successful", 0) > 0:
                        st.success(f"Indexed {res['successful']} files")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("No files indexed")

# ============== Manage Tab ==============
with tab_manage:
    st.markdown("<div style='height: 1rem'></div>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.markdown("### Indexed Documents")
    with col2:
        if st.button("Refresh List", use_container_width=True):
            st.rerun()
            
    engine = get_search_engine()
    docs = engine.get_indexed_documents()
    
    if docs:
        for idx, doc in enumerate(docs):
            icon_html = get_file_icon_html(doc.get('file_type', 'txt'))
            filepath = doc.get('filepath', '')
            filename = doc.get('filename', 'Unknown')
            
            # Document card
            st.markdown(f"""
            <div style="background: #18181b; border: 1px solid #27272a; border-radius: 12px; padding: 1rem; margin-bottom: 0.75rem;">
                <div style="display: flex; align-items: center; gap: 16px;">
                    {icon_html}
                    <div style="flex: 1;">
                        <div style="color: #fafafa; font-weight: 500; margin-bottom: 0.25rem;">{filename}</div>
                        <div style="color: #71717a; font-size: 0.75rem;">{doc.get('chunk_count', 0)} chunks • {doc.get('file_type', '').upper()}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Action buttons
            col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
            
            with col1:
                if filepath and Path(filepath).exists():
                    file_data = get_file_content(filepath)
                    if file_data:
                        st.download_button(
                            label="Download",
                            data=file_data,
                            file_name=filename,
                            mime="application/octet-stream",
                            key=f"manage_dl_{idx}",
                            use_container_width=True
                        )
            
            with col2:
                if st.button("Open Location", key=f"manage_loc_{idx}", use_container_width=True):
                    open_file_location(filepath)
            
            with col3:
                if st.button("View Info", key=f"manage_info_{idx}", use_container_width=True):
                    st.session_state[f"manage_details_{idx}"] = not st.session_state.get(f"manage_details_{idx}", False)
            
            with col4:
                if st.button("Delete", key=f"del_{filename}", use_container_width=True):
                    engine.delete_document(filename)
                    st.rerun()
            
            # Show document details
            if st.session_state.get(f"manage_details_{idx}", False):
                doc_info = engine.get_document_info(filename)
                if doc_info:
                    keywords_html = ''.join([f'<span style="background: #27272a; color: #a1a1aa; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin: 0.125rem;">{kw}</span>' for kw in doc_info.get('keywords', [])[:15] if kw])
                    
                    st.markdown(f"""
                    <div style="background: #09090b; border: 1px solid #27272a; border-radius: 8px; padding: 1rem; margin: 0.5rem 0;">
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
                            <div>
                                <p style="font-size: 0.7rem; text-transform: uppercase; color: #71717a;">Pages</p>
                                <p style="color: #fafafa; font-weight: 500;">{doc_info.get('page_count', 'N/A')}</p>
                            </div>
                            <div>
                                <p style="font-size: 0.7rem; text-transform: uppercase; color: #71717a;">Size</p>
                                <p style="color: #fafafa; font-weight: 500;">{doc_info.get('file_size', 0) // 1024} KB</p>
                            </div>
                        </div>
                        <p style="font-size: 0.7rem; text-transform: uppercase; color: #71717a; margin-bottom: 0.5rem;">Summary</p>
                        <p style="color: #a1a1aa; font-size: 0.875rem; line-height: 1.6; margin-bottom: 1rem;">{doc_info.get('summary', 'No summary available')}</p>
                        <p style="font-size: 0.7rem; text-transform: uppercase; color: #71717a; margin-bottom: 0.5rem;">Keywords</p>
                        <div style="display: flex; flex-wrap: wrap; gap: 0.375rem;">
                            {keywords_html if keywords_html else '<span style="color: #71717a;">No keywords extracted</span>'}
                        </div>
                        <p style="font-size: 0.7rem; text-transform: uppercase; color: #71717a; margin: 1rem 0 0.5rem 0;">Preview</p>
                        <p style="color: #71717a; font-size: 0.8rem; line-height: 1.5; max-height: 100px; overflow: hidden;">{doc_info.get('preview', '')[:500]}...</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.markdown("<div style='height: 0.5rem'></div>", unsafe_allow_html=True)
            
        st.markdown("<div style='height: 2rem'></div>", unsafe_allow_html=True)
        if st.button("Clear All Data", type="secondary"):
            engine.clear_index()
            st.rerun()
    else:
        st.markdown(f"""
        <div class="empty-state">
            <div class="empty-state-icon">{ICONS['empty']}</div>
            <h3 style="color: #fafafa; font-weight: 600; margin-bottom: 0.5rem;">Knowledge base is empty</h3>
            <p>Upload documents to get started.</p>
        </div>
        """, unsafe_allow_html=True)

# ============== Footer ==============
st.markdown("""
<div style="text-align: center; padding: 3rem 0; margin-top: 2rem; border-top: 1px solid #27272a;">
    <p style="color: #52525b; font-size: 0.75rem;">Phalanx Search • Enterprise Edition</p>
</div>
""", unsafe_allow_html=True)
