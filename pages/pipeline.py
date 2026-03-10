import json
import os
import io
import base64
import uuid
from datetime import datetime

import pandas as pd
from dash import html, dcc, callback, Input, Output, State, ALL, no_update

from config import COLORS
from components.cards import kpi_card, info_card
from components.forms import styled_input, styled_dropdown, form_group
from components.tables import dark_table
from utils.data import calc_feasibility, estimate_fba_fee, calc_referral_fee

DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "pipeline.json")

STAGES = ["new", "scored", "review", "accepted", "rejected"]
STAGE_COLORS = {
    "new": COLORS["info"],
    "scored": COLORS["primary"],
    "review": COLORS["warning"],
    "accepted": COLORS["success"],
    "rejected": COLORS["danger"],
}
STAGE_ICONS = {
    "new": "bi-inbox",
    "scored": "bi-speedometer2",
    "review": "bi-search",
    "accepted": "bi-check-circle",
    "rejected": "bi-x-circle",
}

# Common column name aliases for auto-mapping
COLUMN_ALIASES = {
    "product_name": ["product_name", "product", "name", "title", "item", "item_name",
                     "product_title", "description", "product_description"],
    "price": ["price", "sell_price", "selling_price", "retail_price", "amazon_price",
              "sale_price", "list_price", "msrp"],
    "cost": ["cost", "unit_cost", "buy_price", "purchase_price", "supplier_price",
             "wholesale_price", "cog", "cogs"],
    "moq": ["moq", "min_order", "minimum_order", "min_qty", "minimum_quantity",
            "min_order_qty"],
    "weight": ["weight", "weight_lb", "weight_lbs", "item_weight", "product_weight",
               "weight_kg"],
    "monthly_sales": ["monthly_sales", "sales", "monthly_units", "est_sales",
                      "estimated_sales", "units_sold", "volume"],
    "category": ["category", "product_category", "dept", "department"],
    "asin": ["asin", "amazon_asin"],
    "upc": ["upc", "barcode", "ean", "gtin"],
}


def _load_pipeline():
    if not os.path.exists(DATA_PATH):
        return {"items": []}
    with open(DATA_PATH) as f:
        return json.load(f)


