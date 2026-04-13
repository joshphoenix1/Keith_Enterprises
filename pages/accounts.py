import json
import os
from dash import html, dcc, callback, Input, Output, State, ctx
from config import COLORS
from components.forms import styled_input, styled_dropdown, form_group
from utils.rules import load_rules, save_rules

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "accounts.json")


def _load_accounts():
    with open(DATA_PATH) as f:
        return json.load(f)


def _save_accounts(data):
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _section_header(icon, title, subtitle, color):
    return html.Div([
        html.Div([
            html.I(className=f"bi {icon}",
                   style={"fontSize": "1.5rem", "color": color}),
        ], style={
            "width": "48px", "height": "48px", "borderRadius": "12px",
            "background": f"{color}15", "display": "flex",
            "alignItems": "center", "justifyContent": "center", "flexShrink": "0",
        }),
        html.Div([
            html.H5(title, style={"marginBottom": "2px", "color": COLORS["text"]}),
            html.P(subtitle, style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                    "marginBottom": "0"}),
        ]),
    ], style={"display": "flex", "gap": "16px", "alignItems": "center",
              "marginBottom": "20px"})


def _toggle_row(label, id, checked=False):
    return html.Div([
        html.Span(label, style={"color": COLORS["text"], "fontSize": "0.85rem"}),
        html.Div([
            dcc.Checklist(
                id=id,
                options=[{"label": " Enable", "value": "on"}],
                value=["on"] if checked else [],
                className="dark-toggle",
                style={"display": "inline-block"},
            ),
            html.Div(id=f"{id}-label"),
        ], style={"display": "flex", "alignItems": "center", "gap": "8px"}),
    ], style={"display": "flex", "justifyContent": "space-between",
              "alignItems": "center", "padding": "8px 0",
              "borderBottom": f"1px solid {COLORS['card_border']}", "marginBottom": "16px"})


def _pipeline_badge(source, target, color):
    return html.Div([
        html.Span(source, style={
            "background": f"{color}20", "color": color, "padding": "4px 10px",
            "borderRadius": "6px", "fontSize": "0.75rem", "fontWeight": "600",
        }),
        html.I(className="bi bi-arrow-right", style={"color": COLORS["text_muted"], "margin": "0 8px"}),
        html.Span(target, style={
            "background": f"{COLORS['purple']}20", "color": COLORS["purple"],
            "padding": "4px 10px", "borderRadius": "6px", "fontSize": "0.75rem", "fontWeight": "600",
        }),
    ], style={"display": "inline-flex", "alignItems": "center", "marginRight": "16px", "marginBottom": "8px"})


