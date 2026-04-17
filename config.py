APP_NAME = "Keith Enterprises"
APP_PORT = 8080

COLORS = {
    "bg": "#0f1117",
    "sidebar": "#161b22",
    "card": "#1c2128",
    "card_border": "#30363d",
    "text": "#e6edf3",
    "text_muted": "#8b949e",
    "primary": "#58a6ff",
    "success": "#3fb950",
    "warning": "#d29922",
    "danger": "#f85149",
    "info": "#79c0ff",
    "purple": "#bc8cff",
    "input_bg": "#0d1117",
    "input_border": "#30363d",
    "hover": "#1f2937",
    "active": "#1f6feb",
}

PAGE_ORDER = [
    {"name": "Home", "path": "/", "icon": "bi-house-fill"},
    {"name": "Inbox", "path": "/inbox", "icon": "bi-chat-left-text"},
    {"name": "Scanner", "path": "/scanner", "icon": "bi-camera"},
    {"name": "Offers", "path": "/offers", "icon": "bi-tag"},
    {"name": "Orders", "path": "/orders", "icon": "bi-cart-check"},
    {"name": "Buyers", "path": "/buyers", "icon": "bi-people"},
    {"name": "Accounts", "path": "/accounts", "icon": "bi-gear", "admin": True},
    {"name": "System Health", "path": "/health", "icon": "bi-heart-pulse", "admin": True},
]
