"""Local, attributed NSE snapshots for one January-June 2026 educational case study."""

import calendar
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import math
from pathlib import Path
from urllib.request import Request, urlopen
import zipfile


ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / ".market-data"
STUDY_PATH = DATA_DIR / "nifty_ppn_2026.json"
ENTRY_DATE = date(2026, 1, 2)
WINDOW_END = date(2026, 6, 30)
ARCHIVE = "https://nsearchives.nseindia.com/content"
RULE = (
    "Nearest available monthly expiry to each 1/3/6-month target, within 21 days; "
    "nearest strike to the entry index close with positive prices/open interest/trades "
    "and the selected minimum entry-day volume in BOTH call and put; "
    "maximum strike distance 5%; ties choose the lower strike. No outcome-based ranking."
)
REFERENCES = {
    "NSE historical derivatives reports": "https://www.nseindia.com/all-reports-derivatives",
    "NSE index-option settlement": "https://www.nseindia.com/static/products-services/equity-derivatives-settlement-price",
    "NSE NIFTY contract specifications": "https://www.nseindia.com/static/products-services/equity-derivatives-nifty50",
    "NSE lot-size circular": "https://nsearchives.nseindia.com/content/circulars/FAOP70616.pdf",
    "NSE copyright / educational-use conditions": "https://www.nseindia.com/static/nse-copyright",
}


def number(value, field, minimum=0.0):
    if isinstance(value, bool):
        raise ValueError(f"Invalid {field}: booleans are not numeric observations.")
    try:
        result = float(value)
    except (ValueError, TypeError) as error:
        raise ValueError(f"Invalid {field}: {value!r}") from error
    if not math.isfinite(result) or result < minimum:
        raise ValueError(f"Invalid {field}: {value!r}")
    return result


def integer(value, field, minimum=0):
    result = number(value, field, minimum)
    if not result.is_integer():
        raise ValueError(f"{field} must be an integer.")
    return int(result)


def parse_index(data, expected_date):
    rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    matches = [row for row in rows if row.get("Index Name", "").strip().upper() == "NIFTY 50"]
    if len(matches) != 1:
        raise ValueError("Index archive must contain exactly one NIFTY 50 row.")
    row = matches[0]
    observed = datetime.strptime(row["Index Date"], "%d-%m-%Y").date()
    if observed != expected_date:
        raise ValueError(f"Index date mismatch: expected {expected_date}, received {observed}.")
    return number(row["Closing Index Value"], "index close", 0.01)


def parse_options(data, entry_date, window_end, entry_spot):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) != 1 or not members[0].filename.endswith(".csv") or members[0].file_size > 128 * 1024**2:
            raise ValueError("Unexpected NSE bhavcopy ZIP contents or size.")
        content = archive.read(members[0])
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    required = {
        "TradDt", "Sgmt", "Src", "FinInstrmTp", "FinInstrmId", "TckrSymb",
        "FininstrmActlXpryDt", "StrkPric", "OptnTp", "ClsPric", "SttlmPric",
        "UndrlygPric", "OpnIntrst", "TtlTradgVol", "TtlNbOfTxsExctd", "NewBrdLotQty",
    }
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("NSE UDiFF option columns are missing; no alternative schema was assumed.")
    options, seen = [], set()
    for row in reader:
        if row["TckrSymb"] != "NIFTY" or row["OptnTp"] not in ("CE", "PE"):
            continue
        if row["TradDt"] != entry_date.isoformat() or row["Sgmt"] != "FO" or row["Src"] != "NSE" or row["FinInstrmTp"] != "IDO":
            raise ValueError("Unexpected option date, exchange, segment or instrument type.")
        expiry = date.fromisoformat(row["FininstrmActlXpryDt"])
        if not entry_date < expiry <= window_end:
            continue
        underlying = number(row["UndrlygPric"], "underlying price", 0.01)
        if abs(underlying - entry_spot) > 0.01:
            raise ValueError("Option archive underlying disagrees with the official entry index close.")
        option = {
            "expiry": expiry.isoformat(),
            "type": "call" if row["OptnTp"] == "CE" else "put",
            "strike": number(row["StrkPric"], "strike", 0.01),
            "premium": number(row["ClsPric"], "closing premium"),
            "settlement_price": number(row["SttlmPric"], "reported settlement price"),
            "volume": integer(row["TtlTradgVol"], "contract volume"),
            "trades": integer(row["TtlNbOfTxsExctd"], "trade count"),
            "open_interest_units": integer(row["OpnIntrst"], "open interest"),
            "lot_size": integer(row["NewBrdLotQty"], "lot size", 1),
            "instrument_id": row["FinInstrmId"],
        }
        key = (option["expiry"], option["strike"], option["type"])
        if key in seen:
            raise ValueError(f"Duplicate option contract: {key}.")
        seen.add(key)
        options.append(option)
    if not options:
        raise ValueError("No NIFTY options found for the requested period.")
    return options


