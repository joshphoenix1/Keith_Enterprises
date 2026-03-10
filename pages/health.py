"""System Health dashboard — live monitoring and auto-heal log."""

from dash import html, dcc, callback, Input, Output
from config import COLORS
from components.cards import kpi_card, info_card
from components.pills import pill


STATUS_COLORS = {
    "pass": COLORS["success"],
    "warn": COLORS["warning"],
    "fail": COLORS["danger"],
    "healthy": COLORS["success"],
    "degraded": COLORS["warning"],
    "critical": COLORS["danger"],
}

STATUS_LABELS = {
    "healthy": "All Systems Operational",
    "degraded": "Degraded — Issues Detected",
    "critical": "Critical — Failures Found",
}

CATEGORY_ICONS = {
    "data": "bi-database",
    "filesystem": "bi-folder2",
    "pages": "bi-file-code",
    "dependencies": "bi-box-seam",
    "oauth": "bi-shield-lock",
    "port": "bi-hdd-network",
    "callbacks": "bi-diagram-3",
}

CATEGORY_LABELS = {
    "data": "Data Files",
    "filesystem": "Filesystem",
    "pages": "Pages & Rendering",
    "dependencies": "Dependencies",
    "oauth": "OAuth / Credentials",
    "port": "Port & Network",
    "callbacks": "Callback Registry",
}


def _status_dot(status, size="10px"):
    color = STATUS_COLORS.get(status, COLORS["text_muted"])
    return html.Span(style={
        "width": size, "height": size, "borderRadius": "50%",
        "backgroundColor": color, "display": "inline-block",
        "flexShrink": "0",
    })


def _time_ago(iso_ts):
    """Convert ISO timestamp to relative time string."""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(iso_ts)
        diff = datetime.now() - dt
        secs = int(diff.total_seconds())
        if secs < 5:
            return "just now"
        if secs < 60:
            return f"{secs}s ago"
        if secs < 3600:
            return f"{secs // 60}m ago"
        if secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:
        return "—"


