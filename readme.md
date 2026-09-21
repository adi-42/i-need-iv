# i-need-iv

C++ option pricers with a local Python GUI. This guide covers implemented functionality and usage.

## What exists

| Component | Files | What it does |
| --- | --- | --- |
| Original simple pricer | `carlos_constant_rate.cpp` | Saved standalone Monte Carlo example: fixed 5% rate, 20% volatility, direct terminal sampling, random seed each run. |
| Stochastic-rate example | `carlos.cpp`, `carlos.hpp` | Vasicek rates with independent stock shocks, consistent discounting, seed control and input checks. Settings are in the source. |
| BSM pricer | `bsm.cpp`, `bsm.hpp` | European calls/puts, delta/gamma/theta/vega/rho and explicit expiry/zero-volatility/zero-strike prices. Greeks are omitted at these boundaries. |
| Binomial pricer | `bino.cpp`, `bino.hpp` | European/American calls/puts using the original drift-shifted tree, with dividend yield support in C++. Not the standard CRR parameterization. |
| Interactive playground | `gui.py`, `mc_gui.cpp`, `pricing_gui.cpp`, `gui_common.hpp` | Three model-pricing tabs with shared inputs, plus a separate Portfolio Strats tab. C++ calculates; Python displays. |
| PPN historical case study | `portfolio_gui.py`, `ppn_data.py`, `ppn_gui.cpp` | Official NIFTY entry premiums and expiry closes; assumed bond funding, explicit selection rules, fractional/whole-lot sizing, payoff charts and JSON export. |
| Launcher and dependencies | `run_gui.ps1`, `requirements-gui.txt` | Builds all three GUI engines when their sources/headers change and starts Streamlit locally. |
| Regression checks | `tests\carlos_tests.cpp`, `tests\pricer_tests.cpp`, `tests\test_gui.py`, `tests\test_ppn.py` | Numerical references, Greeks, trees, PPN accounting, source integrity, entry-only contract selection, controls and error handling. |
| Separate experiments | `bsm_calc_iv.cpp`, `barrier_options.cpp` | Synthetic-noise IV and barrier/KIKO examples. Not part of the GUI or its validated pricing results. |

**GUI tabs**

- **Monte Carlo:** price/BSM comparison, estimated standard error and 95% interval, convergence, terminal-price/payoff histograms and simulation timing. Direct terminal sampling, not a time-stepped stock path.
- **BSM:** live sliders and separate delta/gamma/theta/vega/rho charts, plus price vs spot/volatility. Choose spot, strike, maturity, rate or volatility as the Greek chart x-axis; other inputs stay fixed. These are model sensitivities, not a market-implied smile.
- **Binomial:** 1-1,000 steps, European/American selection, price convergence and signed European error against BSM. Early-exercise premium compares American and European prices on the same grid, separately from discretization error. American exercise is checked at grid dates.
- **Portfolio Strats:** PPN learning case with its own form; compares call/put outcomes, assumed fixed income and unprotected NIFTY price returns. Displays the selection process and limits, not a recommended historical winner.

The first three tabs use constant rates/volatility and **zero dividends** so the European comparisons match. MC/BSM remain European when American exercise is selected for the tree. The GUI does not use Vasicek. Its uncertainty bands describe sampling error, not model accuracy; sparse payoffs can make them unreliable. Portfolio Strats uses observed premiums, not model-generated or zero-dividend option prices.

The **seed** initializes Monte Carlo's pseudorandom sequence. Same inputs/seed/build reproduce a run; another seed changes the sample. Larger seed values do not improve accuracy. BSM and Binomial are deterministic and ignore it. Vasicek's separate example uses illustrative, uncalibrated parameters and allows negative rates.

## Run the GUI

In PowerShell or the VS Code terminal on this machine:

```powershell
cd C:\Users\aditraj\IdeaProjects\i-need-iv
.\run_gui.ps1
```

Open `http://127.0.0.1:8501`, change inputs and click **Run pricers** to update the first three tabs. Portfolio Strats has a separate **Run PPN study** button. Rates and volatility are percentages. Switching tabs does not resample. Vega/rho in the GUI are per one percentage point; theta is per day using 365 days/year. Exported C++ Greeks use decimal-rate/volatility and year units.

In **BSM**, release any slider to update its price, Greek values and charts automatically; no button is required. Its call/put and x-axis selectors also update immediately. Only BSM is recalculated, using the existing C++ formulas. Slider ranges stay fixed while exploring; **Run pricers** reloads the shared sidebar inputs, adjusts the ranges and resets the sweep to spot. Downloads reflect the live BSM inputs. Boundary Greeks are gaps, not zeroes; sampled curves can miss very narrow near-expiry peaks.

Keep that terminal open; **Ctrl+C** stops its server. If the GUI is already running, use its existing page. For another port: `.\run_gui.ps1 -Port 8502`.

### First-time setup only

The current machine is already configured. A new setup needs Windows, LLVM/`clang++` with Microsoft C++ build tools, and `uv` for these commands. Run them from the repository; do not recreate an existing working `.venv`.

```powershell
uv venv --python 3.12 .venv
.\.venv\Scripts\python.exe -m ensurepip
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
```

The launcher finds `clang++` on PATH or at `C:\Program Files\LLVM\bin\clang++.exe`.

## PPN historical data and assumptions

Prepare the local dataset once from the repository:

```powershell
.\.venv\Scripts\python.exe ppn_data.py
```

