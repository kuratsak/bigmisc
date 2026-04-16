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


def drop_outliers(obj, lower_bound=0.003, upper_bound=0.997):
    lower_b, upper_b = obj.quantile([lower_bound, upper_bound])
    print("dropping outliers:\n", obj[(obj < lower_b) | (obj > upper_b)])
    return obj[(obj >= lower_b) & (obj <= upper_b)]


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
    use_raw_ratio=None,
    # use_raw_ratio=True
    start="2015-04-01",
    end="2026-04-16",
    future_months=12,
):
    if fx_ticker.lower() == "none":
        fx_ticker = None

    if use_raw_ratio is not None:
        use_raw_ratio = use_raw_ratio.lower() in ["raw", "flat"]

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

    p_a = drop_outliers(p_a)
    p_b = drop_outliers(p_b)

    full_idx = pd.date_range(start=df.index.min(), end=df.index.max(), freq="D")
    p_a_daily = p_a.reindex(full_idx).ffill(limit=7)
    p_b_daily = p_b.reindex(full_idx).ffill(limit=7)

    # 2. Rolling 1-Year Yield vs Raw Ratio Toggle
    if use_raw_ratio:
        ann_gap_full = (p_a_daily / p_b_daily) * 100 - 100
    else:
        # Rolling 365-day yield based on DATE, not ROW COUNT
        yield_a = (p_a_daily / p_a_daily.shift(365)) - 1
        yield_b = (p_b_daily / p_b_daily.shift(365)) - 1

        # Align back to the original trading days to remove weekend noise
        yield_a = yield_a.reindex(df.index)
        yield_b = yield_b.reindex(df.index)

        # Use subtraction for the gap (Avoids the division-by-zero 1000% jumps)
        ann_gap_full = (yield_a - yield_b) * 100

    ann_gap = ann_gap_full.ffill()
    print(f"Total data found (before cut): {len(df)}")
    print(f"Total data found (after rolling cut): {len(ann_gap)}")

    # 3. Logarithmic Trend & Robust Floor
    ann_gap_clean = drop_outliers(ann_gap)

    x_data = np.arange(1, len(ann_gap_clean) + 1)
    y_data = ann_gap_clean.values

    coeffs = np.polyfit(np.log(x_data), y_data, 1)

    # Rolling Median & Average (1 year window)
    rolling_med = ann_gap.rolling(window=365).median()
    # rolling_avg = ann_gap.rolling(window=365).mean()

    floor_val = (
        ann_gap_full.iloc[-365:].median()
        if len(ann_gap_full) >= 365
        else ann_gap_full.median()
    )

    # 1. Calculate the raw long-term alpha (expanding window)
    days_passed = np.arange(1, len(p_a_daily) + 1)
    cum_yield_a = (p_a_daily / p_a_daily.ffill().iloc[0]) ** (365 / days_passed) - 1
    cum_yield_b = (p_b_daily / p_b_daily.ffill().iloc[0]) ** (365 / days_passed) - 1
    long_term_alpha_raw = (cum_yield_a - cum_yield_b) * 100

    # 2. Use EMA instead of Median for "soft" outlier rejection
    # span=63 (~3 months) provides stability without erasing real trends
    long_term_alpha_smooth = long_term_alpha_raw.ewm(span=63, adjust=False).mean()

    # 3. Trim the noisy start (first year)
    long_term_alpha = long_term_alpha_smooth.iloc[365:]

    # Noise: 2 Standard Deviations of residuals
    residuals = y_data - (coeffs[0] * np.log(x_data) + coeffs[1])
    std_error = np.std(residuals) * 2

    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()

    ax1.scatter(
        ann_gap_full.index,
        ann_gap_full,
        s=2,
        color="tab:blue",
        alpha=0.5,
        label=f"Annual yield of {t1}/{t2}",
    )

    # long term year adjusted yield
    ax1.plot(
        long_term_alpha.index,
        long_term_alpha,
        color="#E66101",
        lw=1.5,
        label="Cumulative Annualized Yield (EMA smoothed)",
    )

    # 4. Extrapolation & Confidence Band (~21 trading days per month)
    x_ext = np.arange(1, len(ann_gap) + int(future_months * 21) + 1)
    future_dates = pd.date_range(ann_gap.index[0], periods=len(x_ext), freq="B")
    trend_line = coeffs[0] * np.log(x_ext) + coeffs[1]

    ax1.plot(
        future_dates,
        trend_line,
        "k--",
        alpha=0.6,
        label=f"Log Trend (End: {trend_line[-1]:.3f}%)",
    )
    ax1.fill_between(
        future_dates,
        trend_line - std_error,
        trend_line + std_error,
        color="gray",
        alpha=0.15,
        label="95% Noise Band",
    )
    ax1.plot(
        ann_gap.index, rolling_med, color="blue", lw=1.5, label="Rolling 1Y Median"
    )
    # ax1.plot(
    #     ann_gap.index,
    #     rolling_avg,
    #     color="cyan",
    #     lw=1,
    #     alpha=0.7,
    #     label="Rolling 1Y Avg",
    # )
    ax1.axhline(
        floor_val,
        color="blue",
        ls=":",
        alpha=0.4,
        label=f"Current Floor ({floor_val:.3f}%)",
    )
    ax1.axhline(0, color="red", lw=0.5)

    # Normalized growth lines for sanity check
    raw_a_growth = (p_a / p_a.iloc[0] - 1) * 100
    raw_b_growth = (p_b / p_b.iloc[0] - 1) * 100

    ax2.plot(raw_a_growth, color="blue", lw=0.8, alpha=0.5, label=f"{t1} Raw %")
    ax2.plot(raw_b_growth, color="orange", lw=0.8, alpha=0.5, label=f"{t2} Raw %")

    ax2.set_ylabel("Total Asset Growth (%)", color="gray", fontsize=12)
    # Set right axis limits to keep lines in the upper background
    ax2.set_ylim(
        bottom=min(raw_a_growth.min(), raw_b_growth.min()) - 5,
        top=max(raw_a_growth.max(), raw_b_growth.max()) * 1.3,
    )

    ax1.set_ylabel("Alpha / Yield Difference (%)")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left", fontsize=9)

    ax1.grid(True, alpha=0.2)

    print(f"Calculated Structural Floor (12M Median): {floor_val:.3f}%")
    print(f"Projected Long-term Trend: {trend_line[-1]:.3f}%")

    plt.title(
        f"Structural Efficiency vs Total Growth: {t1} vs {t2}\n\n{t1}:{t1Name}\n{t2}:{t2Name}"
    )
    plt.tight_layout()
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
