import json
import math
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / ".gui-build" / "mc_gui.exe"
PRICING_ENGINE = ROOT / ".gui-build" / "pricing_gui.exe"
DEFAULTS = ["100", "100", "1", "0.05", "0.2", "100000", "42", "call"]


def price(**changes):
    names = ["spot", "strike", "maturity", "rate", "volatility", "simulations", "seed", "option"]
    args = [str(changes.get(name, default)) for name, default in zip(names, DEFAULTS)]
    result = subprocess.run([str(ENGINE), *args], capture_output=True, text=True, check=True, timeout=20)
    return json.loads(result.stdout)


def analytic(method="bsm", **changes):
    names = ["spot", "strike", "maturity", "rate", "volatility", "option"]
    defaults = ["100", "100", "1", "0.05", "0.2", "call"]
    args = [method, *[str(changes.get(name, default)) for name, default in zip(names, defaults)]]
    if method == "binomial":
        args += [str(changes.get("steps", 100)), changes.get("exercise", "european")]
    result = subprocess.run([str(PRICING_ENGINE), *args], capture_output=True, text=True, check=True, timeout=20)
    return json.loads(result.stdout)


class EngineTests(unittest.TestCase):
    def test_black_scholes_references(self):
        for option, expected in [("call", 10.450583572185565), ("put", 5.573526022256971)]:
            with self.subTest(option=option):
                result = price(option=option)
                self.assertAlmostEqual(result["black_scholes"], expected, places=11)
                self.assertGreater(result["standard_error"], 0)
                self.assertLess(abs(result["price"] - expected), 7 * result["standard_error"])

    def test_seed_reproducibility(self):
        first, second = price(), price()
        first.pop("simulation_ms")
        second.pop("simulation_ms")
        self.assertEqual(first, second)
        self.assertNotEqual(first["price"], price(seed=43)["price"])

    def test_histograms_and_checkpoints(self):
        for count in [2, 100, 1000000]:
            with self.subTest(count=count):
                result = price(simulations=count)
                for key in ["terminal_histogram", "payoff_histogram"]:
                    histogram = result[key]
                    self.assertEqual(sum(histogram["counts"]), count)
                    self.assertEqual(len(histogram["counts"]), len(histogram["centers"]))
                    self.assertGreater(histogram["width"], 0)
                history = result["convergence"]
                self.assertEqual(history["n"], sorted(set(history["n"])))
                self.assertEqual(history["n"][0], 2)
                self.assertEqual(history["n"][-1], count)
                self.assertLessEqual(len(history["n"]), 200)
                self.assertEqual(len(history["n"]), len(history["price"]))
                self.assertEqual(len(history["n"]), len(history["standard_error"]))
                self.assertEqual(history["price"][-1], result["price"])
                self.assertEqual(history["standard_error"][-1], result["standard_error"])
                self.assertTrue(all(math.isfinite(x) for x in history["price"]))

    def test_expiry(self):
        for spot in [80, 100, 120]:
            for option in ["call", "put"]:
                with self.subTest(spot=spot, option=option):
                    result = price(spot=spot, maturity=0, simulations=100, option=option)
                    expected = max(spot - 100 if option == "call" else 100 - spot, 0)
                    self.assertEqual(result["price"], expected)
                    self.assertEqual(result["black_scholes"], expected)
                    self.assertEqual(result["standard_error"], 0)
                    self.assertEqual(len(result["terminal_histogram"]["counts"]), 1)

    def test_zero_volatility_and_zero_strike(self):
        result = price(volatility=0, strike=95, simulations=100)
        expected = 100 - 95 * math.exp(-0.05)
        self.assertAlmostEqual(result["price"], expected, places=12)
        self.assertAlmostEqual(result["black_scholes"], expected, places=12)
        self.assertEqual(result["standard_error"], 0)
        zero_put = price(strike=0, simulations=100, option="put")
        self.assertEqual(zero_put["price"], 0)
        self.assertEqual(zero_put["black_scholes"], 0)
        self.assertEqual(zero_put["nonzero_payoffs"], 0)

    def test_negative_rates_and_changed_parameters(self):
        call = price(spot=110, strike=90, maturity=2, rate=-0.02, volatility=0.35)
        put = price(spot=110, strike=90, maturity=2, rate=-0.02, volatility=0.35, option="put")
        self.assertAlmostEqual(call["black_scholes"] - put["black_scholes"], 110 - 90 * math.exp(0.04))
        for result in [call, put]:
            self.assertLess(
                abs(result["price"] - result["black_scholes"]), 7 * result["standard_error"]
            )
        self.assertEqual(call["inputs"]["volatility"], 0.35)
        self.assertEqual(call["inputs"]["rate"], -0.02)

    def test_invalid_inputs_fail_explicitly(self):
        cases = [
            (0, "0"), (0, "nan"), (1, "-1"), (2, "-1"), (2, "inf"),
            (3, "0.51"), (4, "-0.1"), (4, "0.2oops"), (5, "1"),
            (5, "1000001"), (5, "10.5"), (6, "-1"), (6, "4294967296"), (7, "other"),
        ]
        for index, value in cases:
            with self.subTest(index=index, value=value):
                args = DEFAULTS.copy()
                args[index] = value
                result = subprocess.run([str(ENGINE), *args], capture_output=True, text=True, timeout=10)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("Pricing failed:", result.stderr)
        missing = subprocess.run([str(ENGINE)], capture_output=True, text=True, timeout=10)
        self.assertNotEqual(missing.returncode, 0)
        self.assertIn("Usage:", missing.stderr)