The script downloads five official NSE archives when absent: the January 2, 2026 F&O UDiFF bhavcopy, and NIFTY index closes for entry and the January 27, March 30 and June 30 expiries. Existing raw files are reused. These approximately 1M/3M/6M holds are **25/87/179 days**, not exact calendar-month durations.

The app uses reported option **closing premiums**, never simulated replacements or theoretical settlement prices. Its fixed rule chooses the nearest available monthly expiry and then the nearest strike within 5% of entry spot with positive prices, open interest, trades and sufficient entry-day volume in both call and put. The default volume floor is 100 contracts per leg. Outcomes do not enter selection. Sources, instrument IDs, observed lot sizes, archive SHA-256 hashes and the selection rule are available in the GUI/report.

Each row is an alternative investment of the full capital, not a combined call/put portfolio or rollover strategy. Choosing a strike from the final index close and filling at that same close is idealised: these snapshots are not an executable order replay.

The bond is **hypothetical**, with a user-supplied annual effective yield and ACT/365 maturity matched to each option expiry:

```text
bond cost = capital / (1 + assumed yield)^(days / 365)
option budget = capital - bond cost
final wealth = capital + unused cash + option payoff
```

Fractional lots model a pooled-note allocation, not directly executable exchange orders. Whole-lot mode rounds down and reports when no option is affordable; idle cash earns zero. A configurable premium markup stresses purchase cost. Other fees/taxes, settlement delays, issuer default and interim mark-to-market are omitted. The fixed-income comparator uses the same assumed yield.

This is one historical cohort, not evidence of a forecasting edge. KIKO is excluded because no historical barrier terms, premium or monitoring path are supplied. The payoff diagram is a maturity scenario curve, not a historical portfolio-value path.

**Attribution:** source observations are from the National Stock Exchange of India (NSE). Unchanged archives and the derived study stay under git-ignored `.market-data`; do not redistribute them without permission. The GUI links to NSE reports, contract/settlement rules and educational-use conditions. Missing or invalid data blocks this tab's results without affecting the other pricers.

## Run C++ without the GUI

Build the interactive engines without starting a server, then request JSON results:

```powershell
.\run_gui.ps1 -BuildOnly
.\.gui-build\mc_gui.exe 100 100 1 0.05 0.20 100000 42 call
.\.gui-build\pricing_gui.exe bsm 100 100 1 0.05 0.20 call
.\.gui-build\pricing_gui.exe binomial 100 100 1 0.05 0.20 put 100 american
.\.gui-build\ppn_gui.exe 100000 0.05 90 100 5 100 110 65 call fractional 0
```

MC arguments: **spot, strike, years, rate, volatility, simulations, seed, call/put**; 2 to 1,000,000 simulations.

Other engine: **bsm/binomial, spot, strike, years, rate, volatility, call/put**, followed by **steps, european/american** for Binomial. CLI rates are decimals (`0.05` means 5%).

BSM optionally accepts **axis, minimum, maximum** for its Greek sweep, e.g. append `volatility 0 0.6`. Axes: `spot`, `strike`, `maturity`, `rate`, `volatility`. Bounds use native units (years and decimal rates/volatility), must contain the selected input, and default to a spot sweep when omitted. All five arrays are returned in `greek_curve`; undefined boundary entries are JSON `null`.

PPN arguments: **capital, annual effective bond yield, days, strike, premium per index point, entry index, expiry index, lot size, call/put, fractional/whole_lots, purchase markup**. Yield/markup are decimal fractions; all cash amounts are INR. This CLI example uses synthetic inputs; the GUI study uses the downloaded NSE observations.

Compile standalone examples **separately**, after the build command above creates `.gui-build`:

```powershell
$env:Path = "C:\Program Files\LLVM\bin;$env:Path"
clang++ -std=c++20 -O2 -Wall -Wextra carlos_constant_rate.cpp -o .gui-build\constant_rate.exe
.\.gui-build\constant_rate.exe
clang++ -std=c++20 -O2 -Wall -Wextra carlos.cpp -o .gui-build\vasicek.exe
.\.gui-build\vasicek.exe
clang++ -std=c++20 -O2 -Wall -Wextra -Werror bsm.cpp -o .gui-build\bsm.exe
.\.gui-build\bsm.exe
clang++ -std=c++20 -O2 -Wall -Wextra -Werror bino.cpp -o .gui-build\bino.exe
.\.gui-build\bino.exe
```

`bsm.hpp` and `bino.hpp` expose reusable interfaces. Compile with `-DPRICERS_NO_MAIN` when linking them into another executable. `Contract::volatility` is the input, not an implied-volatility estimate; check `greeksAvailable` before reading Greeks.

## Run checks

From the repository, with the environment above installed:

```powershell
.\run_gui.ps1 -BuildOnly
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
$env:Path = "C:\Program Files\LLVM\bin;$env:Path"
clang++ -std=c++20 -O2 -Wall -Wextra -Werror -DPRICERS_NO_MAIN -I . bsm.cpp bino.cpp tests\pricer_tests.cpp -o .gui-build\pricer_tests.exe
.\.gui-build\pricer_tests.exe
clang++ -std=c++20 -O2 -Wall -Wextra -Werror -DCARLOS_NO_MAIN -I . carlos.cpp tests\carlos_tests.cpp -o .gui-build\vasicek_tests.exe
.\.gui-build\vasicek_tests.exe
```

`.venv`, `.gui-build` and `.market-data` are local generated directories, not source code. The tests use explicitly synthetic fixtures offline and also check the real archives when locally available. Rebuild executables from source rather than relying on old binaries.
