import json
from pathlib import Path
import subprocess

import plotly.graph_objects as go
import streamlit as st

from portfolio_gui import render_portfolio


ROOT = Path(__file__).resolve().parent
MC_ENGINE = ROOT / ".gui-build" / "mc_gui.exe"
PRICING_ENGINE = ROOT / ".gui-build" / "pricing_gui.exe"
BSM_AXES = {
    "spot": ("Spot", 1),
    "strike": ("Strike", 1),
    "maturity": ("Time to expiry (years)", 1),
    "rate": ("Interest rate (%)", 100),
    "volatility": ("Volatility (%)", 100),
}
GREEKS = [
    ("delta", "Delta", 1), ("gamma", "Gamma", 1), ("theta", "Theta / day", 365),
    ("vega", "Vega / 1 percentage point", 100), ("rho", "Rho / 1 percentage point", 100),
]


def bsm_slider_ranges(inputs):
    anchor = inputs["strike"] or inputs["spot"]
    return {
        "spot": (max(0.01, 0.5 * min(inputs["spot"], anchor)), min(1e9, 1.5 * max(inputs["spot"], anchor))),
        "strike": (0.0, min(1e9, max(1.0, 2 * max(inputs["spot"], inputs["strike"])))),
        "maturity": (0.0, min(30.0, max(2.0, 2 * inputs["maturity"]))),
        "rate": (min(-0.1, inputs["rate"]), max(0.2, inputs["rate"])),
        "volatility": (0.0, min(3.0, max(0.6, 1.5 * inputs["volatility"]))),
    }


def run_engine(engine, args):
    try:
        process = subprocess.run(
            [str(engine), *map(str, args)], capture_output=True, text=True, check=True, timeout=30
        )
        result = json.loads(process.stdout)
    except FileNotFoundError as error:
        raise RuntimeError("C++ engine not found. Start this app with .\\run_gui.ps1 to build it.") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(error.stderr.strip() or f"C++ engine exited with code {error.returncode}.") from error
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("C++ calculation exceeded 30 seconds. Reduce simulations or tree steps.") from error
    except json.JSONDecodeError as error:
        raise RuntimeError(f"C++ engine returned invalid JSON: {error}") from error
    if engine == PRICING_ENGINE and args[0] == "bsm":
        required = {"inputs", "price", "intrinsic_value", "lower_bound", "greeks", "spot_curve", "volatility_curve", "greek_curve"}
        curve = result.get("greek_curve") if isinstance(result, dict) else None
        if (
            not isinstance(result, dict) or not required.issubset(result) or not isinstance(curve, dict)
            or curve.get("axis") not in BSM_AXES or not isinstance(curve.get("values"), list)
            or not curve["values"]
            or any(not isinstance(curve.get(name), list) or len(curve[name]) != len(curve["values"]) for name, _, _ in GREEKS)
        ):
            raise RuntimeError("C++ BSM engine returned an unexpected schema. Rebuild with .\\run_gui.ps1 -BuildOnly.")
    return result


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


def render_bsm_result(result):
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
    curve = result["greek_curve"]
    axis = curve["axis"]
    axis_label, axis_scale = BSM_AXES[axis]
    st.caption(
        f"Each Greek vs {axis_label.lower()}; all other inputs are held fixed. The dot marks the selected option. "
        "Changing the x-axis input moves the dot; changing another input reshapes the curves."
    )
    columns = st.columns(2)
    for index, (name, label, scale) in enumerate(GREEKS):
        figure = go.Figure(go.Scatter(
            x=[value * axis_scale for value in curve["values"]],
            y=[None if value is None else value / scale for value in curve[name]],
            mode="lines", name=label, connectgaps=False,
        ))
        if greeks is not None:
            figure.add_scatter(
                x=[inputs[axis] * axis_scale], y=[greeks[name] / scale],
                mode="markers", name="Selected inputs", marker_size=10,
            )
        figure.add_hline(y=0, line_dash="dot", line_color="gray")
        figure.update_layout(
            title=label, xaxis_title=axis_label, yaxis_title=label, height=310,
        )
        with columns[index % 2]:
            st.plotly_chart(figure, width="stretch", key=f"bsm_greek_{name}")
    st.caption(
        "Gaps denote Greeks omitted at zero time, volatility or strike, not zero sensitivities. "
        "Theta measures time passing, so it is the negative derivative with respect to time remaining. "
        "Curves are sampled; very sharp near-expiry peaks may be under-resolved."
    )
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


