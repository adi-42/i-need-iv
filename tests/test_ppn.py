import copy
import csv
from datetime import date
import io
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import ppn_data
import portfolio_gui


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / ".gui-build" / "ppn_gui.exe"
EXPIRIES = ["2026-01-27", "2026-03-30", "2026-06-30"]


def price(**changes):
    inputs = dict(capital=100000, bond_yield=0.05, days=365, strike=100, premium=10,
                  entry_index=100, expiry_index=120, lot_size=65, option="call",
                  sizing="fractional", premium_markup=0)
    inputs.update(changes)
    process = subprocess.run(
        [str(ENGINE), *map(str, inputs.values())], capture_output=True, text=True, check=True, timeout=15,
    )
    return json.loads(process.stdout)


def option_archive():
    """Synthetic fixtures only; no historical premiums are committed in tests."""
    rows = []
    for expiry in ["2026-01-06", "2026-01-27", "2026-02-03", "2026-02-24", "2026-03-30", "2026-06-30"]:
        for strike in [100, 101]:
            for option in ["CE", "PE"]:
                rows.append({
                    "TradDt": "2026-01-02", "Sgmt": "FO", "Src": "NSE", "FinInstrmTp": "IDO",
                    "FinInstrmId": f"{expiry}-{strike}-{option}", "TckrSymb": "NIFTY",
                    "FininstrmActlXpryDt": expiry, "StrkPric": str(strike), "OptnTp": option,
                    "ClsPric": "2.5", "SttlmPric": "3.0", "UndrlygPric": "100",
                    "OpnIntrst": "6500", "TtlTradgVol": "200", "TtlNbOfTxsExctd": "100", "NewBrdLotQty": "65",
                })
    content = io.StringIO(newline="")
    writer = csv.DictWriter(content, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as file:
        file.writestr("synthetic.csv", content.getvalue())
    return archive.getvalue()


def index_archive(day, close):
    return f"Index Name,Index Date,Closing Index Value\nNifty 50,{day:%d-%m-%Y},{close}\n".encode()


def make_dataset(directory):
    raw = Path(directory) / "raw"
    raw.mkdir()
    (raw / "BhavCopy_NSE_FO_0_0_0_20260102_F_0000.csv.zip").write_bytes(option_archive())
    for day, close in [
        (date(2026, 1, 2), 100), (date(2026, 1, 27), 95),
        (date(2026, 3, 30), 90), (date(2026, 6, 30), 105),
    ]:
        (raw / f"ind_close_all_{day:%d%m%Y}.csv").write_bytes(index_archive(day, close))
    with patch("ppn_data.urlopen", side_effect=AssertionError("Offline fixtures must not access the network")):
        path = ppn_data.prepare_study(directory)
    return path, ppn_data.load_study(path)


class CashflowTests(unittest.TestCase):
    def test_fractional_cashflow_identity_and_payoff_not_double_counted(self):
        result = price()
        bond = 100000 / 1.05
        units = (100000 - bond) / 10
        self.assertAlmostEqual(result["bond_cost"], bond)
        self.assertAlmostEqual(result["units"], units)
        self.assertAlmostEqual(result["final_value"], 100000 + units * 20)
        self.assertAlmostEqual(result["option_pnl"], units * (20 - 10))
        self.assertAlmostEqual(result["bond_cost"] + result["option_spend"] + result["idle_cash"], 100000)
        self.assertAlmostEqual(result["fixed_income_value"], 105000)
        self.assertAlmostEqual(result["excess_over_fixed_income"], result["final_value"] - 105000)
        self.assertEqual(result["idle_cash"], 0)

    def test_actual_day_count_put_and_worthless_option(self):
        for days in [25, 87, 179]:
            result = price(days=days, option="put", expiry_index=80)
            self.assertAlmostEqual(result["bond_cost"], 100000 / 1.05 ** (days / 365))
            self.assertAlmostEqual(result["option_payoff"], result["units"] * 20)
            self.assertAlmostEqual(result["final_value"], price(days=days)["final_value"])
            worthless = price(days=days, expiry_index=80)
            self.assertAlmostEqual(worthless["final_value"], 100000)
            self.assertLess(worthless["excess_over_fixed_income"], 0)

    def test_whole_lot_affordability_cash_and_exact_budget(self):
        result = price(sizing="whole_lots")
        self.assertEqual(result["lots"], 7)
        self.assertEqual(result["units"], 455)
        self.assertGreater(result["idle_cash"], 0)
        self.assertAlmostEqual(result["final_value"], 100000 + result["idle_cash"] + 455 * 20)
        small = price(capital=100, sizing="whole_lots")
        self.assertEqual(small["lots"], 0)
        self.assertEqual(small["option_payoff"], 0)
        self.assertEqual(small["final_value"], 100 + small["idle_cash"])
        exact = price(capital=100, bond_yield=0.25, premium=2, strike=150, lot_size=10, sizing="whole_lots")
        self.assertEqual(exact["lots"], 1)
        self.assertEqual(exact["idle_cash"], 0)

    def test_zero_yield_cost_markup_and_capital_scaling(self):
        zero = price(bond_yield=0)
        self.assertEqual(zero["bond_cost"], 100000)
        self.assertEqual(zero["units"], 0)
        self.assertEqual(zero["final_value"], 100000)
        self.assertIsNone(zero["minimum_capital_one_lot"])
        base, cost = price(), price(premium_markup=0.1)
        self.assertAlmostEqual(cost["units"], base["units"] / 1.1)
        self.assertLess(cost["final_value"], base["final_value"])
        self.assertAlmostEqual(price(capital=200000)["final_value"], 2 * base["final_value"])
        self.assertAlmostEqual(base["minimum_capital_one_lot"], 650 / (1 - 1 / 1.05))

    def test_payoff_curve_matches_realised_result_and_floor(self):
        for option in ["call", "put"]:
            result = price(option=option)
            curve = result["curve"]
            self.assertEqual(curve["index"], sorted(set(curve["index"])))
            self.assertEqual(len(curve["index"]), len(curve["final_value"]))
            i = curve["index"].index(120)
            self.assertEqual(curve["final_value"][i], result["final_value"])
            self.assertTrue(all(math.isfinite(v) and v >= 100000 for v in curve["final_value"]))

    def test_invalid_inputs_fail_without_json(self):
        defaults = ["100000", "0.05", "365", "100", "10", "100", "120", "65", "call", "fractional", "0"]
        for index, value in [(0, "0"), (0, "nan"), (1, "-0.01"), (2, "0"), (2, "1.5"),
                             (4, "0"), (5, "0"), (6, "-1"), (7, "0"), (8, "kiko"), (9, "other"), (10, "-1")]:
            with self.subTest(index=index, value=value):
                args = defaults.copy()
                args[index] = value
                result = subprocess.run([str(ENGINE), *args], capture_output=True, text=True, timeout=15)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assertIn("PPN calculation failed:", result.stderr)


class DataTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path, self.study = make_dataset(self.directory.name)

    def test_dates_monthly_selection_and_reported_close(self):
        choices = ppn_data.select_contracts(self.study)
        self.assertEqual([c["expiry"] for c in choices], EXPIRIES)
        self.assertEqual([c["days"] for c in choices], [25, 87, 179])
        self.assertEqual(choices[0]["target_date"], "2026-02-02")
        self.assertEqual(choices[0]["call"]["premium"], 2.5)
        self.assertNotEqual(choices[0]["call"]["premium"], choices[0]["call"]["settlement_price"])
        self.assertEqual(len(self.study["sources"]), 5)

    def test_entry_only_selection_and_liquidity_filter(self):
        for option in self.study["options"]:
            if option["strike"] == 100:
                option["volume"] = 4
        before = ppn_data.select_contracts(self.study, 100)
        self.assertTrue(all(c["strike"] == 101 and c["nearest_listed_strike"] == 100 for c in before))
        self.assertTrue(all(c["strike"] == 100 for c in ppn_data.select_contracts(self.study, 1)))
        changed = copy.deepcopy(self.study)
        for expiry in EXPIRIES:
            changed["index_closes"][expiry] *= 10
        after = ppn_data.select_contracts(changed, 100)
        self.assertEqual(
            [(c["expiry"], c["strike"], c["call"]["instrument_id"], c["put"]["instrument_id"]) for c in before],
            [(c["expiry"], c["strike"], c["call"]["instrument_id"], c["put"]["instrument_id"]) for c in after],
        )

    def test_missing_liquidity_invalid_fields_and_duplicate_rows(self):
        with self.assertRaisesRegex(ValueError, "no call/put pair"):
            ppn_data.select_contracts(self.study, 1000000)
        for key, value in [("premium", float("nan")), ("lot_size", 0), ("volume", 1.5), ("type", "kiko")]:
            changed = copy.deepcopy(self.study)
            changed["options"][0][key] = value
            with self.assertRaises(ValueError):
                ppn_data.validate_study(changed)
        changed = copy.deepcopy(self.study)
        changed["options"].append(changed["options"][0])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            ppn_data.validate_study(changed)

    def test_source_date_and_checksum_failures(self):
        with self.assertRaisesRegex(ValueError, "date mismatch"):
            ppn_data.parse_index(index_archive(date(2026, 1, 3), 100), ppn_data.ENTRY_DATE)
        with self.assertRaisesRegex(ValueError, "underlying disagrees"):
            ppn_data.parse_options(option_archive(), ppn_data.ENTRY_DATE, ppn_data.WINDOW_END, 101)
        source = self.study["sources"][0]
        raw = self.path.parent / "raw" / source["file"]
        raw.write_bytes(raw.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            ppn_data.load_study(self.path)

    def test_invalid_study_shapes_and_boolean_prices(self):
        for value in [None, [], "not a dataset", {"index_closes": [], "sources": []}]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                ppn_data.validate_study(value)
        changed = copy.deepcopy(self.study)
        changed["options"][0]["premium"] = True
        with self.assertRaisesRegex(ValueError, "booleans"):
            ppn_data.validate_study(changed)

    def test_index_values_are_validated_and_normalized_on_load(self):
        changed = copy.deepcopy(self.study)
        changed["entry_spot"] = "100"
        changed["index_closes"] = {day: str(value) for day, value in changed["index_closes"].items()}
        self.path.write_text(json.dumps(changed), encoding="utf-8")
        loaded = ppn_data.load_study(self.path)
        self.assertEqual(loaded["entry_spot"], 100.0)
        self.assertTrue(all(isinstance(value, float) for value in loaded["index_closes"].values()))
        changed["index_closes"]["2025-12-31"] = 100
        with self.assertRaisesRegex(ValueError, "outside the study window"):
            ppn_data.validate_study(changed)

    def test_network_error_is_explicit_and_no_fake_dataset_written(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("ppn_data.urlopen", side_effect=OSError("Network unavailable")):
                with self.assertRaisesRegex(OSError, "Network unavailable"):
                    ppn_data.prepare_study(directory)
            self.assertFalse((Path(directory) / ppn_data.STUDY_PATH.name).exists())


class PortfolioGuiTests(unittest.TestCase):
    def setUp(self):
        from streamlit.testing.v1 import AppTest
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path, self.study = make_dataset(self.directory.name)
        self.patches = [
            patch("portfolio_gui.load_study", side_effect=lambda: ppn_data.load_study(self.path)),
            patch("portfolio_gui.STUDY_PATH", self.path),
        ]
        for mock in self.patches:
            mock.start()
            self.addCleanup(mock.stop)
        self.app = AppTest.from_file(str(ROOT / "gui.py"), default_timeout=25).run()

    def test_fourth_tab_separate_controls_and_cached_results(self):
        app = self.app
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.tabs[3].label, "Portfolio Strats")
        prior = copy.deepcopy(app.session_state["results"])
        app.button(key="ppn_run").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        report = copy.deepcopy(app.session_state["ppn_report"])
        self.assertEqual(len(report["cases"]), 6)
        self.assertEqual(report["assumptions"]["annual_effective_bond_yield"], 0.05)
        self.assertEqual(app.session_state["results"], prior)
        self.assertEqual(len(app.get("plotly_chart")), 14)
        with patch("subprocess.run") as run:
            app.selectbox(key="ppn_curve_tenor").select("6M").run()
        run.assert_not_called()
        self.assertFalse(app.exception)
        app.number_input(key="seed").set_value(43)
        app.button(key="run_pricers").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.session_state["ppn_report"], report)
        app.slider(key="bsm_volatility").set_value(35.0).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(app.session_state["ppn_report"], report)

    def test_objective_whole_lots_and_percent_units(self):
        app = self.app
        app.selectbox(key="ppn_goal").select(portfolio_gui.GOALS[2])
        app.selectbox(key="ppn_sizing").select(portfolio_gui.SIZING[1])
        app.number_input(key="ppn_capital").set_value(100.0)
        app.number_input(key="ppn_yield").set_value(6.0)
        app.number_input(key="ppn_markup").set_value(2.0)
        app.button(key="ppn_run").click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        report = app.session_state["ppn_report"]
        self.assertEqual(len(report["cases"]), 3)
        for case in report["cases"]:
            self.assertEqual(case["result"]["inputs"]["option"], "put")
            self.assertEqual(case["result"]["inputs"]["bond_yield"], 0.06)
            self.assertEqual(case["result"]["inputs"]["premium_markup"], 0.02)
            self.assertEqual(case["result"]["lots"], 0)
        self.assertTrue(any("ZERO options" in warning.value for warning in app.warning))

    def test_failure_clears_only_ppn_results(self):
        app = self.app
        app.button(key="ppn_run").click().run()
        prior = copy.deepcopy(app.session_state["results"])
        failure = subprocess.CalledProcessError(1, [str(ENGINE)], stderr="Intentional PPN failure")
        with patch("subprocess.run", side_effect=failure):
            app.button(key="ppn_run").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.error[0].value, "Intentional PPN failure")
        self.assertNotIn("ppn_report", app.session_state)
        self.assertEqual(app.session_state["results"], prior)
        self.assertEqual(len(app.get("plotly_chart")), 12)

    def test_missing_data_and_changed_fingerprint(self):
        app = self.app
        app.button(key="ppn_run").click().run()
        self.path.write_text(self.path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        app.run()
        self.assertFalse(app.exception)
        self.assertNotIn("ppn_report", app.session_state)
        self.assertTrue(any("Source data changed" in info.value for info in app.info))
        with patch("portfolio_gui.load_study", side_effect=FileNotFoundError("Missing historical file")):
            app.run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertEqual(len(app.get("plotly_chart")), 12)
        self.assertTrue(any("data is unavailable" in warning.value for warning in app.warning))


@unittest.skipUnless(ppn_data.STUDY_PATH.exists(), "Historical data is local and not committed.")
class LocalHistoricalDataTests(unittest.TestCase):
    def test_selected_observations_match_raw_nse_archives(self):
        study = ppn_data.load_study()
        directory = ppn_data.STUDY_PATH.parent / "raw"
        option_source = next(s for s in study["sources"] if s["file"].endswith(".zip"))
        original = ppn_data.parse_options(
            (directory / option_source["file"]).read_bytes(), ppn_data.ENTRY_DATE,
            ppn_data.WINDOW_END, study["entry_spot"],
        )
        self.assertEqual(study["options"], original)
        for day, close in study["index_closes"].items():
            parsed = date.fromisoformat(day)
            self.assertEqual(ppn_data.parse_index((directory / f"ind_close_all_{parsed:%d%m%Y}.csv").read_bytes(), parsed), close)
        for choice in ppn_data.select_contracts(study):
            for kind in ["call", "put"]:
                self.assertGreaterEqual(choice[kind]["volume"], 100)
                self.assertGreater(choice[kind]["premium"], 0)
                self.assertEqual(choice[kind]["lot_size"], choice["lot_size"])


if __name__ == "__main__":
    unittest.main()