class AnalyticEngineTests(unittest.TestCase):
    def test_bsm_references_and_shared_mc_benchmark(self):
        for option, expected in [("call", 10.450583572185565), ("put", 5.573526022256971)]:
            with self.subTest(option=option):
                result = analytic(option=option)
                self.assertAlmostEqual(result["price"], expected, places=11)
                self.assertEqual(result["price"], price(option=option)["black_scholes"])
                self.assertNotIn("implied_volatility", result)
                self.assertLessEqual(result["lower_bound"], result["price"])
                self.assertEqual(result["inputs"]["dividend_yield"], 0)

    def test_greeks_against_finite_differences(self):
        for option in ["call", "put"]:
            with self.subTest(option=option):
                inputs = dict(spot=95, strike=105, rate=-0.02, maturity=0.7, volatility=0.35, option=option)
                result = analytic(**inputs)
                greeks = result["greeks"]
                up_spot = analytic(**{**inputs, "spot": 95.01})["price"]
                down_spot = analytic(**{**inputs, "spot": 94.99})["price"]
                self.assertAlmostEqual(greeks["delta"], (up_spot - down_spot) / 0.02, delta=1e-7)
                self.assertAlmostEqual(
                    greeks["gamma"], (up_spot - 2 * result["price"] + down_spot) / 0.01**2, delta=1e-7
                )
                for name, greek, sign in [("volatility", "vega", 1), ("rate", "rho", 1), ("maturity", "theta", -1)]:
                    h = 1e-5
                    upper = analytic(**{**inputs, name: inputs[name] + h})["price"]
                    lower = analytic(**{**inputs, name: inputs[name] - h})["price"]
                    self.assertAlmostEqual(greeks[greek], sign * (upper - lower) / (2 * h), delta=1e-6)

    def test_sensitivity_curve_shapes_and_parity(self):
        call, put = analytic(), analytic(option="put")
        self.assertAlmostEqual(call["price"] - put["price"], 100 - 100 * math.exp(-0.05), places=12)
        for result, direction in [(call, 1), (put, -1)]:
            curve = result["spot_curve"]
            self.assertEqual(len(curve["spot"]), 61)
            self.assertEqual(curve["spot"][30], 100)
            self.assertEqual(curve["price"][30], result["price"])
            differences = [b - a for a, b in zip(curve["price"], curve["price"][1:])]
            self.assertTrue(all(direction * value >= -1e-10 for value in differences))
            self.assertTrue(all(b >= a - 1e-10 for a, b in zip(differences, differences[1:])))
            vols = result["volatility_curve"]
            self.assertEqual(len(vols["volatility"]), 41)
            self.assertEqual(vols["volatility"][0], 0)
            self.assertTrue(all(b >= a - 1e-10 for a, b in zip(vols["price"], vols["price"][1:])))

    def test_boundary_prices_and_greek_availability(self):
        for changes in [dict(maturity=0, spot=80), dict(volatility=0, spot=80), dict(strike=0)]:
            for option in ["call", "put"]:
                with self.subTest(changes=changes, option=option):
                    bsm = analytic(option=option, **changes)
                    tree = analytic("binomial", option=option, **changes)
                    self.assertIsNone(bsm["greeks"])
                    self.assertAlmostEqual(tree["european_price"], bsm["price"], delta=1e-10)
                    self.assertGreaterEqual(tree["american_price"] + 1e-10, tree["european_price"])
                    self.assertTrue(all(math.isfinite(value) for value in tree["convergence"]["european"]))
        put = analytic("binomial", spot=80, volatility=0, option="put", exercise="american")
        self.assertEqual(put["price"], 20)
        self.assertGreater(put["early_exercise_premium"], 0)
        call = analytic("binomial", spot=120, volatility=0, rate=-0.05, exercise="american")
        self.assertEqual(call["price"], 20)
        self.assertGreater(call["early_exercise_premium"], 0)

    def test_binomial_preserves_original_one_step_scheme(self):
        for option in ["call", "put"]:
            result = analytic("binomial", steps=1, option=option)
            up, down = math.exp(0.05 + 0.2), math.exp(0.05 - 0.2)
            p = (math.exp(0.05) - down) / (up - down)
            sign = 1 if option == "call" else -1
            expected = math.exp(-0.05) * (
                p * max(sign * (100 * up - 100), 0) + (1 - p) * max(sign * (100 * down - 100), 0)
            )
            self.assertAlmostEqual(result["price"], expected, places=12)
            self.assertAlmostEqual(result["tree_parameters"]["up_probability"], p, places=14)
            self.assertEqual(result["convergence"]["steps"], [1])

    def test_binomial_convergence_and_exercise_comparison(self):
        for option in ["call", "put"]:
            result = analytic("binomial", steps=1000, option=option, exercise="american")
            history = result["convergence"]
            self.assertEqual(history["steps"], sorted(set(history["steps"])))
            self.assertEqual(history["steps"][-2:], [999, 1000])
            self.assertLessEqual(len(history["steps"]), 20)
            self.assertEqual(history["european"][-1], result["european_price"])
            self.assertEqual(history["american"][-1], result["price"])
            self.assertLess(abs(result["european_error"]), 0.01)
            self.assertLess(
                abs(result["european_error"]), abs(history["european"][0] - result["black_scholes"])
            )
            self.assertAlmostEqual(
                result["early_exercise_premium"], result["american_price"] - result["european_price"]
            )
            self.assertAlmostEqual(
                result["european_error"], result["european_price"] - result["black_scholes"]
            )
            self.assertTrue(all(a + 1e-10 >= e for a, e in zip(history["american"], history["european"])))
            if option == "call":
                self.assertAlmostEqual(result["early_exercise_premium"], 0, places=10)
            else:
                self.assertGreater(result["early_exercise_premium"], 0.4)

    def test_binomial_indistinguishable_branches_fail_explicitly(self):
        result = subprocess.run(
            [str(PRICING_ENGINE), "binomial", "100", "100", "1", "0.05", "1e-20", "call", "100", "european"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertIn("indistinguishable at double precision", result.stderr)

    def test_extreme_supported_inputs_and_negative_rates(self):
        for changes in [
            dict(spot=1e9, strike=1e9, maturity=30, rate=-0.5, volatility=3),
            dict(spot=0.01, strike=1e9, maturity=30, rate=0.5, volatility=3, option="put"),
            dict(spot=110, strike=90, maturity=2, rate=-0.02, volatility=0.35),
        ]:
            for method in ["bsm", "binomial"]:
                with self.subTest(method=method, changes=changes):
                    result = analytic(method, steps=1000, **changes)
                    self.assertTrue(math.isfinite(result["price"]))
                    self.assertGreaterEqual(result["price"], -1e-10)
                    self.assertEqual(result["inputs"]["rate"], changes["rate"])
        result = analytic("binomial", steps=1000, rate=-0.02, volatility=0.35)
        self.assertLess(abs(result["european_error"]), 0.02)

    def test_invalid_analytic_inputs_fail_without_partial_json(self):
        defaults = ["bsm", "100", "100", "1", "0.05", "0.2", "call"]
        cases = []
        for index, value in [
            (0, "other"), (1, "0"), (1, "nan"), (2, "-1"), (3, "inf"),
            (4, "-0.51"), (5, "-1"), (5, "0.2oops"), (6, "other"),
        ]:
            args = defaults.copy()
            args[index] = value
            cases.append(args)
        cases += [[], defaults + ["10", "european"], ["binomial", *defaults[1:]]]
        for steps, exercise in [("0", "european"), ("1001", "european"), ("1.5", "american"),
                                ("-1", "european"), ("100", "other")]:
            cases.append(["binomial", *defaults[1:], steps, exercise])
        for args in cases:
            with self.subTest(args=args):
                result = subprocess.run(
                    [str(PRICING_ENGINE), *args], capture_output=True, text=True, timeout=10
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("Pricing failed:", result.stderr)


class GuiTests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(ROOT / "gui.py"), default_timeout=20).run()

    def test_default_view_and_parameter_submission(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual([tab.label for tab in app.tabs], ["Monte Carlo", "BSM", "Binomial"])
        self.assertEqual(len(app.metric), 11)
        self.assertEqual(len(app.get("plotly_chart")), 7)
        app.selectbox(key="option").select("Put")
        app.number_input(key="seed").set_value(17)
        app.number_input(key="rate").set_value(-2.0)
        app.select_slider(key="simulations").set_value(1000)
        app.number_input(key="steps").set_value(101)
        app.selectbox(key="exercise").select("American")
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        results = app.session_state["results"]
        inputs = results["mc"]["inputs"]
        self.assertEqual(inputs["option"], "put")
        self.assertEqual(inputs["seed"], 17)
        self.assertEqual(inputs["rate"], -0.02)
        self.assertEqual(inputs["simulations"], 1000)
        for method in ["bsm", "binomial"]:
            self.assertEqual(results[method]["inputs"]["option"], "put")
            self.assertEqual(results[method]["inputs"]["rate"], -0.02)
            self.assertEqual(results[method]["inputs"]["volatility"], 0.2)
        self.assertEqual(results["bsm"]["inputs"]["exercise"], "european")
        self.assertEqual(results["binomial"]["inputs"]["exercise"], "american")
        self.assertEqual(results["binomial"]["inputs"]["steps"], 101)

    def test_seed_only_changes_mc_and_rerun_does_not_reprice(self):
        app = self.app()
        before = dict(app.session_state["results"])
        with patch("subprocess.run") as run:
            app.run()
        run.assert_not_called()
        self.assertFalse(app.exception)
        app.number_input(key="seed").set_value(43)
        app.button[0].click().run()
        after = app.session_state["results"]
        self.assertNotEqual(before["mc"]["price"], after["mc"]["price"])
        self.assertEqual(before["bsm"], after["bsm"])
        self.assertEqual(before["binomial"], after["binomial"])

    def test_greek_display_units_and_boundary_view(self):
        app = self.app()
        greeks = app.session_state["results"]["bsm"]["greeks"]
        table = app.table[0].value
        for row, greek, scale in [(2, "theta", 365), (3, "vega", 100), (4, "rho", 100)]:
            self.assertAlmostEqual(float(table.iloc[row]["Value"]), greeks[greek] / scale, places=6)
        app.number_input(key="maturity").set_value(0.0)
        app.number_input(key="spot").set_value(120.0)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.table), 0)
        for result in app.session_state["results"].values():
            self.assertEqual(result["price"], 20)

    def test_sparse_payoff_warning(self):
        app = self.app()
        app.number_input(key="strike").set_value(1000.0)
        app.select_slider(key="simulations").set_value(100)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.warning)
        self.assertIn("Few nonzero", app.warning[0].value)

    def test_error_removes_stale_results(self):
        app = self.app()
        failure = subprocess.CalledProcessError(1, [str(ENGINE)], stderr="Intentional engine failure")
        with patch("subprocess.run", side_effect=failure):
            app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertIn("Intentional engine failure", app.error[0].value)
        self.assertEqual(len(app.metric), 0)
        self.assertEqual(len(app.get("plotly_chart")), 0)

    def test_failure_is_isolated_to_its_tab(self):
        app = self.app()
        run = subprocess.run

        def fail_mc(command, **kwargs):
            if command[0] == str(ENGINE):
                raise subprocess.CalledProcessError(1, command, stderr="MC failed")
            return run(command, **kwargs)

        with patch("subprocess.run", side_effect=fail_mc):
            app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertEqual(app.error[0].value, "MC failed")
        self.assertNotIn("mc", app.session_state["results"])
        self.assertEqual(len(app.metric), 7)
        self.assertEqual(len(app.get("plotly_chart")), 4)
        app.button[0].click().run()
        self.assertFalse(app.error)
        self.assertEqual(len(app.session_state["results"]), 3)

    def test_missing_engine_timeout_and_malformed_json(self):
        for failure, expected in [
            (FileNotFoundError(), "engine not found"),
            (subprocess.TimeoutExpired("engine", 30), "exceeded 30 seconds"),
            (subprocess.CompletedProcess("engine", 0, stdout="{broken"), "invalid JSON"),
        ]:
            with self.subTest(expected=expected):
                app = self.app()
                kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
                with patch("subprocess.run", **kwargs):
                    app.button[0].click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.error), 3)
                self.assertTrue(all(expected in error.value for error in app.error))
                self.assertEqual(len(app.metric), 0)


if __name__ == "__main__":
    unittest.main()
