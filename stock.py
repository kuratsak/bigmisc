import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yfinance as yf


# Quarterly Momentum Check: Compare 1-year returns
def get_return(ticker):
    hist = yf.Ticker(ticker).history(period="1y")
    return (hist["Close"].iloc[-1] / hist["Close"].iloc[0]) - 1


def check_ira_rotation(stock1="EQQS.L", stock2="SPXS.L"):
    # Tickers: Nasdaq 100 vs S&P 500
    stock1_ret = get_return(stock1)
    stock2_ret = get_return(stock2)

    print(f"stock1 ({stock1}): {stock1_ret:.2%}")
    print(f"stock2 ({stock2}): {stock2_ret:.2%}")

    winner, loser = (stock1, stock2) if stock1_ret > stock2_ret else (stock2, stock1)
    win_val = max(stock1_ret, stock2_ret)

    print(f"Yields for stock 1&2: {stock1_ret:.5f}, {stock2_ret:.5f}")

    if win_val < 0:
        print("ACTION: Both negative. MOVE TO CASH (BIL).")
    else:
        print(f"ACTION: hold 70% in {winner} and 30% in {loser}.")


def decay_model(x, a, b, c):
    """Exponential decay toward an asymptote c."""
    return a * np.exp(-b * x) + c


def analyze_relative_yield(
    # t1="EIMI.L",
    # t2="IS-FF101.TA", # EM IMI
    t1="SPXS.L",
    # t1="CSPX.L",
    # t2="SPXS.MI",
    t2="IN-FF1.TA",  # 1183441, spxs in TASE exchange
    # t2="CNDX.L",  # 1183441, spxs in TASE exchange
    fx_ticker="ILSUSD=X",
    # fx_ticker=None,
    # fx_ticker="EURUSD=X",
    start="2015-04-01",
    end="2026-04-16",
    future_months=12,
):
    if fx_ticker.lower() == "none":
        fx_ticker = None

    t1 = t1.upper()
    t2 = t2.upper()

    getName = lambda ticker: yf.Ticker(ticker).info["longName"]
    fx_info = f"{fx_ticker}:{getName(fx_ticker)}" if fx_ticker else ""
    t1Name = getName(t1)
    t2Name = getName(t2)

    print(f"analyzing tickers: {t1}, {t2} with fx_ticker {fx_ticker}")
    print(f"Full names:\n{t1}:{t1Name}\n{t2}:{t2Name}\n{fx_info}")

    data = yf.download(
        [t1, t2] + ([fx_ticker] if fx_ticker else []), start=start, end=end
    )["Close"]
    df = data.dropna()

    # 1. Raw Series (USD Normalized)
    p_a = df[t1]
    p_b = df[t2] * (1 if not fx_ticker else df[fx_ticker] / 100)

    # 2. Rolling 1-Year Yield vs Raw Ratio Toggle
    use_raw_ratio = False
    # use_raw_ratio = True
    if use_raw_ratio:
        ann_gap_full = (p_a / p_b) * 100 - 100
    else:
        # Rolling 1Y (252 days) yield: (Price_t / Price_{t-252}) - 1
        yield_a = p_a.pct_change(252)
        yield_b = p_b.pct_change(252)
        ann_gap_full = (yield_a / yield_b) * 100 - 100

    ann_gap = ann_gap_full.dropna()
    print(f"Total data found (before cut): {len(df)}")
    print(f"Total data found (after rolling cut): {len(ann_gap)}")

    # 3. Logarithmic Trend & Robust Floor
    lower_b, upper_b = ann_gap.quantile([0.002, 0.998])
    ann_gap_clean = ann_gap[(ann_gap >= lower_b) & (ann_gap <= upper_b)]

    x_data = np.arange(1, len(ann_gap_clean) + 1)
    y_data = ann_gap_clean.values

    coeffs = np.polyfit(np.log(x_data), y_data, 1)

    # Rolling Median & Average (252-day window)
    rolling_med = ann_gap.rolling(window=252).median()
    rolling_avg = ann_gap.rolling(window=252).mean()
    floor_val = ann_gap.iloc[-52:].median() if len(ann_gap) >= 52 else ann_gap.median()

    # Noise: 2 Standard Deviations of residuals
    residuals = y_data - (coeffs[0] * np.log(x_data) + coeffs[1])
    std_error = np.std(residuals) * 2
    print(residuals, std_error)

    plt.figure(figsize=(14, 7))
    plt.scatter(
        ann_gap_full.index,
        ann_gap_full,
        s=2,
        color="tab:blue",
        alpha=0.5,
        label=f"Annual yield of {t1}/{t2}",
    )

    # 4. Extrapolation & Confidence Band (~21 trading days per month)
    x_ext = np.arange(1, len(ann_gap) + int(future_months * 21) + 1)
    future_dates = pd.date_range(ann_gap.index[0], periods=len(x_ext), freq="B")
    trend_line = coeffs[0] * np.log(x_ext) + coeffs[1]

    plt.plot(
        future_dates,
        trend_line,
        "k--",
        alpha=0.6,
        label=f"Log Trend (End: {trend_line[-1]:.3f}%)",
    )
    plt.fill_between(
        future_dates,
        trend_line - std_error,
        trend_line + std_error,
        color="gray",
        alpha=0.15,
        label="95% Noise Band",
    )
    plt.plot(
        ann_gap.index, rolling_med, color="blue", lw=1.5, label="Rolling 1Y Median"
    )
    plt.plot(
        ann_gap.index,
        rolling_avg,
        color="cyan",
        lw=1,
        alpha=0.7,
        label="Rolling 1Y Avg",
    )
    plt.axhline(
        floor_val,
        color="blue",
        ls=":",
        alpha=0.4,
        label=f"Current Floor ({floor_val:.3f}%)",
    )
    plt.axhline(0, color="red", lw=0.5, label="Zero Gap")

    plt.title(
        f"Structural Efficiency Floor: {t1} vs {t2}\n\n{t1}:{t1Name}\n{t2}:{t2Name}"
    )
    plt.ylabel("Annualized Yield Difference (%)")
    plt.legend()
    plt.grid(True, alpha=0.2)

    print(f"Calculated Structural Floor (12M Median): {floor_val:.3f}%")
    print(f"Projected Long-term Trend: {trend_line[-1]:.3f}%")
    plt.show()