@st.fragment
def render_bsm(initial_result):
    baseline = initial_result["inputs"]
    ranges = bsm_slider_ranges(baseline)
    if "bsm_baseline" not in st.session_state:
        st.session_state.bsm_baseline = dict(baseline)
        for name, (_, scale) in BSM_AXES.items():
            st.session_state[f"bsm_{name}"] = float(baseline[name] * scale)
        st.session_state.bsm_option = baseline["option"].title()
        st.session_state.bsm_axis = "spot"
        for key in ("bsm_explorer_result", "bsm_explorer_request", "bsm_explorer_error"):
            st.session_state.pop(key, None)
        # An already-open session can still hold a result from before Greek sweeps were added.
        curve = initial_result.get("greek_curve")
        if curve is not None and curve["axis"] == "spot" and (curve["values"][0], curve["values"][-1]) == ranges["spot"]:
            st.session_state.bsm_explorer_result = initial_result
            st.session_state.bsm_explorer_request = (
                *[baseline[name] for name in BSM_AXES], baseline["option"], "spot", *ranges["spot"],
            )

    st.subheader("Live Greek explorer")
    st.caption(
        "Sliders update BSM automatically when released; no Run button is needed. "
        "Monte Carlo, Binomial and PPN stay unchanged. Run pricers reloads the shared inputs and resets the sweep to spot."
    )
    left, right = st.columns(2)
    with left:
        option = st.selectbox("BSM option", ["Call", "Put"], key="bsm_option").lower()
    with right:
        axis = st.selectbox("Chart x-axis", list(BSM_AXES), format_func=lambda name: BSM_AXES[name][0], key="bsm_axis")
    values = {}
    for index, (name, (label, scale)) in enumerate(BSM_AXES.items()):
        low, high = (value * scale for value in ranges[name])
        with (left if index % 2 == 0 else right):
            values[name] = st.slider(
                label, float(low), float(high), step=float((high - low) / 200),
                format="%.4f", key=f"bsm_{name}",
            ) / scale
    st.caption("Slider ranges stay fixed while exploring. To explore a different scale, set the sidebar inputs and Run pricers.")
    request = (*[values[name] for name in BSM_AXES], option, axis, *ranges[axis])
    if request != st.session_state.get("bsm_explorer_request"):
        st.session_state.bsm_explorer_request = request
        st.session_state.pop("bsm_explorer_result", None)
        st.session_state.pop("bsm_explorer_error", None)
        try:
            st.session_state.bsm_explorer_result = run_engine(PRICING_ENGINE, [
                "bsm", values["spot"], values["strike"], values["maturity"], values["rate"],
                values["volatility"], option, axis, *ranges[axis],
            ])
        except RuntimeError as error:
            st.session_state.bsm_explorer_error = str(error)
    if "bsm_explorer_error" in st.session_state:
        st.error(st.session_state.bsm_explorer_error)
        st.caption("After resolving the error, move a slider or click Run pricers to retry.")
        return
    result = st.session_state.bsm_explorer_result
    inputs = result["inputs"]
    st.caption(
        f"Live BSM: {inputs['option']} | S={inputs['spot']:g}, K={inputs['strike']:g}, "
        f"T={inputs['maturity']:g} years, r={inputs['rate']:.2%}, volatility={inputs['volatility']:.2%}"
    )
    render_bsm_result(result)
    st.download_button(
        "Download live BSM (JSON)", json.dumps(result, indent=2, allow_nan=False),
        file_name="bsm_run.json", mime="application/json", key="download_bsm",
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
st.caption("First three tabs: constant interest/volatility, no dividends. Portfolio Strats: historical inputs and explicit funding assumptions.")

with st.sidebar.form("inputs"):
    st.subheader("Inputs for the first three tabs")
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
    submitted = st.form_submit_button("Run pricers", key="run_pricers", type="primary")

if submitted or "results" not in st.session_state:
    common = [spot, strike, maturity, rate / 100, volatility / 100]
    bsm_inputs = dict(zip(BSM_AXES, common))
    bounds = bsm_slider_ranges(bsm_inputs)["spot"]
    jobs = {
        "mc": (MC_ENGINE, [*common, simulations, seed, option.lower()]),
        "bsm": (PRICING_ENGINE, ["bsm", *common, option.lower(), "spot", *bounds]),
        "binomial": (PRICING_ENGINE, ["binomial", *common, option.lower(), steps, exercise.lower()]),
    }
    results, errors = {}, {}
    with st.spinner("Running C++ pricers..."):
        for method, (engine, args) in jobs.items():
            try:
                results[method] = run_engine(engine, args)
            except RuntimeError as error:
                errors[method] = str(error)
    st.session_state.results = results
    st.session_state.errors = errors
    for key in ("bsm_baseline", "bsm_explorer_request", "bsm_explorer_result", "bsm_explorer_error"):
        st.session_state.pop(key, None)

st.caption("Run pricers updates the first three tabs. BSM also has live sliders; Portfolio Strats has separate controls. Switching tabs does not resample Monte Carlo.")
tabs = st.tabs(["Monte Carlo", "BSM", "Binomial", "Portfolio Strats"])
for tab, method, render in zip(
    tabs[:3],
    ["mc", "bsm", "binomial"],
    [render_mc, render_bsm, render_binomial],
):
    with tab:
        if method in st.session_state.errors:
            st.error(st.session_state.errors[method])
            continue
        result = st.session_state.results[method]
        if method == "bsm":
            render(result)
            continue
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

with tabs[3]:
    render_portfolio()
