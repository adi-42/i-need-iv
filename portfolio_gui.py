import hashlib
import json
from pathlib import Path
import subprocess

import plotly.graph_objects as go
import streamlit as st

from ppn_data import REFERENCES, RULE, STUDY_PATH, load_study, select_contracts


ENGINE = Path(__file__).resolve().parent / ".gui-build" / "ppn_gui.exe"
GOALS = ["Compare call and put (learning only)", "Rising market: call", "Falling market: put"]
SIZING = ["Fractional (pooled-note illustration)", "Whole listed lots"]


def run_study(study, capital, bond_yield, goal, sizing, minimum_volume, markup):
    if goal not in GOALS or sizing not in SIZING:
        raise ValueError("Unknown payoff objective or sizing mode.")
    selected = select_contracts(study, minimum_volume)
    types = ["call", "put"] if goal == GOALS[0] else ["call" if goal == GOALS[1] else "put"]
    mode = "fractional" if sizing == SIZING[0] else "whole_lots"
    cases = []
    for choice in selected:
        for option in types:
            quote = choice[option]
            args = [
                capital, bond_yield, choice["days"], choice["strike"], quote["premium"],
                choice["entry_spot"], choice["expiry_spot"], choice["lot_size"], option, mode, markup,
            ]
            process = subprocess.run(
                [str(ENGINE), *map(str, args)], capture_output=True, text=True, check=True, timeout=20
            )
            result = json.loads(process.stdout)
            if not isinstance(result, dict) or not {"inputs", "curve", "final_value", "portfolio_return"}.issubset(result):
                raise ValueError("PPN engine returned an unexpected result schema.")
            cases.append({"tenor": choice["tenor"], "expiry": choice["expiry"], "quote": quote, "result": result})
    return {
        "entry_date": study["entry_date"], "window_end": study["window_end"],
        "assumptions": {
            "capital": capital, "annual_effective_bond_yield": bond_yield, "goal": goal,
            "sizing": sizing, "minimum_entry_volume": minimum_volume, "premium_markup": markup,
            "day_count": "ACT/365", "idle_cash_interest": 0,
            "bond": "Hypothetical default-free zero-coupon funding matched to each actual expiry.",
            "exclusions": "Identified bond quotes, issuer/default risk, full fees/taxes/spreads, settlement lag, interim mark-to-market.",
        },
        "selection_rule": RULE, "selected_contracts": selected, "cases": cases,
        "sources": study["sources"], "attribution": study["attribution"],
    }


def show_method(study):
    with st.expander("Decision process: choose the objective, not the historical winner", expanded=True):
        st.write(
            "Call = participate in a rising index. Put = benefit from a falling index. "
            "Compare mode studies both; it does not pick the better realised performer as a recommendation."
        )
        st.write(
            "Contract rule: use only the January 2 snapshot. Pick the closest available monthly expiries "
            "to 1/3/6 months, then the nearest strike with sufficient entry-day volume in BOTH call and put. "
            "Reject pairs more than 5% from spot. The volume floor is an illustrative filter, not proof of liquidity."
        )
        st.write(
            "Funding rule: reserve enough today for an assumed zero-coupon payment equal to the starting capital "
            "on each option's actual expiry. Spend only the remaining budget on long options. "
            "Whole-lot mode rounds down; unused cash earns zero interest."
        )
        st.code(
            "T = actual calendar days / 365\n"
            "bond cost = capital / (1 + assumed annual yield)^T\n"
            "option budget = capital - bond cost\n"
            "purchase premium = observed close * (1 + assumed markup)\n"
            "final wealth = capital + unused cash + option payoff",
            language="text",
        )
        st.warning(
            "KIKO is excluded from these historical results: a vanilla NIFTY quote is not a KIKO premium. "
            "A barrier study needs an actual term sheet, entry premium and a path at the specified monitoring frequency; "
            "four closing-index observations cannot establish barrier events."
        )
    with st.expander("What this case study does NOT establish"):
        st.write(
            "One entry date and three overlapping holding periods are not independent evidence of a profitable strategy. "
            "The bond yield is assumed, not a realised bond investment. Protection exists only at maturity in the "
            "default-free funding model; an actual issuer can default and early sale can lose money."
        )
        st.write(
            "Reported closing premiums are not executable bid/ask quotes. Same-day volume does not establish quote "
            "freshness at a common timestamp. Choosing the strike from the final index close and filling at that "
            "same close is an idealisation, not an executable order replay. The markup is a stress assumption, not measured transaction costs. "
            "Fees, taxes and settlement delays are otherwise omitted. NIFTY comparisons are price returns, excluding dividends."
        )
        st.write(
            "Fractional lots illustrate pooled note replication, not a directly executable small exchange account. "
            "Holding only whole lots may leave too little budget to purchase any option. "
            "The fixed-income comparator reveals foregone interest; return of nominal principal is not a real return after inflation."
        )
    with st.expander("NSE sources and audit trail"):
        st.caption(study["attribution"])
        st.write("Raw archives are preserved unchanged under .market-data\\raw and excluded from Git. Do not redistribute them without permission.")
        for source in study["sources"]:
            st.markdown(f"[{source['file']}]({source['url']})")
            st.caption(f"SHA-256: {source['sha256']} | Cached UTC: {source['cached_at_utc']}")
        for title, url in REFERENCES.items():
            st.markdown(f"[{title}]({url})")


