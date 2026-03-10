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
                     ad_spend_pct=0.10, other_costs=0,
                     num_competitors=0, avg_reviews=0, avg_rating=0,
                     avg_competitor_price=0, bsr=0, moq=0, lead_time=0,
                     shipping_cost=0, storage_cost=0):
    """Calculate full feasibility metrics for a product."""
    revenue = price * monthly_sales
    total_cost_per_unit = cost + fba_fee + referral_fee + shipping_cost
    ad_spend_per_unit = price * ad_spend_pct
    all_costs = total_cost_per_unit + ad_spend_per_unit + other_costs + storage_cost

    profit_per_unit = price - all_costs
    margin = (profit_per_unit / price * 100) if price > 0 else 0
    monthly_profit = profit_per_unit * monthly_sales
    roi = (profit_per_unit / cost * 100) if cost > 0 else 0
    annual_profit = monthly_profit * 12
    initial_investment = cost * max(moq, monthly_sales) + (shipping_cost * max(moq, monthly_sales))
    breakeven_units = int(all_costs / profit_per_unit) if profit_per_unit > 0 else 0

    # Feasibility score (0-100) — weighted across 6 dimensions
    score = 0

    # 1. Margin score (max 20)
    if margin > 30:
        score += 20
    elif margin > 20:
        score += 14
    elif margin > 10:
        score += 8
    else:
        score += 3

    # 2. ROI score (max 20)
    if roi > 100:
        score += 20
    elif roi > 50:
        score += 14
    elif roi > 25:
        score += 8
    else:
        score += 3

    # 3. Monthly profit score (max 20)
    if monthly_profit > 3000:
        score += 20
    elif monthly_profit > 1500:
        score += 14
    elif monthly_profit > 500:
        score += 8
    else:
        score += 3

    # 4. Sales volume score (max 15)
    if monthly_sales > 500:
        score += 15
    elif monthly_sales > 200:
        score += 10
    elif monthly_sales > 50:
        score += 5

    # 5. Competition score (max 15) — lower competition = higher score
    if num_competitors > 0:
        if num_competitors <= 5:
            score += 15
        elif num_competitors <= 15:
            score += 10
        elif num_competitors <= 30:
            score += 5
        else:
            score += 2

        # Adjust for review barrier
        if avg_reviews > 0:
            if avg_reviews > 1000:
                score -= 5  # very hard to compete
            elif avg_reviews > 500:
                score -= 3
            elif avg_reviews < 100:
                score += 3  # easy to enter
    else:
        score += 8  # no data, neutral

    # 6. Price competitiveness (max 10)
    if avg_competitor_price > 0 and price > 0:
        price_ratio = price / avg_competitor_price
        if 0.85 <= price_ratio <= 1.0:
            score += 10  # slightly undercut
        elif 0.7 <= price_ratio < 0.85:
            score += 7   # significantly cheaper
        elif 1.0 < price_ratio <= 1.15:
            score += 6   # slightly more expensive
        else:
            score += 3   # way off
    else:
        score += 5  # no data

    score = max(0, min(score, 100))

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
        "annual_profit": round(annual_profit, 2),
        "roi": round(roi, 1),
        "score": score,
        "verdict": verdict,
        "ad_spend_per_unit": round(ad_spend_per_unit, 2),
        "initial_investment": round(initial_investment, 2),
        "breakeven_units": breakeven_units,
        "shipping_cost": round(shipping_cost, 2),
        "storage_cost": round(storage_cost, 2),
    }
