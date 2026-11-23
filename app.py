from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def simulate_with_dynamic_leverage(
    initial: float,
    income: float,
    spend: float,
    growth_pct: float,
    rate_pct: float,
    years: int,
    target_ltv_pct: float,
    max_step_lev_pct: float = 15.0,
):
    months = max(1, int(years) * 12)
    r_month = (growth_pct / 100.0) / 12.0
    loan_month = (rate_pct / 100.0) / 12.0
    target_ratio = max(0.0, target_ltv_pct) / 100.0
    max_step_ratio = max(0.0, max_step_lev_pct) / 100.0

    labels = []

    bbd_portfolio = float(initial)
    bbd_debt = 0.0
    current_lev_pct = 0.0

    bbd_portfolio_series = []
    bbd_debt_series = []
    bbd_net_worth_series = []
    bbd_ltv_series = []
    lev_usage_series = []

    std_portfolio = float(initial)
    std_portfolio_series = []

    for m in range(months + 1):
        if m % 12 == 0:
            ltv_pct = (bbd_debt / bbd_portfolio * 100.0) if bbd_portfolio > 0 else 0.0
            labels.append(f"Год {m // 12}")
            bbd_portfolio_series.append(round(bbd_portfolio, 2))
            bbd_debt_series.append(round(bbd_debt, 2))
            bbd_net_worth_series.append(round(bbd_portfolio - bbd_debt, 2))
            bbd_ltv_series.append(round(ltv_pct, 2))
            lev_usage_series.append(round(current_lev_pct, 2))
            std_portfolio_series.append(round(std_portfolio, 2))

        if m < months:
            # Начало месяца: оцениваем LTV и при необходимости берем плечо на докупку акций
            # Формула макс. доп. займа x до целевого LTV: (debt + x) / (portfolio + x) = target_ratio
            # => x = (target_ratio * portfolio - debt) / (1 - target_ratio)
            added_leverage = 0.0
            if target_ratio < 0.95 and bbd_portfolio > 0:
                max_allowed_borrow = (target_ratio * bbd_portfolio - bbd_debt) / (1.0 - target_ratio)
                step_cap = bbd_portfolio * max_step_ratio
                if max_allowed_borrow > 0:
                    added_leverage = min(max_allowed_borrow, step_cap)

            current_lev_pct = (added_leverage / bbd_portfolio * 100.0) if bbd_portfolio > 0 else 0.0

            # Добавляем доп. плечо в портфель и в долг, затем прибавляем доход и траты на жизнь
            bbd_portfolio = (bbd_portfolio + added_leverage) * (1.0 + r_month) + income
            bbd_debt = (bbd_debt + added_leverage + spend) * (1.0 + loan_month)

            net_contribution = max(0.0, income - spend)
            std_portfolio = std_portfolio * (1.0 + r_month) + net_contribution

    return {
        "labels": labels,
        "bbd": {
            "portfolio": bbd_portfolio_series,
            "debt": bbd_debt_series,
            "netWorth": bbd_net_worth_series,
            "ltvPct": bbd_ltv_series,
            "levUsagePct": lev_usage_series,
            "finalPortfolio": bbd_portfolio_series[-1],
            "finalDebt": bbd_debt_series[-1],
            "finalNetWorth": bbd_net_worth_series[-1],
            "finalLtvPct": bbd_ltv_series[-1],
            "finalLevUsagePct": lev_usage_series[-1],
        },
        "standard": {
            "portfolio": std_portfolio_series,
            "finalPortfolio": std_portfolio_series[-1],
        },
    }


def solve_income_for_target_ltv(
    initial: float,
    spend: float,
    growth_pct: float,
    rate_pct: float,
    years: int,
    target_ltv_pct: float,
    max_step_lev_pct: float,
) -> float:
    lo, hi = 0.0, 250000.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        sim = simulate_with_dynamic_leverage(
            initial, mid, spend, growth_pct, rate_pct, years, target_ltv_pct, max_step_lev_pct
        )
        # При большем доходе портфель больше -> LTV ниже
        if sim["bbd"]["finalLtvPct"] > target_ltv_pct:
            lo = mid
        else:
            hi = mid
    return round(hi, 0)


def solve_spend_for_target_ltv(
    initial: float,
    income: float,
    growth_pct: float,
    rate_pct: float,
    years: int,
    target_ltv_pct: float,
    max_step_lev_pct: float,
) -> float:
    lo, hi = 0.0, 100000.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        sim = simulate_with_dynamic_leverage(
            initial, income, mid, growth_pct, rate_pct, years, target_ltv_pct, max_step_lev_pct
        )
        # При меньших тратах долг меньше -> LTV ниже
        if sim["bbd"]["finalLtvPct"] <= target_ltv_pct:
            lo = mid
        else:
            hi = mid
    return round(lo, 0)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    data = request.get_json(force=True)
    initial = float(data.get("initial", 300000))
    income = float(data.get("income", 12000))
    spend = float(data.get("spend", 4000))
    growth = float(data.get("growth", 8.0))
    rate = float(data.get("rate", 4.0))
    years = int(data.get("years", 20))
    target_ltv = float(data.get("targetLtv", 15.0))
    max_step_lev = float(data.get("maxStepLev", 15.0))

    ltv_locked = bool(data.get("ltvLocked", False))
    solved_by = data.get("solvedBy")

    if ltv_locked:
        if solved_by == "income_moved":
            spend = solve_spend_for_target_ltv(initial, income, growth, rate, years, target_ltv, max_step_lev)
        else:
            income = solve_income_for_target_ltv(initial, spend, growth, rate, years, target_ltv, max_step_lev)

    sim = simulate_with_dynamic_leverage(initial, income, spend, growth, rate, years, target_ltv, max_step_lev)
    sim["resolvedParams"] = {
        "initial": initial,
        "income": income,
        "spend": spend,
        "growth": growth,
        "rate": rate,
        "years": years,
        "maxStepLev": max_step_lev,
        "targetLtv": round(sim["bbd"]["finalLtvPct"], 2) if not ltv_locked else target_ltv,
    }
    return jsonify(sim)


if __name__ == "__main__":
    app.run(debug=True, port=5000)