def render_report(report):
    assumptions = report["assumptions"]
    cases = report["cases"]
    st.caption(
        f"Displayed study: entry {report['entry_date']} | Capital INR {assumptions['capital']:,.2f} | "
        f"ASSUMED annual effective yield {assumptions['annual_effective_bond_yield']:.2%} | "
        f"{assumptions['sizing']} | Entry volume floor {assumptions['minimum_entry_volume']:,} | "
        f"Assumed premium markup {assumptions['premium_markup']:.1%}"
    )
    st.dataframe([{
        "Tenor": f"{case['tenor']} ({case['result']['inputs']['days']} days)",
        "Expiry": case["expiry"], "Option": case["result"]["inputs"]["option"],
        "Lots held": round(case["result"]["lots"], 5),
        "Option payoff (INR)": round(case["result"]["option_payoff"], 2),
        "Final wealth (INR)": round(case["result"]["final_value"], 2),
        "Return (%)": round(100 * case["result"]["portfolio_return"], 3),
        "Fixed income (INR)": round(case["result"]["fixed_income_value"], 2),
        "Vs fixed income (INR)": round(case["result"]["excess_over_fixed_income"], 2),
    } for case in cases], hide_index=True, width="stretch")
    st.caption(
        "Each row is an alternative investment of the FULL capital, not a combined call+put position or a rollover strategy. "
        "Returns cover the actual holding period, not a year. Fixed income uses the same hypothetical yield, not an identified historical bond."
    )
    if assumptions["sizing"] == SIZING[0]:
        st.info("Fractional lots are an idealised pooled-note allocation. Switch to Whole listed lots to inspect direct-trading affordability.")
    if any(case["result"]["units"] == 0 for case in cases):
        st.warning("At least one row buys ZERO options. That row is only a bond plus idle cash, not an implemented option-linked position.")
    if any(case["quote"]["volume"] < 100 for case in cases):
        st.warning("A selected quote has fewer than 100 contracts traded at entry. Treat this deliberately thin-volume scenario with particular caution.")

    figure = go.Figure()
    for option in ("call", "put"):
        rows = [case for case in cases if case["result"]["inputs"]["option"] == option]
        if rows:
            figure.add_bar(
                x=[row["tenor"] for row in rows],
                y=[100 * row["result"]["portfolio_return"] for row in rows], name=f"PPN {option}",
            )
    first_by_tenor = {case["tenor"]: case["result"] for case in cases}
    labels = list(first_by_tenor)
    figure.add_bar(
        x=labels,
        y=[100 * (first_by_tenor[label]["fixed_income_value"] / assumptions["capital"] - 1) for label in labels],
        name="Assumed fixed income",
    )
    figure.add_bar(
        x=labels, y=[100 * first_by_tenor[label]["underlying_return"] for label in labels],
        name="Unprotected NIFTY price return",
    )
    figure.add_hline(y=0, line_dash="dash")
    figure.update_layout(
        title="Observed option outcomes + hypothetical funding", xaxis_title="Approximate tenor",
        yaxis_title="Holding-period return (%)", barmode="group", height=400,
    )
    st.plotly_chart(figure, width="stretch")

    tenor = st.selectbox("Inspect maturity payoff", labels, key="ppn_curve_tenor")
    maturity = go.Figure()
    for case in (case for case in cases if case["tenor"] == tenor):
        result = case["result"]
        option = result["inputs"]["option"]
        maturity.add_scatter(
            x=result["curve"]["index"], y=result["curve"]["final_value"], mode="lines", name=f"{option} terminal wealth",
        )
        maturity.add_scatter(
            x=[result["inputs"]["expiry_index"]], y=[result["final_value"]],
            mode="markers", marker_size=11, name=f"{option}: observed expiry",
        )
    maturity.add_hline(y=assumptions["capital"], line_dash="dash", annotation_text="Nominal principal")
    maturity.add_hline(y=first_by_tenor[tenor]["fixed_income_value"], line_dash="dot", annotation_text="Assumed fixed income")
    maturity.update_layout(
        title=f"{tenor}: maturity payoff scenarios, NOT a historical portfolio path",
        xaxis_title="NIFTY at expiry", yaxis_title="Final wealth (INR)", height=400,
    )
    st.plotly_chart(maturity, width="stretch")

    with st.expander("Selected quotes and the reason for each selection", expanded=True):
        st.write(report["selection_rule"])
        st.dataframe([{
            "Tenor": choice["tenor"], "Target date": choice["target_date"], "Actual expiry": choice["expiry"],
            "Nearest listed strike": choice["nearest_listed_strike"], "Selected strike": choice["strike"],
            "Eligible pairs": choice["eligible_pairs"], "Lot size": choice["lot_size"],
            "Entry index": choice["entry_spot"], "Expiry index": choice["expiry_spot"],
            "Call close": choice["call"]["premium"], "Call volume": choice["call"]["volume"],
            "Put close": choice["put"]["premium"], "Put volume": choice["put"]["volume"],
        } for choice in report["selected_contracts"]], hide_index=True, width="stretch")
        st.caption(
            "A selected strike can differ from the nearest listed strike because of the paired liquidity filter. "
            "Longer expiries can have wider strike spacing. The app uses ClsPric, not theoretical or illiquid settlement substitutes."
        )
    with st.expander("Capital allocation and affordability"):
        st.dataframe([{
            "Tenor": case["tenor"], "Option": case["result"]["inputs"]["option"],
            "Bond cost": round(case["result"]["bond_cost"], 2),
            "Option budget": round(case["result"]["option_budget"], 2),
            "Option spend": round(case["result"]["option_spend"], 2),
            "Idle cash": round(case["result"]["idle_cash"], 2),
            "Option P&L": round(case["result"]["option_pnl"], 2),
            "Option notional / capital (%)": round(100 * case["result"]["notional_ratio"], 2),
            "Minimum capital for one lot": case["result"]["minimum_capital_one_lot"],
        } for case in cases], hide_index=True, width="stretch")
        st.caption(
            "Option payoff is not option P&L: the premium was paid at inception. Do not subtract it a second time "
            "from final wealth. Notional/capital describes exposure, not a guaranteed participation return. "
            "At zero yield there is no option budget, regardless of capital."
        )
    st.download_button(
        "Download PPN study (JSON)", json.dumps(report, indent=2, allow_nan=False),
        file_name="ppn_nifty_2026_study.json", mime="application/json", key="ppn_download",
    )


