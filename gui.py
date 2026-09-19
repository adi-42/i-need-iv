import json
from pathlib import Path
import subprocess

import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
MC_ENGINE = ROOT / ".gui-build" / "mc_gui.exe"
PRICING_ENGINE = ROOT / ".gui-build" / "pricing_gui.exe"


def render_mc(result):
    inputs = result["inputs"]
    price = result["price"]
    se = result["standard_error"]
    benchmark = result["black_scholes"]
    st.caption(f"N={inputs['simulations']:,} | Seed={inputs['seed']} | European exercise")
    columns = st.columns(4)
    columns[0].metric("Monte Carlo price", f"{price:.6f}")
    columns[1].metric("Black-Scholes price", f"{benchmark:.6f}")
    columns[2].metric("Absolute error", f"{abs(price - benchmark):.6f}")
    columns[3].metric("Simulation time", f"{result['simulation_ms']:.2f} ms")
    st.write(
        f"Estimated standard error: **{se:.6f}** | "
        f"Approximate 95% interval: **[{price - 1.96 * se:.6f}, {price + 1.96 * se:.6f}]**"
    )
    st.caption("Time measures the C++ simulation and running statistics, excluding process startup and plotting.")
    if inputs["maturity"] > 0 and inputs["volatility"] > 0 and result["nonzero_payoffs"] < 30:
        st.warning(
            "Few nonzero payoffs were observed. The normal-approximation interval can be unreliable; "
            "zero sampled error does not prove the option is worthless."
        )

    history = result["convergence"]
    lower = [mean - 1.96 * error for mean, error in zip(history["price"], history["standard_error"])]
    upper = [mean + 1.96 * error for mean, error in zip(history["price"], history["standard_error"])]
    convergence = go.Figure()
    convergence.add_scatter(x=history["n"], y=lower, line_width=0, showlegend=False, hoverinfo="skip")
    convergence.add_scatter(
        x=history["n"], y=upper, line_width=0, fill="tonexty",
        fillcolor="rgba(59,130,246,0.18)", name="Approx. 95% interval", hoverinfo="skip",
    )
    convergence.add_scatter(x=history["n"], y=history["price"], mode="lines", name="Monte Carlo")
    convergence.add_hline(y=benchmark, line_dash="dash", annotation_text="Black-Scholes")
    convergence.update_layout(
        title="Price convergence", xaxis_title="Simulations (log scale)",
        xaxis_type="log", yaxis_title="Option price", height=390,
    )
    st.plotly_chart(convergence, width="stretch")
    st.caption(
        "Intervals are pointwise estimates, not a guarantee for the whole curve. "
        "One run need not get steadily closer to BSM. Sampling error typically falls as 1/sqrt(N): "
        "roughly four times as many simulations to halve the standard error."
    )
    for column, key, title, marker, label in zip(
        st.columns(2),
        ["terminal_histogram", "payoff_histogram"],
        ["Terminal stock prices", "Discounted payoffs"],
        [inputs["strike"], price],
        ["Strike", "MC mean"],
    ):
        histogram = result[key]
        figure = go.Figure(go.Bar(
            x=histogram["centers"], y=histogram["counts"], width=histogram["width"], name="Count"
        ))
        figure.add_vline(x=marker, line_dash="dash", annotation_text=label)
        figure.update_layout(title=title, xaxis_title="Value", yaxis_title="Count", height=330)
        with column:
            st.plotly_chart(figure, width="stretch")
    st.caption(
        f"Zero payoffs: {1 - result['nonzero_payoffs'] / inputs['simulations']:.1%}. "
        "Histograms use all simulations; only bin counts are sent to the GUI. "
        "These are terminal model outcomes, not simulated paths or market forecasts."
    )
    st.info(
        "The seed selects a pseudorandom sequence, not an economic assumption. Same inputs, seed and build "
        "reproduce the run; another seed changes finite-sample noise. Larger seed values are not more accurate. "
        "Keep it fixed for reproducible comparisons; use multiple seeds to study variability, not to cherry-pick BSM agreement."
    )


