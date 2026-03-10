import base64
from dash import html, dcc, callback, Input, Output, State
from config import COLORS
from components.cards import info_card
from components.tables import dark_table
from utils.vision import analyze_image, analyze_multiple_images, save_scan_result, load_scans


def _result_section(data):
    """Render extracted product data as a styled card."""
    if "error" in data:
        return html.Div([
            html.I(className="bi bi-exclamation-triangle-fill me-2",
                   style={"color": COLORS["danger"]}),
            html.Span(data["error"], style={"color": COLORS["danger"]}),
        ], style={"padding": "16px"})

    # Main product info
    fields = [
        ("Product Name", data.get("product_name"), "bi-box-seam", COLORS["primary"]),
        ("Brand", data.get("brand"), "bi-tag", COLORS["info"]),
        ("Category", data.get("category"), "bi-grid", COLORS["purple"]),
        ("Description", data.get("description"), "bi-card-text", COLORS["text_muted"]),
        ("Net Weight", data.get("net_weight"), "bi-speedometer", COLORS["warning"]),
        ("UPC/Barcode", data.get("upc_barcode"), "bi-upc-scan", COLORS["info"]),
        ("Manufacturer", data.get("manufacturer"), "bi-building", COLORS["text_muted"]),
        ("Amazon Category", data.get("amazon_category_guess"), "bi-cart", COLORS["warning"]),
        ("Competition", data.get("estimated_competition"), "bi-people", COLORS["danger"]),
    ]

    info_rows = []
    for label, value, icon, color in fields:
        if value:
            info_rows.append(html.Div([
                html.Div([
                    html.I(className=f"bi {icon}", style={"color": color, "fontSize": "0.9rem"}),
                ], style={"width": "28px", "flexShrink": "0"}),
                html.Div([
                    html.Span(label, style={"color": COLORS["text_muted"], "fontSize": "0.75rem",
                                            "display": "block"}),
                    html.Span(str(value), style={"color": COLORS["text"], "fontSize": "0.85rem",
                                                  "fontWeight": "500"}),
                ]),
            ], style={"display": "flex", "gap": "10px", "alignItems": "flex-start",
                       "padding": "8px 0", "borderBottom": f"1px solid {COLORS['card_border']}"}))

    # Claims/certifications
    claims = data.get("claims", [])
    claims_pills = []
    if claims:
        for c in claims:
            claims_pills.append(html.Span(c, style={
                "background": f"{COLORS['success']}20", "color": COLORS["success"],
                "padding": "3px 10px", "borderRadius": "12px", "fontSize": "0.75rem",
                "fontWeight": "600", "marginRight": "6px", "marginBottom": "4px",
                "display": "inline-block",
            }))

    # Warnings
    warnings = data.get("warnings", [])
    warning_items = []
    if warnings:
        for w in warnings:
            warning_items.append(html.Div([
                html.I(className="bi bi-exclamation-triangle me-2",
                       style={"color": COLORS["warning"], "flexShrink": "0"}),
                html.Span(w, style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
            ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "4px"}))

    # Key selling points
    selling_points = data.get("key_selling_points", [])
    sp_items = []
    if selling_points:
        for sp in selling_points:
            sp_items.append(html.Div([
                html.I(className="bi bi-check-circle-fill me-2",
                       style={"color": COLORS["success"], "flexShrink": "0"}),
                html.Span(sp, style={"color": COLORS["text"], "fontSize": "0.85rem"}),
            ], style={"display": "flex", "alignItems": "flex-start", "marginBottom": "6px"}))

    # Ingredients
    ingredients = data.get("ingredients", [])
    ingredients_section = None
    if ingredients:
        ingredients_section = html.Div([
            html.H6([html.I(className="bi bi-list-ul me-2"), "Ingredients"],
                     style={"color": COLORS["text"], "fontWeight": "600", "marginBottom": "8px"}),
            html.P(", ".join(ingredients),
                   style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                          "lineHeight": "1.6", "marginBottom": "0"}),
        ], style={"marginTop": "16px"})

    # Nutrition facts
    nutrition = data.get("nutrition_facts")
    nutrition_section = None
    if nutrition and any(v for v in nutrition.values() if v):
        nut_rows = []
        if nutrition.get("serving_size"):
            nut_rows.append(f"Serving Size: {nutrition['serving_size']}")
        if nutrition.get("calories"):
            nut_rows.append(f"Calories: {nutrition['calories']}")
        other = nutrition.get("other", {})
        if isinstance(other, dict):
            for k, v in other.items():
                nut_rows.append(f"{k}: {v}")
        nutrition_section = html.Div([
            html.H6([html.I(className="bi bi-clipboard-data me-2"), "Nutrition Facts"],
                     style={"color": COLORS["text"], "fontWeight": "600", "marginBottom": "8px"}),
            html.Div([html.P(r, style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                                        "marginBottom": "2px"}) for r in nut_rows]),
        ], style={"marginTop": "16px"})

    # Notes
    notes = data.get("notes")
    notes_section = None
    if notes:
        notes_section = html.Div([
            html.I(className="bi bi-sticky me-2", style={"color": COLORS["info"]}),
            html.Span(notes, style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
        ], style={
            "background": f"{COLORS['info']}10", "padding": "12px 14px",
            "borderRadius": "8px", "marginTop": "16px",
        })

    # Model/token info
    model_used = data.get("_model_used", "")
    tokens = data.get("_tokens_used", {})
    meta_info = None
    if model_used:
        meta_info = html.Div([
            html.Span(f"Model: {model_used}", style={"color": COLORS["text_muted"], "fontSize": "0.7rem"}),
            html.Span(f" | Tokens: {tokens.get('input', '?')} in / {tokens.get('output', '?')} out",
                      style={"color": COLORS["text_muted"], "fontSize": "0.7rem"})
            if tokens else None,
        ], style={"marginTop": "16px", "paddingTop": "12px",
                  "borderTop": f"1px solid {COLORS['card_border']}"})

    return html.Div([
        html.Div(info_rows),
        html.Div(claims_pills, style={"marginTop": "12px"}) if claims_pills else None,
        html.Div([
            html.H6([html.I(className="bi bi-megaphone me-2"), "Key Selling Points"],
                     style={"color": COLORS["text"], "fontWeight": "600",
                            "marginTop": "16px", "marginBottom": "8px"}),
            html.Div(sp_items),
        ]) if sp_items else None,
        html.Div(warning_items, style={"marginTop": "12px"}) if warning_items else None,
        ingredients_section,
        nutrition_section,
        notes_section,
        meta_info,
    ])


def _build_scans_table():
    """Build the history table from saved scans."""
    scans = load_scans()
    if not scans:
        return html.P("No scans yet. Upload an image to get started.",
                      style={"color": COLORS["text_muted"], "padding": "16px", "textAlign": "center"})

    rows = []
    for s in reversed(scans):
        d = s.get("data", {})
        if "error" in d:
            continue
        rows.append({
            "id": s["id"],
            "product": d.get("product_name", "Unknown"),
            "brand": d.get("brand", "—"),
            "category": d.get("category", "—"),
            "weight": d.get("net_weight", "—"),
            "competition": d.get("estimated_competition", "—"),
            "claims": ", ".join(d.get("claims", [])[:3]) or "—",
            "scanned": s.get("timestamp", "")[:16].replace("T", " "),
            "file": s.get("filename", "—"),
        })

    if not rows:
        return html.P("No successful scans yet.",
                      style={"color": COLORS["text_muted"], "padding": "16px", "textAlign": "center"})

    columns = [
        {"name": "#", "id": "id"},
        {"name": "Product", "id": "product"},
        {"name": "Brand", "id": "brand"},
        {"name": "Category", "id": "category"},
        {"name": "Weight", "id": "weight"},
        {"name": "Competition", "id": "competition"},
        {"name": "Claims", "id": "claims"},
        {"name": "Scanned", "id": "scanned"},
        {"name": "File", "id": "file"},
    ]
    return dark_table("scanner-history-table", columns, rows)


def layout():
    return html.Div([
        html.Div([
            html.H2("Product Scanner"),
            html.P("Upload product images — labels, packaging, screenshots — for AI-powered data extraction"),
        ], className="page-header"),

        html.Div([
            # Upload area
            html.Div([
                info_card("Upload Image", html.Div([
                    dcc.Upload(
                        id="scanner-upload",
                        children=html.Div([
                            html.I(className="bi bi-cloud-arrow-up",
                                   style={"fontSize": "2.5rem", "color": COLORS["primary"],
                                          "display": "block", "marginBottom": "12px"}),
                            html.Div("Drag & drop or click to upload", style={
                                "color": COLORS["text"], "fontWeight": "600",
                                "fontSize": "0.95rem", "marginBottom": "4px",
                            }),
                            html.Div("Upload one or multiple images — JPG, PNG, WebP, GIF", style={
                                "color": COLORS["text_muted"], "fontSize": "0.8rem",
                            }),
                        ], style={"textAlign": "center", "padding": "40px 20px"}),
                        style={
                            "border": f"2px dashed {COLORS['card_border']}",
                            "borderRadius": "12px",
                            "cursor": "pointer",
                            "transition": "border-color 0.2s",
                            "background": COLORS["input_bg"],
                        },
                        style_active={
                            "border": f"2px dashed {COLORS['primary']}",
                            "background": f"{COLORS['primary']}08",
                        },
                        multiple=True,
                        max_size=20_000_000,
                    ),
                    html.Div([
                        html.I(className="bi bi-funnel me-2", style={"color": COLORS["success"]}),
                        html.Span("Smart filtering: ",
                                  style={"color": COLORS["success"], "fontWeight": "600", "fontSize": "0.8rem"}),
                        html.Span("When you upload multiple images (e.g. all attachments from a supplier email), "
                                  "Claude automatically identifies which images show actual products and ignores "
                                  "logos, signatures, banners, and other non-product images.",
                                  style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                    ], style={
                        "background": f"{COLORS['success']}10", "padding": "10px 14px",
                        "borderRadius": "8px", "marginTop": "12px",
                    }),
                    html.Div([
                        html.I(className="bi bi-lightbulb me-2", style={"color": COLORS["warning"]}),
                        html.Span("Works with supplement bottle labels, product packaging, Amazon listings, "
                                  "spec sheets, catalogue pages, and any image with product information.",
                                  style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
                    ], style={
                        "background": f"{COLORS['warning']}10", "padding": "10px 14px",
                        "borderRadius": "8px", "marginTop": "8px",
                    }),
                ]), "bi-camera"),
            ]),

            # Preview + status
            html.Div([
                info_card("Preview", html.Div(id="scanner-preview",
                    children=html.Div([
                        html.I(className="bi bi-image", style={
                            "fontSize": "3rem", "color": COLORS["card_border"],
                            "display": "block", "marginBottom": "8px",
                        }),
                        html.P("No image uploaded", style={
                            "color": COLORS["text_muted"], "fontSize": "0.85rem",
                        }),
                    ], style={"textAlign": "center", "padding": "50px 20px"}),
                ), "bi-eye"),
            ]),
        ], className="grid-row grid-2"),

        # Loading indicator
        dcc.Loading(
            id="scanner-loading",
            type="default",
            color=COLORS["primary"],
            children=html.Div(id="scanner-results"),
        ),

        # Scan history table
        html.Div([
            info_card("Scan History",
                      html.Div(id="scanner-history", children=_build_scans_table()),
                      "bi-clock-history"),
        ], style={"marginTop": "20px"}),
    ])


@callback(
    Output("scanner-preview", "children"),
    Output("scanner-results", "children"),
    Output("scanner-history", "children"),
    Input("scanner-upload", "contents"),
    State("scanner-upload", "filename"),
    prevent_initial_call=True,
)
def process_upload(contents_list, filename_list):
    if not contents_list:
        return (
            html.P("No image", style={"color": COLORS["text_muted"], "textAlign": "center", "padding": "40px"}),
            "",
            _build_scans_table(),
        )

    # Normalize to lists (single upload comes as string, multiple as list)
    if isinstance(contents_list, str):
        contents_list = [contents_list]
        filename_list = [filename_list]

    # Build preview grid
    preview_items = []
    for contents, fname in zip(contents_list, filename_list):
        preview_items.append(html.Div([
            html.Img(src=contents, style={
                "width": "100%", "maxHeight": "200px", "objectFit": "contain",
                "borderRadius": "8px",
            }),
            html.P(fname, style={
                "color": COLORS["text_muted"], "fontSize": "0.75rem",
                "textAlign": "center", "marginTop": "4px", "marginBottom": "0",
                "overflow": "hidden", "textOverflow": "ellipsis", "whiteSpace": "nowrap",
            }),
        ], style={"background": COLORS["input_bg"], "padding": "8px",
                  "borderRadius": "8px", "border": f"1px solid {COLORS['card_border']}"}))

    cols = min(len(preview_items), 4)
    preview = html.Div(preview_items, style={
        "display": "grid", "gridTemplateColumns": f"repeat({cols}, 1fr)",
        "gap": "10px",
    })

    # Decode images
    images = []
    for contents, fname in zip(contents_list, filename_list):
        _, content_data = contents.split(",", 1)
        images.append({"bytes": base64.b64decode(content_data), "filename": fname})

    # Single image: direct analysis. Multiple: smart filter first.
    result_cards = []
    skipped_cards = []

    if len(images) == 1:
        result = analyze_image(images[0]["bytes"], images[0]["filename"])
        if result.get("is_product") is False:
            skipped_cards.append(_skipped_card(images[0]["filename"], result.get("reason", "")))
        else:
            save_scan_result(result, images[0]["filename"])
            result_cards.append(info_card(
                f"Extracted — {result.get('product_name', images[0]['filename'])}",
                _result_section(result), "bi-cpu",
            ))
    else:
        results = analyze_multiple_images(images)
        for r in results:
            fname = r.get("filename", "unknown")
            if r.get("skipped") or r.get("is_product") is False:
                skipped_cards.append(_skipped_card(fname, r.get("reason", "Not a product")))
            else:
                save_scan_result(r, fname)
                result_cards.append(info_card(
                    f"Extracted — {r.get('product_name', fname)}",
                    _result_section(r), "bi-cpu",
                ))

    # Build output
    output_sections = []

    if skipped_cards:
        output_sections.append(html.Div([
            html.Div([
                html.I(className="bi bi-funnel-fill me-2", style={"color": COLORS["text_muted"]}),
                html.Span(f"{len(skipped_cards)} image{'s' if len(skipped_cards) != 1 else ''} "
                          f"filtered out (not product images)",
                          style={"color": COLORS["text_muted"], "fontSize": "0.85rem"}),
            ], style={"marginBottom": "8px"}),
            html.Div(skipped_cards),
        ], style={"marginTop": "20px"}))

    if result_cards:
        output_sections.append(html.Div([
            html.Div([
                html.I(className="bi bi-check-circle-fill me-2", style={"color": COLORS["success"]}),
                html.Span(f"{len(result_cards)} product{'s' if len(result_cards) != 1 else ''} extracted",
                          style={"color": COLORS["success"], "fontSize": "0.85rem", "fontWeight": "600"}),
            ], style={"marginBottom": "12px"}),
            html.Div(result_cards, style={"display": "flex", "flexDirection": "column", "gap": "16px"}),
        ], style={"marginTop": "20px"}))
    elif not skipped_cards:
        output_sections.append(html.P("No product data could be extracted.",
                                      style={"color": COLORS["text_muted"], "marginTop": "20px"}))

    return preview, html.Div(output_sections), _build_scans_table()


def _skipped_card(filename, reason):
    return html.Div([
        html.I(className="bi bi-skip-forward-fill me-2", style={"color": COLORS["text_muted"]}),
        html.Span(filename, style={"color": COLORS["text"], "fontWeight": "500",
                                    "fontSize": "0.85rem", "marginRight": "8px"}),
        html.Span(f"— {reason}", style={"color": COLORS["text_muted"], "fontSize": "0.8rem"}),
    ], style={
        "padding": "8px 12px", "background": f"{COLORS['card_border']}30",
        "borderRadius": "6px", "marginBottom": "4px",
    })
