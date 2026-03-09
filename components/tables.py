from dash import dash_table
from config import COLORS


def dark_table(id, columns, data, **kwargs):
    return dash_table.DataTable(
        id=id,
        columns=columns,
        data=data,
        style_header={
            "backgroundColor": COLORS["sidebar"],
            "color": COLORS["text"],
            "fontWeight": "600",
            "border": f"1px solid {COLORS['card_border']}",
            "fontSize": "0.85rem",
            "padding": "12px 16px",
        },
        style_cell={
            "backgroundColor": COLORS["card"],
            "color": COLORS["text"],
            "border": f"1px solid {COLORS['card_border']}",
            "fontSize": "0.85rem",
            "padding": "10px 16px",
            "textAlign": "left",
        },
        style_data_conditional=[
            {"if": {"state": "active"},
             "backgroundColor": COLORS["hover"],
             "border": f"1px solid {COLORS['card_border']}"},
        ],
        style_filter={
            "backgroundColor": COLORS["input_bg"],
            "color": COLORS["text"],
        },
        page_size=10,
        sort_action="native",
        filter_action="native",
        style_table={"overflowX": "auto"},
        **kwargs,
    )


def sortable_table(id, columns, data, **kwargs):
    return dark_table(id, columns, data,
                      sort_action="native",
                      sort_mode="multi",
                      **kwargs)
