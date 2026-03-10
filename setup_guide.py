import dash
from dash import html, dcc
from config import COLORS

app = dash.Dash(
    __name__,
    title="Keith Enterprises — Seller Assistant Setup",
    external_stylesheets=[
        "https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css",
    ],
)

STEP_STYLE = {
    "background": COLORS["card"], "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "12px", "padding": "24px", "marginBottom": "20px",
}
LINK_STYLE = {"color": COLORS["primary"], "fontWeight": "600", "textDecoration": "none"}
CODE_STYLE = {
    "background": COLORS["input_bg"], "border": f"1px solid {COLORS['card_border']}",
    "borderRadius": "6px", "padding": "2px 8px", "fontFamily": "monospace",
    "fontSize": "0.85rem", "color": COLORS["info"],
}


def step_card(number, title, icon, children):
    return html.Div([
        html.Div([
            html.Div(str(number), style={
                "width": "32px", "height": "32px", "borderRadius": "50%",
                "background": COLORS["active"], "color": "#fff", "display": "flex",
                "alignItems": "center", "justifyContent": "center",
                "fontWeight": "700", "fontSize": "0.9rem", "flexShrink": "0",
            }),
            html.I(className=f"bi {icon}", style={"color": COLORS["primary"], "fontSize": "1.2rem"}),
            html.H5(title, style={"color": COLORS["text"], "marginBottom": "0"}),
        ], style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "16px"}),
        html.Div(children),
    ], style=STEP_STYLE)


