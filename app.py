from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def simulate_step(
    initial: float,
    income: float,
    spend: float,
    growth_pct: float,
    rate_pct: float,
    years: int,
):
    months = max(1, int(years) * 12)
    r_month = (growth_pct / 100.0) / 12.0
    loan_month = (rate_pct / 100.0) / 12.0

    labels = []

    bbd_portfolio = float(initial)
    bbd_debt = 0.0
    bbd_portfolio_series = []
    bbd_debt_series = []
    bbd_net_worth_series = []
    bbd_ltv_series = []

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
            std_portfolio_series.append(round(std_portfolio, 2))

        if m < months:
            bbd_portfolio = bbd_portfolio * (1.0 + r_month) + income
            bbd_debt = (bbd_debt + spend) * (1.0 + loan_month)

            net_contribution = max(0.0, income - spend)
            std_portfolio = std_portfolio * (1.0 + r_month) + net_contribution

    final_ltv = bbd_ltv_series[-1]

    return {
        "labels": labels,
        "bbd": {
            "portfolio": bbd_portfolio_series,
            "debt": bbd_debt_series,
            "netWorth": bbd_net_worth_series,
            "ltvPct": bbd_ltv_series,
            "finalPortfolio": bbd_portfolio_series[-1],
            "finalDebt": bbd_debt_series[-1],
            "finalNetWorth": bbd_net_worth_series[-1],
            "finalLtvPct": final_ltv,
        },
        "standard": {
            "portfolio": std_portfolio_series,
            "finalPortfolio": std_portfolio_series[-1],
        },
    }


def project_portfolio_only(initial: float, income: float, growth_pct: float, years: int) -> float:
    months = max(1, int(years) * 12)
    r_month = (growth_pct / 100.0) / 12.0
    p = float(initial)
    for _ in range(months):
        p = p * (1.0 + r_month) + income
    return p


def project_debt_only(spend: float, rate_pct: float, years: int) -> float:
    months = max(1, int(years) * 12)
    loan_month = (rate_pct / 100.0) / 12.0
    d = 0.0
    for _ in range(months):
        d = (d + spend) * (1.0 + loan_month)
    return d


def solve_income_for_target_ltv(
    initial: float, spend: float, growth_pct: float, rate_pct: float, years: int, target_ltv_pct: float
) -> float:
    target_debt = project_debt_only(spend, rate_pct, years)
    target_ratio = max(0.001, target_ltv_pct / 100.0)
    required_portfolio = target_debt / target_ratio

    # Бинарный поиск нужного ежемесячного дохода в портфель
    lo, hi = 0.0, 200000.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if project_portfolio_only(initial, mid, growth_pct, years) < required_portfolio:
            lo = mid
        else:
            hi = mid
    return round(hi, 0)


def solve_spend_for_target_ltv(
    initial: float, income: float, growth_pct: float, rate_pct: float, years: int, target_ltv_pct: float
) -> float:
    portfolio = project_portfolio_only(initial, income, growth_pct, years)
    max_debt = portfolio * (max(0.0, target_ltv_pct) / 100.0)

    # Бинарный поиск допустимых ежемесячных трат
    lo, hi = 0.0, 100000.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        if project_debt_only(mid, rate_pct, years) <= max_debt:
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
    initial = float(data.get("initial", 200000))
    income = float(data.get("income", 8000))
    spend = float(data.get("spend", 4000))
    growth = float(data.get("growth", 8.0))
    rate = float(data.get("rate", 4.0))
    years = int(data.get("years", 20))

    ltv_locked = bool(data.get("ltvLocked", False))
    target_ltv = float(data.get("targetLtv", 15.0))
    solved_by = data.get("solvedBy")  # "spend_moved" или "income_moved"

    if ltv_locked:
        if solved_by == "income_moved":
            spend = solve_spend_for_target_ltv(initial, income, growth, rate, years, target_ltv)
        else:
            income = solve_income_for_target_ltv(initial, spend, growth, rate, years, target_ltv)

    sim = simulate_step(initial, income, spend, growth, rate, years)
    sim["resolvedParams"] = {
        "initial": initial,
        "income": income,
        "spend": spend,
        "growth": growth,
        "rate": rate,
        "years": years,
        "targetLtv": round(sim["bbd"]["finalLtvPct"], 2) if not ltv_locked else target_ltv,
    }
    return jsonify(sim)


if __name__ == "__main__":
    app.run(debug=True, port=5000)