def render_bsm(result):
    inputs = result["inputs"]
    st.caption("Black-Scholes-Merton | European exercise | Deterministic: seed and simulation count do not apply")
    columns = st.columns(3)
    columns[0].metric("BSM price", f"{result['price']:.6f}")
    columns[1].metric("Immediate payoff", f"{result['intrinsic_value']:.6f}")
    columns[2].metric("Discounted lower bound", f"{result['lower_bound']:.6f}")
    st.caption(
        "Immediate payoff means exercising now, which European contracts do not allow. "
        "It is not always a lower bound on their price."
    )
    greeks = result["greeks"]
    if greeks is None:
        st.info("Boundary price calculated. Greeks are omitted at expiry, zero volatility or zero strike.")
    else:
        st.table({
            "Greek": ["Delta", "Gamma", "Theta / day", "Vega / 1 percentage point", "Rho / 1 percentage point"],
            "Value": [
                f"{greeks['delta']:.6f}", f"{greeks['gamma']:.6f}", f"{greeks['theta'] / 365:.6f}",
                f"{greeks['vega'] / 100:.6f}", f"{greeks['rho'] / 100:.6f}",
            ],
            "Local interpretation": [
                "Price change per +1 spot unit", "Delta change per +1 spot unit",
                "Price change as one day passes (365 days/year)",
                "Price change for volatility 20% -> 21%", "Price change for rate 5% -> 6%",
            ],
        })
    for column, key, x_key, title, x_label, scale in zip(
        st.columns(2),
        ["spot_curve", "volatility_curve"],
        ["spot", "volatility"],
        ["Price vs spot", "Price vs volatility"],
        ["Spot", "Volatility (%)"],
        [1, 100],
    ):
        curve = result[key]
        figure = go.Figure(go.Scatter(
            x=[value * scale for value in curve[x_key]], y=curve["price"], mode="lines", name="BSM"
        ))
        figure.add_scatter(
            x=[inputs[x_key] * scale], y=[result["price"]], mode="markers", name="Selected inputs",
            marker_size=10,
        )
        figure.update_layout(title=title, xaxis_title=x_label, yaxis_title="Option price", height=350)
        with column:
            st.plotly_chart(figure, width="stretch")
    st.info(
        "Each curve varies one input, holding the others fixed. Delta describes the spot-curve slope; "
        "gamma describes its curvature; vega describes sensitivity to volatility. Greeks are local "
        "approximations, not exact changes for large moves. These are model sensitivities, not an implied-volatility smile "
        "or a comparison with market prices."
    )


def render_binomial(result):
    inputs = result["inputs"]
    style = inputs["exercise"].title()
    st.caption(f"{inputs['steps']:,} tree steps | {style} exercise | Deterministic: no seed")
    columns = st.columns(4)
    columns[0].metric(f"{style} tree price", f"{result['price']:.6f}")
    columns[1].metric("European BSM", f"{result['black_scholes']:.6f}")
    columns[2].metric("European tree - BSM", f"{result['european_error']:+.6f}")
    columns[3].metric("Early-exercise premium", f"{result['early_exercise_premium']:.6f}")
    st.caption(
        f"At the same step count: European={result['european_price']:.6f}, "
        f"American={result['american_price']:.6f}. Early-exercise premium = American minus European tree price; "
        "it is not numerical error. The BSM error always uses the European tree."
    )
    history = result["convergence"]
    convergence = go.Figure()
    convergence.add_scatter(
        x=history["steps"], y=history["european"], mode="lines+markers", name="European tree",
    )
    if inputs["exercise"] == "american":
        convergence.add_scatter(
            x=history["steps"], y=history["american"], mode="lines+markers", name="American tree",
        )
    convergence.add_hline(y=result["black_scholes"], line_dash="dash", annotation_text="European BSM")
    convergence.update_layout(
        title="Tree convergence", xaxis_title="Tree steps (log scale)", xaxis_type="log",
        yaxis_title="Option price", height=350,
    )
    error = go.Figure(go.Scatter(
        x=history["steps"], y=[value - result["black_scholes"] for value in history["european"]],
        mode="lines+markers", name="European discretization error",
    ))
    error.add_hline(y=0, line_dash="dash")
    error.update_layout(
        title="European tree minus BSM", xaxis_title="Tree steps (log scale)", xaxis_type="log",
        yaxis_title="Signed price error", height=350,
    )
    left, right = st.columns(2)
    with left:
        st.plotly_chart(convergence, width="stretch")
    with right:
        st.plotly_chart(error, width="stretch")
    st.info(
        "More steps refine the exercise/price grid, not a random sample. Error can oscillate rather than improve "
        "at every step; the final two adjacent step counts help reveal this. There is no sampling confidence interval. "
        "This implementation takes O(N^2) work and O(N) memory. American exercise is checked at the grid dates."
    )
    if inputs["maturity"] == 0 or inputs["volatility"] == 0:
        st.caption("Expiry/zero-volatility case: priced directly; there is no random up/down branching.")
    else:
        tree = result["tree_parameters"]
        st.caption(
            f"Final grid: dt={tree['dt']:.6g} years | up={tree['up']:.6g} | down={tree['down']:.6g} | "
            f"risk-neutral up probability={tree['up_probability']:.6f} (not a forecast probability)."
        )
    with st.expander("How this tree is built"):
        st.write("This preserves the drift-shifted up/down factors in bino.cpp; it is not the standard CRR parameterization.")
        st.code(
            "dt = T / N\nu = exp(r*dt + sigma*sqrt(dt))\nd = exp(r*dt - sigma*sqrt(dt))\n"
            "p = (exp(r*dt) - d) / (u - d)\n"
            "continuation = exp(-r*dt) * (p*up_value + (1-p)*down_value)\n"
            "American value = max(continuation, immediate_payoff)",
            language="text",
        )
        st.caption("The GUI uses zero dividends for every tab. The standalone C++ tree still accepts a dividend yield.")


