"""Rebuild ng_compliance/data/fedco_coa.json and the ERPNext importer CSV from the CoA workbook.

    python3 tools/build_coa.py path/to/CoA_draft.xlsx

Workbook columns: Sub-Ledger Code | Sub-Ledger Account | Headline Code | Headline Account | FS Category
Re-run after editing the workbook, commit the generated files, then `bench migrate` +
`bench execute ng_compliance.setup.coa.import_chart`.
"""

import csv
import json
import os
import sys
from collections import Counter

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "..", "ng_compliance", "data")

ROOTS = {
	"Asset": "Assets",
	"Liability": "Liabilities",
	"Equity": "Equity",
	"Income": "Income",
	"Expense": "Expenses",
}

# ERPNext account types needed for automation (stock, receivables, depreciation, banking, tax...)
ACCOUNT_TYPES = {
	**{c: "Fixed Asset" for c in ("11001", "11002", "11003", "11004", "11005", "11006", "12001")},
	**{c: "Accumulated Depreciation" for c in ("11051", "11052", "11053", "11054", "11055", "11056", "12051")},
	**{c: "Stock" for c in ("10010", "10011", "10014", "10015", "10016", "10017")},
	"10021": "Tax",
	"10022": "Tax",
	"10025": "Receivable",
	"10026": "Receivable",
	"10001": "Cash",
	"10003": "Cash",
	"10004": "Cash",
	"10002": "Bank",
	"10005": "Bank",
	"20001": "Payable",
	"20003": "Payable",
	"20004": "Payable",  # payroll payable: Frappe HR v16 requires account type Payable
	"20006": "Stock Received But Not Billed",
	**{c: "Tax" for c in ("20011", "20012", "20013", "20014", "20015", "20016", "20017", "20019")},
	"40001": "Income Account",
	"40002": "Income Account",
	"40003": "Income Account",
	"50001": "Cost of Goods Sold",
	"50032": "Stock Adjustment",
	**{c: "Depreciation" for c in ("50011", "50012", "50013", "50014", "60008", "60009", "60011")},
	"60010": "Round Off",
}

CURRENCY = {"10005": "USD", "10026": "USD", "20005": "USD"}

HEADLINE_TYPES = {"H02": "Stock"}  # group type ERPNext uses to auto-create warehouse accounts

# Codes reassigned because the draft reused them
RECODE = {("10002", "Bank - USD"): "10005"}

# Accounts the draft does not have but payroll / statutory posting needs
ADDITIONS = [
	("20008", "HMO & Group Life Premiums Payable", "H05", "Accounts Payable", "Liability"),
	("20014", "Statutory Payables - Pension", "H08", "Taxation Payable", "Liability"),
	("20015", "Statutory Payables - NHF", "H08", "Taxation Payable", "Liability"),
	("20016", "Statutory Payables - NSITF", "H08", "Taxation Payable", "Liability"),
	("20017", "Statutory Payables - ITF", "H08", "Taxation Payable", "Liability"),
	("20019", "Statutory Payables - CIT & Development Levy", "H08", "Taxation Payable", "Liability"),
]


def build(xlsx):
	ws = openpyxl.load_workbook(xlsx, data_only=True).active
	rows, notes = [], []
	headlines = {}
	for r in list(ws.iter_rows(values_only=True))[1:]:
		if not r or r[0] is None:
			continue
		code, name, hcode, hname, cat = (str(x).strip() if x is not None else "" for x in r[:5])
		new = RECODE.get((code, name))
		if new:
			notes.append(f"Recoded '{name}' {code} -> {new} (code {code} was used twice)")
			code = new
		if hcode in headlines and headlines[hcode][0] != hname:
			notes.append(
				f"{code} '{name}': headline name '{hname}' differs from {hcode} '{headlines[hcode][0]}'; "
				f"kept under {hcode} (code wins)"
			)
		headlines.setdefault(hcode, (hname, cat))
		rows.append([code, name, hcode, cat])
	for code, name, hcode, hname, cat in ADDITIONS:
		notes.append(f"Added {code} '{name}' under {hcode}")
		headlines.setdefault(hcode, (hname, cat))
		rows.append([code, name, hcode, cat])

	dupes = [c for c, n in Counter(r[0] for r in rows).items() if n > 1]
	if dupes:
		raise SystemExit(f"Duplicate codes remain: {dupes}")

	chart = {
		"roots": ROOTS,
		"headlines": [
			{"code": h, "name": n, "root_type": c, "account_type": HEADLINE_TYPES.get(h, "")}
			for h, (n, c) in sorted(headlines.items(), key=lambda kv: int(kv[0][1:]))
		],
		"accounts": [
			{
				"code": code,
				"name": name,
				"headline": hcode,
				"root_type": cat,
				"account_type": ACCOUNT_TYPES.get(code, ""),
				"currency": CURRENCY.get(code, ""),
			}
			for code, name, hcode, cat in sorted(rows, key=lambda r: (r[2] and int(r[2][1:]), r[0]))
		],
		"notes": notes,
	}
	os.makedirs(OUT_DIR, exist_ok=True)
	with open(os.path.join(OUT_DIR, "fedco_coa.json"), "w") as f:
		json.dump(chart, f, indent=1, ensure_ascii=False)

	# CSV for ERPNext's built-in "Chart of Accounts Importer" (new company, no transactions yet)
	with open(os.path.join(OUT_DIR, "fedco_coa_importer.csv"), "w", newline="", encoding="utf-8") as f:
		w = csv.writer(f)
		w.writerow(["Account Name", "Parent Account", "Account Number", "Parent Account Number",
			"Is Group", "Account Type", "Root Type", "Account Currency"])
		for rt, root in ROOTS.items():
			w.writerow([root, "", "", "", 1, "", rt, ""])
		for h in chart["headlines"]:
			w.writerow([h["name"], ROOTS[h["root_type"]], h["code"], "", 1, h["account_type"], h["root_type"], ""])
		for a in chart["accounts"]:
			hn = headlines[a["headline"]][0]
			w.writerow([a["name"], hn, a["code"], a["headline"], 0, a["account_type"], a["root_type"], a["currency"]])
	return chart


if __name__ == "__main__":
	c = build(sys.argv[1])
	print(f"{len(c['headlines'])} headlines, {len(c['accounts'])} accounts")
	print("\n".join(c["notes"]))