def tenor_expiries(options, entry_date):
    # Use the last listed expiry in each month, before any liquidity filtering.
    monthly = {}
    for option in options:
        expiry = date.fromisoformat(option["expiry"])
        month = (expiry.year, expiry.month)
        monthly[month] = max(monthly.get(month, expiry), expiry)
    if not monthly:
        raise ValueError("No listed expiries available.")
    choices = []
    for months in (1, 3, 6):
        month_index = entry_date.year * 12 + entry_date.month - 1 + months
        year, month_zero = divmod(month_index, 12)
        month = month_zero + 1
        target = date(year, month, min(entry_date.day, calendar.monthrange(year, month)[1]))
        expiry = min(monthly.values(), key=lambda value: (abs((value - target).days), value))
        if abs((expiry - target).days) > 21 or expiry <= entry_date:
            raise ValueError(f"No sufficiently close listed monthly expiry for {months}M.")
        choices.append({"tenor": f"{months}M", "target_date": target.isoformat(), "expiry": expiry.isoformat()})
    if len({choice["expiry"] for choice in choices}) != 3:
        raise ValueError("The requested tenors must use three distinct expiries.")
    return choices


def select_contracts(study, minimum_volume=100):
    minimum_volume = integer(minimum_volume, "minimum volume", 1)
    entry = date.fromisoformat(study["entry_date"])
    spot = number(study["entry_spot"], "entry spot", 0.01)
    choices = []
    for tenor in tenor_expiries(study["options"], entry):
        by_strike = {}
        for option in study["options"]:
            if option["expiry"] == tenor["expiry"]:
                by_strike.setdefault(option["strike"], {})[option["type"]] = option
        eligible = []
        for strike, pair in by_strike.items():
            if set(pair) != {"call", "put"} or abs(strike / spot - 1) > 0.05:
                continue
            if all(q["premium"] > 0 and q["open_interest_units"] > 0 and q["trades"] > 0 and
                   q["volume"] >= minimum_volume for q in pair.values()):
                if pair["call"]["lot_size"] != pair["put"]["lot_size"]:
                    raise ValueError("Paired call/put lot sizes disagree.")
                eligible.append((strike, pair))
        if not eligible:
            raise ValueError(f"{tenor['tenor']}: no call/put pair meets the entry-day liquidity and 5% strike-distance rules.")
        strike, pair = min(eligible, key=lambda item: (abs(item[0] - spot), item[0]))
        expiry_spot = number(study["index_closes"][tenor["expiry"]], "expiry index close", 0.01)
        choices.append({
            **tenor, "days": (date.fromisoformat(tenor["expiry"]) - entry).days,
            "entry_spot": spot, "expiry_spot": expiry_spot, "strike": strike,
            "lot_size": pair["call"]["lot_size"], "call": pair["call"], "put": pair["put"],
            "eligible_pairs": len(eligible),
            "nearest_listed_strike": min(by_strike, key=lambda value: (abs(value - spot), value)),
        })
    return choices


def validate_study(study):
    if not isinstance(study, dict) or not isinstance(study.get("index_closes"), dict) or not isinstance(study.get("sources"), list):
        raise ValueError("The study must be an object with index observations and a source list.")
    if study.get("schema_version") != 1 or study.get("entry_date") != ENTRY_DATE.isoformat() or study.get("window_end") != WINDOW_END.isoformat():
        raise ValueError("Unsupported study version or period; this preset is January-June 2026.")
    spot = number(study["entry_spot"], "entry spot", 0.01)
    study["entry_spot"] = spot
    for day, value in study["index_closes"].items():
        if not ENTRY_DATE <= date.fromisoformat(day) <= WINDOW_END:
            raise ValueError("Index observation is outside the study window.")
        study["index_closes"][day] = number(value, "index close", 0.01)
    if study["index_closes"].get(study["entry_date"]) != spot:
        raise ValueError("Entry close and entry spot disagree.")
    if not isinstance(study["options"], list) or not study["options"]:
        raise ValueError("The study has no option observations.")
    seen = set()
    for option in study["options"]:
        expiry = date.fromisoformat(option["expiry"])
        if not ENTRY_DATE < expiry <= WINDOW_END or option["type"] not in ("call", "put"):
            raise ValueError("Invalid option expiry or type.")
        for key in ("strike", "premium", "settlement_price"):
            option[key] = number(option[key], key, 0.01 if key == "strike" else 0)
        for key in ("volume", "trades", "open_interest_units", "lot_size"):
            option[key] = integer(option[key], key, 1 if key == "lot_size" else 0)
        if not isinstance(option["instrument_id"], str) or not option["instrument_id"]:
            raise ValueError("Option instrument ID is missing.")
        key = (option["expiry"], option["strike"], option["type"])
        if key in seen:
            raise ValueError("Duplicate contract in study.")
        seen.add(key)
    tenors = tenor_expiries(study["options"], ENTRY_DATE)
    for tenor in tenors:
        number(study["index_closes"][tenor["expiry"]], "expiry index close", 0.01)
    if len(study["sources"]) != 5:
        raise ValueError("The study requires the option archive and four index archives.")
    expected = {f"BhavCopy_NSE_FO_0_0_0_{ENTRY_DATE:%Y%m%d}_F_0000.csv.zip": "fo"}
    for day in [ENTRY_DATE, *[date.fromisoformat(t["expiry"]) for t in tenors]]:
        expected[f"ind_close_all_{day:%d%m%Y}.csv"] = "indices"
    if {source["file"] for source in study["sources"]} != set(expected):
        raise ValueError("NSE source archive names do not match the study dates.")
    for source in study["sources"]:
        if source["url"] != f"{ARCHIVE}/{expected[source['file']]}/{source['file']}" or len(source["sha256"]) != 64:
            raise ValueError("Invalid NSE source provenance.")
        int(source["sha256"], 16)
        integer(source["bytes"], "source size", 1)
        datetime.fromisoformat(source["cached_at_utc"])
    if not isinstance(study["attribution"], str) or not study["attribution"]:
        raise ValueError("Source attribution is missing.")
    return study


