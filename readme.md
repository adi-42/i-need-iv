Exploring option pricing, numerical accuracy, and model limitations in C++.

`carlos.cpp` prices European calls and puts using Monte Carlo with stochastic risk-free rates and constant 20% stock volatility. The stock pays no dividends. Each simulation samples the accumulated rate and terminal stock price directly, without intermediate time steps.

## Simple constant-rate version

`carlos_constant_rate.cpp` preserves the earlier standalone Monte Carlo code, before the Vasicek update: fixed 5% interest, fixed 20% stock volatility, and direct terminal sampling without the 100-step loop. It retains the original random-device seeding, so estimates vary between runs, and does not include the newer input validation or seed parameter. Use valid inputs with positive simulation counts and nonnegative maturity.

The two `.cpp` files are separate programs with their own `main()` and helper functions. Compile them separately, not together.

## Dynamic interest rates

The short rate follows a Vasicek model under an assumed risk-neutral measure:

$$
dr_t = \kappa(\theta-r_t)\,dt + \eta\,dW_t^r.
$$

The rate moves randomly while tending back toward a long-run level. Edit `rates` in `main()`:

| Parameter | Example | Meaning |
| --- | --- | --- |
| `initialRate` | `0.05` | Today's continuously compounded short rate: 5% |
| `longRunRate` | `0.05` | Long-run rate level under the pricing measure: 5% |
| `meanReversion` | `1.0` | Speed of reversion, in inverse years |
| `volatility` | `0.01` | Rate diffusion scale: one percentage point per square-root year |

These are educational inputs, **not calibrated Indian-market parameters or forecasts**. Gaussian Vasicek rates can be negative; the code does not clip them. Stock and rate Brownian shocks are assumed independent.

"Risk-free" does not mean the rate is known for all future dates: the model's instantaneous bank-account return is locally risk-free, while future short rates are uncertain. Historical rate observations alone do not determine the risk-neutral parameters used for pricing.

For a European payoff, only the accumulated rate $I=\int_0^T r_t\,dt$ is needed. It is normally distributed, with

$$
B(T)=\frac{1-e^{-\kappa T}}{\kappa},\qquad
m_I=r_0B(T)+\theta[T-B(T)],
$$

$$
v_I=\frac{\eta^2}{\kappa^2}
\left[T-2B(T)+\frac{1-e^{-2\kappa T}}{2\kappa}\right].
$$

The implementation uses `expm1` and a small-argument series to avoid cancellation. At zero mean reversion it uses the continuous limit $m_I=r_0T$ and $v_I=\eta^2T^3/3$.

Each simulation draws $I=m_I+\sqrt{v_I}Z_r$ and an independent standard normal $Z_S$, then computes

$$
S_T=S_0\exp\left(I-\tfrac12\sigma^2T+\sigma\sqrt{T}Z_S\right).
$$

The price is the average of **individually discounted** payoffs $e^{-I}\,\mathrm{payoff}(S_T)$. Reusing the same $I$ in stock growth and discounting is essential. Discounting the average payoff afterward at 5% would be inconsistent with this model.

The simulation represents a genuinely time-varying rate process through its integrated distribution, rather than drawing today's rate randomly or generating a rate trajectory. It does not expose intermediate rate values. A terminal rate draw multiplied by maturity is not a substitute for $I$.

Set `volatility = 0.0` and `initialRate = longRunRate = 0.05` to recover the previous constant-rate model. With zero rate volatility but unequal initial and long-run rates, the rate still changes deterministically through mean reversion.

The configurable seed is `42` in the example. Calls and puts intentionally reuse the same seed and shocks; their estimates are correlated. Reproducibility is within the same toolchain, since standard-library normal generators may differ across platforms.

References: [risk-neutral pricing and short-rate models, University of Edinburgh, Sections 2 and 4](https://www.maths.ed.ac.uk/~dsiska/RNAP-Notes.pdf); [integrated Vasicek-rate derivation](https://hannoreuvers.github.io/post/vasicek/).

## Build and run

From the repository in PowerShell, with `clang++` on PATH:

```powershell
clang++ -std=c++20 -O2 -Wall -Wextra carlos.cpp -o carlos.exe
.\carlos.exe
```

To build and run the preserved simple version instead:

```powershell
clang++ -std=c++20 -O2 -Wall -Wextra carlos_constant_rate.cpp -o carlos_constant_rate.exe
.\carlos_constant_rate.exe
```

Regression checks (no external test framework):

```powershell
clang++ -std=c++20 -O2 -Wall -Wextra -Werror -DCARLOS_NO_MAIN -I . carlos.cpp tests\carlos_tests.cpp -o carlos_tests.exe
.\carlos_tests.exe
```

The checks cover integrated-rate moments, expiry and constant-rate limits, seeded reproducibility, invalid inputs, and stochastic-rate option prices against an independent analytical reference. Sample count remains configurable in `main()`; production confidence-interval reporting is still future work.

For the analytical test reference, write $P(0,T)=\exp(-m_I+v_I/2)$ and $w=\sigma^2T+v_I$. Under the stated independence assumptions, Gaussian integration gives

$$
C=S_0\Phi(d_1)-KP(0,T)\Phi(d_2),\qquad
d_1=\frac{\log(S_0/K)+m_I+\tfrac12\sigma^2T}{\sqrt{w}},\qquad
d_2=d_1-\sqrt{w}.
$$

Puts follow from $C-P_{\mathrm{put}}=S_0-KP(0,T)$. Tests obtain the rate moments independently using numerical quadrature, compare equivalent pathwise calculations, and apply broad seven-standard-error checks against the analytical prices. These checks are not a confidence-interval coverage study.

This model therefore still has a lognormal forward-measure representation at each expiry: adding independent Gaussian rates is **not a mechanism for generating a strike-dependent volatility smile**. It adds a specific rate-risk assumption to investigate, not automatic market realism.

## Project roadmap

See the [implementation and learning roadmap](docs/implementation-roadmap.md) for the project scope, build sequence, numerical experiments, Indian-market data methodology, and completion criteria.

Stochastic rates are a small exploratory extension, not a prerequisite for that roadmap. Keep the constant-rate case as the reference when studying Monte Carlo convergence and variance reduction.