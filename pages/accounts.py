import json
import os
from dash import html, dcc, callback, Input, Output, State
from config import COLORS
from components.forms import styled_input, styled_dropdown, form_group

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

    # ── Data Pipeline Overview ──
    pipeline_section = html.Div([
        _section_header("bi-diagram-3", "Data Pipeline",
                        "Ingest data from connected sources, process with Claude AI, and output insights",
                        COLORS["info"]),
        html.Div([
            _pipeline_badge("Seller Assistant", "Claude AI", COLORS["success"]),
            _pipeline_badge("WhatsApp", "Claude AI", "#25D366"),
            _pipeline_badge("Email", "Claude AI", COLORS["primary"]),
            _pipeline_badge("Google Drive", "Claude AI", COLORS["warning"]),
        ], style={"marginBottom": "16px"}),
        html.Div([
            html.Div([
                html.I(className="bi bi-info-circle me-2", style={"color": COLORS["info"]}),
                html.Span("Data flows: Sources ", style={"color": COLORS["text_muted"]}),
                html.I(className="bi bi-arrow-right mx-1", style={"color": COLORS["text_muted"]}),
                html.Span(" Ingest ", style={"color": COLORS["text_muted"]}),
                html.I(className="bi bi-arrow-right mx-1", style={"color": COLORS["text_muted"]}),
                html.Span(" Claude AI Processing ", style={"color": COLORS["purple"]}),
                html.I(className="bi bi-arrow-right mx-1", style={"color": COLORS["text_muted"]}),
                html.Span(" Dashboard Insights", style={"color": COLORS["success"]}),
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
            form_group("Model",
                       styled_dropdown("acct-cl-model",
                                       [{"label": m, "value": m} for m in [
                                           "claude-opus-4-6",
                                           "claude-sonnet-4-6",
                                           "claude-haiku-4-5-20251001",
                                       ]],
                                       cl.get("model", "claude-sonnet-4-6"))),
        ], className="grid-row grid-2"),
        _toggle_row("Process on Ingest", "acct-cl-autoproc", cl.get("process_on_ingest", True)),
        _toggle_row("Auto-Process Scheduled", "acct-cl-autorun", cl.get("auto_process", False)),
        html.Div([
            form_group("Processing Tasks",
                       dcc.Checklist(
                           id="acct-cl-tasks",
                           options=[
                               {"label": " Summarize content", "value": "summarize"},
                               {"label": " Extract key metrics", "value": "extract_metrics"},
                               {"label": " Sentiment analysis", "value": "sentiment"},
                               {"label": " Competitor insights", "value": "competitor"},
                               {"label": " Product feasibility scoring", "value": "feasibility"},
                               {"label": " Risk assessment", "value": "risk"},
                           ],
                           value=cl.get("tasks", ["summarize", "extract_metrics", "sentiment"]),
                           className="dark-checklist",
                           style={"display": "flex", "flexDirection": "column", "gap": "8px"},
                       )),
        ]),
        html.Div([
            html.I(className="bi bi-lightbulb me-2", style={"color": COLORS["warning"]}),
            html.Span("Claude processes ingested data from Seller Assistant, WhatsApp, emails, and Drive files "
                      "to extract product insights, supplier evaluations, and market intelligence.",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['warning']}10", "padding": "12px 16px",
            "borderRadius": "8px", "marginTop": "8px",
        }),
    ])

    # ── Seller Assistant Section ──
    sa_form = html.Div([
        _section_header("bi-bag-check-fill", "Seller Assistant",
                        "Primary tool — ingest product lookups, IP alerts, restrictions, and competitor data",
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
        _section_header("bi-whatsapp", "WhatsApp",
                        "Ingest supplier messages, order confirmations, and negotiation threads",
                        "#25D366"),
        _toggle_row("WhatsApp Integration", "acct-wa-enabled", wa.get("enabled", False)),
        html.Div([
            form_group("Phone Number",
                       styled_input("acct-wa-phone", "+1 (555) 000-0000", type="text",
                                    value=wa.get("phone_number", ""))),
            form_group("Business Name",
                       styled_input("acct-wa-business", "My Business", type="text",
                                    value=wa.get("business_name", ""))),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("API Key",
                       styled_input("acct-wa-apikey", "Enter your API key", type="password",
                                    value=wa.get("api_key", ""))),
            form_group("Webhook URL",
                       styled_input("acct-wa-webhook", "https://...", type="text",
                                    value=wa.get("webhook_url", ""))),
        ], className="grid-row grid-2"),
        _toggle_row("Send Notifications", "acct-wa-notify", wa.get("notifications", True)),
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

    return html.Div([
        html.Div([
            html.H2("Accounts & Integrations"),
            html.P("Connect data sources, configure AI processing, and manage your integration pipeline"),
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
    "acct-wa-enabled", "acct-wa-notify",
    "acct-em-enabled", "acct-em-tls", "acct-em-notify",
    "acct-gd-enabled", "acct-gd-autobackup",
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
    State("acct-cl-model", "value"),
    State("acct-cl-autoproc", "value"),
    State("acct-cl-autorun", "value"),
    State("acct-cl-tasks", "value"),
    # WhatsApp
    State("acct-wa-enabled", "value"),
    State("acct-wa-phone", "value"),
    State("acct-wa-business", "value"),
    State("acct-wa-apikey", "value"),
    State("acct-wa-webhook", "value"),
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
    prevent_initial_call=True,
)
def save_accounts(n_clicks,
                  sa_enabled, sa_apikey, sa_plan, sa_webhook, sa_gsheet, sa_autosync, sa_freq, sa_channels, sa_email, sa_password,
                  cl_enabled, cl_model, cl_autoproc, cl_autorun, cl_tasks,
                  wa_enabled, wa_phone, wa_business, wa_apikey, wa_webhook, wa_notify,
                  em_enabled, em_provider, em_address, em_smtp, em_port, em_user, em_pass, em_tls, em_notify,
                  gd_enabled, gd_email, gd_folder, gd_clientid, gd_secret, gd_autobackup, gd_frequency):
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
            "model": cl_model or "claude-sonnet-4-6",
            "process_on_ingest": bool(cl_autoproc),
            "auto_process": bool(cl_autorun),
            "tasks": cl_tasks or [],
        },
        "whatsapp": {
            "enabled": bool(wa_enabled),
            "phone_number": wa_phone or "",
            "business_name": wa_business or "",
            "api_key": wa_apikey or "",
            "webhook_url": wa_webhook or "",
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

    sources = sum([data["seller_assistant"]["enabled"], data["whatsapp"]["enabled"],
                   data["email"]["enabled"], data["google_drive"]["enabled"]])
    ai = "active" if data["claude_code"]["enabled"] else "inactive"

    return html.Div([
        html.I(className="bi bi-check-circle-fill me-2",
               style={"color": COLORS["success"]}),
        html.Span(f"Settings saved! {sources}/4 data sources connected, Claude Code {ai}.",
                  style={"color": COLORS["success"], "fontWeight": "500"}),
    ], style={"fontSize": "0.9rem"})
