import json
from pathlib import Path
import subprocess

import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parent
ENGINE = ROOT / ".gui-build" / "mc_gui.exe"

st.set_page_config(page_title="Monte Carlo playground", layout="wide")
st.title("Monte Carlo playground")
st.caption("European options | Constant interest and volatility | No dividends | C++ pricing")

with st.sidebar.form("inputs"):
    st.subheader("Inputs")
    option = st.selectbox("Option", ["Call", "Put"], key="option")
    spot = st.number_input("Spot", 0.01, 1e9, 100.0, key="spot")
    strike = st.number_input("Strike", 0.0, 1e9, 100.0, key="strike")
    maturity = st.number_input("Maturity (years)", 0.0, 30.0, 1.0, step=0.25, key="maturity")
    rate = st.number_input("Interest rate (%)", -50.0, 50.0, 5.0, step=0.5, key="rate")
    volatility = st.number_input("Volatility (%)", 0.0, 300.0, 20.0, step=1.0, key="volatility")
    simulations = st.select_slider(
        "Simulations", [100, 1000, 10000, 100000, 1000000], value=100000, key="simulations"
    )
    seed = st.number_input("Seed", 0, 4294967295, 42, step=1, key="seed")
    submitted = st.form_submit_button("Run simulation", type="primary")

if submitted or "result" not in st.session_state:
    args = [spot, strike, maturity, rate / 100, volatility / 100, simulations, seed, option.lower()]
    try:
        with st.spinner("Running C++ simulation..."):
            process = subprocess.run(
                [str(ENGINE), *map(str, args)], capture_output=True, text=True, check=True, timeout=30
            )
            st.session_state.result = json.loads(process.stdout)
    except FileNotFoundError:
        st.session_state.pop("result", None)
        st.error("C++ engine not found. Start this app with .\\run_gui.ps1 to build it.")
    except subprocess.CalledProcessError as error:
        st.session_state.pop("result", None)
        st.error(error.stderr.strip() or f"C++ engine exited with code {error.returncode}.")
    except subprocess.TimeoutExpired:
        st.session_state.pop("result", None)
        st.error("Simulation exceeded 30 seconds. Reduce the number of simulations.")
    except json.JSONDecodeError as error:
        st.session_state.pop("result", None)
        st.error(f"C++ engine returned invalid JSON: {error}")

if "result" not in st.session_state:
    st.stop()

result = st.session_state.result
inputs = result["inputs"]
price = result["price"]
se = result["standard_error"]
benchmark = result["black_scholes"]
st.caption(
    f"Displayed run: {inputs['option']} | S={inputs['spot']:g}, K={inputs['strike']:g}, "
    f"T={inputs['maturity']:g} years, r={inputs['rate']:.2%}, "
    f"volatility={inputs['volatility']:.2%} | N={inputs['simulations']:,} | Seed={inputs['seed']}"
)
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
    "One run need not get steadily closer to the benchmark. Keep the seed fixed to compare inputs."
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
    "Histograms use all simulations; only bin counts are sent to the GUI. These are model outcomes, not forecasts."
)
st.download_button(
    "Download this run (JSON)", json.dumps(result, indent=2),
    file_name="monte_carlo_run.json", mime="application/json",
)
