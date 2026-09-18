import json
import math
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / ".gui-build" / "mc_gui.exe"
DEFAULTS = ["100", "100", "1", "0.05", "0.2", "100000", "42", "call"]


def price(**changes):
    names = ["spot", "strike", "maturity", "rate", "volatility", "simulations", "seed", "option"]
    args = [str(changes.get(name, default)) for name, default in zip(names, DEFAULTS)]
    result = subprocess.run([str(ENGINE), *args], capture_output=True, text=True, check=True, timeout=20)
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


class GuiTests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        return AppTest.from_file(str(ROOT / "gui.py"), default_timeout=20).run()

    def test_default_view_and_parameter_submission(self):
        app = self.app()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(len(app.get("plotly_chart")), 3)
        app.selectbox(key="option").select("Put")
        app.number_input(key="seed").set_value(17)
        app.number_input(key="rate").set_value(-2.0)
        app.select_slider(key="simulations").set_value(1000)
        app.button[0].click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        inputs = app.session_state["result"]["inputs"]
        self.assertEqual(inputs["option"], "put")
        self.assertEqual(inputs["seed"], 17)
        self.assertEqual(inputs["rate"], -0.02)
        self.assertEqual(inputs["simulations"], 1000)

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


if __name__ == "__main__":
    unittest.main()