def bullet(text, icon="bi-check-circle-fill", color=None):
    color = color or COLORS["success"]
    return html.Div([
        html.I(className=f"bi {icon}", style={"color": color, "flexShrink": "0", "marginTop": "2px"}),
        html.Span(text, style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
    ], style={"display": "flex", "gap": "8px", "marginBottom": "6px"})


def link_button(text, url, icon="bi-box-arrow-up-right"):
    return html.A([
        html.I(className=f"bi {icon} me-2"),
        text,
    ], href=url, target="_blank", style={
        **LINK_STYLE, "display": "inline-flex", "alignItems": "center",
        "background": f"{COLORS['primary']}15", "padding": "8px 16px",
        "borderRadius": "8px", "marginRight": "10px", "marginBottom": "8px",
        "fontSize": "0.85rem",
    })


def _plan_row(plan, monthly, annual, has_api, features):
    api_cell = html.I(className="bi bi-check-circle-fill",
                      style={"color": COLORS["success"]}) if has_api else html.I(
        className="bi bi-x-circle", style={"color": COLORS["text_muted"]})
    highlight = {"borderLeft": f"3px solid {COLORS['success']}"} if has_api else {}
    return html.Tr([
        html.Td(html.Strong(plan), style={"padding": "10px 16px", "color": COLORS["text"],
                                           "borderBottom": f"1px solid {COLORS['card_border']}", **highlight}),
        html.Td(monthly, style={"padding": "10px 16px", "color": COLORS["text_muted"],
                                "borderBottom": f"1px solid {COLORS['card_border']}"}),
        html.Td(annual, style={"padding": "10px 16px", "color": COLORS["primary"], "fontWeight": "600",
                               "borderBottom": f"1px solid {COLORS['card_border']}"}),
        html.Td(api_cell, style={"padding": "10px 16px", "textAlign": "center",
                                 "borderBottom": f"1px solid {COLORS['card_border']}"}),
        html.Td(features, style={"padding": "10px 16px", "color": COLORS["text_muted"],
                                  "fontSize": "0.8rem",
                                  "borderBottom": f"1px solid {COLORS['card_border']}"}),
    ])


def _endpoint(method, path, desc):
    method_color = COLORS["success"] if method == "GET" else COLORS["warning"]
    return html.Div([
        html.Span(method, style={
            "background": f"{method_color}20", "color": method_color,
            "padding": "2px 8px", "borderRadius": "4px", "fontSize": "0.75rem",
            "fontWeight": "700", "fontFamily": "monospace", "minWidth": "40px",
            "textAlign": "center", "display": "inline-block",
        }),
        html.Code(path, style={**CODE_STYLE, "marginLeft": "8px"}),
        html.Span(f" — {desc}", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
    ], style={"marginBottom": "8px", "display": "flex", "alignItems": "center", "gap": "4px"})


app.layout = html.Div([
    # Header
    html.Div([
        html.Div([
            html.H2([
                html.I(className="bi bi-bag-check-fill me-3", style={"color": COLORS["success"]}),
                "Seller Assistant — Setup Guide",
            ], style={"color": COLORS["text"], "fontWeight": "700"}),
            html.P("Step-by-step instructions to create your account and integrate with Keith Enterprises",
                   style={"color": COLORS["text_muted"], "marginBottom": "0"}),
        ], style={"maxWidth": "900px", "margin": "0 auto", "padding": "32px 24px 20px"}),
    ]),

    html.Div([

        # ── Step 1: Create Account ──
        step_card(1, "Create a Seller Assistant Account", "bi-person-plus", html.Div([
            html.Ol([
                html.Li([
                    "Go to the registration page: ",
                    html.A("app.sellerassistant.app/register", href="https://app.sellerassistant.app/register",
                           target="_blank", style=LINK_STYLE),
                ]),
                html.Li("Sign up with Google or enter your name, email, and create a password"),
                html.Li([html.Strong("14-day free trial"), " starts automatically — no credit card required"]),
                html.Li("Complete the onboarding setup wizard"),
            ], style={"color": COLORS["text_muted"], "fontSize": "0.9rem", "paddingLeft": "20px",
                       "display": "flex", "flexDirection": "column", "gap": "8px"}),
            html.Div([
                link_button("Register Now", "https://app.sellerassistant.app/register", "bi-person-plus"),
                link_button("Login", "https://app.sellerassistant.app/", "bi-box-arrow-in-right"),
            ], style={"marginTop": "16px"}),
        ])),

        # ── Step 2: Choose Plan ──
        step_card(2, "Choose the Right Plan", "bi-credit-card", html.Div([
            html.P("API access requires the Business plan or above.",
                   style={"color": COLORS["warning"], "fontWeight": "600", "fontSize": "0.9rem"}),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Plan", style={"padding": "10px 16px", "textAlign": "left"}),
                    html.Th("Monthly", style={"padding": "10px 16px"}),
                    html.Th("Annual", style={"padding": "10px 16px"}),
                    html.Th("API", style={"padding": "10px 16px", "textAlign": "center"}),
                    html.Th("Key Features", style={"padding": "10px 16px"}),
                ], style={"backgroundColor": COLORS["sidebar"], "borderBottom": f"1px solid {COLORS['card_border']}"})),
                html.Tbody([
                    _plan_row("Start", "Annual only", "$13.33/mo", False, "3,500 lookups/mo, Extension + IP alerts"),
                    _plan_row("Pro", "$29.99/mo", "$24.99/mo", False, "10K lookups/mo, 2 seats, VPN"),
                    _plan_row("Business", "$79.99/mo", "$69.99/mo", True,
                              "150K scans/mo, Bulk tools, Zapier/Make, API"),
                    _plan_row("Business Plus", "$189.99/mo", "$159.99/mo", True,
                              "5 seats, Unlimited features, Full API"),
                    _plan_row("Agency", "From $399.99/mo", "Annual contract", True,
                              "Unlimited seats, Dedicated CSM, SSO"),
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse", "fontSize": "0.85rem"}),
            html.Div([
                link_button("View Pricing", "https://www.sellerassistant.app/pricing", "bi-currency-dollar"),
            ], style={"marginTop": "16px"}),
        ])),

        # ── Step 3: Connect Amazon ──
        step_card(3, "Connect Your Amazon Seller Account", "bi-amazon", html.Div([
            html.P("Required for live product data, restriction checks, and eligibility verification.",
                   style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
            html.Ol([
                html.Li("Log in to Seller Assistant"),
                html.Li("Go to Account Settings"),
                html.Li("Click \"Connect Amazon Account\""),
                html.Li("Sign in with your Amazon Seller Central credentials"),
                html.Li("Authorize the permissions requested"),
                html.Li("Select your marketplace(s)"),
            ], style={"color": COLORS["text_muted"], "fontSize": "0.9rem", "paddingLeft": "20px",
                       "display": "flex", "flexDirection": "column", "gap": "6px"}),
            html.Div([
                html.I(className="bi bi-globe me-2", style={"color": COLORS["info"]}),
                html.Strong("Supported marketplaces: ", style={"color": COLORS["text"]}),
                html.Span("US, CA, UK, DE, ES, IT, FR, IN, MX, BR",
                          style={"color": COLORS["text_muted"]}),
            ], style={
                "background": f"{COLORS['info']}10", "padding": "12px 16px",
                "borderRadius": "8px", "marginTop": "12px", "fontSize": "0.85rem",
            }),
        ])),

        # ── Step 4: Generate API Key ──
        step_card(4, "Generate Your API Key", "bi-key", html.Div([
            html.P([html.Strong("Requires Business plan or above", style={"color": COLORS["warning"]})],
                   style={"fontSize": "0.9rem"}),
            html.Ol([
                html.Li("Log in to Seller Assistant"),
                html.Li(["Navigate to ", html.Span("Profile → API Keys", style=CODE_STYLE),
                         " or go directly to:"]),
                html.Li([html.A("app.sellerassistant.app/settings/api-keys",
                               href="https://app.sellerassistant.app/settings/api-keys",
                               target="_blank", style=LINK_STYLE)]),
                html.Li("Click \"Generate API Key\""),
                html.Li("Give it a name (e.g. \"Keith Enterprises\")"),
                html.Li([html.Strong("Copy the key immediately"), " — it won't be shown again"]),
            ], style={"color": COLORS["text_muted"], "fontSize": "0.9rem", "paddingLeft": "20px",
                       "display": "flex", "flexDirection": "column", "gap": "6px"}),
            html.Div([
                html.I(className="bi bi-shield-lock me-2", style={"color": COLORS["warning"]}),
                html.Span("Store your API key securely. You can use it in two ways:",
                          style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
                html.Div([
                    html.Div([
                        html.Span("Query param: ", style={"color": COLORS["text_muted"]}),
                        html.Code("?api_key=YOUR_KEY", style=CODE_STYLE),
                    ], style={"marginTop": "8px"}),
                    html.Div([
                        html.Span("Header: ", style={"color": COLORS["text_muted"]}),
                        html.Code("X-Api-Key: YOUR_KEY", style=CODE_STYLE),
                    ], style={"marginTop": "4px"}),
                ]),
            ], style={
                "background": f"{COLORS['warning']}10", "padding": "16px",
                "borderRadius": "8px", "marginTop": "12px",
            }),
            html.Div([
                link_button("API Keys Settings", "https://app.sellerassistant.app/settings/api-keys", "bi-key"),
                link_button("API Developer Portal", "https://developer.sellerassistant.app/", "bi-code-slash"),
            ], style={"marginTop": "16px"}),
        ])),

        # ── Step 5: API Endpoints ──
        step_card(5, "Available API Endpoints", "bi-diagram-3", html.Div([
            html.P(["Base URL: ", html.Code("https://app.sellerassistant.app/api/v1/", style=CODE_STYLE)],
                   style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
            html.P(["Rate limit: ", html.Code("60 requests/minute", style=CODE_STYLE)],
                   style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
            html.Div([
                _endpoint("GET", "products/{asin}", "Get product info by ASIN and domain"),
                _endpoint("GET", "sales/bsr", "Sales estimation by BSR and category"),
                _endpoint("GET", "sales/asin", "Sales estimation by ASIN"),
                _endpoint("GET", "restrictions", "Check selling restrictions (ALLOWED / NOT_ELIGIBLE / APPROVAL_REQUIRED)"),
                _endpoint("GET", "upc-to-asin", "Convert UPC/EAN to ASIN"),
                _endpoint("GET", "asin-to-upc", "Convert ASIN to UPC/EAN/GTIN"),
                _endpoint("GET", "catalog/search", "Search catalog items (SP-API proxy)"),
                _endpoint("GET", "listings/search", "Search listings (SP-API proxy)"),
                _endpoint("PUT", "listings/item", "Put listings item (SP-API proxy)"),
            ]),
            html.Div([
                link_button("Full API Docs", "https://developer.sellerassistant.app/", "bi-book"),
            ], style={"marginTop": "16px"}),
        ])),

        # ── Step 6: Connect to Keith Enterprises ──
        step_card(6, "Connect to Keith Enterprises Dashboard", "bi-plug", html.Div([
            html.P("Once you have your API key, connect it to your main dashboard:",
                   style={"color": COLORS["text_muted"], "fontSize": "0.9rem"}),
            html.Ol([
                html.Li(["Go to your main dashboard: ",
                         html.A("http://localhost:5011/accounts", href="http://localhost:5011/accounts",
                                style=LINK_STYLE)]),
                html.Li("Scroll to the Seller Assistant section (green border)"),
                html.Li("Enter your account email and password"),
                html.Li("Paste your API key"),
                html.Li("Select your plan"),
                html.Li("Configure sync channels (Products, Restrictions, IP Alerts, Competitors)"),
                html.Li("Toggle \"Enable\" and click \"Save All Settings\""),
            ], style={"color": COLORS["text_muted"], "fontSize": "0.9rem", "paddingLeft": "20px",
                       "display": "flex", "flexDirection": "column", "gap": "6px"}),
            html.Div([
                html.I(className="bi bi-lightning-fill me-2", style={"color": COLORS["success"]}),
                html.Span("Your Seller Assistant data will be ingested and processed by Claude Code "
                          "for product insights, supplier evaluations, and market intelligence.",
                          style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
            ], style={
                "background": f"{COLORS['success']}10", "padding": "12px 16px",
                "borderRadius": "8px", "marginTop": "12px",
            }),
        ])),

        # ── Quick Links ──
        html.Div([
            html.H5([html.I(className="bi bi-link-45deg me-2", style={"color": COLORS["primary"]}),
                     "Quick Links"], style={"color": COLORS["text"], "marginBottom": "16px"}),
            html.Div([
                link_button("Register", "https://app.sellerassistant.app/register", "bi-person-plus"),
                link_button("Pricing", "https://www.sellerassistant.app/pricing", "bi-currency-dollar"),
                link_button("API Keys", "https://app.sellerassistant.app/settings/api-keys", "bi-key"),
                link_button("Developer Portal", "https://developer.sellerassistant.app/", "bi-code-slash"),
                link_button("API Docs", "https://www.sellerassistant.app/products/api", "bi-book"),
                link_button("Help Center", "https://help.sellerassistant.app/en/", "bi-question-circle"),
                link_button("Support Email", "mailto:support@sellerassistant.app", "bi-envelope"),
            ], style={"display": "flex", "flexWrap": "wrap"}),
        ], style=STEP_STYLE),

    ], style={"maxWidth": "900px", "margin": "0 auto", "padding": "0 24px 40px"}),
], style={"backgroundColor": COLORS["bg"], "minHeight": "100vh"})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5012)
