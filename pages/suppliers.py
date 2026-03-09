from dash import html, dcc, callback, Input, Output, State
from config import COLORS
from components.cards import info_card
from components.forms import styled_input, styled_dropdown, form_group
from components.tables import dark_table
from components.pills import pill
from utils.data import load_suppliers, save_suppliers


def layout():
    suppliers = load_suppliers()

    columns = [
        {"name": "Name", "id": "name"},
        {"name": "Platform", "id": "platform"},
        {"name": "Country", "id": "country"},
        {"name": "Products", "id": "products"},
        {"name": "MOQ", "id": "moq"},
        {"name": "Lead Time", "id": "lead_time_days"},
        {"name": "Rating", "id": "rating"},
        {"name": "Verified", "id": "verified_str"},
    ]
    data = [{**s, "verified_str": "✓ Yes" if s["verified"] else "✗ No"} for s in suppliers]

    form = html.Div([
        html.Div([
            form_group("Supplier Name",
                       styled_input("suppliers-name", "Company name", type="text")),
            form_group("Platform",
                       styled_dropdown("suppliers-platform",
                                       [{"label": p, "value": p} for p in
                                        ["Alibaba", "1688", "Made-in-China", "IndiaMART", "Other"]],
                                       "Alibaba")),
        ], className="grid-row grid-2"),
        html.Div([
            form_group("Country",
                       styled_input("suppliers-country", "China", type="text", value="China")),
            form_group("Products",
                       styled_input("suppliers-products", "Product types", type="text")),
            form_group("MOQ",
                       styled_input("suppliers-moq", "500", value=500)),
            form_group("Lead Time (days)",
                       styled_input("suppliers-leadtime", "20", value=20)),
        ], className="grid-row grid-4"),
        html.Div([
            form_group("Rating (1-5)",
                       styled_input("suppliers-rating", "4.5", value=4.5,
                                    min=1, max=5, step=0.1)),
            form_group("Contact Email",
                       styled_input("suppliers-contact", "email@example.com", type="text")),
            form_group("Notes",
                       styled_input("suppliers-notes", "Notes...", type="text")),
        ], className="grid-row grid-3"),
        html.Button([html.I(className="bi bi-plus-circle me-2"), "Add Supplier"],
                    id="suppliers-add-btn", className="btn-primary-dark",
                    style={"marginTop": "8px"}),
        html.Div(id="suppliers-add-status", style={"marginTop": "8px"}),
    ])

    return html.Div([
        html.Div([
            html.H2("Suppliers"),
            html.P("Manage and compare your supplier contacts"),
        ], className="page-header"),

        html.Div([
            info_card("Supplier Directory",
                      html.Div(id="suppliers-table-container",
                               children=dark_table("suppliers-table", columns, data)),
                      "bi-truck"),
        ]),

        html.Div([
            info_card("Add New Supplier", form, "bi-plus-circle"),
        ], style={"marginTop": "20px"}),
    ])


@callback(
    Output("suppliers-table-container", "children"),
    Output("suppliers-add-status", "children"),
    Input("suppliers-add-btn", "n_clicks"),
    State("suppliers-name", "value"),
    State("suppliers-platform", "value"),
    State("suppliers-country", "value"),
    State("suppliers-products", "value"),
    State("suppliers-moq", "value"),
    State("suppliers-leadtime", "value"),
    State("suppliers-rating", "value"),
    State("suppliers-contact", "value"),
    State("suppliers-notes", "value"),
    prevent_initial_call=True,
)
def add_supplier(n_clicks, name, platform, country, products, moq, leadtime,
                 rating, contact, notes):
    if not name:
        return (
            _build_table(),
            html.Span("Please enter a supplier name",
                      style={"color": COLORS["danger"], "fontSize": "0.85rem"}),
        )

    suppliers = load_suppliers()
    new_supplier = {
        "id": max((s["id"] for s in suppliers), default=0) + 1,
        "name": name,
        "platform": platform or "Alibaba",
        "country": country or "China",
        "products": products or "",
        "moq": int(moq or 500),
        "lead_time_days": int(leadtime or 20),
        "rating": float(rating or 4.0),
        "verified": False,
        "contact": contact or "",
        "notes": notes or "",
    }
    suppliers.append(new_supplier)
    save_suppliers(suppliers)

    return (
        _build_table(),
        html.Span([html.I(className="bi bi-check-circle me-2"), f"Added {name}!"],
                  style={"color": COLORS["success"], "fontSize": "0.85rem"}),
    )


def _build_table():
    suppliers = load_suppliers()
    columns = [
        {"name": "Name", "id": "name"},
        {"name": "Platform", "id": "platform"},
        {"name": "Country", "id": "country"},
        {"name": "Products", "id": "products"},
        {"name": "MOQ", "id": "moq"},
        {"name": "Lead Time", "id": "lead_time_days"},
        {"name": "Rating", "id": "rating"},
        {"name": "Verified", "id": "verified_str"},
    ]
    data = [{**s, "verified_str": "✓ Yes" if s["verified"] else "✗ No"} for s in suppliers]
    return dark_table("suppliers-table", columns, data)