def _build_dashboard(latest, history):
    """Build the full health dashboard from latest report and history."""
    if not latest:
        return html.Div([
            html.Div([
                html.I(className="bi bi-hourglass-split",
                       style={"fontSize": "2rem", "color": COLORS["text_muted"],
                              "display": "block", "marginBottom": "12px"}),
                html.P("Health check initializing...",
                       style={"color": COLORS["text_muted"]}),
                html.P("First check will run in a few seconds.",
                       style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={"textAlign": "center", "padding": "60px 20px"}),
        ])

    overall = latest.get("overall_status", "healthy")
    overall_color = STATUS_COLORS.get(overall, COLORS["text_muted"])
    checks = latest.get("checks", [])

    # ── Status banner ──
    status_banner = html.Div([
        html.Div([
            html.Div(style={
                "width": "16px", "height": "16px", "borderRadius": "50%",
                "backgroundColor": overall_color,
                "animation": "pulse 2s infinite" if overall != "healthy" else "none",
                "flexShrink": "0",
            }),
            html.Span(STATUS_LABELS.get(overall, overall.title()), style={
                "color": overall_color, "fontWeight": "700", "fontSize": "1.1rem",
            }),
        ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
        html.Div([
            html.Span(f"Last check: {_time_ago(latest.get('timestamp', ''))}",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            html.Span(f" · {latest.get('duration_ms', 0)}ms",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ]),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "background": f"{overall_color}10", "border": f"1px solid {overall_color}40",
        "padding": "16px 20px", "borderRadius": "10px", "marginBottom": "20px",
    })

    # ── KPI row ──
    total_healed_all_time = sum(r.get("healed", 0) for r in history)
    pass_rate = round(latest["passed"] / latest["total_checks"] * 100) if latest["total_checks"] else 0
    pass_color = COLORS["success"] if pass_rate == 100 else COLORS["warning"] if pass_rate >= 90 else COLORS["danger"]

    kpi_row = html.Div([
        kpi_card("Total Checks", str(latest["total_checks"]), "bi-clipboard-check", COLORS["primary"]),
        kpi_card("Pass Rate", f"{pass_rate}%", "bi-check-circle", pass_color),
        kpi_card("Warnings", str(latest["warnings"]), "bi-exclamation-triangle",
                 COLORS["warning"] if latest["warnings"] else COLORS["text_muted"]),
        kpi_card("Auto-Healed", str(total_healed_all_time), "bi-bandaid",
                 COLORS["info"] if total_healed_all_time else COLORS["text_muted"],
                 subtitle=f"{latest['healed']} this check" if latest["healed"] else None),
    ], className="grid-row grid-4", style={"marginBottom": "20px"})

    # ── Category status grid ──
    categories = {}
    for c in checks:
        cat = c["category"]
        if cat not in categories:
            categories[cat] = {"pass": 0, "warn": 0, "fail": 0, "healed": 0, "total": 0}
        categories[cat]["total"] += 1
        categories[cat][c["status"]] += 1
        if c.get("healed"):
            categories[cat]["healed"] += 1

    cat_cards = []
    for cat_key in ["data", "filesystem", "pages", "dependencies", "oauth", "port", "callbacks"]:
        if cat_key not in categories:
            continue
        cat = categories[cat_key]
        icon = CATEGORY_ICONS.get(cat_key, "bi-question-circle")
        label = CATEGORY_LABELS.get(cat_key, cat_key.title())

        if cat["fail"] > 0:
            cat_status = "fail"
        elif cat["warn"] > 0:
            cat_status = "warn"
        else:
            cat_status = "pass"
        cat_color = STATUS_COLORS[cat_status]

        healed_text = f", {cat['healed']} healed" if cat["healed"] else ""
        summary = f"{cat['pass']}/{cat['total']} passing{healed_text}"

        cat_cards.append(html.Div([
            html.Div([
                html.I(className=f"bi {icon}", style={"color": cat_color, "fontSize": "1.2rem"}),
                html.Div([
                    html.Div(label, style={
                        "color": COLORS["text"], "fontWeight": "600", "fontSize": "0.85rem",
                    }),
                    html.Div(summary, style={
                        "color": COLORS["text_muted"], "fontSize": "0.75rem",
                    }),
                ]),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center"}),
            _status_dot(cat_status, "12px"),
        ], className="dash-card", style={
            "display": "flex", "justifyContent": "space-between", "alignItems": "center",
            "borderLeft": f"3px solid {cat_color}",
        }))

    cat_grid = html.Div(cat_cards, className="grid-row grid-3" if len(cat_cards) > 3 else "grid-row grid-2",
                        style={"marginBottom": "20px"})

    # ── Detailed checks table ──
    # Sort: failures first, then warnings, then passes
    sort_order = {"fail": 0, "warn": 1, "pass": 2}
    sorted_checks = sorted(checks, key=lambda c: sort_order.get(c["status"], 3))

    check_rows = []
    for c in sorted_checks:
        status_color = STATUS_COLORS.get(c["status"], COLORS["text_muted"])
        healed_badge = None
        if c.get("healed"):
            healed_badge = html.Span([
                html.I(className="bi bi-bandaid me-1"),
                "Healed",
            ], style={
                "background": f"{COLORS['info']}20", "color": COLORS["info"],
                "padding": "2px 8px", "borderRadius": "10px",
                "fontSize": "0.7rem", "fontWeight": "600",
            })

        heal_detail = None
        if c.get("heal_action"):
            heal_detail = html.Div([
                html.I(className="bi bi-wrench me-1", style={"color": COLORS["info"]}),
                html.Span(c["heal_action"], style={
                    "color": COLORS["info"], "fontSize": "0.75rem",
                }),
            ], style={"marginTop": "4px"})

        check_rows.append(html.Div([
            html.Div([
                _status_dot(c["status"]),
                html.Div([
                    html.Div([
                        html.Span(c["name"], style={
                            "color": COLORS["text"], "fontWeight": "500",
                            "fontSize": "0.85rem",
                        }),
                        html.Span(f" · {CATEGORY_LABELS.get(c['category'], c['category'])}",
                                  style={"color": COLORS["text_muted"], "fontSize": "0.75rem"}),
                    ]),
                    html.Div(c["message"], style={
                        "color": COLORS["text_muted"], "fontSize": "0.8rem",
                        "marginTop": "2px", "whiteSpace": "pre-wrap",
                    }),
                    heal_detail,
                ], style={"flex": "1"}),
                healed_badge,
            ], style={"display": "flex", "gap": "12px", "alignItems": "flex-start"}),
        ], style={
            "padding": "10px 14px",
            "borderBottom": f"1px solid {COLORS['card_border']}",
            "background": f"{status_color}05" if c["status"] != "pass" else "transparent",
        }))

    checks_section = info_card("All Checks", html.Div(check_rows), "bi-list-check")

    # ── History log ──
    history_rows = []
    for report in reversed(history[-20:]):
        r_status = report.get("overall_status", "healthy")
        r_color = STATUS_COLORS.get(r_status, COLORS["text_muted"])
        r_healed = report.get("healed", 0)
        r_failures = report.get("failures", 0)
        r_warnings = report.get("warnings", 0)
        r_time = report.get("timestamp", "")[:19].replace("T", " ")

        badges = []
        if r_failures:
            badges.append(pill(f"{r_failures} fail", COLORS["danger"]))
        if r_warnings:
            badges.append(pill(f"{r_warnings} warn", COLORS["warning"]))
        if r_healed:
            badges.append(pill(f"{r_healed} healed", COLORS["info"]))

        # Show heal actions from this report
        heal_actions = []
        for c in report.get("checks", []):
            if c.get("healed") and c.get("heal_action"):
                heal_actions.append(html.Div([
                    html.I(className="bi bi-wrench me-1", style={"color": COLORS["info"], "fontSize": "0.7rem"}),
                    html.Span(c["heal_action"], style={"color": COLORS["info"], "fontSize": "0.7rem"}),
                ], style={"marginTop": "2px"}))

        history_rows.append(html.Div([
            html.Div([
                _status_dot(r_status),
                html.Span(r_time, style={
                    "color": COLORS["text"], "fontSize": "0.8rem", "fontWeight": "500",
                    "minWidth": "140px",
                }),
                html.Span(f"{report.get('total_checks', 0)} checks · {report.get('duration_ms', 0)}ms",
                          style={"color": COLORS["text_muted"], "fontSize": "0.75rem",
                                 "minWidth": "140px"}),
                html.Div(badges, style={"display": "flex", "gap": "6px"}),
            ], style={"display": "flex", "gap": "12px", "alignItems": "center", "flexWrap": "wrap"}),
            html.Div(heal_actions) if heal_actions else None,
        ], style={
            "padding": "8px 14px",
            "borderBottom": f"1px solid {COLORS['card_border']}",
            "background": f"{r_color}05" if r_status != "healthy" else "transparent",
        }))

    history_section = info_card(
        f"Check History (last {min(len(history), 20)} runs)",
        html.Div(history_rows) if history_rows else html.P(
            "No history yet.", style={"color": COLORS["text_muted"], "padding": "16px"}),
        "bi-clock-history",
    )

    return html.Div([
        status_banner,
        kpi_row,
        cat_grid,
        checks_section,
        html.Div(style={"height": "20px"}),
        history_section,
    ])


def layout():
    return html.Div([
        html.Div([
            html.H2("System Health"),
            html.P("Live monitoring, auto-healing, and diagnostic logs"),
        ], className="page-header"),

        # Manual check button
        html.Div([
            html.Button([
                html.I(className="bi bi-arrow-clockwise me-2"),
                "Run Check Now",
            ], id="health-run-btn", n_clicks=0, className="btn-primary-dark",
                style={"marginRight": "12px"}),
            html.Span("Auto-checks run every 60 seconds",
                      style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={"marginBottom": "20px"}),

        # Auto-refreshing content
        html.Div(id="health-content"),

        # Interval for auto-refresh (30 seconds)
        dcc.Interval(id="health-interval", interval=30_000, n_intervals=0),
    ])


@callback(
    Output("health-content", "children"),
    Input("health-interval", "n_intervals"),
    Input("health-run-btn", "n_clicks"),
)
def refresh_health(n_intervals, n_clicks):
    from dash import ctx
    from flask import current_app

    checker = getattr(current_app, "health_checker", None)
    if not checker:
        return html.Div([
            html.I(className="bi bi-exclamation-triangle",
                   style={"fontSize": "2rem", "color": COLORS["warning"],
                          "display": "block", "marginBottom": "12px"}),
            html.P("Health checker not initialized.",
                   style={"color": COLORS["text_muted"]}),
        ], style={"textAlign": "center", "padding": "60px 20px"})

    # If manual button clicked, run checks now
    if ctx.triggered_id == "health-run-btn" and n_clicks:
        checker.run_checks_now()

    latest = checker.get_latest()
    history = checker.get_history(n=50)
    return _build_dashboard(latest, history)