def analyze_strict_overlap(t1="SPXS.L", t2="IN-FF1.TA", fx="ILSUSD=X"):
    # 1. Fetch 1m data (limit 7 days)
    data = yf.download([t1, t2, fx], period="360d", interval="1d")["Close"]

    # 2. Strict Filter: Only keep rows where ALL 3 exist
    # This removes all periods where any market is closed
    df_strict = data.dropna()

    if df_strict.empty:
        print("No simultaneous data found for these tickers.")
        return

    # 3. Currency translation (Agorot to Shekel / 100)
    p1_usd = df_strict[t1]
    p2_usd = (df_strict[t2] / 100.0) * df_strict[fx]

    # 4. Plotting
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10), sharex=True)

    # Use scatter to visualize the 'dots' of actual data points
    ax1.scatter(df_strict.index, p1_usd, s=1, color="tab:blue", label=f"{t1} (USD)")
    ax1.scatter(df_strict.index, p2_usd, s=1, color="tab:orange", label=f"{t2} (USD)")

    ax1.set_title("Strict Simultaneous 1m Price (No Gaps/Fills)")
    ax1.set_ylabel("USD Price")
    ax1.legend()
    ax1.grid(True, alpha=0.2)

    # Price Ratio
    ratio = p1_usd / p2_usd
    ax2.scatter(df_strict.index, ratio, s=1, color="tab:red", label="Price Ratio")
    ax2.set_title("Relative Yield Ratio (Calculated only on Overlap)")
    ax2.set_ylabel("Ratio")
    ax2.legend()
    ax2.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    import sys

    # check_ira_rotation()
    # analyze_strict_overlap()
    if len(sys.argv) > 1:
        analyze_relative_yield(*sys.argv[1:])
    else:
        analyze_relative_yield()
