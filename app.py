from flask import Flask, render_template, request, jsonify

app = Flask(__name__)


def simulate_models(
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
            "finalLtvPct": bbd_ltv_series[-1],
        },
        "standard": {
            "portfolio": std_portfolio_series,
            "finalPortfolio": std_portfolio_series[-1],
        },
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/simulate", methods=["POST"])
def api_simulate():
    data = request.get_json(force=True)
    result = simulate_models(
        initial=float(data.get("initial", 350000)),
        income=float(data.get("income", 7000)),
        spend=float(data.get("spend", 4000)),
        growth_pct=float(data.get("growth", 8.0)),
        rate_pct=float(data.get("rate", 4.0)),
        years=int(data.get("years", 15)),
    )
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5000)