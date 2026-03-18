def gemel(years, r=1.06, y=80, cut=10):
    """rough estimate of tax with real earnings"""
    s = 0
    for i in range(1, years + 1):
        s += y * (r**i)
    totals = [0.25 * (y * (r**i) - y) for i in range(1, years + 1)]
    invested = y * years
    nominal_tax = 0.25 * (s - invested)
    postcut = len(totals) - cut
    print(
        "total, tax, invested, saved_ratio: "
        f"{s:.2f}, "
        f"{nominal_tax:.2f}, "
        f"{invested:.2f}, "
        f"{100 * nominal_tax / invested:.1f}%"
    )
    return (
        s,
        nominal_tax,
        invested,
        (100 * sum(totals[-cut:]) / sum(totals), sum(totals[-cut:]), cut),
        (100 * sum(totals[:postcut]) / sum(totals), sum(totals[:postcut]), postcut),
        totals[-3:],
    )


def savings(
    years=30,
    cut=10,
    annual_deposit=80,
    growth=1.09,
    inflation=1.03,
    mgmt_gemel_coefficient=0.993,
    mgmt_self_coefficient=0.9995,
    should_print=True,
):
    """intelligent estimate including inflation, tax, and gemel expense management cost ~0.7% vs 0.03"""
    if cut > years - 1:
        print(f"adjusting cut:{cut} to half of years:{years} -> {years/2}")
        cut = int(years / 2)

    def get_totals(rate):
        # Every year is a deposit year.
        return [annual_deposit * (rate**i) for i in range(years, 0, -1)]

    # Base calculations
    theoretical_totals = get_totals(growth)
    sum_theoretical_gross = sum(theoretical_totals)
    invested = annual_deposit * years

    # Tracks
    self_totals = get_totals(growth * mgmt_self_coefficient)
    gemel_totals = get_totals(growth * mgmt_gemel_coefficient)
    inflated_principals = get_totals(inflation)

    # Global Costs
    tax_self = max(0, (sum(self_totals) - sum(inflated_principals)) * 0.25)
    tax_honi = max(0, (sum(gemel_totals) - invested) * 0.15)
    fees_self = sum_theoretical_gross - sum(self_totals)
    fees_gemel = sum_theoretical_gross - sum(gemel_totals)

    if should_print:
        print(f"--- Analysis: {years}y Horizon | Cut at {cut}y ---")
        print(f"Total Invested: {invested:,}")
        print(
            f"First 3 deposits final values (Self, "
            f"{100*sum(self_totals[:3])/sum(self_totals):.1f}%):"
            f"{[round(x) for x in self_totals[:3]]}\n"
        )

    options = [
        ("Self Trading", self_totals, tax_self, fees_self),
        ("Gemel Honi", gemel_totals, tax_honi, fees_gemel),
        ("Gemel Kitzba", gemel_totals, 0, fees_gemel),
    ]

    return_data = {}
    for name, totals_array, tax, fees in options:
        total_gross = sum_theoretical_gross
        net = total_gross - tax - fees

        # Contribution Analysis: First 'cut' years vs the rest
        sum_cut = sum(totals_array[:cut])
        sum_rest = total_gross - sum_cut

        p_cut = 100 * sum_cut / total_gross
        p_rest = 100 * sum_rest / total_gross

        if should_print:
            print(f"[{name}], net total: {net:,.0f}")
            print(f"Accumulated Total Gross: {total_gross:,.0f}")
            print(f"Accumulated Total Net (post tax+fees): {net:,.0f}")
            print(f"Total Paid: {tax + fees:,.0f} (Tax: {tax:,.0f}, Fees: {fees:,.0f})")
            print(
                f"First {cut}y: {p_cut:.1f}% ({round(sum_cut):,}) | Remaining {years - cut}y: {p_rest:.1f}% ({round(sum_rest):,})"
            )
            print("-" * 30)

        return_data[name] = {"net": net, "tax": tax, "fees": fees, "gross": total_gross}

    return return_data


def find_break_even(
    total_years=30,
    cut=10,
    annual_deposit=80,
    inflation_rate=1.03,
    start_yield=1.01,
    end_yield=1.2,
):
    stop_at = 0
    # loop to find where Gemel Kitzba beats Self Trading
    print(
        f"{'Yield':<10} | {'Relative':<10} | {'Self Net':<12} | {'Kitzba Net':<12} | {'Winner'}"
    )
    print("-" * 50)

    current_yield = start_yield
    while stop_at < 3 and current_yield <= end_yield:
        results = savings(
            years=total_years,
            cut=cut,
            annual_deposit=annual_deposit,
            growth=current_yield,
            inflation=inflation_rate,
            should_print=False,
        )

        self_net = results["Self Trading"]["net"]
        kitzba_net = results["Gemel Kitzba"]["net"]
        winner = "Kitzba" if kitzba_net > self_net else "Self"
        relative = 100 * kitzba_net / self_net

        print(
            f"{current_yield:<10.2f} | {f'{relative:.2f}%':<10} | {self_net:<12,.0f} | {kitzba_net:<12,.0f} | {winner}"
        )

        if stop_at == 0:
            if kitzba_net > self_net * 1.1:
                print(f"^ Break-even found at yield: {current_yield:.2f}")
                stop_at += 1
        else:
            stop_at += 1

        current_yield += 0.01


# Run Example
savings(years=30, cut=10)
