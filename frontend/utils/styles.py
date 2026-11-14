"""Streamlit Styling and Theming Constants"""

CUSTOM_CSS = """
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1f4e79;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #555555;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1rem 1.2rem;
        border-left: 4px solid #1f4e79;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1f4e79;
    }
    .metric-label {
        font-size: 0.85rem;
        color: #666666;
        text-transform: uppercase;
        font-weight: 600;
    }
    .badge-open {
        background-color: #ffeaa7;
        color: #d63031;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
</style>
"""

COLOR_PALETTE = {
    "primary": "#1f4e79",
    "secondary": "#2d8659",
    "accent": "#e67e22",
    "danger": "#e74c3c",
    "info": "#2980b9",
    "dark": "#2c3e50",
    "light": "#ecf0f1"
}

