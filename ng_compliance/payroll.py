"""Post employer contributions (pension 10%, NSITF, ITF, HMO, group life) to the ledger.

Only needed on Frappe HR builds older than v16.12, where these are statistical rows on the
salary slip. Newer builds post them automatically ("Employer Contribution" components).

Button: "Post Employer Contributions" on a submitted Payroll Entry, or
    bench --site <site> execute ng_compliance.payroll.post_employer_contributions \
        --kwargs "{'payroll_entry': 'HR-PRUN-2026-00001'}"

Journal Entry: Dr 60001 Staff Costs / Cr each statutory payable (20014, 20016, 20017, 20008).
Safe to click twice: an existing entry for the same Payroll Entry is returned instead.
"""

import frappe
from frappe import _
from frappe.utils import flt

from ng_compliance.setup.payroll import EMPLOYER_COMPONENTS, components
from ng_compliance.setup.profile import account


def _remark(payroll_entry):
	return f"Employer contributions for Payroll Entry {payroll_entry}"


def _liability_keys():
	return {name: mapping[1] for name, _a, _t, _f, _c, _fl, mapping, _i in components()
		if name in EMPLOYER_COMPONENTS and isinstance(mapping, tuple)}


@frappe.whitelist()
def post_employer_contributions(payroll_entry):
	frappe.only_for(("System Manager", "Accounts Manager", "HR Manager"))
	pe = frappe.get_doc("Payroll Entry", payroll_entry)
	if pe.docstatus != 1:
		frappe.throw(_("Submit the Payroll Entry first."))

	existing = frappe.db.get_value(
		"Journal Entry", {"user_remark": _remark(pe.name), "docstatus": ("<", 2), "company": pe.company}, "name"
	)
	if existing:
		return {"journal_entry": existing, "message": _("Already posted in {0}").format(existing)}

	slips = frappe.get_all("Salary Slip", filters={"payroll_entry": pe.name, "docstatus": 1}, pluck="name")
	if not slips:
		frappe.throw(_("No submitted Salary Slips for {0}. Submit the salary slips first.").format(pe.name))

	from ng_compliance.setup.payroll import supports_employer_contribution

	if supports_employer_contribution():
		return {"journal_entry": None, "message": _(
			"This Frappe HR version posts employer contributions automatically with the payroll.")}
	totals = {}
	for name in slips:
		for component, amount in employer_contributions_for(frappe.get_doc("Salary Slip", name)).items():
			totals[component] = totals.get(component, 0) + amount
	totals = {k: flt(v, 2) for k, v in totals.items() if flt(v, 2)}
	if not totals:
		return {"journal_entry": None, "message": _("No employer contributions to post for these slips.")}

	expense = account(pe.company, "staff_costs")
	if not expense:
		frappe.throw(_("Staff Costs account (60001) not found - run the chart of accounts import."))
	keys = _liability_keys()
	cost_center = pe.cost_center or frappe.get_cached_value("Company", pe.company, "cost_center")

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = pe.company
	je.posting_date = pe.posting_date
	je.title = _("Employer contributions {0}").format(pe.name)
	je.user_remark = _remark(pe.name)
	total = 0
	for component, amount in sorted(totals.items()):
		liability = account(pe.company, keys.get(component, "hmo_payable"))
		if not liability:
			frappe.throw(_("Liability account for {0} not found - run the chart of accounts import.").format(component))
		je.append("accounts", {"account": liability, "credit_in_account_currency": amount, "cost_center": cost_center,
			"user_remark": component})
		total += amount
	je.append("accounts", {"account": expense, "debit_in_account_currency": flt(total, 2), "cost_center": cost_center,
		"user_remark": _("Employer contributions")})
	je.insert()
	je.submit()
	return {"journal_entry": je.name, "message": _("Posted {0}: ₦{1:,.2f}").format(je.name, total)}


# --- employer contributions computed from the slip itself -------------------------------------
# Frappe HR builds before v16.12 do not store statistical rows on the Salary Slip, so the
# employer costs are recomputed here from the slip's earnings and the assignment's HMO premium.

PENSIONABLE = ("Basic Salary", "Housing Allowance", "Transport Allowance")
EMOLUMENTS = ("Basic Salary", "Cost of Living Allowance", "Housing Allowance", "Transport Allowance",
	"Other Allowances")


def _earning(slip, names):
	return sum(flt(d.amount) for d in slip.get("earnings") or [] if d.salary_component in names)


def _hmo_premium(slip):
	if not frappe.get_meta("Salary Structure Assignment").has_field("ng_hmo_premium"):
		return 0
	rows = frappe.get_all(
		"Salary Structure Assignment",
		filters={"employee": slip.employee, "docstatus": 1, "from_date": ("<=", slip.start_date)},
		fields=["ng_hmo_premium"], order_by="from_date desc", limit=1,
	)
	return flt(rows[0].ng_hmo_premium) if rows else 0


def computed_employer_contributions(slip):
	"""{component: amount} for one salary slip, using the rates in data/fedco_profile.json."""
	from ng_compliance.setup.profile import params

	p = params()
	pensionable, emoluments = _earning(slip, PENSIONABLE), _earning(slip, EMOLUMENTS)
	out = {
		"Employer Pension": pensionable * p["employer_pension_rate"],
		"NSITF Employer": emoluments * p["nsitf_rate"],
	}
	if p.get("itf_applicable"):
		out["ITF Employer"] = emoluments * p["itf_rate"]
	if p.get("hmo_premium_monthly"):
		out["HMO Premium"] = _hmo_premium(slip)
	if p.get("group_life_rate_of_annual_emoluments"):
		out["Group Life Assurance"] = emoluments * p["group_life_rate_of_annual_emoluments"]
	return {k: flt(v, 2) for k, v in out.items() if flt(v, 2)}


def employer_contributions_for(slip):
	"""Stored rows when the slip has them (v16.12+ or statistical rows), else computed."""
	stored = {}
	for d in list(slip.get("employer_contributions") or []) + list(slip.get("deductions") or []):
		if d.salary_component in EMPLOYER_COMPONENTS:
			stored[d.salary_component] = stored.get(d.salary_component, 0) + flt(d.amount)
	return {k: v for k, v in stored.items() if v} or computed_employer_contributions(slip)