def _save_pipeline(data):
    with open(DATA_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _auto_map_column(col_name):
    """Try to auto-map a column name to a known field."""
    col_lower = col_name.strip().lower().replace(" ", "_").replace("-", "_")
    for field, aliases in COLUMN_ALIASES.items():
        if col_lower in aliases:
            return field
    return ""


def _stage_card(stage, count):
    """Build a stage summary card."""
    color = STAGE_COLORS.get(stage, COLORS["text_muted"])
    icon = STAGE_ICONS.get(stage, "bi-circle")
    return html.Div([
        html.Div([
            html.I(className=f"bi {icon}",
                   style={"fontSize": "1.2rem", "color": color}),
        ], style={
            "width": "40px", "height": "40px", "borderRadius": "10px",
            "background": f"{color}15", "display": "flex",
            "alignItems": "center", "justifyContent": "center",
        }),
        html.Div([
            html.P(stage.upper(), style={
                "color": COLORS["text_muted"], "fontSize": "0.7rem",
                "fontWeight": "700", "marginBottom": "2px",
                "letterSpacing": "0.05em",
            }),
            html.H4(str(count), style={
                "fontWeight": "700", "color": COLORS["text"], "marginBottom": "0",
            }),
        ]),
    ], style={
        "display": "flex", "gap": "12px", "alignItems": "center",
        "padding": "16px 20px",
        "background": COLORS["card"],
        "border": f"1px solid {COLORS['card_border']}",
        "borderRadius": "10px",
        "minWidth": "140px",
    })


def layout():
    pipeline = _load_pipeline()
    items = pipeline.get("items", [])

    # Count items per stage
    stage_counts = {s: 0 for s in STAGES}
    for item in items:
        st = item.get("stage", "new")
        if st in stage_counts:
            stage_counts[st] += 1

    # Build pipeline table data
    pipeline_table_data = []
    for item in items:
        pipeline_table_data.append({
            "id": item.get("id", ""),
            "product_name": item.get("product_name", "Unknown"),
            "price": item.get("price", 0),
            "cost": item.get("cost", 0),
            "margin": item.get("margin", 0),
            "roi": item.get("roi", 0),
            "score": item.get("score", 0),
            "verdict": item.get("verdict", ""),
            "stage": item.get("stage", "new"),
            "added": item.get("added", ""),
        })

    return html.Div([
        # Stores
        dcc.Store(id="pipeline-upload-store", data=None),
        dcc.Store(id="pipeline-scored-store", data=None),
        dcc.Download(id="pipeline-download"),

        # Page header
        html.Div([
            html.H2("Deal Pipeline"),
            html.P("Bulk import supplier price lists, score products, and track deals through your pipeline"),
        ], className="page-header"),

        # ── Stage Summary Cards ──
        html.Div([
            html.Div([
                html.I(className="bi bi-kanban me-2", style={"color": COLORS["primary"]}),
                html.H6("Pipeline Stages", className="mb-0",
                         style={"color": COLORS["text"], "fontWeight": "600"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),
            html.Div(
                [_stage_card(stage, stage_counts[stage]) for stage in STAGES],
                style={
                    "display": "flex", "gap": "12px", "flexWrap": "wrap",
                },
            ),
        ], className="dash-card", style={"marginBottom": "20px"}),

        # ── Bulk Import Section ──
        html.Div([
            html.Div([
                html.I(className="bi bi-cloud-arrow-up me-2",
                       style={"color": COLORS["primary"], "fontSize": "1.2rem"}),
                html.H6("Bulk Import", className="mb-0",
                         style={"color": COLORS["text"], "fontWeight": "600"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

            # Upload area
            dcc.Upload(
                id="pipeline-upload",
                children=html.Div([
                    html.I(className="bi bi-file-earmark-spreadsheet",
                           style={"fontSize": "2.5rem", "color": COLORS["primary"],
                                  "marginBottom": "12px"}),
                    html.Div([
                        html.Span("Drag & drop a CSV or Excel file here, or ",
                                  style={"color": COLORS["text_muted"]}),
                        html.Span("browse", style={
                            "color": COLORS["primary"], "fontWeight": "600",
                            "textDecoration": "underline", "cursor": "pointer",
                        }),
                    ]),
                    html.P("Supported: .csv, .xlsx, .xls",
                           style={"color": COLORS["text_muted"], "fontSize": "0.75rem",
                                  "marginTop": "8px", "marginBottom": "0"}),
                ], style={"textAlign": "center"}),
                style={
                    "border": f"2px dashed {COLORS['card_border']}",
                    "borderRadius": "12px",
                    "padding": "40px 20px",
                    "textAlign": "center",
                    "cursor": "pointer",
                    "background": COLORS["input_bg"],
                    "transition": "border-color 0.2s",
                },
                multiple=False,
                accept=".csv,.xlsx,.xls",
            ),

            # Column mapping area (hidden until file uploaded)
            html.Div(id="pipeline-mapping-area", style={"marginTop": "20px"}),

            # Score All button and status
            html.Div(id="pipeline-score-section", style={"marginTop": "16px"}),

        ], className="dash-card", style={"marginBottom": "20px"}),

        # ── Scored Results Section ──
        html.Div(id="pipeline-results-section"),

        # ── Pipeline Items Table ──
        html.Div([
            html.Div([
                html.I(className="bi bi-table me-2",
                       style={"color": COLORS["purple"], "fontSize": "1.2rem"}),
                html.H6("All Pipeline Items", className="mb-0",
                         style={"color": COLORS["text"], "fontWeight": "600"}),
            ], style={"display": "flex", "alignItems": "center", "marginBottom": "16px"}),

            dark_table(
                id="pipeline-items-table",
                columns=[
                    {"name": "Product", "id": "product_name"},
                    {"name": "Price", "id": "price", "type": "numeric",
                     "format": {"specifier": "$.2f"}},
                    {"name": "Cost", "id": "cost", "type": "numeric",
                     "format": {"specifier": "$.2f"}},
                    {"name": "Margin %", "id": "margin", "type": "numeric",
                     "format": {"specifier": ".1f"}},
                    {"name": "ROI %", "id": "roi", "type": "numeric",
                     "format": {"specifier": ".1f"}},
                    {"name": "Score", "id": "score", "type": "numeric"},
                    {"name": "Verdict", "id": "verdict"},
                    {"name": "Stage", "id": "stage", "presentation": "dropdown"},
                    {"name": "Added", "id": "added"},
                ],
                data=pipeline_table_data,
                editable=True,
                dropdown={
                    "stage": {
                        "options": [{"label": s.upper(), "value": s} for s in STAGES],
                    },
                },
                style_data_conditional=[
                    {"if": {"state": "active"},
                     "backgroundColor": COLORS["hover"],
                     "border": f"1px solid {COLORS['card_border']}"},
                    {"if": {"filter_query": "{verdict} = GO", "column_id": "verdict"},
                     "color": COLORS["success"], "fontWeight": "700"},
                    {"if": {"filter_query": "{verdict} = MAYBE", "column_id": "verdict"},
                     "color": COLORS["warning"], "fontWeight": "700"},
                    {"if": {"filter_query": '{verdict} = "NO GO"', "column_id": "verdict"},
                     "color": COLORS["danger"], "fontWeight": "700"},
                ],
            ),
        ], className="dash-card", style={"marginBottom": "20px"}),
    ])


# ── Callback: Parse uploaded file and show column mapping ──
@callback(
    Output("pipeline-mapping-area", "children"),
    Output("pipeline-upload-store", "data"),
    Input("pipeline-upload", "contents"),
    State("pipeline-upload", "filename"),
    prevent_initial_call=True,
)
def parse_upload(contents, filename):
    if contents is None:
        return no_update, no_update

    content_type, content_string = contents.split(",")
    decoded = base64.b64decode(content_string)

    try:
        if filename.lower().endswith(".csv"):
            df = pd.read_csv(io.StringIO(decoded.decode("utf-8")))
        elif filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(decoded))
        else:
            return html.Div([
                html.I(className="bi bi-exclamation-triangle me-2",
                       style={"color": COLORS["danger"]}),
                html.Span("Unsupported file format. Please upload CSV or Excel.",
                          style={"color": COLORS["danger"]}),
            ]), no_update
    except Exception as e:
        return html.Div([
            html.I(className="bi bi-exclamation-triangle me-2",
                   style={"color": COLORS["danger"]}),
            html.Span(f"Error reading file: {str(e)}",
                      style={"color": COLORS["danger"]}),
        ]), no_update

    detected_cols = list(df.columns)
    # Store the data as JSON-serializable dict
    store_data = {
        "filename": filename,
        "columns": detected_cols,
        "rows": df.head(500).fillna("").to_dict("records"),
        "total_rows": len(df),
    }

    # Build auto-mapped column dropdowns
    target_fields = [
        {"label": "-- Skip --", "value": ""},
        {"label": "Product Name", "value": "product_name"},
        {"label": "Price (sell)", "value": "price"},
        {"label": "Cost (buy)", "value": "cost"},
        {"label": "MOQ", "value": "moq"},
        {"label": "Weight (lb)", "value": "weight"},
        {"label": "Monthly Sales", "value": "monthly_sales"},
        {"label": "Category", "value": "category"},
        {"label": "ASIN", "value": "asin"},
        {"label": "UPC/Barcode", "value": "upc"},
    ]

    mapping_rows = []
    for col in detected_cols:
        auto_val = _auto_map_column(col)
        mapping_rows.append(
            html.Div([
                html.Div([
                    html.Code(col, style={
                        "color": COLORS["primary"], "fontSize": "0.85rem",
                        "background": f"{COLORS['primary']}15",
                        "padding": "2px 8px", "borderRadius": "4px",
                    }),
                ], style={"flex": "1", "display": "flex", "alignItems": "center"}),
                html.I(className="bi bi-arrow-right",
                       style={"color": COLORS["text_muted"], "margin": "0 12px"}),
                html.Div([
                    styled_dropdown(
                        id={"type": "col-map", "index": col},
                        options=target_fields,
                        value=auto_val,
                        placeholder="Map to field...",
                    ),
                ], style={"flex": "1"}),
            ], style={
                "display": "flex", "alignItems": "center", "padding": "8px 0",
                "borderBottom": f"1px solid {COLORS['card_border']}",
            })
        )

    # Preview of first few rows
    preview_cols = [{"name": c, "id": c} for c in detected_cols[:8]]
    preview_data = df.head(5).fillna("").astype(str).to_dict("records")

    return html.Div([
        # File info banner
        html.Div([
            html.I(className="bi bi-check-circle-fill me-2",
                   style={"color": COLORS["success"]}),
            html.Span(f"Loaded ", style={"color": COLORS["text"]}),
            html.Strong(filename, style={"color": COLORS["primary"]}),
            html.Span(f" — {len(df)} rows, {len(detected_cols)} columns",
                      style={"color": COLORS["text_muted"]}),
        ], style={
            "background": f"{COLORS['success']}12",
            "border": f"1px solid {COLORS['success']}40",
            "padding": "12px 16px", "borderRadius": "8px", "marginBottom": "16px",
        }),

        # Preview table
        html.Div([
            html.P("Preview (first 5 rows):", style={
                "color": COLORS["text_muted"], "fontSize": "0.8rem",
                "marginBottom": "8px",
            }),
            dark_table("pipeline-preview-table", preview_cols, preview_data,
                       page_size=5, sort_action="none", filter_action="none"),
        ], style={"marginBottom": "20px"}),

        # Column mapping
        html.Div([
            html.P([
                html.I(className="bi bi-diagram-2 me-2",
                       style={"color": COLORS["info"]}),
                "Column Mapping",
            ], style={"color": COLORS["text"], "fontWeight": "600",
                      "marginBottom": "12px"}),
            html.P("Map your file columns to the required fields. Auto-detected mappings are pre-filled.",
                   style={"color": COLORS["text_muted"], "fontSize": "0.8rem",
                          "marginBottom": "16px"}),
            html.Div(mapping_rows),
        ]),
    ]), store_data


# ── Callback: Show Score All button after mapping ──
@callback(
    Output("pipeline-score-section", "children"),
    Input("pipeline-upload-store", "data"),
    prevent_initial_call=True,
)
def show_score_button(store_data):
    if store_data is None:
        return no_update
    return html.Div([
        html.Button([
            html.I(className="bi bi-lightning-fill me-2"),
            f"Score All ({store_data['total_rows']} items)",
        ], id="pipeline-score-btn", className="btn-primary-dark",
           style={"marginRight": "12px"}),
        html.Button([
            html.I(className="bi bi-x-circle me-2"),
            "Clear",
        ], id="pipeline-clear-btn", className="btn-outline-dark"),
    ])


# ── Callback: Score all rows ──
@callback(
    Output("pipeline-results-section", "children"),
    Output("pipeline-scored-store", "data"),
    Input("pipeline-score-btn", "n_clicks"),
    State("pipeline-upload-store", "data"),
    State({"type": "col-map", "index": ALL}, "value"),
    State({"type": "col-map", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def score_all_rows(n_clicks, store_data, mapping_values, mapping_ids):
    if not store_data or not n_clicks:
        return no_update, no_update

    # Build column mapping: source_col -> target_field
    col_map = {}
    for mid, mval in zip(mapping_ids, mapping_values):
        if mval:
            col_map[mid["index"]] = mval

    # Reverse map: target_field -> source_col
    field_to_col = {}
    for src, tgt in col_map.items():
        field_to_col[tgt] = src

    rows = store_data["rows"]
    scored_rows = []

    for row in rows:
        product_name = str(row.get(field_to_col.get("product_name", ""), "Unknown"))
        try:
            price = float(row.get(field_to_col.get("price", ""), 0) or 0)
        except (ValueError, TypeError):
            price = 0
        try:
            cost = float(row.get(field_to_col.get("cost", ""), 0) or 0)
        except (ValueError, TypeError):
            cost = 0
        try:
            moq = int(float(row.get(field_to_col.get("moq", ""), 0) or 0))
        except (ValueError, TypeError):
            moq = 0
        try:
            weight = float(row.get(field_to_col.get("weight", ""), 1) or 1)
        except (ValueError, TypeError):
            weight = 1
        try:
            monthly_sales = int(float(row.get(field_to_col.get("monthly_sales", ""), 100) or 100))
        except (ValueError, TypeError):
            monthly_sales = 100

        fba_fee = estimate_fba_fee(weight)
        referral_fee = calc_referral_fee(price)

        result = calc_feasibility(
            price=price,
            cost=cost,
            fba_fee=fba_fee,
            referral_fee=referral_fee,
            monthly_sales=monthly_sales,
            moq=moq,
        )

        scored_rows.append({
            "product_name": product_name,
            "price": price,
            "cost": cost,
            "moq": moq,
            "margin": result["margin"],
            "roi": result["roi"],
            "score": result["score"],
            "verdict": result["verdict"],
        })

    # Compute KPI summaries
    total = len(scored_rows)
    go_count = sum(1 for r in scored_rows if r["verdict"] == "GO")
    maybe_count = sum(1 for r in scored_rows if r["verdict"] == "MAYBE")
    nogo_count = sum(1 for r in scored_rows if r["verdict"] == "NO GO")
    avg_margin = round(sum(r["margin"] for r in scored_rows) / total, 1) if total > 0 else 0

    results_ui = html.Div([
        # KPI row
        html.Div([
            kpi_card("Total Items", str(total), "bi-box-seam", COLORS["primary"]),
            kpi_card("GO", str(go_count), "bi-check-circle-fill", COLORS["success"]),
            kpi_card("MAYBE", str(maybe_count), "bi-question-circle-fill", COLORS["warning"]),
            kpi_card("NO GO", str(nogo_count), "bi-x-circle-fill", COLORS["danger"]),
            kpi_card("Avg Margin", f"{avg_margin}%", "bi-percent", COLORS["info"]),
        ], style={
            "display": "grid",
            "gridTemplateColumns": "repeat(auto-fit, minmax(180px, 1fr))",
            "gap": "12px", "marginBottom": "20px",
        }),

        # Scored results table
        html.Div([
            html.Div([
                html.Div([
                    html.I(className="bi bi-speedometer2 me-2",
                           style={"color": COLORS["success"], "fontSize": "1.2rem"}),
                    html.H6("Scored Results", className="mb-0",
                             style={"color": COLORS["text"], "fontWeight": "600"}),
                ], style={"display": "flex", "alignItems": "center"}),
                html.Div([
                    html.Button([
                        html.I(className="bi bi-plus-circle me-2"),
                        "Add to Pipeline",
                    ], id="pipeline-add-btn", className="btn-primary-dark",
                       style={"marginRight": "8px"}),
                    html.Button([
                        html.I(className="bi bi-download me-2"),
                        "Export CSV",
                    ], id="pipeline-export-btn", className="btn-outline-dark"),
                ]),
            ], style={
                "display": "flex", "justifyContent": "space-between",
                "alignItems": "center", "marginBottom": "16px",
            }),

            dark_table(
                id="pipeline-scored-table",
                columns=[
                    {"name": "Product", "id": "product_name"},
                    {"name": "Price", "id": "price", "type": "numeric",
                     "format": {"specifier": "$.2f"}},
                    {"name": "Cost", "id": "cost", "type": "numeric",
                     "format": {"specifier": "$.2f"}},
                    {"name": "MOQ", "id": "moq", "type": "numeric"},
                    {"name": "Margin %", "id": "margin", "type": "numeric",
                     "format": {"specifier": ".1f"}},
                    {"name": "ROI %", "id": "roi", "type": "numeric",
                     "format": {"specifier": ".1f"}},
                    {"name": "Score", "id": "score", "type": "numeric"},
                    {"name": "Verdict", "id": "verdict"},
                ],
                data=scored_rows,
                row_selectable="multi",
                style_data_conditional=[
                    {"if": {"state": "active"},
                     "backgroundColor": COLORS["hover"],
                     "border": f"1px solid {COLORS['card_border']}"},
                    {"if": {"filter_query": "{verdict} = GO", "column_id": "verdict"},
                     "color": COLORS["success"], "fontWeight": "700"},
                    {"if": {"filter_query": "{verdict} = MAYBE", "column_id": "verdict"},
                     "color": COLORS["warning"], "fontWeight": "700"},
                    {"if": {"filter_query": '{verdict} = "NO GO"', "column_id": "verdict"},
                     "color": COLORS["danger"], "fontWeight": "700"},
                ],
            ),
            html.Div(id="pipeline-add-status", style={"marginTop": "12px"}),
        ], className="dash-card", style={"marginBottom": "20px"}),
    ])

    return results_ui, scored_rows


# ── Callback: Export scored results as CSV ──
@callback(
    Output("pipeline-download", "data"),
    Input("pipeline-export-btn", "n_clicks"),
    State("pipeline-scored-store", "data"),
    prevent_initial_call=True,
)
def export_csv(n_clicks, scored_data):
    if not scored_data or not n_clicks:
        return no_update
    df = pd.DataFrame(scored_data)
    return dcc.send_data_frame(df.to_csv, "pipeline_scored_results.csv", index=False)


# ── Callback: Add selected scored items to pipeline ──
@callback(
    Output("pipeline-add-status", "children"),
    Output("pipeline-items-table", "data", allow_duplicate=True),
    Input("pipeline-add-btn", "n_clicks"),
    State("pipeline-scored-table", "selected_rows"),
    State("pipeline-scored-store", "data"),
    prevent_initial_call=True,
)
def add_to_pipeline(n_clicks, selected_rows, scored_data):
    if not scored_data or not n_clicks:
        return no_update, no_update

    # If no rows selected, add all GO/MAYBE items
    if not selected_rows:
        items_to_add = [r for r in scored_data if r["verdict"] in ("GO", "MAYBE")]
    else:
        items_to_add = [scored_data[i] for i in selected_rows if i < len(scored_data)]

    if not items_to_add:
        return html.Div([
            html.I(className="bi bi-info-circle me-2",
                   style={"color": COLORS["warning"]}),
            html.Span("No items to add. Select rows or ensure there are GO/MAYBE items.",
                      style={"color": COLORS["warning"], "fontSize": "0.85rem"}),
        ]), no_update

    pipeline = _load_pipeline()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    added_count = 0

    for item in items_to_add:
        pipeline_item = {
            "id": str(uuid.uuid4())[:8],
            "product_name": item.get("product_name", "Unknown"),
            "price": item.get("price", 0),
            "cost": item.get("cost", 0),
            "moq": item.get("moq", 0),
            "margin": item.get("margin", 0),
            "roi": item.get("roi", 0),
            "score": item.get("score", 0),
            "verdict": item.get("verdict", ""),
            "stage": "scored",
            "added": now,
        }
        pipeline["items"].append(pipeline_item)
        added_count += 1

    _save_pipeline(pipeline)

    # Rebuild table data
    table_data = []
    for item in pipeline["items"]:
        table_data.append({
            "id": item.get("id", ""),
            "product_name": item.get("product_name", "Unknown"),
            "price": item.get("price", 0),
            "cost": item.get("cost", 0),
            "margin": item.get("margin", 0),
            "roi": item.get("roi", 0),
            "score": item.get("score", 0),
            "verdict": item.get("verdict", ""),
            "stage": item.get("stage", "new"),
            "added": item.get("added", ""),
        })

    return html.Div([
        html.I(className="bi bi-check-circle-fill me-2",
               style={"color": COLORS["success"]}),
        html.Span(f"Added {added_count} items to pipeline.",
                  style={"color": COLORS["success"], "fontWeight": "500",
                         "fontSize": "0.85rem"}),
    ]), table_data


# ── Callback: Update pipeline stage when edited in table ──
@callback(
    Output("pipeline-items-table", "data", allow_duplicate=True),
    Input("pipeline-items-table", "data_timestamp"),
    State("pipeline-items-table", "data"),
    prevent_initial_call=True,
)
def update_pipeline_stages(timestamp, table_data):
    if not table_data:
        return no_update

    pipeline = _load_pipeline()

    # Build lookup by id
    id_map = {item["id"]: item for item in pipeline["items"]}

    for row in table_data:
        rid = row.get("id", "")
        if rid in id_map:
            id_map[rid]["stage"] = row.get("stage", id_map[rid].get("stage", "new"))

    _save_pipeline(pipeline)
    return table_data


# ── Callback: Clear upload ──
@callback(
    Output("pipeline-mapping-area", "children", allow_duplicate=True),
    Output("pipeline-upload-store", "data", allow_duplicate=True),
    Output("pipeline-score-section", "children", allow_duplicate=True),
    Output("pipeline-results-section", "children", allow_duplicate=True),
    Input("pipeline-clear-btn", "n_clicks"),
    prevent_initial_call=True,
)
def clear_upload(n_clicks):
    return None, None, None, None
