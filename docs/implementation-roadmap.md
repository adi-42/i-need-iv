# i-need-iv: implementation and learning roadmap

**Theme:** Numerical accuracy, market uncertainty, and the limits of a constant-volatility option-pricing model.

**Planning date:** 10 September 2026.

**Status:** This is an implementation specification, not documentation of an existing pricing engine. At the time of writing, the repository has no implementation. The file layout, commands, outputs, and acceptance criteria below are targets to build toward, not features already available.

**How to use it:** read Sections 1-4 first, then implement Stages 1-8 in order. Sections 13-16 define the execution, evidence, and schedule. Treat each completion gate as a checkpoint before adding another feature.

## 1. What this project should actually answer

Build a small, trustworthy C++ pricing engine and use it to investigate three questions:

1. **Numerical accuracy:** How much computation is needed to estimate an option price to a specified precision, and which variance-reduction techniques buy the most accuracy per second?
2. **Reliability of implied volatility:** How sensitive is an inferred volatility to the bid-ask spread, the forward, the discount factor, and the quality of the quote?
3. **Model limitations:** For a carefully selected Indian index-option snapshot, can one volatility per expiry explain the retained quotes within their bid-ask bands? If not, how should the smile and surface be represented without claiming more than the data supports?

The connection between these questions is the project's strongest feature. An extremely precise numerical answer can still be financially uninformative when its inputs are uncertain or its assumptions are inappropriate.

### A credible motivation

> I wanted to distinguish an accurately computed option price from a financially reliable one. I built a pricing engine whose numerical errors I could measure, then investigated whether market-implied volatility estimates were precise enough to support the conclusions usually drawn from a smile or surface.

Use this motivation only if it reflects your actual interest. You do not need to invent a trading strategy, an internship problem, or a claim of original research.

### What the project is not

- Not a trading bot, an alpha strategy, or a profit claim.
- Not a claim that Monte Carlo is a different market model from Black-Scholes when both use the same lognormal dynamics.
- Not proof that a fitted surface is an arbitrage-free dynamic model.
- Not an attempt to predict future realized volatility from one option-chain snapshot.
- Not a production derivatives library. Numerical boundaries and unsupported cases must be documented honestly.

**An honest successful outcome:** some methods may add little value, some market quotes may be unusable, and some apparent smile features may not survive input sensitivity checks. Those are findings, not failures.

## 2. Scope, time budget, and stopping rules

Assume basic programming, probability, calculus, and linear algebra, with approximately **12-15 focused hours per week for eight weeks**. This is an estimate, not a guarantee. If C++ tooling or market-data access is new, cut scope rather than sacrifice validation.

| Priority | Deliverable | Why it belongs |
| --- | --- | --- |
| Core | European call/put pricing, stable implied-volatility inversion, tests | Establishes a trustworthy numerical foundation |
| Core | Plain Monte Carlo, antithetic variates, one control variate | Supports a focused comparison with known reference prices |
| Core | Repeated-run convergence, coverage, and fixed-cost experiments | Turns an implementation into an investigation |
| Core | One documented NIFTY 50 snapshot; quote-quality analysis and smile | Connects the engine to actual market observations |
| Core, conditional on sufficient data | A modest surface across 3-5 expiries, uncertainty overlays, interpolation diagnostics | Adds maturity structure without requiring a new pricing model |
| Next | Held-out-strike comparison of flat volatility versus smile interpolation | Tests reconstruction rather than merely in-sample fit |
| Next | A few additional snapshots using the same protocol | Checks whether conclusions depend on one observation date |
| Stretch: choose at most one | Asian-option pricing, or CPU parallelism | Extends either financial application or systems programming, not both |

If only six weeks are available, retain all correctness work, use three representative Monte Carlo contracts, and restrict market work to one well-documented snapshot. Cut repeated-date analysis and stretch features first.

If only one or two usable expiries are available, publish smiles and a term-structure discussion. **Do not manufacture a convincing-looking surface from inadequate support.**

Do not spend the first month writing a generalized framework. A few well-tested functions and small data structures are preferable to a hierarchy of instruments, models, factories, and engines.

## 3. Definitions that prevent misleading conclusions

### Three different meanings of variance

| Quantity | Meaning | What this project does with it |
| --- | --- | --- |
| Monte Carlo estimator variance | Variability of an estimated price across independent simulation runs | Measure directly; reduce it per unit computational cost |
| Implied total variance, $w(k,T)=\sigma_{\mathrm{imp}}(k,T)^2T$ | A useful coordinate for representing a Black-implied-volatility surface | Plot and interpolate it, with explicit assumptions and diagnostics |
| Realized return variance | Ex-post variability of returns over an observation interval | Out of scope for the first version |

An individual option's squared Black implied volatility is not generally a model-free expectation of future realized variance. A smile, risk premia, sampling conventions, and maturity alignment complicate that interpretation.

### Three different sources of discrepancy

**Numerical error:** finite samples, floating-point limitations, solver termination, or time discretization where applicable.

**Input and observation uncertainty:** bid-ask spreads, stale or asynchronous quotes, uncertain carry, and an imperfect discount factor.

**Model limitations:** a single volatility not representing the cross-section, deterministic rates/carry assumptions, or lognormal dynamics being inadequate for the intended question.

Use these labels in plots and conclusions. Increasing simulations addresses the first category, not the other two.

### One convention throughout the engine

Use a **forward-and-discount representation** for European options:

- $F$: forward level for the option expiry.
- $D$: discount factor to that expiry.
- $K$: strike.
- $T$: remaining time in years.
- $\sigma$: annualized volatility as a decimal; `0.20` means 20%.

For positive $T$ and $\sigma$,

$$
d_1=\frac{\log(F/K)+\tfrac12\sigma^2T}{\sigma\sqrt{T}},
\qquad d_2=d_1-\sigma\sqrt{T}.
$$

$$
C=D[F\Phi(d_1)-K\Phi(d_2)],
\qquad
P=D[K\Phi(-d_2)-F\Phi(-d_1)].
$$

For synthetic Black-Scholes examples with deterministic rates and continuous dividend yield, convert using $F=S_0e^{(r-q)T}$ and $D=e^{-rT}$. This is the same European lognormal formula expressed differently, not a second model to compare competitively.

The market engine should accept $F$ and $D$ explicitly so that dividend assumptions are not hidden inside the pricing function.

Premiums and strikes are in **index points per unit**, not whole-contract rupees. Convert to contract amounts only using the verified contract multiplier. Do not hardcode a lot size.

## 4. Stage 0: fix the experiment and data plan before coding

**Learn or refresh:** European versus American exercise; cash versus physical settlement; bid, ask, last trade, and settlement price; risk-neutral pricing versus forecasting.

**Build or decide:**

