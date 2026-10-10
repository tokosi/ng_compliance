"""Embed templates/print_formats/*.html into the standard Print Format JSON files.

    python3 tools/build_print_formats.py   # then: bench --site <site> migrate
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "..", "ng_compliance")
FORMATS = [
	("Nigeria Payslip", "Salary Slip", "nigeria_payslip.html"),
	("Nigeria VAT Invoice", "Sales Invoice", "nigeria_vat_invoice.html"),
]

for name, doctype, tpl in FORMATS:
	html = open(os.path.join(APP, "templates", "print_formats", tpl), encoding="utf-8").read()
	folder = os.path.join(APP, "ng_compliance", "print_format", name.lower().replace(" ", "_"))
	os.makedirs(folder, exist_ok=True)
	open(os.path.join(folder, "__init__.py"), "a").close()
	doc = {
		"doctype": "Print Format",
		"name": name,
		"doc_type": doctype,
		"module": "NG Compliance",
		"standard": "Yes",
		"custom_format": 1,
		"print_format_type": "Jinja",
		"print_format_builder": 0,
		"print_format_builder_beta": 0,
		"raw_printing": 0,
		"disabled": 0,
		"align_labels_right": 0,
		"show_section_headings": 0,
		"line_breaks": 0,
		"absolute_value": 0,
		"font_size": 0,
		"margin_top": 15.0,
		"margin_bottom": 15.0,
		"margin_left": 15.0,
		"margin_right": 15.0,
		"page_number": "Hide",
		"default_print_language": "en",
		"docstatus": 0,
		"idx": 0,
		"owner": "Administrator",
		"modified_by": "Administrator",
		"creation": "2026-10-10 12:00:00.000000",
		"modified": "2026-10-10 12:00:00.000000",
		"html": html,
	}
	with open(os.path.join(folder, os.path.basename(folder) + ".json"), "w", encoding="utf-8") as f:
		json.dump(doc, f, indent=1, ensure_ascii=False)
	print("built", name)