st.set_page_config(page_title="Option pricing playground", layout="wide")
st.title("Option pricing playground")
st.caption("Shared contract inputs | Constant interest and volatility | No dividends | All pricing in C++")

with st.sidebar.form("inputs"):
    st.subheader("Shared inputs")
    option = st.selectbox("Option", ["Call", "Put"], key="option")
    spot = st.number_input("Spot", 0.01, 1e9, 100.0, key="spot")
    strike = st.number_input("Strike", 0.0, 1e9, 100.0, key="strike")
    maturity = st.number_input("Maturity (years)", 0.0, 30.0, 1.0, step=0.25, key="maturity")
    rate = st.number_input("Interest rate (%)", -50.0, 50.0, 5.0, step=0.5, key="rate")
    volatility = st.number_input("Volatility (%)", 0.0, 300.0, 20.0, step=1.0, key="volatility")
    st.subheader("Monte Carlo only")
    simulations = st.select_slider(
        "Simulations", [100, 1000, 10000, 100000, 1000000], value=100000, key="simulations"
    )
    seed = st.number_input(
        "Seed", 0, 4294967295, 42, step=1, key="seed",
        help="Selects the random sequence. Bigger is not better; keep fixed for reproducible runs.",
    )
    st.subheader("Binomial only")
    steps = st.number_input("Tree steps", 1, 1000, 100, step=1, key="steps")
    exercise = st.selectbox("Tree exercise", ["European", "American"], key="exercise")
    submitted = st.form_submit_button("Run pricers", type="primary")

if submitted or "results" not in st.session_state:
    common = [spot, strike, maturity, rate / 100, volatility / 100]
    jobs = {
        "mc": (MC_ENGINE, [*common, simulations, seed, option.lower()]),
        "bsm": (PRICING_ENGINE, ["bsm", *common, option.lower()]),
        "binomial": (PRICING_ENGINE, ["binomial", *common, option.lower(), steps, exercise.lower()]),
    }
    results, errors = {}, {}
    with st.spinner("Running C++ pricers..."):
        for method, (engine, args) in jobs.items():
            try:
                process = subprocess.run(
                    [str(engine), *map(str, args)], capture_output=True, text=True, check=True, timeout=30
                )
                results[method] = json.loads(process.stdout)
            except FileNotFoundError:
                errors[method] = "C++ engine not found. Start this app with .\\run_gui.ps1 to build it."
            except subprocess.CalledProcessError as error:
                errors[method] = error.stderr.strip() or f"C++ engine exited with code {error.returncode}."
            except subprocess.TimeoutExpired:
                errors[method] = "C++ calculation exceeded 30 seconds. Reduce simulations or tree steps."
            except json.JSONDecodeError as error:
                errors[method] = f"C++ engine returned invalid JSON: {error}"
    st.session_state.results = results
    st.session_state.errors = errors

st.caption("Change inputs and click Run pricers to update all tabs. Switching tabs does not resample Monte Carlo.")
for tab, method, render in zip(
    st.tabs(["Monte Carlo", "BSM", "Binomial"]),
    ["mc", "bsm", "binomial"],
    [render_mc, render_bsm, render_binomial],
):
    with tab:
        if method in st.session_state.errors:
            st.error(st.session_state.errors[method])
            continue
        result = st.session_state.results[method]
        inputs = result["inputs"]
        st.caption(
            f"Displayed run: {inputs['option']} | S={inputs['spot']:g}, K={inputs['strike']:g}, "
            f"T={inputs['maturity']:g} years, r={inputs['rate']:.2%}, volatility={inputs['volatility']:.2%}"
        )
        render(result)
        st.download_button(
            "Download this run (JSON)", json.dumps(result, indent=2),
            file_name="monte_carlo_run.json" if method == "mc" else f"{method}_run.json",
            mime="application/json", key=f"download_{method}",
        )
