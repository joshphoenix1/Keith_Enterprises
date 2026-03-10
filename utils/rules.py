import json
import os

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "rules.json")

DEFAULT_RULES = {
    "auto_reject": {
        "enabled": True,
        "min_margin_pct": 15,
        "min_roi_pct": 30,
        "max_competitors": 50,
        "min_monthly_sales": 50,
        "max_bsr": 100000,
    },
    "auto_accept": {
        "enabled": True,
        "min_margin_pct": 35,
        "min_roi_pct": 100,
        "max_competitors": 10,
        "min_monthly_sales": 300,
        "min_score": 75,
    },
    "alerts": {
        "high_margin_threshold": 40,
        "low_competition_threshold": 5,
        "notify_on_go": True,
    },
}


def load_rules() -> dict:
    """Load rules from rules.json, returning defaults if the file is missing or corrupt."""
    if not os.path.exists(RULES_PATH):
        save_rules(DEFAULT_RULES)
        return DEFAULT_RULES
    try:
        with open(RULES_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return DEFAULT_RULES


def save_rules(rules: dict):
    """Persist rules dict to rules.json."""
    with open(RULES_PATH, "w") as f:
        json.dump(rules, f, indent=2)


def apply_rules(feasibility_result: dict, rules: dict) -> str:
    """Evaluate a feasibility result against the rules engine.

    Parameters
    ----------
    feasibility_result : dict
        Output of ``calc_feasibility`` — expected keys include *margin*, *roi*,
        *score*, *monthly_sales* (or the caller may pass it in), *num_competitors*,
        and *bsr*.
    rules : dict
        The full rules configuration (auto_reject, auto_accept, alerts sections).

    Returns
    -------
    str
        One of ``"auto_accept"``, ``"auto_reject"``, or ``"review"``.
    """
    margin = feasibility_result.get("margin", 0)
    roi = feasibility_result.get("roi", 0)
    score = feasibility_result.get("score", 0)
    monthly_sales = feasibility_result.get("monthly_sales", 0)
    num_competitors = feasibility_result.get("num_competitors", 0)
    bsr = feasibility_result.get("bsr", 0)

    # --- Auto-reject check (any threshold breach triggers rejection) ---
    ar = rules.get("auto_reject", {})
    if ar.get("enabled", False):
        if margin < ar.get("min_margin_pct", 0):
            return "auto_reject"
        if roi < ar.get("min_roi_pct", 0):
            return "auto_reject"
        if num_competitors > 0 and num_competitors > ar.get("max_competitors", 9999):
            return "auto_reject"
        if monthly_sales > 0 and monthly_sales < ar.get("min_monthly_sales", 0):
            return "auto_reject"
        if bsr > 0 and bsr > ar.get("max_bsr", 999999):
            return "auto_reject"

    # --- Auto-accept check (all thresholds must be met) ---
    aa = rules.get("auto_accept", {})
    if aa.get("enabled", False):
        passes = True
        if margin < aa.get("min_margin_pct", 100):
            passes = False
        if roi < aa.get("min_roi_pct", 100):
            passes = False
        if num_competitors > 0 and num_competitors > aa.get("max_competitors", 0):
            passes = False
        if monthly_sales > 0 and monthly_sales < aa.get("min_monthly_sales", 0):
            passes = False
        if score < aa.get("min_score", 100):
            passes = False
        if passes:
            return "auto_accept"

    return "review"