1. Write the three research questions from Section 1 into the future report.
2. Choose European calls and puts only. Use NIFTY 50 index options for the market study, not single-stock or US equity options.
3. Select a legal data route and inspect an actual small sample in the first week. Confirm that the fields needed for your intended claims exist.
4. Record the data source, acquisition rights, timestamp meaning, contract identifiers, units, and whether bid/ask observations are available.
5. Choose conventions before examining results: time to expiry, discounting, forward estimation, liquidity filters, supported maturity range, and quote-band handling.
6. Create a small experiment manifest: case IDs, seeds, sample counts, tolerances, and output paths.

**Completion gate:** you can explain the project's intended conclusions and identify which observed fields support each one. If historical data contains only daily trade/settlement information, narrow the market question now; do not discover this limitation in week seven.

**Do not waste time:** obtaining years of tick data, reverse-engineering an exchange website, or building a live feed. The initial study needs a small defensible dataset, not the largest dataset.

## 5. Stage 1: build the smallest useful C++ project

**Learn or refresh:** compilation and linking, CMake targets, value types, `const`, RAII, standard containers, unit tests, and floating-point comparison.

Use **C++20**, CMake, and a small test framework such as Catch2. Use a pinned JSON dependency only if the configuration/manifest format requires it. Pin dependency versions or commit hashes; do not build against moving branches.

Suggested structure:

```text
i-need-iv\
  CMakeLists.txt
  CMakePresets.json                  # optional convenience after basic builds work
  include\ivlab\
    types.hpp
    black.hpp
    implied_vol.hpp
    monte_carlo.hpp
    statistics.hpp
  src\
    black.cpp
    implied_vol.cpp
    monte_carlo.cpp
    statistics.cpp
  app\
    main.cpp
  tests\
    test_black.cpp
    test_implied_vol.cpp
    test_monte_carlo.cpp
    test_statistics.cpp
    fixtures\                       # synthetic or redistributable reference inputs
  configs\
    smoke.json
    mc_study.json
    benchmark.json
    market.json
  scripts\
    prepare_quotes.py
    analyze_mc.py
    analyze_market.py
    build_report.py
  data\
    raw\                            # immutable, private by default; ignored by Git
    processed\                      # derived data; also ignored by default
    synthetic\                      # distributable fixtures and example inputs
  results\                          # generated outputs, ignored by default
  reports\                          # selected publication-safe report and figures
  docs\
    implementation-roadmap.md
  requirements.txt
```

The `ivlab` library must not print, parse command-line arguments, read market files, or draw plots. The executable handles input/output and calls the library. Python handles data preparation, analysis, interpolation, and visualization.

Suggested types:

- `OptionType`: a scoped enumeration for call/put, not a Boolean.
- `PricingInputs`: forward, strike, discount factor, maturity, volatility.
- `IvResult`: status, volatility if identified, final bracket, repricing residual, iteration count, and warning flags.
- `McResult`: price, standard error, confidence interval, independent observation count, terminal payoff evaluations, seed, and elapsed time.
- `RunningMoments`: count, mean, and a stable variance accumulator.

Invalid inputs must produce explicit errors. Do not return zero or `NaN` and continue as if pricing succeeded. Batch jobs should write row-level rejection reasons and counts; fatal configuration/schema failures should return a nonzero exit status.

**Completion gate:** a fresh checkout can configure, compile, and run one unit test. Add a small CI job on Windows and, if practical, Linux. No market credentials or network data retrieval belongs in CI.

**Do not waste time:** GUI development, Python bindings, a web API, custom memory allocators, or an elaborate plugin architecture.

## 6. Stage 2: analytical prices and financial invariants

**Learn or refresh:** the lognormal distribution, discounting, put-call parity, Greeks, limiting cases, and floating-point cancellation.

Before coding, derive the European formula once from the discounted lognormal payoff expectation. Understand why the pricing drift is the carry rate rather than an estimate of the asset's historical return. Review the delta-hedging/replication argument and its idealizations: continuous trading, frictionless execution, and the assumed dynamics. Knowing the formula is not the same as understanding why it applies.

**Implementation order:**

1. Validate finite inputs and units. Require $F,K,D>0$, $T\geq0$, and $\sigma\geq0$. Do not incorrectly reject $D>1$: negative rates can produce such a discount factor.
2. Implement the normal CDF using `std::erfc`; avoid a low-quality hand-written polynomial.
3. Implement the zero-volatility limit separately. Handle expiry explicitly; economically consistent expiry inputs have $D=1$ and $F=S_0$.
4. Implement calls, puts, and vega. For this parameterization,
   $$
   \mathrm{Vega}=DF\phi(d_1)\sqrt{T}.
   $$
5. Use an OTM-first evaluation and parity where it improves stability for ITM values. Check small log-moneyness and extreme tails carefully. No single rearrangement removes every floating-point limitation.
6. Add the spot/rate/dividend convenience wrapper without duplicating the pricing formula.

Vega here is the price change for a **unit** change in volatility. Vega per one percentage point is this value divided by 100.

Test more than a few known prices:

- Put-call parity: $C-P=D(F-K)$.
- Bounds: $D(F-K)^+\leq C<DF$ and $D(K-F)^+\leq P<DK$ for finite positive-volatility interior cases.
- Price nonnegativity and positive vega in the supported interior domain.
- Call price decreases and is convex with strike; put price increases and is convex.
- Zero-volatility and expiry limits, including ATM cases.
- Agreement of analytical vega with a carefully sized central finite difference away from boundaries.
- Agreement with an independent reference such as QuantLib on a documented grid.

Use scale-aware price tolerances: for example, compare normalized error $|P-P_{\mathrm{ref}}|/(DF)$ against `1e-10` on a moderate reference grid. Declare a supported domain and add adversarial tests outside the easy cases; do not infer extreme-tail accuracy from an ATM example.

An initial deterministic grid can use $K/F\in\{0.8,1,1.2\}$, $T\in\{0.05,0.5,2\}$, $\sigma\in\{0.1,0.2,0.5\}$, and $D\in\{0.9,1,1.02\}$, at both $F=100$ and $F=25000$. This is only 162 cases per option type. Add separate boundary, tiny-price, and invalid-input cases rather than making one permissive tolerance cover everything.

A useful smoke reference is $S_0=K=100$, $r=0.05$, $q=0$, $T=1$, and $\sigma=0.20$:

```text
Call: 10.450583572186
Put:   5.573526022257
```

**Completion gate:** financial invariants and independent-reference tests pass. A bug in the analytical reference would otherwise contaminate every Monte Carlo and implied-volatility conclusion.

**Do not waste time:** implementing every Greek. Price and vega are essential; delta is a reasonable small addition, but a full Greeks engine is not needed.

## 7. Stage 3: implied volatility as a numerical and financial problem

**Learn or refresh:** monotone root finding, bisection, Newton's method, bracketing, and conditioning.

**Implementation order:**

