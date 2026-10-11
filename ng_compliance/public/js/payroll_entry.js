frappe.ui.form.on("Payroll Entry", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !frm.doc.salary_slips_submitted) return;
		frm.add_custom_button(__("Post Employer Contributions"), () => {
			frappe.call({
				method: "ng_compliance.payroll.post_employer_contributions",
				args: { payroll_entry: frm.doc.name },
				freeze: true,
				freeze_message: __("Posting employer pension, NSITF, ITF and HMO..."),
				callback(r) {
					if (!r.message) return;
					frappe.msgprint(r.message.message);
					if (r.message.journal_entry) frappe.set_route("Form", "Journal Entry", r.message.journal_entry);
				},
			});
		}, __("Nigeria"));
	},
});
