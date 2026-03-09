import json
import os
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_products():
    with open(os.path.join(DATA_DIR, "products.json")) as f:
        return json.load(f)


def save_products(products):
    with open(os.path.join(DATA_DIR, "products.json"), "w") as f:
        json.dump(products, f, indent=2)


def load_suppliers():
    with open(os.path.join(DATA_DIR, "suppliers.json")) as f:
        return json.load(f)


def save_suppliers(suppliers):
    with open(os.path.join(DATA_DIR, "suppliers.json"), "w") as f:
        json.dump(suppliers, f, indent=2)


def load_niches():
    return pd.read_csv(os.path.join(DATA_DIR, "niches.csv"))


def load_activity():
    with open(os.path.join(DATA_DIR, "activity.json")) as f:
        return json.load(f)


def estimate_fba_fee(weight_lb, length=0, width=0, height=0):
    """Estimate FBA fulfillment fee based on weight and size."""
    if weight_lb <= 0.5:
        base = 3.22
    elif weight_lb <= 1.0:
        base = 3.86
    elif weight_lb <= 2.0:
        base = 5.26
    elif weight_lb <= 3.0:
        base = 5.88
    else:
        base = 5.88 + (weight_lb - 3.0) * 0.40
    return round(base, 2)


def calc_referral_fee(price, category="default"):
    """Calculate Amazon referral fee (typically 15%)."""
    rates = {
        "default": 0.15,
        "Cell Phones & Accessories": 0.08,
        "Consumer Electronics": 0.08,
        "Clothing & Accessories": 0.17,
    }
    rate = rates.get(category, 0.15)
    return round(price * rate, 2)


def calc_feasibility(price, cost, fba_fee, referral_fee, monthly_sales,
                     ad_spend_pct=0.10, other_costs=0):
    """Calculate full feasibility metrics for a product."""
    revenue = price * monthly_sales
    total_cost_per_unit = cost + fba_fee + referral_fee
    ad_spend_per_unit = price * ad_spend_pct
    all_costs = total_cost_per_unit + ad_spend_per_unit + other_costs

    profit_per_unit = price - all_costs
    margin = (profit_per_unit / price * 100) if price > 0 else 0
    monthly_profit = profit_per_unit * monthly_sales
    roi = (profit_per_unit / cost * 100) if cost > 0 else 0

    # Feasibility score (0-100)
    score = 0
    if margin > 30:
        score += 35
    elif margin > 20:
        score += 25
    elif margin > 10:
        score += 15
    else:
        score += 5

    if roi > 100:
        score += 25
    elif roi > 50:
        score += 18
    elif roi > 25:
        score += 10
    else:
        score += 3

    if monthly_profit > 3000:
        score += 25
    elif monthly_profit > 1500:
        score += 18
    elif monthly_profit > 500:
        score += 10
    else:
        score += 3

    if monthly_sales > 500:
        score += 15
    elif monthly_sales > 200:
        score += 10
    elif monthly_sales > 50:
        score += 5

    score = min(score, 100)

    if score >= 75:
        verdict = "GO"
    elif score >= 50:
        verdict = "MAYBE"
    else:
        verdict = "NO GO"

    return {
        "revenue": round(revenue, 2),
        "total_cost_per_unit": round(all_costs, 2),
        "profit_per_unit": round(profit_per_unit, 2),
        "margin": round(margin, 1),
        "monthly_profit": round(monthly_profit, 2),
        "roi": round(roi, 1),
        "score": score,
        "verdict": verdict,
        "ad_spend_per_unit": round(ad_spend_per_unit, 2),
    }