1. Check the observed price against the theoretical bounds before solving.
2. Implement bisection as the correctness baseline.
3. Add a safeguarded Newton solver: retain a valid bracket and fall back to bisection whenever a Newton step leaves it, vega is too small, or the step is nonfinite.
4. Expand an initial upper-volatility bracket only up to a documented configurable ceiling. Failure to bracket is a reported outcome, not permission to return the ceiling as an answer.
5. Check bracket-width convergence and verify the final price residual. A small price residual alone is not sufficient in a nearly flat, low-vega region.
6. Compare with an independent Brent implementation in Python/SciPy on the same inputs.

Important statuses include invalid input, price outside bounds, expired quote, zero-volatility boundary, no finite volatility at the upper price limit, not bracketed, nonconverged, and numerically ill-conditioned.

When the target equals the lower bound, zero volatility is a boundary result, not an ordinary well-determined interior estimate. If floating-point precision makes many volatilities indistinguishable in price, report that limitation.

For synthetic round trips, price a grid of contracts, invert the prices, and reprice:

- For well-conditioned cases: recover volatility within a specified tolerance, initially `1e-8` in absolute decimal volatility.
- For low-vega cases: evaluate price residual and identification warnings rather than demanding an unjustifiable volatility tolerance.
- For invalid and boundary cases: verify the exact status, not just that the program did not crash.

### The financially meaningful experiment

Use the local approximation

$$
\Delta\sigma \approx \frac{\Delta P}{\mathrm{Vega}}
$$

to explain why similar price uncertainty can create very different volatility uncertainty. Check the approximation against full inversion; it can be poor for wide spreads or near boundaries.

Invert bid and ask separately where admissible. These are **quote-implied bands**, not statistical confidence intervals and not guaranteed executable prices.

If a quoted price interval only partly overlaps theoretical bounds, flag it and show the admissible/censored interval explicitly. Do not silently clip prices to make inversion succeed. If there is no overlap, reject it with a reason.

**Completion gate:** solver statuses, bounds, round trips, and conditioning behavior are tested. Record iteration counts as well as residuals.

**Do not waste time:** chasing the fastest possible IV algorithm before the straightforward safeguarded solver is correct. Newton iteration speed cannot repair uncertain inputs.

## 8. Stage 4: plain Monte Carlo with honest uncertainty estimates

**Learn or refresh:** risk-neutral expectations, the law of large numbers, the central limit theorem, sample variance, standard error, and confidence-interval coverage.

Under the same deterministic-rate lognormal setup as the analytical formula, simulate the terminal level directly:

$$
S_T=F\exp(-\tfrac12\sigma^2T+\sigma\sqrt{T}Z),\qquad Z\sim N(0,1).
$$

For a call, $X_i=D(S_{T,i}-K)^+$, and

$$
\widehat C_N=\frac1N\sum_iX_i,\qquad
\widehat{\mathrm{SE}}=\frac{s_X}{\sqrt N}.
$$

Use an approximately 95% normal interval $\widehat C_N\pm1.96\widehat{\mathrm{SE}}$, explicitly labeled as asymptotic. The later coverage experiment tests how well it actually performs.

**Implementation order:**

1. Inject a random seed; do not seed from the clock inside the pricing function.
2. Start with `std::mt19937_64` and `std::normal_distribution<double>`.
3. Stream observations through a stable online variance calculation, such as Welford's algorithm.
4. Return price, standard error, interval, observation count, and payoff-evaluation count.
5. Benchmark only after correctness tests work.

There are no time steps and no time-discretization bias in this terminal simulation. Do not construct daily paths for vanilla European payoffs.

A fixed standard-library seed does not guarantee identical normal draws across compilers or standard-library implementations. Record the toolchain. For cross-platform deterministic fixtures, supply a fixed small vector of normal draws directly.

Generate and save a seed ledger keyed by experiment, case, replication, and pilot/main role. Never reuse a pilot stream as its main sample. Common random numbers across methods can be useful for paired comparisons, but disclose that pairing; do not describe the resulting method estimates as mutually independent.

**Critical edge case:** a far-OTM sample may contain no positive payoffs and report sample variance zero. Do not call that evidence of an exact zero price. Flag insufficient payoff observations, report the count of positive payoffs, and demonstrate the limitation in the coverage study.

**Completion gate:** exact deterministic-path fixtures pass; estimates and repeated-run behavior agree with the analytical benchmark. Do not write a flaky unit test that expects the true price to be inside every nominal 95% interval.

## 9. Stage 5: variance reduction with correct accounting

**Learn or refresh:** covariance, correlation, paired estimators, control variates, and computational efficiency.

### Antithetic variates

For each independent $Z_i$, evaluate both $Z_i$ and $-Z_i$, and form

$$
A_i=\frac{X(Z_i)+X(-Z_i)}2.
$$

Compute the standard error from the independent **pair averages** $A_i$. The two legs of a pair are not independent samples.

If `samples = N`, define that as $N$ independent estimator observations: $N$ ordinary paths for plain Monte Carlo and $N$ pairs / $2N$ terminal payoff evaluations for antithetic Monte Carlo. Emit both counts so graphs cannot hide the extra work.

### A discounted-terminal-level control variate

Choose $Y_i=DS_{T,i}$, whose expectation is $DF$. Then

$$
X_i^{\mathrm{cv}}=X_i-\beta(Y_i-DF),\qquad
\beta^*=\frac{\mathrm{Cov}(X,Y)}{\mathrm{Var}(Y)}.
$$

Estimate beta on an **independent pilot**, freeze it, and estimate the corrected mean and standard error on a separate main sample. Include pilot cost in end-to-end timing. This avoids quietly treating a fitted coefficient as known while also using its training observations for inference.

Handle negligible control variance explicitly. If controls are combined with antithetics later, estimate covariance and standard error on pair-level variables.

The known analytical vanilla price is your reference, not an excuse to use the payoff itself as a trivial zero-variance control. That would defeat the experiment.

### Fair comparisons

Report both:

- **Equal work:** same total terminal payoff evaluations, with RNG work also recorded.
- **Equal wall-clock budget:** use a short calibration to choose fixed sample counts for each method, then time independent complete runs.

Avoid stopping a run exactly when the wall clock expires and presenting its partial output as statistically equivalent to a predetermined sample. Do not assume a variance reduction is a speedup until total runtime confirms it.

**Completion gate:** corrected standard errors have plausible coverage across independent replications; pilot cost is visible; at least one regime where the method helps little is retained in the results.

## 10. Stage 6: design the numerical investigation

Do not run the full Cartesian product of every parameter, seed, and sample count. Separate a wide deterministic correctness grid from a deliberately small stochastic research grid.

### Experiment A: convergence