def load_study(path=STUDY_PATH):
    with Path(path).open(encoding="utf-8") as file:
        study = validate_study(json.load(file))
    for source in study["sources"]:
        raw = (Path(path).parent / "raw" / source["file"]).read_bytes()
        if len(raw) != source["bytes"] or hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Cached NSE archive checksum mismatch: {source['file']}.")
    return study


def download_archive(relative_url, raw_dir):
    url = f"{ARCHIVE}/{relative_url}"
    path = raw_dir / relative_url.rsplit("/", 1)[-1]
    if path.exists():
        data = path.read_bytes()
    else:
        request = Request(url, headers={"User-Agent": "i-need-iv educational historical-data study"})
        with urlopen(request, timeout=40) as response:
            data = response.read(20 * 1024**2 + 1)
        if len(data) > 20 * 1024**2:
            raise ValueError("NSE archive exceeds the download size limit.")
        path.write_bytes(data)
    return data, {
        "provider": "National Stock Exchange of India (NSE)",
        "url": url, "file": path.name, "sha256": hashlib.sha256(data).hexdigest(),
        "bytes": len(data),
        "cached_at_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
    }


def prepare_study(data_dir=DATA_DIR):
    data_dir = Path(data_dir)
    raw_dir = data_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    sources = []
    entry_csv, source = download_archive(f"indices/ind_close_all_{ENTRY_DATE:%d%m%Y}.csv", raw_dir)
    sources.append(source)
    spot = parse_index(entry_csv, ENTRY_DATE)
    option_zip, source = download_archive(f"fo/BhavCopy_NSE_FO_0_0_0_{ENTRY_DATE:%Y%m%d}_F_0000.csv.zip", raw_dir)
    sources.append(source)
    options = parse_options(option_zip, ENTRY_DATE, WINDOW_END, spot)
    closes = {ENTRY_DATE.isoformat(): spot}
    for tenor in tenor_expiries(options, ENTRY_DATE):
        expiry = date.fromisoformat(tenor["expiry"])
        content, source = download_archive(f"indices/ind_close_all_{expiry:%d%m%Y}.csv", raw_dir)
        sources.append(source)
        closes[expiry.isoformat()] = parse_index(content, expiry)
    study = validate_study({
        "schema_version": 1, "entry_date": ENTRY_DATE.isoformat(), "window_end": WINDOW_END.isoformat(),
        "entry_spot": spot, "index_closes": closes, "options": options, "sources": sources,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "selection_rule": RULE, "references": REFERENCES,
        "attribution": "Historical source observations: National Stock Exchange of India (NSE). Local educational use; not for redistribution.",
        "premium_field": "ClsPric (reported close), not a bid/ask quote or a substituted theoretical settlement price.",
    })
    destination = data_dir / STUDY_PATH.name
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(study, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(destination)
    return destination


if __name__ == "__main__":
    try:
        destination = prepare_study()
        study = load_study(destination)
        print(f"Saved {len(study['options'])} entry-date option observations to {destination}")
        for choice in select_contracts(study):
            print(f"{choice['tenor']}: expiry={choice['expiry']}, days={choice['days']}, strike={choice['strike']:g}, "
                  f"call={choice['call']['premium']:g}, put={choice['put']['premium']:g}, lot={choice['lot_size']}")
    except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as error:
        raise SystemExit(f"NSE study preparation failed: {error}") from error