def render_portfolio():
    st.subheader("PPN: NIFTY 50 historical case study")
    st.caption("Real NSE option closes and expiry index values | Hypothetical matched-maturity bond | Separate from the three model pricers")
    try:
        study = load_study()
        fingerprint = hashlib.sha256(STUDY_PATH.read_bytes()).hexdigest()
    except (OSError, ValueError, KeyError, TypeError) as error:
        st.session_state.pop("ppn_report", None)
        st.warning(f"Historical PPN data is unavailable or invalid: {error}")
        st.code(".\\.venv\\Scripts\\python.exe ppn_data.py", language="powershell")
        st.caption("This downloads five official NSE archives for local educational use. Missing prices are never replaced with simulated data.")
        return
    st.caption(
        f"Entry: {study['entry_date']} | Study ends: {study['window_end']} | "
        f"{len(study['options']):,} entry-date option observations | Data fingerprint: {fingerprint[:12]}"
    )
    show_method(study)
    with st.form("ppn_inputs"):
        left, right = st.columns(2)
        with left:
            goal = st.selectbox("Payoff objective", GOALS, key="ppn_goal")
            capital = st.number_input("Capital (INR)", 100.0, 1e10, 100000.0, step=10000.0, key="ppn_capital")
            bond_yield = st.number_input(
                "ASSUMED annual effective bond yield (%)", 0.0, 20.0, 5.0, step=0.25, key="ppn_yield",
                help="Illustrative funding assumption, not a historical observed yield. ACT/365; maturity matches each expiry.",
            )
        with right:
            sizing = st.selectbox("Option sizing", SIZING, key="ppn_sizing")
            minimum_volume = st.number_input("Minimum entry-day volume per leg (contracts)", 1, 10000000, 100, step=1, key="ppn_min_volume")
            markup = st.number_input(
                "ASSUMED option purchase markup (%)", 0.0, 100.0, 0.0, step=0.5, key="ppn_markup",
                help="Stress the reported closing premium; not an observed spread or a complete fee/tax model.",
            )
        submitted = st.form_submit_button("Run PPN study", key="ppn_run", type="primary")

    if submitted:
        st.session_state.pop("ppn_report", None)
        st.session_state.pop("ppn_error", None)
        try:
            report = run_study(study, capital, bond_yield / 100, goal, sizing, minimum_volume, markup / 100)
            report["data_fingerprint"] = fingerprint
            st.session_state.ppn_report = report
        except FileNotFoundError:
            st.session_state.ppn_error = "PPN engine not found. Run .\\run_gui.ps1 -BuildOnly."
        except subprocess.CalledProcessError as error:
            st.session_state.ppn_error = error.stderr.strip() or f"PPN engine exited with code {error.returncode}."
        except subprocess.TimeoutExpired:
            st.session_state.ppn_error = "PPN calculation exceeded 20 seconds."
        except (ValueError, KeyError, TypeError) as error:
            st.session_state.ppn_error = f"PPN study failed: {error}"
    if "ppn_report" in st.session_state and st.session_state.ppn_report["data_fingerprint"] != fingerprint:
        st.session_state.pop("ppn_report")
        st.info("Source data changed. Run the study again before interpreting results.")
    if "ppn_error" in st.session_state:
        st.error(st.session_state.ppn_error)
    elif "ppn_report" in st.session_state:
        render_report(st.session_state.ppn_report)
    else:
        st.info("Set the objective and assumptions, then Run PPN study. Existing pricer controls do not change this study.")