Start with $F=100$, $D=e^{-0.05T}$, three representative strikes $K/F\in\{0.9,1.0,1.1\}$, $T=0.5$, and $\sigma=0.20$. The 5% rate is a synthetic experiment setting, not an Indian-market rate assumption.

Use sample counts `1,000`, `10,000`, and `100,000`, initially with **100 independent replications** per case and method. Then add `1,000,000` for a small selected subset if the measured runtime permits it.

Compute:

$$
\mathrm{RMSE}(N)=\sqrt{\frac1R\sum_{j=1}^R(\widehat P_{N,j}-P_{\mathrm{analytic}})^2}.
$$

Plot RMSE against $N$ on log-log axes with a slope `-0.5` reference line. Use this to check Monte Carlo sampling behavior; do not estimate convergence from one lucky random trajectory.

Include uncertainty on empirical RMSE, for example by bootstrapping independent replications in Python. If using nested random streams across sample counts, disclose that dependence instead of treating all plotted estimates as independent.

### Experiment B: interval coverage

On a small set of ATM and low-payoff-probability cases, increase to approximately **200 replications** and measure how often the analytical price is covered.

Show a binomial uncertainty interval for the measured coverage. With 200 replications and true coverage 95%, the standard deviation of the measured fraction is about **1.54 percentage points**. A result different from exactly 95% is not automatically a bug.

Report coverage, interval width, positive-payoff count, and warnings together. A deceptively narrow interval is not necessarily a good interval.

### Experiment C: efficiency across regimes

For a small selection of short/long maturities and ITM/ATM/OTM contracts, report:

- RMSE and standard error.
- Median wall time and a runtime spread across repeat timings.
- RMSE at comparable runtime budgets.
- Time to reach a chosen precision target, or "not reached within budget."
- Where controls and antithetics help, have little effect, or cost more than they save.

Pilot large studies first. Three contracts times 200 replications times one million paths is already **600 million plain paths**, before other methods and sample counts.

### Experiment D: the bridge to market relevance

Only run this experiment with observations whose licence/permission covers the intended simulation use. Otherwise use explicitly synthetic prices and spread scenarios, keeping exchange observations out of the simulation. The core numerical study never requires real market data.

For a few accepted market quotes, use midpoint IV as a *conditional input* and ask how expensive it is for Monte Carlo to resolve the corresponding price to, for example, one-tenth of the bid-ask half-width.

For a chosen price tolerance $\epsilon$, estimate

$$
N \approx (1.96s_X/\epsilon)^2
$$

from an independent pilot, impose a documented maximum budget, then verify the planned precision in independent main runs. Include pilot time and report cases that exceed the budget.

The chosen fraction of the spread is a study convention; try another value as a sensitivity check. Also compare with analytical evaluation.

This is **not market validation**: inverting midpoint IV and repricing the same option matches the midpoint by construction. The question is the computational cost of resolving a price relative to observable quote granularity.

### Profiling and optimization order

1. Establish a correct scalar Release-build baseline.
2. Profile RNG, exponentials, payoff evaluation, accumulation, and file handling separately.
3. Eliminate unnecessary paths, allocations, and repeated invariant computations.
4. Measure variance reduction before introducing threads.
5. Only then consider batching, parallel execution, or a faster RNG, one change at a time.

Use `std::chrono::steady_clock`, warm-up runs, enough repetitions to exceed timer noise, and a consumed checksum so calculations cannot be optimized away. Record CPU, compiler, flags, build type, thread count, commit, and power-mode constraints.

Measure kernel and end-to-end time separately. Never compare Debug against Release or a vectorized implementation against a scalar one without saying so. Do not enable fast-math silently.

Report algorithmic improvements and implementation speedups separately. A "10x improvement" without an accuracy target, denominator, and cost definition is not a useful result.

## 11. Stage 7: bring in Indian index-option data

**Learn or refresh:** exchange contract specifications, forwards and carry, put-call parity with spreads, timestamp alignment, day-count conventions, and the difference between observations and exchange-derived fields.

### Choose one underlying and a small initial sample

Use **NIFTY 50 index options**, with 3-5 usable expiries and roughly 10-20 liquid strikes around the forward per expiry where available. Acquire calls and puts even if the plotted smile ultimately selects OTM contracts.

Prefer a quiet, documented observation window away from expiry-day effects for the first snapshot. This is a starting simplification, not a claim that the market is stationary or that the window is always representative.

Contract exercise style, settlement rules, actual expiry date, multiplier, and applicable trading calendar must come from the exchange or an entitled provider. Do not infer them from a remembered expiry weekday, a fixed symbol format, or an old lot size.

