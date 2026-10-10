import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ng_compliance"))
from paye import compute_annual_paye, rent_relief, tax_on_chargeable_income  # noqa: E402


class TestNTA2025(unittest.TestCase):
	def test_nil_band(self):
		self.assertEqual(tax_on_chargeable_income(800_000)[0], 0)

	def test_band_boundaries(self):
		# 2.2m @15% = 330,000
		self.assertEqual(tax_on_chargeable_income(3_000_000)[0], 330_000)
		# + 9m @18% = 1,620,000 -> 1,950,000
		self.assertEqual(tax_on_chargeable_income(12_000_000)[0], 1_950_000)
		# + 13m @21% = 2,730,000 -> 4,680,000
		self.assertEqual(tax_on_chargeable_income(25_000_000)[0], 4_680_000)
		# + 25m @23% = 5,750,000 -> 10,430,000
		self.assertEqual(tax_on_chargeable_income(50_000_000)[0], 10_430_000)
		# + 10m @25% = 2,500,000
		self.assertEqual(tax_on_chargeable_income(60_000_000)[0], 12_930_000)

	def test_rent_relief(self):
		self.assertEqual(rent_relief(600_000), 120_000)
		self.assertEqual(rent_relief(5_000_000), 500_000)
		self.assertEqual(rent_relief(0), 0)

	def test_minimum_wage_is_untaxed_with_pension(self):
		# N70,000/month minimum wage, all basic
		r = compute_annual_paye(840_000, annual_basic=840_000)
		self.assertEqual(r["annual_tax"], 0)

	def test_worked_example(self):
		# N500k/month: basic 250k, housing 150k, transport 100k; rent N1.2m/yr
		r = compute_annual_paye(
			6_000_000, annual_basic=3_000_000, annual_housing=1_800_000,
			annual_transport=1_200_000, annual_rent=1_200_000,
		)
		self.assertEqual(r["pension"], 480_000)
		self.assertEqual(r["nhf"], 75_000)
		self.assertEqual(r["rent_relief"], 240_000)
		self.assertEqual(r["chargeable_income"], 5_205_000)
		# 330,000 + (2,205,000 * 18%) = 726,900
		self.assertEqual(r["annual_tax"], 726_900)
		self.assertEqual(r["monthly_tax"], 60_575)


class TestFedcoSamplePayslip(unittest.TestCase):
	def test_draft_payslip_fwa_007(self):
		# FEDCO draft payslip Sept 2026: Basic N1.2m only, pension 8%, no NHF, no rent relief
		r = compute_annual_paye(14_400_000, annual_basic=14_400_000, include_nhf=False)
		self.assertEqual(r["chargeable_income"] / 12, 1_104_000)
		self.assertEqual(r["monthly_tax"], 184_340)
		self.assertEqual(1_200_000 - 96_000 - r["monthly_tax"], 919_660)


def hrms_slab_tax(annual, slabs):
	"""Copy of hrms.payroll.doctype.income_tax_slab.calculate_base_tax_from_tax_slabs (v16)."""
	tax = 0
	for s in slabs:
		if not s["to_amount"] and annual >= s["from_amount"]:
			tax += (annual - s["from_amount"] + 1) * s["percent_deduction"] * 0.01
			continue
		if annual >= s["from_amount"] and annual < s["to_amount"]:
			tax += (annual - s["from_amount"] + 1) * s["percent_deduction"] * 0.01
		elif annual >= s["from_amount"] and annual >= s["to_amount"]:
			tax += (s["to_amount"] - s["from_amount"] + 1) * s["percent_deduction"] * 0.01
	return tax


class TestSlabMatchesHRMS(unittest.TestCase):
	def test_generated_slab_rows_reproduce_statutory_tax(self):
		from paye import NTA_2025_BANDS

		rows, lower = [], 0
		for upper, rate in NTA_2025_BANDS:  # same logic as setup/payroll.py
			rows.append({"from_amount": lower + 1 if lower else 0, "to_amount": upper or 0, "percent_deduction": rate * 100})
			lower = upper or lower
		for income in (0, 500_000, 800_000, 800_001, 1_000_000, 3_000_000, 5_205_000, 12_000_000,
				20_000_000, 25_000_000, 49_999_999, 50_000_000, 75_000_000, 250_000_000):
			self.assertAlmostEqual(hrms_slab_tax(income, rows), tax_on_chargeable_income(income)[0], delta=0.5,
				msg=f"income {income}")


if __name__ == "__main__":
	unittest.main()
