# i-need-iv

C++ option pricers with a local Python GUI. This guide covers implemented functionality and usage.

## What exists

| Component | Files | What it does |
| --- | --- | --- |
| Original simple pricer | `carlos_constant_rate.cpp` | Saved standalone Monte Carlo example: fixed 5% rate, 20% volatility, direct terminal sampling, random seed each run. |
| Stochastic-rate example | `carlos.cpp`, `carlos.hpp` | Vasicek rates with independent stock shocks, consistent discounting, seed control and input checks. Settings are in the source. |
| BSM pricer | `bsm.cpp`, `bsm.hpp` | European calls/puts, delta/gamma/theta/vega/rho and explicit expiry/zero-volatility/zero-strike prices. Greeks are omitted at these boundaries. |
| Binomial pricer | `bino.cpp`, `bino.hpp` | European/American calls/puts using the original drift-shifted tree, with dividend yield support in C++. Not the standard CRR parameterization. |
| Interactive playground | `gui.py`, `mc_gui.cpp`, `pricing_gui.cpp`, `gui_common.hpp` | Three tabs with shared inputs and per-tab JSON downloads. C++ prices; Python displays. |
| Launcher and dependencies | `run_gui.ps1`, `requirements-gui.txt` | Builds both GUI engines when their sources/headers change and starts Streamlit locally. |
| Regression checks | `tests\carlos_tests.cpp`, `tests\pricer_tests.cpp`, `tests\test_gui.py` | Numerical references, finite-difference Greeks, tree/exercise/dividend behavior, boundaries, seeded reproducibility, controls and error handling. |
| Separate experiments | `bsm_calc_iv.cpp`, `barrier_options.cpp` | Synthetic-noise IV and barrier/KIKO examples. Not part of the GUI or its validated pricing results. |

**GUI tabs**

- **Monte Carlo:** price/BSM comparison, estimated standard error and 95% interval, convergence, terminal-price/payoff histograms and simulation timing. Direct terminal sampling, not a time-stepped stock path.
- **BSM:** price, local Greeks, spot sensitivity and volatility sensitivity. The volatility curve varies an input; it is not a market-implied smile.
- **Binomial:** 1-1,000 steps, European/American selection, price convergence and signed European error against BSM. Early-exercise premium compares American and European prices on the same grid, separately from discretization error. American exercise is checked at grid dates.

All GUI tabs use constant rates/volatility and **zero dividends** so the European comparisons match. MC/BSM remain European when American exercise is selected for the tree. The GUI does not use Vasicek. Its uncertainty bands describe sampling error, not model accuracy; sparse payoffs can make them unreliable.

The **seed** initializes Monte Carlo's pseudorandom sequence. Same inputs/seed/build reproduce a run; another seed changes the sample. Larger seed values do not improve accuracy. BSM and Binomial are deterministic and ignore it. Vasicek's separate example uses illustrative, uncalibrated parameters and allows negative rates.

## Run the GUI

In PowerShell or the VS Code terminal on this machine:

```powershell
cd C:\Users\aditraj\IdeaProjects\i-need-iv
.\run_gui.ps1
```

Open `http://127.0.0.1:8501`, change inputs and click **Run pricers** to update all three tabs. Rates and volatility are percentages. Switching tabs does not resample. Vega/rho in the GUI are per one percentage point; theta is per day using 365 days/year. Exported C++ Greeks use decimal-rate/volatility and year units.

Keep that terminal open; **Ctrl+C** stops its server. If the GUI is already running, use its existing page. For another port: `.\run_gui.ps1 -Port 8502`.

### First-time setup only

The current machine is already configured. A new setup needs Windows, LLVM/`clang++` with Microsoft C++ build tools, and `uv` for these commands. Run them from the repository; do not recreate an existing working `.venv`.

```powershell
uv venv --python 3.12 .venv
.\.venv\Scripts\python.exe -m ensurepip
.\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt
```

The launcher finds `clang++` on PATH or at `C:\Program Files\LLVM\bin\clang++.exe`.

## Run C++ without the GUI

Build the interactive engines without starting a server, then request JSON results:

```powershell
.\run_gui.ps1 -BuildOnly
.\.gui-build\mc_gui.exe 100 100 1 0.05 0.20 100000 42 call
.\.gui-build\pricing_gui.exe bsm 100 100 1 0.05 0.20 call
.\.gui-build\pricing_gui.exe binomial 100 100 1 0.05 0.20 put 100 american
```

MC arguments: **spot, strike, years, rate, volatility, simulations, seed, call/put**; 2 to 1,000,000 simulations.

Other engine: **bsm/binomial, spot, strike, years, rate, volatility, call/put**, followed by **steps, european/american** for Binomial. CLI rates are decimals (`0.05` means 5%).

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
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_gui.py -v
$env:Path = "C:\Program Files\LLVM\bin;$env:Path"
clang++ -std=c++20 -O2 -Wall -Wextra -Werror -DPRICERS_NO_MAIN -I . bsm.cpp bino.cpp tests\pricer_tests.cpp -o .gui-build\pricer_tests.exe
.\.gui-build\pricer_tests.exe
clang++ -std=c++20 -O2 -Wall -Wextra -Werror -DCARLOS_NO_MAIN -I . carlos.cpp tests\carlos_tests.cpp -o .gui-build\vasicek_tests.exe
.\.gui-build\vasicek_tests.exe
```

`.venv` and `.gui-build` are local generated directories, not source code. Rebuild executables from source rather than relying on old binaries.