**Dated convention check:** the [NSE specifications](https://www.nse.in/static/products-services/equity-derivatives-nifty50) inspected on 10 September 2026 list `OPTIDX`, `NIFTY`, `CE`/`PE`, a 0.05-point tick, Tuesday weekly expiries, and the last Tuesday for monthly expiries, adjusted to the previous trading day for a trading holiday. These are reference observations, not constants to embed in code. NSE directs readers to the dated `NSE_FO_contract_ddmmyyyy.csv.gz` file for applicable lot sizes; preserve the master appropriate to your observation date.

NIFTY index options are European and cash-settled; [Zerodha's expiry explanation](https://support.zerodha.com/category/trading-and-markets/trading-faqs/f-otrading/articles/options-on-expiry-day) describes automatic ITM exercise against the expiry-day index closing price. The inspected NSE product page contains conflicting settlement wording. Cross-check the applicable clearing specification/provider metadata rather than copying that sentence into the model. This roadmap does not claim to have verified the current detailed clearing payment schedule or exact intraday expiry-fixing time.

### Data routes and permissible conclusions

| Route | Appropriate use | Limitation |
| --- | --- | --- |
| Authorized timestamped broker/vendor quotes | Bid/ask IV bands and the main cross-sectional study | Requires the user's actual entitlement; timestamp quality and redistribution terms still matter |
| Exchange-provided download, where its terms permit the intended use | Small snapshot analysis with an acquisition manifest | A downloadable file is not automatically licensed for public redistribution |
| Historical daily derivatives files | EOD trade/settlement-based exploratory analysis | Not a substitute for synchronized bid/ask observations |
| Synthetic fixtures | Tests, CI, public demonstration, and reproducibility without data rights | Must never be labeled Indian market observations |

Do not use internal website endpoints, spoofing, cookie tricks, or rate-limit workarounds as the project's data pipeline. If access fails, use an authorized alternative or reduce the study's claims.

This is a substantive constraint: [NSE's Terms of Use](https://www.nse.in/static/nse-terms-of-use), clauses 8-9, restrict website-data simulation use and systematic/automated collection. Its [Copyright Policy](https://www.nse.in/static/nse-copyright) describes conditional personal/noncommercial/educational downloading, which is not a blanket override of those restrictions. Obtain clarification or appropriate written permission where necessary; do not assume "educational project" resolves the conflict. The [Data Sharing & Usage Policy](https://www.nse.in/static/market-data/nse-data-policy) provides a research-access process but does not establish your entitlement.

Treat raw market data as private and ignored by Git by default. Check permission for derived tables and figures as well. Publish the schema, acquisition instructions, code, and synthetic examples even when the real dataset cannot be redistributed.

**A concrete authorized-API route:** if you already have suitable broker entitlements, [Kite Connect's quote documentation](https://kite.trade/docs/connect/v3/market-quotes/) describes an instrument master with expiry, strike, lot size, and tick size, and full quotes with depth, exchange-packet time, and last-trade time. Three to five expiries with 10-20 paired strikes is about 60-200 option instruments, within the documented 500-instrument quote-request capacity at review time. That is technical feasibility, not a promise of free access, permission, or atomic synchronization.

The daily instrument master's `last_price` is not live. Instrument tokens can also be reused after expiry; retain dated exchange/symbol/expiry/strike/type identifiers rather than treating a token as permanent.

**Do not target NSE's displayed IV as ground truth.** The [option-chain page](https://www.nse.in/option-chain) exposes displayed IV alongside market fields, but its current rate, dividend, and refresh assumptions were not verified during this review. The product page's MIBOR language concerns theoretical base prices, not necessarily displayed-IV calculation. Compute project IVs with your own declared inputs and use the displayed field, if legally obtained, only as ancillary information.

### Required canonical fields

Keep one row per contract and observation:

```text
source, source_file_hash, instrument_id, underlying, option_type,
strike, expiry_timestamp, capture_timestamp, quote_timestamp,
timestamp_quality, bid, ask, bid_size, ask_size, last_price,
volume, open_interest, spot_reference, spot_timestamp,
contract_multiplier, tick_size, price_unit
```

Fields unavailable from a source must be explicitly missing, with provenance. Do not fabricate a quote timestamp from download time or assume a missing size is zero.

The raw source plus a separate manifest should preserve timezone (`Asia/Kolkata`, UTC+05:30), capture window, source field definitions, rights notes, and contract metadata. Normalize timestamps before pricing.

For the initial study, use actual elapsed seconds to expiry divided by `365 * 24 * 60 * 60`, documented as an ACT/365F-style time convention. Do not substitute trading-day count without converting every annualized input consistently. Preserve the rate source's own conventions when constructing $D$.

Consult the dated [trading-hours page](https://www.nse.in/static/market-data/market-timings) and [exchange calendars](https://www.nse.in/resources/exchange-communication-holidays), but distinguish session end, index closing calculation, expiry fixing, and clearing payment. Do not infer all four from a remembered 15:30 close. If the precise fixing time cannot be verified, record the chosen time as an assumption, exclude expiry-day quotes, and perturb it in sensitivity checks rather than disguising it as supplied metadata.

### Cleaning is a recorded experiment, not a hidden step

1. Reject malformed, nonfinite, duplicated, expired, and incompatible-contract rows.
2. Detect crossed quotes and nonpositive/missing asks; distinguish missing bids from observed zero bids.
3. Establish a conservative positive-bid, two-sided subset for the main smile. Record excluded zero-bid contracts rather than deleting them silently.
4. Check snapshot/quote ages when available. Unknown quote age is **unknown**, not fresh.
5. Record spreads and sizes. Volume and open interest do not prove a quote is current or executable.
6. Apply a declared relative-spread filter and inspect sensitivity to stricter and looser versions. For example, compare thresholds of 10%, 20%, and 40%; these are experiment settings, not exchange standards.
7. Exclude expiry-day contracts initially and justify any further maturity/liquidity limits.
8. Preserve a rejection ledger: original row ID, filter, reason, and stage.

Display the retained and rejected counts by expiry. A surface built from five surviving points should not visually resemble one supported by hundreds.

### Forward and discount inputs

Keep $F(T)$ and $D(T)$ explicit, sourced, and subject to sensitivity checks.

A same-expiry forward observation can be useful when available. **Do not reuse a monthly futures quote as the exact forward for every weekly option expiry.**

Alternatively, with an externally specified $D$, European put-call parity gives

$$
F=K+\frac{C-P}{D}.
$$

For matching call/put bid-ask quotes at the same strike and expiry, a spread-consistent interval is

$$
F\in
\left[
K+\frac{C_{\mathrm{bid}}-P_{\mathrm{ask}}}{D},
\quad
K+\frac{C_{\mathrm{ask}}-P_{\mathrm{bid}}}{D}
\right].
$$

Use several liquid near-ATM pairs, inspect their intervals, and choose a documented robust estimate such as the median midpoint estimate. If the intervals conflict, flag the inconsistency; a median does not establish that the quotes are mutually consistent.

Use market-appropriate discount inputs where available. A policy rate, a retail deposit rate, or an arbitrary flat percentage is not automatically the matching zero rate. If a flat-rate proxy is unavoidable, label it and recompute the study over a justified range.

The [RBI government-securities primer](https://www.rbi.org.in/commonperson/English/Scripts/FAQs.aspx?Id=711) explains Treasury bills as discount instruments. Dated T-bill observations can inform a documented rate proxy, but their maturity, valuation date, yield convention, interpolation, and short-expiry extrapolation still need treatment. A 91-day yield is not directly the discount factor for a weekly option.

For example, a base proxy plus/minus 50 and 100 basis points can be a transparent stress grid, not a confidence interval or an empirically estimated rate error. Base forward scenarios on actual parity/forward evidence where possible. Record why the selected scenarios are informative for the expiries studied.

Do not simultaneously estimate an unstable forward and discount factor from a handful of noisy strike pairs without studying identifiability. For the first version, choose one documented discount curve/proxy and infer $F$ conditional on it.

Carry an explicit $F,D$ scenario set through IV inversion and the flat-volatility test. Spread-derived IV bands conditional on one forward do not include all input uncertainty.

For strictly held-out market evaluation, estimate any parity-based forward from designated training/anchor pairs. Holding out a call while using its matching put/call pair to set the forward leaks test information.

### EOD-only fallback

If you obtain only daily OHLC, last-trade, or settlement records, make an **EOD indicative-IV study**, not the bid/ask study described above.

The [NSE derivatives reports page](https://www.nse.in/all-reports-derivatives) states that the legacy F&O Bhavcopy CSV was discontinued from 8 July 2024 in favor of the F&O-UDiFF Common Bhavcopy Final ZIP. Do not build an importer around an old tutorial's filenames or headers. Inspect an actual permitted file and its current schema first.

The reviewed [historical contract-wise report](https://www.nse.in/report-detail/fo_eq_security) schema contains daily contract identification, OHLC/LTP/settlement, trading activity, and underlying-value fields, not synchronized bid/ask depth. This is a finding about that report interface, not a claim that a current UDiFF archive was downloaded or its exact headers checked. Historical coverage and a real sample remain Stage 0 implementation checks.

Check the source's settlement methodology for the selected records; a derived settlement price can introduce circularity when used to "validate" a pricing model. Different contracts' daily trade prices need not refer to the same instant.

In particular, the NIFTY specifications describe weighted recent-trade closes, fallback LTP, and theoretical next-day base prices for untraded contracts. A theoretical base price is not an independent market observation; nor does this rule establish the meaning of every field named "settlement." Daily high/low is not a substitute for bid/ask.

Remove bid/ask-band conclusions, executable-arbitrage language, and claims of synchronized quote consistency. Document the timing problem, use reasonable input sensitivity scenarios, and keep this study separate from synthetic numerical experiments.

**Completion gate:** every plotted point is traceable to a source row and declared $F,D,T$ inputs; exclusions and unavailable fields are visible; data rights have been checked.

## 12. Stage 8: smiles, surfaces, and model limitations

**Learn or refresh:** log-forward moneyness, term structure, total implied variance, static price restrictions, interpolation, and out-of-sample evaluation.

### Start with a smile, not a surface

1. Invert the accepted bid, midpoint, and ask prices through the C++ solver.
2. Plot volatility against $k=\log(K/F)$, rather than raw strike alone.
3. Prefer puts below the forward and calls above it for the displayed OTM smile; choose and document the ATM convention.
4. Preserve call/put parity checks separately. Switching from puts to calls must not conceal a disagreement around ATM.
5. Show IV bands, rejected/flagged points, expiry, snapshot time, and retained sample size.

The inverse of midpoint price is generally not the arithmetic mean of bid IV and ask IV.

### A simple, meaningful constant-volatility test

For an expiry, each retained contract supplies an admissible IV interval conditional on $F,D,T$. Use valid interior intervals for the first implementation; keep boundary/censored or nonidentified contracts separately visible rather than substituting arbitrary IV values.

Compute

$$
L=\max_i\sigma_{\mathrm{bid},i},
\qquad U=\min_i\sigma_{\mathrm{ask},i}.
$$

If $L\leq U$, at least one volatility can represent all those price bands under the declared inputs and numerical conventions. This does **not** validate the model or show the volatility is uniquely identified.

If $L>U$, no single volatility represents all retained bands simultaneously under those assumptions. Identify the conflicting quotes, inspect their provenance, and repeat under filtering and forward/discount scenarios.

This is a conditional feasibility diagnostic, not a statistical rejection test and not evidence of executable arbitrage. Quotes may be stale, and transaction costs or input uncertainty may explain apparent conflicts.

Use one constant volatility **per expiry** as the baseline. This isolates the strike smile without confusing it with the separate question of a volatility term structure.

### Build a deliberately modest surface

Represent points as $(k,T,w)$, with $w=\sigma_{\mathrm{imp}}^2T$.

Start with piecewise-linear interpolation of total variance across $k$ for each expiry, then interpolate in time at fixed $k$ only where both neighboring expiries have observed support. Mask unsupported regions and avoid extrapolation.

Show observed points over the interpolation and create both:

- A heatmap or contour plot of total variance.
- Several explicit expiry slices with IV quote bands.

A 3D rendering is optional; slices and uncertainty overlays are often easier to interpret. Low interpolation error at observed points is not evidence of good predictive performance.

### Diagnostics before presentation

For each expiry, check call-price bounds and discrete strike slopes. If $K_1<K_2<K_3$,

$$
-D \leq
\frac{C(K_2)-C(K_1)}{K_2-K_1}
\leq
\frac{C(K_3)-C(K_2)}{K_3-K_2}
\leq 0.
$$

These express monotonicity, bounded vertical-spread values, and convexity at sampled strikes. Apply checks to observed prices and to repriced interpolation grids; report violations rather than silently smoothing them away.

At fixed log-forward moneyness, nondecreasing total variance across maturities is a useful calendar diagnostic **under the deterministic-rate/proportional-carry setup supporting that comparison**. State those assumptions; do not compare raw prices at different forwards and call a decline calendar arbitrage.

Neither linear interpolation of total variance nor passing a finite mesh of tests guarantees an arbitrage-free surface everywhere. A failed midpoint test also does not establish an executable arbitrage inside the bid-ask bands. A bid/ask feasibility linear program is an optional stronger extension, not a requirement for version one.

Do not start with SVI, SABR, Heston, or local volatility. Read about their purposes after the basic diagnostics work; each introduces an additional calibration and validation project.

### Held-out-strike evaluation, if time permits

Group calls and puts at the same strike/expiry as one economic observation for splitting. Keep enough training strikes to bracket held-out strikes; do not extrapolate and describe it as interpolation.

Compare:

- A flat volatility per expiry fitted on training quotes.
- The modest smile interpolator fitted on training IVs.

Use a simple bounded scalar fit for the flat baseline, with price residuals scaled by a declared spread/tick floor. Use established numerical routines in Python for this analysis; final reported prices should be checked through the C++ batch pricer.

Measure held-out price error in points, fraction inside the observed bid-ask band, and IV error for sufficiently well-conditioned observations. Report cases where the flexible representation does not help.

Split before choosing fit parameters, liquidity thresholds, or parity-based anchors. A repeated-date extension should freeze the protocol before the later snapshot.

This evaluates cross-sectional reconstruction, not future price forecasting or trading profitability.

**Completion gate:** every surface has support/uncertainty information, static diagnostics, and a limitations paragraph. The flat-volatility conclusion survives declared sensitivity checks or is reported as inconclusive.

## 13. Build, test, and run contract

The following is the **interface to implement**, not a set of commands that works in the current repository.

### Tooling

- A C++20 compiler. On Windows, use Visual Studio 2022 Build Tools with the Desktop development with C++ workload.
- CMake 3.24 or later; use a generator supported by the installed compiler.
- Python 3.11 or later for preparation, analysis, and plotting.
- A pinned test framework and, if used, a pinned JSON dependency.
- A versioned Python requirements file, typically containing NumPy, pandas, SciPy, matplotlib, and pytest. QuantLib can be an optional independent-reference dependency.

Do not install a large scientific C++ stack just to draw plots. Do not require a full QuantLib C++ build when its Python interface is sufficient for offline reference fixtures.

### Windows PowerShell build

After the relevant build files and dependency declarations exist:

```powershell
Set-Location C:\Users\aditraj\IdeaProjects\i-need-iv
cmake -S . -B build -G "Visual Studio 17 2022" -A x64
cmake --build build --config Debug
ctest --test-dir build -C Debug --output-on-failure
cmake --build build --config Release
ctest --test-dir build -C Release --output-on-failure
```

Use Debug for development and Release for performance claims. Enable appropriate warnings, such as `/W4` on MSVC and `-Wall -Wextra -Wpedantic` on GCC/Clang. Run available sanitizers on a supported toolchain; document platform-specific limitations.

After `requirements.txt` has been authored:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest
```

Have CMake produce `build\Release\ivlab.exe` for the Windows configuration above. If target output paths change, update examples and smoke tests together.

### Proposed CLI examples

```powershell
# Analytical smoke price, using the spot convenience wrapper.
.\build\Release\ivlab.exe price --engine analytic --type call --spot 100 --strike 100 --rate 0.05 --dividend 0 --years 1 --vol 0.20

# Plain Monte Carlo: samples are independent estimator observations.
.\build\Release\ivlab.exe price --engine mc --method plain --type call --spot 100 --strike 100 --rate 0.05 --dividend 0 --years 1 --vol 0.20 --samples 100000 --seed 42

# Reproducible multi-case study and separate timing study.
.\build\Release\ivlab.exe experiment --config configs\mc_study.json --out results\mc
.\build\Release\ivlab.exe benchmark --config configs\benchmark.json --out results\benchmark

# Normalize an entitled dataset; no download or authentication is implied.
.\.venv\Scripts\python.exe scripts\prepare_quotes.py --input data\raw\nifty_snapshot.csv --config configs\market.json --out data\processed\nifty_snapshot.csv

# Batch inversion uses explicit forward, discount, and maturity columns.
.\build\Release\ivlab.exe iv-batch --input data\processed\nifty_snapshot.csv --out results\market

.\.venv\Scripts\python.exe scripts\analyze_mc.py --input results\mc --benchmark results\benchmark --out results\analysis\mc
.\.venv\Scripts\python.exe scripts\analyze_market.py --input results\market --config configs\market.json --out results\analysis\market
.\.venv\Scripts\python.exe scripts\build_report.py --input results\analysis --out results\report
```

Define `prepare_quotes.py` to record the chosen forward/discount construction and split/anchor assignments, as well as cleaning. Keep its financial assumptions in versioned configuration, not hidden inside a notebook.

The market-analysis script should generate `pricing_queries.csv`, invoke `price-batch` using the configured executable path, then ingest repriced results. This avoids invoking one process per quote or requiring Python bindings. Its internal batch-pricing step has this interface, run only after the query file exists:

```powershell
.\build\Release\ivlab.exe price-batch --input data\processed\pricing_queries.csv --out results\market\repriced.csv
```

Define the processed IV-input schema to include `row_id`, `option_type`, `strike`, `forward`, `discount`, `maturity_years`, `bid`, `mid`, `ask`, `reference_price`, `reference_price_kind`, `tick_size`, `scenario_id`, and source/quality fields. Pricing queries additionally contain `volatility`. Preserve a stable row ID through every stage.

Make `dataset_kind` (`synthetic` or `market`) and `observation_mode` (`two_sided_quotes` or `eod_prices`) mandatory configuration fields. In EOD mode, bid/mid/ask remain missing; invert only the labeled reference price and emit `quote_side=reference`. Disable IV-band, flat-volatility band-feasibility, and spread-relative precision outputs rather than fabricating bid/ask values. The report must prominently identify the narrower mode.

Scripts must create documented output directories, validate schemas, and fail explicitly when required files are missing. Running the real-data command on a synthetic example must require an explicit dataset label.

The smoke pipeline should be small enough to run on each commit: a handful of synthetic contracts, deterministic reference prices, valid and invalid IV rows, and one supported/one deliberately invalid synthetic surface. Keep the expensive repeated Monte Carlo study behind a separate command.

### Output contract

| Output | Essential contents |
| --- | --- |
| `manifest.json` per run | Commit, config hash, dataset label/hash, platform, compiler, build flags, seed policy, units, conventions, start time |
| MC raw-result CSV | Case ID, method, replicate, seed, sample count, payoff evaluations, pilot count, estimate, SE, CI, true price, elapsed time, warnings |
| IV-result CSV | Row ID, scenario, quote side, price, IV/status, vega, final bracket, residual, iterations |
| Quote-quality CSV | Row ID, stage, accepted/rejected/flagged, reason, source metadata |
| Surface-result tables | Observed versus interpolated flags, support mask, $k,T,w$, scenario, diagnostic violations |
| Report | Methods, figures, quantitative findings, uncertainty, failures, limitations, reproduction commands |

Hash files for provenance, not as a substitute for permission to publish them. Do not commit credentials, broker tokens, or licensed data in manifests.

## 14. Test strategy: what each layer must prove

| Layer | Required checks | Where it runs |
| --- | --- | --- |
| Analytical core | Invariants, reference prices, vega, expiry/zero-volatility limits, extreme-input statuses | Every commit |
| IV solver | Round trips, inadmissible prices, boundaries, bracketing, convergence failures, low-vega cases | Every commit |
| Statistics | Known-vector mean/variance, online versus batch accumulation, paired-observation accounting | Every commit |
| Monte Carlo core | Injected-normal fixtures, zero-volatility behavior, seed/config propagation, pilot separation | Every commit |
| Data preparation | Duplicate/crossed/missing quotes, timestamps, timezone conversion, units, metadata changes, rejection ledger | Every commit, synthetic fixtures |
| Market analysis | Parity interval arithmetic, interval-intersection logic, no call/put leakage, support masking, known surface violations | Every commit, synthetic fixtures |
| CLI/integration | Bad arguments return failure; smoke inputs generate valid schemas and expected values | Every commit |
| Statistical research | RMSE, coverage, and variance-reduction efficiency over independent replications | Explicit research command, not fragile default CI |
| Performance | Same-machine Release runs with archived configuration and timing distributions | Explicit benchmark command |

Add regression fixtures whenever a real bug is found. Include deliberately corrupted market examples so the pipeline proves it can reject bad data rather than only processing clean examples.

The synthetic end-to-end example must remain runnable without network access or private market data after dependencies have been installed. Give it a tiny deterministic configuration, separate from the full research workload, and verify its report is explicitly labeled synthetic.

## 15. Display the results so they answer questions

Avoid a wall of charts. Each figure needs a question, units, an experiment identifier, and a caption stating what it does and does not establish.

| Figure/table | Question it answers |
| --- | --- |
| Log-log RMSE versus independent sample count | Does sampling error follow the expected rate? |
| Coverage and interval width by payoff regime | Are reported uncertainty intervals reliable? |
| RMSE versus runtime, with analytical reference cost | Which method buys useful precision fastest? |
| Variance-reduction efficiency heatmap over a small regime grid | Where does each technique help or fail to help? |
| Price-perturbation versus IV-perturbation plot, with vega | Why are some IV estimates poorly identified? |
| Quote-retention table and rejection reasons | How much market evidence supports the result? |
| Smile slices with quote-implied bands and forward scenarios | Is the apparent strike pattern larger than input sensitivity? |
| Total-variance heatmap with observed points and masked gaps | What maturity/strike structure is actually supported? |
| Flat-volatility feasibility summary by expiry and scenario | Can one volatility explain the retained price bands? |
| Numerical tolerance versus bid-ask uncertainty table | When does additional computational precision cease to matter for this dataset? |

A compact final report can be 8-12 pages plus technical appendices. Lead with three or four actual findings, including negative findings. Put derivations, test matrices, detailed conventions, and full timing tables in appendices.

Write conclusions in conditional language:

- Good: "Conditional on the documented forward and discount inputs, these retained quotes had no common IV interval; the conflict persisted under these sensitivity scenarios."
- Bad: "Black-Scholes does not work in India."
- Good: "The control-variate method reached the declared price precision in less total time in these cases, including pilot cost."
- Bad: "Monte Carlo was 20x better."
- Good: "The surface summarizes the observed snapshot within the displayed support."
- Bad: "The surface predicts where volatility will go."

Do not put illustrative numbers into the final report or resume as measured results. Replace all proposed targets with actual outcomes and retain the run manifests behind them.

## 16. Eight-week implementation sequence

| Week | Learning and implementation | Evidence to finish with |
| --- | --- | --- |
| 1 | Check data entitlement/sample; fix conventions; learn CMake/test workflow; implement analytical prices | Clean build, documented data route, parity and reference tests |
| 2 | Learn root finding/conditioning; implement safeguarded IV and edge statuses | Synthetic round trips and a price-to-IV sensitivity plot |
| 3 | Learn estimator uncertainty; implement terminal Monte Carlo and online statistics | Deterministic fixtures, initial RMSE/coverage experiment |
| 4 | Implement antithetic and pilot-fitted control variates; benchmark fairly | Accuracy/runtime comparison with correct sample and pilot accounting |
| 5 | Run the focused numerical study; profile one real bottleneck; normalize the Indian snapshot | Reproducible numerical results plus quote-quality report |
| 6 | Estimate forward/discount scenarios; invert bands; test constant-volatility feasibility | Explainable smile slices and conditional market conclusions |
| 7 | Build the supported total-variance surface and diagnostics; add held-out evaluation if ready | Surface/support plots and a clear limitations section |
| 8 | Rerun from clean inputs; review tests and claims; write report and README | Reproduction guide, selected figures, honest conclusions |

A phase is complete when its evidence exists, not when its nominal week ends. If behind schedule, remove extensions before shortening the correctness or data-quality stages.

### Optional Asian extension: only after the main study is complete

Implement a discretely monitored arithmetic-average Asian payoff using exact GBM transitions between specified fixing dates. Under that contract definition, those fixings define the payoff; they are not an Euler discretization of vanilla terminal pricing.

A geometric-average Asian payoff can provide an analytical benchmark/control when its formula and matching fixing convention are independently verified. Include the initial observation or exclude it consistently in both payoff definitions.

This is a principled way to show where simulation is useful because the simple European formula does not price the arithmetic-average payoff. It is a new contract, not evidence that Monte Carlo beats the vanilla analytical formula on the same task.

Do not add stochastic volatility, barriers, American exercise, GPU kernels, and calibration at the same time.

## 17. What to be able to explain without opening the code

Before calling the project finished, answer these in your own words:

1. Why do analytical and Monte Carlo prices converge to the same answer here?
2. Why is terminal simulation enough, and when would paths become necessary?
3. Why is Monte Carlo standard error not an estimate of model error?
4. Why are antithetic legs not two independent observations?
5. Why does fitting a control coefficient require care in uncertainty estimation?
6. Why can a small price error imply a large IV error?
7. How were forward, discounting, expiry time, and contract units obtained?
8. Which market observations were rejected, and could those choices change the conclusion?
9. Why does matching an option with its own implied volatility prove little?
10. What does a smooth surface fail to guarantee?
11. What measured improvement was worth its implementation complexity?
12. What would you refuse to claim from this dataset?

If these answers are strong, the project demonstrates more than familiarity with finance terminology. It demonstrates a coherent modeling workflow and an ability to evaluate one's own results.

## 18. References and targeted learning

Use references just before implementing the corresponding component. Do not postpone coding until you have completed several textbooks.

- **Monte Carlo efficiency and variance reduction:** Martin Haugh, Columbia, [Simulation Efficiency and Variance Reduction](https://www.columbia.edu/~mh2078/MonteCarlo/MCS_Basic_VarRed_MasterSlides.pdf). Read for control variates, antithetics, and computational-cost comparisons.
- **Independent pricing reference:** [QuantLib](https://www.quantlib.org/). Use as an external correctness check, not as a replacement for the engine you intend to learn to implement.
- **Root finding:** [SciPy `brentq` documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.brentq.html). Read the bracket requirements, stopping conditions, and failure behavior.
- **Build tooling:** [CMake tutorial](https://cmake.org/cmake/help/latest/guide/tutorial/index.html). Learn targets and tests first; advanced packaging can wait.
- **Advanced surface reading:** Gatheral and Jacquier, [Arbitrage-free SVI volatility surfaces](https://arxiv.org/abs/1204.0646). Read for the distinction between a fitted smile and arbitrage restrictions; SVI implementation is not a prerequisite.

### Indian-market source checklist

The sources linked in Stage 7 were reviewed on **10 September 2026**. Recheck them for the observation date you actually use. The contract-specification page states an update date of 23 September 2025; a page review date is not proof that every current or historical contract follows the same terms.

| Topic | Reference | What to verify when implementing |
| --- | --- | --- |
| Contract metadata | NSE NIFTY specifications and the dated contract master linked/discussed there | Actual expiry, exercise/settlement, tick, multiplier, identifiers |
| Expiry settlement | Broker expiry explanation, cross-checked with applicable exchange/clearing rules | Cash settlement, index fixing, exercise and payment conventions |
| Website snapshots | NSE option-chain page | Available fields, source timestamp, capture window, methodology notes |
| Historical files | NSE derivatives reports and contract-wise history | Current format, date coverage, price-field meaning, absent quote fields |
| Data permission | NSE Terms, Copyright, and Data Sharing & Usage Policy; provider contract | Collection, retention, simulation/research, redistribution, derived outputs |
| Authorized acquisition | Kite Connect market-quotes documentation or another entitled provider | Subscription/permission, timestamp semantics, missing instruments, rate limits |
| Rates | RBI government-securities primer and dated permitted market observations | Discount-factor construction and uncertainty, not just an annual percentage |
| Time conventions | NSE trading-hours page and trading/clearing calendars | Dated schedules and the distinct expiry-fixing convention |

**Deliberate verification limits:** no real market dataset, today's contract master, or complete historical archive was acquired while writing this plan. Current displayed-IV assumptions and precise expiry-fixing/payment details were not established. These are explicit data-onboarding gates, not missing values to fill with guesses.
