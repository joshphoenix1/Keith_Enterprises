from dash import html, dcc
from config import COLORS


INPUT_STYLE = {
    "backgroundColor": COLORS["input_bg"],
    "border": f"1px solid {COLORS['input_border']}",
    "color": COLORS["text"],
    "borderRadius": "8px",
    "padding": "8px 12px",
    "width": "100%",
    "fontSize": "0.9rem",
}

DROPDOWN_STYLE = {
    "backgroundColor": COLORS["input_bg"],
    "color": COLORS["text"],
}


def styled_input(id, placeholder="", type="number", value=None, **kwargs):
    return dcc.Input(
        id=id,
        type=type,
        placeholder=placeholder,
        value=value,
        style=INPUT_STYLE,
        className="dark-input",
        **kwargs,
    )


def styled_dropdown(id, options, value=None, placeholder="Select...", **kwargs):
    return dcc.Dropdown(
        id=id,
        options=options,
        value=value,
        placeholder=placeholder,
        className="dark-dropdown",
        style={"fontSize": "0.9rem"},
        **kwargs,
    )


def styled_slider(id, min_val=0, max_val=100, value=50, step=1, marks=None):
    return dcc.Slider(
        id=id,
        min=min_val,
        max=max_val,
        value=value,
        step=step,
        marks=marks or {min_val: str(min_val), max_val: str(max_val)},
        className="dark-slider",
    )


def form_group(label, input_component, help_text=None):
    children = [
        html.Label(label, style={
            "color": COLORS["text"], "fontSize": "0.85rem",
            "fontWeight": "500", "marginBottom": "4px", "display": "block",
        }),
        input_component,
    ]
    if help_text:
        children.append(html.Small(help_text, style={"color": COLORS["text_muted"]}))
    return html.Div(children, style={"marginBottom": "16px"})
