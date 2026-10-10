import json
import os
import unittest

DATA = os.path.join(os.path.dirname(__file__), "..", "ng_compliance", "data")


class TestFedcoProfile(unittest.TestCase):
	def setUp(self):
		with open(os.path.join(DATA, "fedco_coa.json")) as f:
			self.chart = json.load(f)
		with open(os.path.join(DATA, "fedco_profile.json")) as f:
			self.profile = json.load(f)
		self.codes = {a["code"] for a in self.chart["accounts"]}

	def test_unique_codes(self):
		codes = [a["code"] for a in self.chart["accounts"]]
		self.assertEqual(len(codes), len(set(codes)))

	def test_every_mapped_account_exists(self):
		acc = self.profile["accounts"]
		mapped = [v for k, v in acc.items() if not k.startswith("_") and isinstance(v, str)]
		mapped += list(acc["company_defaults"].values())
		missing = [c for c in mapped if c not in self.codes]
		self.assertEqual(missing, [])

	def test_headlines_exist(self):
		heads = {h["code"] for h in self.chart["headlines"]}
		self.assertTrue(all(a["headline"] in heads for a in self.chart["accounts"]))

	def test_mandatory_account_types_present(self):
		types = {a["account_type"] for a in self.chart["accounts"]}
		for t in ("Bank", "Cash", "Receivable", "Payable", "Stock", "Fixed Asset", "Depreciation",
				"Cost of Goods Sold", "Stock Adjustment", "Round Off"):
			self.assertIn(t, types)


if __name__ == "__main__":
	unittest.main()