def _wa_connection_status():
    """Check WhatsApp bridge status and show QR code or connection info at page load."""
    try:
        from utils.whatsapp import test_connection, get_qr_code
        status = test_connection()

        if status.get("connected"):
            phone = status.get("phone_number", "")
            return html.Div([
                html.Div([
                    html.I(className="bi bi-check-circle-fill me-2",
                           style={"color": COLORS["success"], "fontSize": "1.1rem"}),
                    html.Span("WhatsApp Connected", style={
                        "color": COLORS["success"], "fontWeight": "700", "marginRight": "16px"}),
                    html.Span(f"Phone: +{phone}" if phone else "",
                              style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                ], style={"display": "flex", "alignItems": "center"}),
            ], style={
                "background": f"{COLORS['success']}12", "border": f"1px solid {COLORS['success']}40",
                "padding": "14px 18px", "borderRadius": "8px", "marginBottom": "16px",
            })

        # Not connected — try to show QR code
        qr = get_qr_code()
        if qr.get("qr"):
            return html.Div([
                html.Div([
                    html.I(className="bi bi-qr-code me-2",
                           style={"color": "#25D366", "fontSize": "1.1rem"}),
                    html.Span("Scan QR Code to Connect", style={
                        "color": "#25D366", "fontWeight": "700"}),
                ], style={"marginBottom": "12px"}),
                html.P([
                    html.Span("Android: ", style={"fontWeight": "600", "color": COLORS["text"]}),
                    "Open WhatsApp ",
                    html.Span("\u22EE", style={"fontWeight": "700", "fontSize": "1rem"}),
                    " (top right) \u2192 Linked Devices \u2192 Link a Device",
                ], style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                html.Div([
                    html.Img(src=qr["qr"],
                             style={"maxWidth": "280px", "borderRadius": "12px",
                                    "border": "2px solid #25D366"}),
                ], style={"textAlign": "center", "padding": "10px 0"}),
            ], style={
                "background": COLORS["card"], "padding": "20px",
                "borderRadius": "12px",
                "border": f"1px solid {COLORS['card_border']}", "marginBottom": "16px",
            })

        # Bridge not running or other error
        error = status.get("error", qr.get("error", ""))
        return html.Div([
            html.I(className="bi bi-exclamation-triangle-fill me-2",
                   style={"color": COLORS["warning"], "fontSize": "1.1rem"}),
            html.Span("WhatsApp Not Connected", style={
                "color": COLORS["warning"], "fontWeight": "700", "marginRight": "12px"}),
            html.Span(error, style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['warning']}12", "border": f"1px solid {COLORS['warning']}40",
            "padding": "14px 18px", "borderRadius": "8px", "marginBottom": "16px",
        })
    except Exception as e:
        return html.Div([
            html.I(className="bi bi-exclamation-triangle-fill me-2",
                   style={"color": COLORS["warning"]}),
            html.Span(f"Could not check WhatsApp status: {e}",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "padding": "14px 18px", "borderRadius": "8px", "marginBottom": "16px",
        })


def _oauth_status_banner():
    """Show OAuth connection status from ~/.claude/.credentials.json."""
    import os as _os
    creds_path = _os.path.expanduser("~/.claude/.credentials.json")
    has_oauth = False
    if _os.path.exists(creds_path):
        try:
            with open(creds_path) as f:
                creds = json.load(f)
            token = creds.get("claudeAiOauth", {}).get("accessToken", "")
            if token:
                has_oauth = True
        except Exception:
            pass

    if has_oauth:
        return html.Div([
            html.Div([
                html.I(className="bi bi-check-circle-fill me-2",
                       style={"color": COLORS["success"], "fontSize": "1.1rem"}),
                html.Span("OAuth Connected", style={
                    "color": COLORS["success"], "fontWeight": "700", "marginRight": "16px",
                }),
                html.Span("Using Claude Code OAuth session — billed to your Claude Max subscription",
                          style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"}),
            html.Div([
                html.Span("Token source: ", style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                html.Code("~/.claude/.credentials.json",
                          style={"color": COLORS["purple"], "fontSize": "0.75rem"}),
            ], style={"marginTop": "6px"}),
        ], style={
            "background": f"{COLORS['success']}12", "border": f"1px solid {COLORS['success']}40",
            "padding": "14px 18px", "borderRadius": "8px", "marginBottom": "16px",
        })
    else:
        return html.Div([
            html.Div([
                html.I(className="bi bi-exclamation-triangle-fill me-2",
                       style={"color": COLORS["warning"], "fontSize": "1.1rem"}),
                html.Span("OAuth Not Connected", style={
                    "color": COLORS["warning"], "fontWeight": "700", "marginRight": "16px",
                }),
                html.Span("Run ", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                html.Code("claude auth", style={"color": COLORS["primary"], "fontSize": "0.8rem"}),
                html.Span(" to connect, or add a fallback API key below.",
                          style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={"display": "flex", "alignItems": "center", "flexWrap": "wrap"}),
        ], style={
            "background": f"{COLORS['warning']}12", "border": f"1px solid {COLORS['warning']}40",
            "padding": "14px 18px", "borderRadius": "8px", "marginBottom": "16px",
        })


def layout():
    accounts = _load_accounts()
    sa = accounts.get("seller_assistant", {})
    wa = accounts.get("whatsapp", {})
    em = accounts.get("email", {})
    gd = accounts.get("google_drive", {})
    cl = accounts.get("claude_code", {})
    rules = load_rules()
    ar = rules.get("auto_reject", {})
    aa = rules.get("auto_accept", {})
    al = rules.get("alerts", {})

    # ── Data Pipeline Overview ──
    pipeline_section = html.Div([
        _section_header("bi-diagram-3", "Data Pipeline",
                        "Capture offers from WhatsApp/email, evaluate with AI, match to buyers",
                        COLORS["info"]),
        html.Div([
            _pipeline_badge("WhatsApp", "Offer Intake", "#25D366"),
            _pipeline_badge("Email", "Offer Intake", COLORS["primary"]),
            _pipeline_badge("Offers", "Claude AI", COLORS["warning"]),
            _pipeline_badge("Claude AI", "Buyer Match", COLORS["purple"]),
        ], style={"marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.I(className="bi bi-info-circle me-2", style={"color": COLORS["info"]}),
                html.Span("Offer flow: ", style={"color": COLORS["text_muted"]}),
                html.Span("WhatsApp/Email ", style={"color": COLORS["text"]}),
                html.I(className="bi bi-arrow-right mx-1", style={"color": COLORS["text_muted"]}),
                html.Span(" Capture & Extract ", style={"color": COLORS["text_muted"]}),
                html.I(className="bi bi-arrow-right mx-1", style={"color": COLORS["text_muted"]}),
                html.Span(" Evaluate (Amazon/Walmart) ", style={"color": COLORS["purple"]}),
                html.I(className="bi bi-arrow-right mx-1", style={"color": COLORS["text_muted"]}),
                html.Span(" Match Buyers", style={"color": COLORS["success"]}),
            ], style={"fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['info']}10", "padding": "12px 16px",
            "borderRadius": "8px",
        }),
    ])

    # ── Claude AI Section ──
    claude_form = html.Div([
        _section_header("bi-cpu", "Claude Code",
                        "Uses your Claude Code OAuth session — billed to your Claude subscription",
                        COLORS["purple"]),
        _oauth_status_banner(),
        _toggle_row("Claude Code Processing", "acct-cl-enabled", cl.get("enabled", False)),
        html.Div([
            html.I(className="bi bi-cpu me-2", style={"color": COLORS["text_muted"]}),
            html.Span("Model: ", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Span("claude-sonnet-4-6", style={"color": COLORS["primary"], "fontSize": "0.8rem",
                                                    "fontWeight": "600"}),
        ], style={"marginBottom": "16px"}),
        html.Div([
            form_group("API Key (fallback if OAuth disconnects)",
                       styled_input("acct-cl-apikey", "sk-ant-... (optional)", type="password",
                                    value=cl.get("api_key", "")),
                       "Only needed if OAuth token expires — leave blank to use OAuth only"),
        ], style={"marginBottom": "8px"}),
        _toggle_row("Process on Ingest", "acct-cl-autoproc", cl.get("process_on_ingest", True)),
        _toggle_row("Auto-Process Scheduled", "acct-cl-autorun", cl.get("auto_process", False)),
        html.Div([
            form_group("Processing Tasks",
                       dcc.Checklist(
                           id="acct-cl-tasks",
                           options=[
                               {"label": " Extract offer fields (UPC, price, qty)", "value": "extract_offers"},
                               {"label": " Auto-categorize products", "value": "categorize"},
                               {"label": " Cross-reference marketplace pricing", "value": "marketplace"},
                               {"label": " Buyer matching suggestions", "value": "buyer_match"},
                               {"label": " Summarize messages", "value": "summarize"},
                               {"label": " Image product extraction", "value": "image_scan"},
                           ],
                           value=cl.get("tasks", ["summarize", "extract_metrics", "sentiment"]),
                           className="dark-checklist",
                           style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                       )),
        ]),
        html.Div([
            html.I(className="bi bi-lightbulb me-2", style={"color": COLORS["warning"]}),
            html.Span("Claude processes incoming offers from WhatsApp and email to extract product details, "
                      "cross-reference marketplace pricing, and suggest buyer matches.",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['warning']}10", "padding": "12px 16px",
            "borderRadius": "8px", "marginTop": "8px",
        }),
    ])

    # ── Seller Assistant Section ──
    sa_form = html.Div([
        _section_header("bi-bag-check-fill", "Seller Assistant / SellersAmp",
                        "Cross-reference offers with Amazon/Walmart marketplace data",
                        COLORS["success"]),
        html.Div([
            html.Span("PRIMARY INTEGRATION", style={
                "background": f"{COLORS['success']}20", "color": COLORS["success"],
                "padding": "4px 12px", "borderRadius": "20px", "fontSize": "0.7rem",
                "fontWeight": "700",
            }),
        ], style={"marginBottom": "16px"}),
        _toggle_row("Seller Assistant Integration", "acct-sa-enabled", sa.get("enabled", False)),
        html.Div([
            form_group("Account Email",
                       styled_input("acct-sa-email", "your@email.com", type="text",
                                    value=sa.get("account_email", ""))),
            form_group("Account Password",
                       styled_input("acct-sa-password", "Password", type="password",
                                    value=sa.get("account_password", ""))),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("API Key",
                       styled_input("acct-sa-apikey", "Enter your Seller Assistant API key",
                                    type="password", value=sa.get("api_key", ""))),
            form_group("Plan",
                       styled_dropdown("acct-sa-plan",
                                       [{"label": p, "value": p} for p in
                                        ["Start", "Pro", "Business", "Business Plus", "Agency"]],
                                       sa.get("plan", "Pro"))),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("Webhook URL (for real-time data push)",
                       styled_input("acct-sa-webhook", "https://your-server.com/webhook",
                                    type="text", value=sa.get("webhook_url", ""))),
            form_group("Google Sheet ID (for Price List Analyzer sync)",
                       styled_input("acct-sa-gsheet", "Spreadsheet ID from URL",
                                    type="text", value=sa.get("google_sheet_id", ""))),
        ], className="grid-row grid-2"),
        _toggle_row("Auto Sync", "acct-sa-autosync", sa.get("auto_sync", False)),
        html.Div([
            form_group("Sync Frequency",
                       styled_dropdown("acct-sa-freq",
                                       [{"label": f, "value": f} for f in
                                        ["Real-time", "Every 15 min", "Hourly", "Daily"]],
                                       sa.get("sync_frequency", "Hourly"))),
        ], style={"maxWidth": "300px"}),
        html.Div([
            form_group("Data Channels to Sync",
                       dcc.Checklist(
                           id="acct-sa-channels",
                           options=[
                               {"label": " Product Lookups & Profit Data", "value": "sync_products"},
                               {"label": " Restriction Checks", "value": "sync_restrictions"},
                               {"label": " IP Complaint Alerts", "value": "sync_ip_alerts"},
                               {"label": " Competitor / Seller Spy Data", "value": "sync_competitors"},
                           ],
                           value=[k for k in ["sync_products", "sync_restrictions",
                                              "sync_ip_alerts", "sync_competitors"]
                                  if sa.get(k, True)],
                           className="dark-checklist",
                           style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                       )),
        ]),
        html.Div([
            html.I(className="bi bi-lightning-fill me-2", style={"color": COLORS["success"]}),
            html.Span("Seller Assistant API (Business+ plans) enables automated ingestion of product "
                      "lookups, bulk scan results, IP alerts, and competitor tracking data. "
                      "Data is processed by Claude AI for insights.",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['success']}10", "padding": "12px 16px",
            "borderRadius": "8px", "marginTop": "8px",
        }),
    ])

    # ── WhatsApp Section ──
    whatsapp_form = html.Div([
        _section_header("bi-whatsapp", "WhatsApp (Personal Account)",
                        "Connect your personal WhatsApp to receive supplier messages and product images",
                        "#25D366"),
        html.Div([
            html.I(className="bi bi-info-circle me-2", style={"color": "#25D366"}),
            html.Span("Self-hosted WhatsApp bridge (open source Baileys). Your data stays on your server. ",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Br(),
            html.Span("Start bridge: ", style={"color": COLORS["text"], "fontSize": "0.8rem", "fontWeight": "600"}),
            html.Code("docker compose -f docker-compose.whatsapp.yml up -d",
                      style={"color": COLORS["primary"], "fontSize": "0.75rem"}),
            html.Span(" — then click Show QR Code below and scan with your phone.",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": "#25D36610", "padding": "12px 16px",
            "borderRadius": "8px", "marginBottom": "16px", "lineHeight": "1.8",
            "border": "1px solid #25D36630",
        }),
        _toggle_row("WhatsApp Integration", "acct-wa-enabled", wa.get("enabled", False)),
        html.Div([
            form_group("Bridge URL",
                       styled_input("acct-wa-bridgeurl", "http://localhost:8085", type="text",
                                    value=wa.get("bridge_url", "http://localhost:8085")),
                       "Where the WhatsApp bridge Docker container is running"),
            form_group("Your Phone Number",
                       styled_input("acct-wa-phone", "+1 (555) 000-0000", type="text",
                                    value=wa.get("phone_number", "")),
                       "The personal number you'll link"),
        ], className="grid-row grid-2"),
        _toggle_row("Auto-Process Images with Claude AI", "acct-wa-autoprocess",
                     wa.get("auto_process_images", True)),
        _toggle_row("Send Notifications", "acct-wa-notify", wa.get("notifications", True)),

        # WhatsApp connection status / QR code (rendered at page load)
        _wa_connection_status(),

        # Action buttons
        html.Div([
            html.Button([
                html.I(className="bi bi-qr-code me-2"),
                "Refresh QR Code",
            ], id="acct-wa-create-btn", className="btn-outline-dark",
               style={"marginRight": "12px"}),
            html.Button([
                html.I(className="bi bi-broadcast me-2"),
                "Test Connection",
            ], id="acct-wa-test-btn", className="btn-outline-dark",
               style={"marginRight": "12px"}),
            html.Button([
                html.I(className="bi bi-send me-2"),
                "Send Test Message",
            ], id="acct-wa-sendtest-btn", className="btn-outline-dark"),
        ], style={"marginTop": "16px"}),

        # Single output area for all WA actions
        html.Div(id="acct-wa-action-result", style={"marginTop": "16px"}),
    ])

    # ── Email Section ──
    email_form = html.Div([
        _section_header("bi-envelope-fill", "Email",
                        "Ingest supplier quotes, shipping updates, and marketplace notifications",
                        COLORS["primary"]),
        _toggle_row("Email Integration", "acct-em-enabled", em.get("enabled", False)),
        html.Div([
            form_group("Email Provider",
                       styled_dropdown("acct-em-provider",
                                       [{"label": p, "value": p} for p in
                                        ["Gmail", "Outlook", "Yahoo", "Custom SMTP"]],
                                       em.get("provider", "Gmail"))),
            form_group("Email Address",
                       styled_input("acct-em-address", "you@example.com", type="text",
                                    value=em.get("email_address", ""))),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("SMTP Server",
                       styled_input("acct-em-smtp", "smtp.gmail.com", type="text",
                                    value=em.get("smtp_server", ""))),
            form_group("SMTP Port",
                       styled_input("acct-em-port", "587",
                                    value=em.get("smtp_port", 587))),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("Username",
                       styled_input("acct-em-user", "Username", type="text",
                                    value=em.get("username", ""))),
            form_group("Password",
                       styled_input("acct-em-pass", "Password", type="password",
                                    value=em.get("password", ""))),
        ], className="grid-row grid-2"),
        _toggle_row("Use TLS", "acct-em-tls", em.get("use_tls", True)),
        _toggle_row("Send Notifications", "acct-em-notify", em.get("notifications", True)),
    ])

    # ── Google Drive Section ──
    gdrive_form = html.Div([
        _section_header("bi-google", "Google Drive",
                        "Ingest spreadsheets, product research docs, and supplier catalogs",
                        COLORS["warning"]),
        _toggle_row("Google Drive Integration", "acct-gd-enabled", gd.get("enabled", False)),
        html.Div([
            form_group("Google Account Email",
                       styled_input("acct-gd-email", "you@gmail.com", type="text",
                                    value=gd.get("account_email", ""))),
            form_group("Folder ID",
                       styled_input("acct-gd-folder", "Drive folder ID", type="text",
                                    value=gd.get("folder_id", ""))),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("Client ID",
                       styled_input("acct-gd-clientid", "OAuth Client ID", type="text",
                                    value=gd.get("client_id", ""))),
            form_group("Client Secret",
                       styled_input("acct-gd-secret", "OAuth Client Secret", type="password",
                                    value=gd.get("client_secret", ""))),
        ], className="grid-row grid-2"),
        _toggle_row("Auto Backup", "acct-gd-autobackup", gd.get("auto_backup", False)),
        html.Div([
            form_group("Backup Frequency",
                       styled_dropdown("acct-gd-frequency",
                                       [{"label": f, "value": f} for f in
                                        ["Hourly", "Daily", "Weekly", "Monthly"]],
                                       gd.get("backup_frequency", "Daily"))),
        ], style={"maxWidth": "300px"}),
    ])

    # ── Filtering Rules Section ──
    rules_form = html.Div([
        _section_header("bi-funnel", "Offer Filtering Rules",
                        "Auto-accept or auto-reject offers based on margin and quantity thresholds",
                        COLORS["warning"]),

        # --- Auto-Reject ---
        html.Div([
            html.Div([
                html.I(className="bi bi-x-circle me-2", style={"color": COLORS["danger"]}),
                html.Span("Auto-Reject Thresholds", style={
                    "color": COLORS["danger"], "fontWeight": "600", "fontSize": "0.9rem",
                }),
            ], style={"marginBottom": "12px"}),
            html.P("Offers failing ANY of these thresholds will be automatically rejected.",
                   style={"color": COLORS["text_muted"], "fontSize": "0.8rem", "marginBottom": "12px"}),
        ]),
        _toggle_row("Auto-Reject Enabled", "acct-rule-ar-enabled", ar.get("enabled", True)),
        html.Div([
            form_group("Min Margin % (vs Amazon price)",
                       styled_input("acct-rule-ar-margin", "15", type="number",
                                    value=ar.get("min_margin_pct", 15))),
            form_group("Min Quantity",
                       styled_input("acct-rule-ar-qty", "50", type="number",
                                    value=ar.get("min_quantity", 50))),
            form_group("Max Offer Price $",
                       styled_input("acct-rule-ar-maxprice", "100", type="number",
                                    value=ar.get("max_offer_price", 100))),
        ], className="grid-row grid-3"),

        # Divider
        html.Hr(style={"borderColor": COLORS["card_border"], "margin": "24px 0"}),

        # --- Auto-Accept ---
        html.Div([
            html.Div([
                html.I(className="bi bi-check-circle me-2", style={"color": COLORS["success"]}),
                html.Span("Auto-Accept Thresholds", style={
                    "color": COLORS["success"], "fontWeight": "600", "fontSize": "0.9rem",
                }),
            ], style={"marginBottom": "12px"}),
            html.P("Offers meeting ALL of these thresholds will be auto-accepted and matched to buyers.",
                   style={"color": COLORS["text_muted"], "fontSize": "0.8rem", "marginBottom": "12px"}),
        ]),
        _toggle_row("Auto-Accept Enabled", "acct-rule-aa-enabled", aa.get("enabled", True)),
        html.Div([
            form_group("Min Margin % (vs Amazon price)",
                       styled_input("acct-rule-aa-margin", "35", type="number",
                                    value=aa.get("min_margin_pct", 35))),
            form_group("Min Quantity",
                       styled_input("acct-rule-aa-qty", "100", type="number",
                                    value=aa.get("min_quantity", 100))),
            form_group("Min Amazon Price $",
                       styled_input("acct-rule-aa-amzprice", "10", type="number",
                                    value=aa.get("min_amazon_price", 10))),
        ], className="grid-row grid-3"),

        # Divider
        html.Hr(style={"borderColor": COLORS["card_border"], "margin": "24px 0"}),

        # --- Alerts ---
        html.Div([
            html.Div([
                html.I(className="bi bi-bell me-2", style={"color": COLORS["info"]}),
                html.Span("Alert Thresholds", style={
                    "color": COLORS["info"], "fontWeight": "600", "fontSize": "0.9rem",
                }),
            ], style={"marginBottom": "12px"}),
            html.P("Get notified when offers hit these standout thresholds.",
                   style={"color": COLORS["text_muted"], "fontSize": "0.8rem", "marginBottom": "12px"}),
        ]),
        html.Div([
            form_group("High Margin Threshold %",
                       styled_input("acct-rule-al-margin", "50", type="number",
                                    value=al.get("high_margin_threshold", 50))),
            form_group("Large Quantity Threshold",
                       styled_input("acct-rule-al-qty", "1000", type="number",
                                    value=al.get("large_quantity_threshold", 1000))),
        ], className="grid-row grid-2"),
        _toggle_row("Notify on High-Value Offers", "acct-rule-al-notify", al.get("notify_on_high_value", True)),

        # Info tip
        html.Div([
            html.I(className="bi bi-info-circle me-2", style={"color": COLORS["info"]}),
            html.Span("Rules are evaluated in order: auto-reject first (any threshold breach), "
                      "then auto-accept (all thresholds must pass). Offers that match neither "
                      "go to manual review in the Offers page.",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['info']}10", "padding": "12px 16px",
            "borderRadius": "8px", "marginTop": "8px",
        }),
    ])

    return html.Div([
        html.Div([
            html.H2("Accounts & Integrations"),
            html.P("Connect intake channels, configure AI processing, and set offer evaluation rules"),
        ], className="page-header"),

        # Pipeline overview
        html.Div([pipeline_section], className="dash-card", style={"marginBottom": "20px"}),

        # Claude AI — top since it's the processing engine
        html.Div([claude_form], className="dash-card", style={"marginBottom": "20px"}),

        # Data sources
        html.Div([
            html.Div([
                html.I(className="bi bi-database me-2", style={"color": COLORS["primary"]}),
                html.H6("Data Sources", className="mb-0",
                         style={"color": COLORS["text"], "fontWeight": "600", "display": "inline"}),
            ], style={"marginBottom": "20px"}),
        ]),
        html.Div([sa_form], className="dash-card",
                 style={"marginBottom": "20px", "border": f"1px solid {COLORS['success']}40"}),
        html.Div([whatsapp_form], className="dash-card", style={"marginBottom": "20px"}),
        html.Div([email_form], className="dash-card", style={"marginBottom": "20px"}),
        html.Div([gdrive_form], className="dash-card", style={"marginBottom": "20px"}),

        # Filtering Rules — before save button
        html.Div([rules_form], className="dash-card",
                 style={"marginBottom": "20px", "border": f"1px solid {COLORS['warning']}40"}),

        # Save button
        html.Div([
            html.Button([html.I(className="bi bi-check-circle me-2"), "Save All Settings"],
                        id="acct-save-btn", className="btn-primary-dark",
                        style={"marginRight": "12px"}),
            html.Button([html.I(className="bi bi-arrow-counterclockwise me-2"), "Reset"],
                        id="acct-reset-btn", className="btn-outline-dark"),
            html.Div(id="acct-save-status", style={"marginTop": "12px"}),
        ]),
    ])


_TOGGLE_IDS = [
    "acct-cl-enabled", "acct-cl-autoproc", "acct-cl-autorun",
    "acct-sa-enabled", "acct-sa-autosync",
    "acct-wa-enabled", "acct-wa-autoprocess", "acct-wa-notify",
    "acct-em-enabled", "acct-em-tls", "acct-em-notify",
    "acct-gd-enabled", "acct-gd-autobackup",
    "acct-rule-ar-enabled", "acct-rule-aa-enabled", "acct-rule-al-notify",
]

for _tid in _TOGGLE_IDS:
    @callback(
        Output(f"{_tid}-label", "children"),
        Input(_tid, "value"),
    )
    def _update_toggle_label(value, _id=_tid):
        is_on = bool(value and "on" in value)
        return html.Span(
            "Enabled" if is_on else "Disabled",
            style={"color": COLORS["success"] if is_on else COLORS["text_muted"],
                   "fontSize": "0.8rem", "fontWeight": "600"},
        )


@callback(
    Output("acct-save-status", "children"),
    Input("acct-save-btn", "n_clicks"),
    # Seller Assistant
    State("acct-sa-enabled", "value"),
    State("acct-sa-apikey", "value"),
    State("acct-sa-plan", "value"),
    State("acct-sa-webhook", "value"),
    State("acct-sa-gsheet", "value"),
    State("acct-sa-autosync", "value"),
    State("acct-sa-freq", "value"),
    State("acct-sa-channels", "value"),
    State("acct-sa-email", "value"),
    State("acct-sa-password", "value"),
    # Claude AI
    State("acct-cl-enabled", "value"),
    State("acct-cl-apikey", "value"),
    State("acct-cl-autoproc", "value"),
    State("acct-cl-autorun", "value"),
    State("acct-cl-tasks", "value"),
    # WhatsApp (Bridge)
    State("acct-wa-enabled", "value"),
    State("acct-wa-bridgeurl", "value"),
    State("acct-wa-phone", "value"),
    State("acct-wa-autoprocess", "value"),
    State("acct-wa-notify", "value"),
    # Email
    State("acct-em-enabled", "value"),
    State("acct-em-provider", "value"),
    State("acct-em-address", "value"),
    State("acct-em-smtp", "value"),
    State("acct-em-port", "value"),
    State("acct-em-user", "value"),
    State("acct-em-pass", "value"),
    State("acct-em-tls", "value"),
    State("acct-em-notify", "value"),
    # Google Drive
    State("acct-gd-enabled", "value"),
    State("acct-gd-email", "value"),
    State("acct-gd-folder", "value"),
    State("acct-gd-clientid", "value"),
    State("acct-gd-secret", "value"),
    State("acct-gd-autobackup", "value"),
    State("acct-gd-frequency", "value"),
    # Filtering Rules — Auto-Reject
    State("acct-rule-ar-enabled", "value"),
    State("acct-rule-ar-margin", "value"),
    State("acct-rule-ar-qty", "value"),
    State("acct-rule-ar-maxprice", "value"),
    # Filtering Rules — Auto-Accept
    State("acct-rule-aa-enabled", "value"),
    State("acct-rule-aa-margin", "value"),
    State("acct-rule-aa-qty", "value"),
    State("acct-rule-aa-amzprice", "value"),
    # Filtering Rules — Alerts
    State("acct-rule-al-margin", "value"),
    State("acct-rule-al-qty", "value"),
    State("acct-rule-al-notify", "value"),
    prevent_initial_call=True,
)
def save_accounts(n_clicks,
                  sa_enabled, sa_apikey, sa_plan, sa_webhook, sa_gsheet, sa_autosync, sa_freq, sa_channels, sa_email, sa_password,
                  cl_enabled, cl_api_key, cl_autoproc, cl_autorun, cl_tasks,
                  wa_enabled, wa_bridgeurl, wa_phone, wa_autoprocess, wa_notify,
                  em_enabled, em_provider, em_address, em_smtp, em_port, em_user, em_pass, em_tls, em_notify,
                  gd_enabled, gd_email, gd_folder, gd_clientid, gd_secret, gd_autobackup, gd_frequency,
                  rule_ar_enabled, rule_ar_margin, rule_ar_qty, rule_ar_maxprice,
                  rule_aa_enabled, rule_aa_margin, rule_aa_qty, rule_aa_amzprice,
                  rule_al_margin, rule_al_qty, rule_al_notify):
    sa_ch = sa_channels or []
    data = {
        "seller_assistant": {
            "enabled": bool(sa_enabled),
            "api_key": sa_apikey or "",
            "plan": sa_plan or "Pro",
            "webhook_url": sa_webhook or "",
            "google_sheet_id": sa_gsheet or "",
            "auto_sync": bool(sa_autosync),
            "sync_frequency": sa_freq or "Hourly",
            "sync_products": "sync_products" in sa_ch,
            "sync_restrictions": "sync_restrictions" in sa_ch,
            "sync_ip_alerts": "sync_ip_alerts" in sa_ch,
            "sync_competitors": "sync_competitors" in sa_ch,
            "account_email": sa_email or "",
            "account_password": sa_password or "",
        },
        "claude_code": {
            "enabled": bool(cl_enabled),
            "model": "claude-sonnet-4-6",
            "api_key": cl_api_key or "",
            "process_on_ingest": bool(cl_autoproc),
            "auto_process": bool(cl_autorun),
            "tasks": cl_tasks or [],
        },
        "whatsapp": {
            "enabled": bool(wa_enabled),
            "bridge_url": wa_bridgeurl or "http://localhost:8085",
            "api_key": "keith-enterprises-wa-key",
            "phone_number": wa_phone or "",
            "auto_process_images": bool(wa_autoprocess),
            "notifications": bool(wa_notify),
        },
        "email": {
            "enabled": bool(em_enabled),
            "provider": em_provider or "Gmail",
            "email_address": em_address or "",
            "smtp_server": em_smtp or "",
            "smtp_port": int(em_port or 587),
            "username": em_user or "",
            "password": em_pass or "",
            "use_tls": bool(em_tls),
            "notifications": bool(em_notify),
        },
        "google_drive": {
            "enabled": bool(gd_enabled),
            "account_email": gd_email or "",
            "client_id": gd_clientid or "",
            "client_secret": gd_secret or "",
            "folder_id": gd_folder or "",
            "auto_backup": bool(gd_autobackup),
            "backup_frequency": gd_frequency or "Daily",
        },
    }
    _save_accounts(data)

    # Save filtering rules
    rules_data = {
        "auto_reject": {
            "enabled": bool(rule_ar_enabled and "on" in rule_ar_enabled),
            "min_margin_pct": float(rule_ar_margin or 15),
            "min_quantity": int(rule_ar_qty or 50),
            "max_offer_price": float(rule_ar_maxprice or 100),
        },
        "auto_accept": {
            "enabled": bool(rule_aa_enabled and "on" in rule_aa_enabled),
            "min_margin_pct": float(rule_aa_margin or 35),
            "min_quantity": int(rule_aa_qty or 100),
            "min_amazon_price": float(rule_aa_amzprice or 10),
        },
        "alerts": {
            "high_margin_threshold": float(rule_al_margin or 50),
            "large_quantity_threshold": int(rule_al_qty or 1000),
            "notify_on_high_value": bool(rule_al_notify and "on" in rule_al_notify),
        },
    }
    save_rules(rules_data)

    sources = sum([data["seller_assistant"]["enabled"], data["whatsapp"]["enabled"],
                   data["email"]["enabled"], data["google_drive"]["enabled"]])
    ai = "active" if data["claude_code"]["enabled"] else "inactive"

    return html.Div([
        html.I(className="bi bi-check-circle-fill me-2",
               style={"color": COLORS["success"]}),
        html.Span(f"Settings saved! {sources}/4 data sources connected, Claude Code {ai}. Filtering rules updated.",
                  style={"color": COLORS["success"], "fontWeight": "500"}),
    ], style={"fontSize": "0.9rem"})


@callback(
    Output("acct-wa-action-result", "children"),
    Input("acct-wa-create-btn", "n_clicks"),
    Input("acct-wa-test-btn", "n_clicks"),
    Input("acct-wa-sendtest-btn", "n_clicks"),
    State("acct-wa-phone", "value"),
    prevent_initial_call=True,
)
def handle_whatsapp_actions(create_clicks, test_clicks, send_clicks, phone_number):
    triggered = ctx.triggered_id

    def _badge(msg, color, icon):
        return html.Div([
            html.I(className=f"bi {icon} me-2", style={"color": color}),
            html.Span(msg, style={"color": color, "fontWeight": "500", "fontSize": "0.85rem"}),
        ], style={"background": f"{color}15", "padding": "10px 14px", "borderRadius": "8px"})

    if triggered == "acct-wa-create-btn":
        try:
            from utils.whatsapp import get_qr_code
            result = get_qr_code()
            if result.get("connected"):
                return _badge(f"Already connected! Phone: {result.get('phone', '')}", COLORS["success"], "bi-check-circle-fill")
            elif result.get("qr"):
                return html.Div([
                    _badge("Scan the QR code below with your WhatsApp", COLORS["warning"], "bi-exclamation-triangle"),
                    html.Div([
                        html.P([
                            html.Span("Android: ", style={"fontWeight": "600", "color": COLORS["text"]}),
                            "Open WhatsApp \u22EE (top right) \u2192 Linked Devices \u2192 Link a Device",
                        ], style={"color": COLORS["text_muted"], "fontSize": "0.8rem", "marginBottom": "12px"}),
                        html.Img(src=result["qr"],
                                 style={"maxWidth": "280px", "borderRadius": "12px",
                                        "border": "2px solid #25D366"}),
                    ], style={"textAlign": "center", "padding": "16px",
                              "background": COLORS["card"], "borderRadius": "12px",
                              "border": f"1px solid {COLORS['card_border']}", "marginTop": "12px"}),
                ])
            else:
                return _badge(result.get("error", "Unknown error"), COLORS["danger"], "bi-x-circle-fill")
        except Exception as e:
            return _badge(f"Error: {e}", COLORS["danger"], "bi-x-circle-fill")

    elif triggered == "acct-wa-test-btn":
        try:
            from utils.whatsapp import test_connection
            result = test_connection()
            if result.get("connected"):
                phone = result.get("phone_number", "")
                return _badge(f"Connected! Phone: +{phone}" if phone else "Connected!", COLORS["success"], "bi-check-circle-fill")
            else:
                return _badge(result.get("error", "Unknown error"), COLORS["danger"], "bi-x-circle-fill")
        except Exception as e:
            return _badge(f"Error: {e}", COLORS["danger"], "bi-x-circle-fill")

    elif triggered == "acct-wa-sendtest-btn":
        if not phone_number:
            return _badge("Enter your phone number first.", COLORS["warning"], "bi-exclamation-triangle")
        try:
            from utils.whatsapp import send_message
            result = send_message(phone_number, "Keith Enterprises test — WhatsApp integration is working!")
            if result.get("success"):
                return _badge(f"Test message sent to {phone_number}!", COLORS["success"], "bi-check-circle-fill")
            else:
                return _badge(f"Failed: {result.get('error', 'Unknown')}", COLORS["danger"], "bi-x-circle-fill")
        except Exception as e:
            return _badge(f"Error: {e}", COLORS["danger"], "bi-x-circle-fill")

    return ""
