"""Unduh data perdagangan Indonesia <-> 27 negara Uni Eropa dari Eurostat Comext.

Sumber : Eurostat, dataset DS-045409 "EU trade since 1988 by HS2-4-6 and CN8"
API    : https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409
Lisensi: Eurostat (CC BY 4.0), boleh dipakai ulang dengan menyebut sumber.

Satu baris hasil = satu negara UE x satu bab HS2 x satu arus x satu bulan.
  flow 1 = impor UE dari Indonesia  (= ekspor Indonesia ke UE)
  flow 2 = ekspor UE ke Indonesia   (= impor Indonesia dari UE)

Data disimpan apa adanya (data mentah). Pembersihan dilakukan di notebook.

Pemakaian:  python3 scripts/fetch_comext.py [tahun_mulai]
Hanya memakai pustaka standar Python.
"""
import csv
import itertools
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/statistics/1.0/data/DS-045409"
REPORTERS = ["AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI", "FR", "GR", "HR", "HU",
             "IE", "IT", "LT", "LU", "LV", "MT", "NL", "PL", "PT", "RO", "SE", "SI", "SK"]
INDICATORS = {"VALUE_IN_EUROS": "nilai_eur", "QUANTITY_IN_100KG": "berat_100kg"}
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "perdagangan_id_ue_hs2_bulanan.csv"


def fetch(reporters, since):
    params = [("format", "JSON"), ("lang", "en"), ("freq", "M"), ("partner", "ID"),
              ("flow", "1"), ("flow", "2"), ("sinceTimePeriod", since)]
    params += [("reporter", r) for r in reporters]
    params += [("indicators", i) for i in INDICATORS]
    params += [("product", f"{p:02d}") for p in range(1, 100)]
    url = BASE + "?" + "&".join(f"{k}={v}" for k, v in params)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r)
        except Exception as e:  # jaringan/timeout: coba lagi
            print(f"  gagal ({e}); coba lagi", file=sys.stderr)
            time.sleep(5 * (attempt + 1))
    raise SystemExit("Gagal mengunduh dari Eurostat")


def rows(ds):
    """Ubah JSON-stat menjadi baris panjang {dimensi..., indikator: nilai}."""
    ids, sizes, values = ds["id"], ds["size"], ds["value"]
    dims = []
    for d in ids:
        cat = ds["dimension"][d]["category"]
        codes = sorted(cat["index"], key=cat["index"].get)
        dims.append([(c, cat.get("label", {}).get(c, c)) for c in codes])
    strides = [1] * len(sizes)
    for i in range(len(sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * sizes[i + 1]
    out = {}
    for k, v in values.items():
        k = int(k)
        pos = {d: dims[i][(k // strides[i]) % sizes[i]] for i, d in enumerate(ids)}
        key = (pos["time"][0], pos["reporter"][0], pos["product"][0], pos["flow"][0])
        rec = out.setdefault(key, {
            "periode": pos["time"][0],
            "kode_negara": pos["reporter"][0],
            "hs2": pos["product"][0],
            "deskripsi_hs2": pos["product"][1],
            "arus": pos["flow"][0],
            "nilai_eur": "",
            "berat_100kg": "",
        })
        rec[INDICATORS[pos["indicators"][0]]] = v
    return out.values()


def main():
    since = (sys.argv[1] if len(sys.argv) > 1 else "2019") + "-01"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fields = ["periode", "kode_negara", "hs2", "deskripsi_hs2", "arus", "nilai_eur", "berat_100kg"]
    n = 0
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        it = iter(REPORTERS)
        while chunk := list(itertools.islice(it, 3)):
            print("mengunduh", ",".join(chunk), file=sys.stderr)
            batch = sorted(rows(fetch(chunk, since)),
                           key=lambda r: (r["periode"], r["kode_negara"], r["hs2"], r["arus"]))
            w.writerows(batch)
            n += len(batch)
    print(f"{n} baris -> {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
