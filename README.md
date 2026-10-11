# NG Compliance — FEDCO Nigeria Payroll, Accounting, VAT & ESS for ERPNext / Frappe HR v16

A Frappe app that sets up **FEDCO West Africa Limited** on **ERPNext v16 + Frappe HR (hrms) v16**:

| Module | What you get |
|---|---|
| **Chart of accounts** | The FEDCO chart (24 headline groups H01–H24, 113 sub-ledgers with their codes) loaded into an existing company, or as a CSV for ERPNext's Chart of Accounts Importer on a new company. Company default accounts mapped. |
| **PAYE (Nigeria Tax Act 2025)** | Slab 0 / 15 / 18 / 21 / 23 / 25 % (Fourth Schedule), cumulative monthly PAYE. Pension, NHF and NHIS/life premium deducted before tax. **Rent relief** = 20% of rent, max ₦500,000, claimed by the employee. |
| **Payroll** | Components exactly as on the FEDCO payslip: Basic, COLA, Housing, Transport, Overtime, Other allowances, Variable pay/bonus; Pension 8%, NHF 2.5% (opt-in), NHIS/life premium, PAYE, Loan/other deductions; employer Pension 10%, NSITF 1%, ITF 1%, HMO ₦1,250. |
| **VAT (NRS rules)** | 7.5% standard, zero-rated exports, exempt supplies, local / import input VAT, reverse charge for non-resident suppliers. Templates are picked automatically from the party's Tax Category. **VAT invoice** with every NRS-required field. **VAT 002 return** worksheet (due 21st). |
| **WHT** | Withholding categories under the 2024 Regulations, posted to 20012. |
| **ESS** | Employee logins on Frappe HR's *Employee Self Service* user type, mobile app at `/hrms`. |
| **Print formats** | **Nigeria Payslip** (FEDCO-branded, used for printing, emailing and the mobile app) and **Nigeria VAT Invoice**. |
| **Reports** | *Nigeria Statutory Remittance* (PAYE by State IRS, Pension by PFA, NHF, NSITF, ITF, HMO) and *Nigeria VAT Return*. |

Verified against the FEDCO draft payslip: Basic ₦1,200,000 → Pension ₦96,000 → chargeable ₦1,104,000 → **PAYE ₦184,340** → **Net ₦919,660** (`python3 -m unittest discover -s tests`).

---

## Part 1 — Repository layout (github.com/tokosi/ng_compliance)

`bench get-app` only accepts this layout — `pyproject.toml` at the top, the Python package in `ng_compliance/`,
and `hooks.py` inside it:

```
ng_compliance/                 <- repository root
├── pyproject.toml
├── README.md
├── license.txt
├── .gitignore
├── tests/  tools/
└── ng_compliance/             <- Python package
    ├── __init__.py
    ├── hooks.py
    ├── modules.txt  patches.txt
    ├── data/ setup/ overrides/ utils/ templates/ public/
    └── ng_compliance/         <- module "NG Compliance" (reports, print formats)
```

To publish a change from your laptop:

```bash
git clone https://github.com/tokosi/ng_compliance.git
cd ng_compliance
# ...edit files...
git add -A
git commit -m "Describe the change"
git push                       # GitHub username + a personal access token as the password
```

The repository is **public**, so anyone can read the chart of accounts and the RC number / TIN in
`ng_compliance/data/fedco_profile.json`. Those already appear on invoices, so that's usually acceptable. If not, make
the repo private (Settings → Danger Zone → Change visibility) and use *If you make the repo private later* below.

---

## Part 2 — Install on the existing ERPNext v16 server

Run everything as the bench user (usually `frappe`), from the bench folder. Replace `erp.fedco.ng` with your site name.

### Step 1 — Check the server and take a backup

```bash
ssh frappe@<server>
cd ~/frappe-bench
bench version                 # frappe, erpnext and hrms must all show 16.x
bench --site erp.fedco.ng list-apps
bench --site erp.fedco.ng backup --with-files
```

Don't continue if `hrms` is missing — install Frappe HR v16 first (`bench get-app --branch version-16 hrms` and
`bench --site erp.fedco.ng install-app hrms`).

### Step 2 — Get the app from GitHub

The repo is public, so no keys or tokens are needed:

```bash
bench get-app https://github.com/tokosi/ng_compliance.git --branch main
```

This clones into `apps/ng_compliance`, installs it into the bench's Python environment and adds it to
`sites/apps.txt`. If it says the app already exists (from an earlier attempt), remove that copy first with
`bench remove-app ng_compliance --force` — only when it isn't installed on any site — and run `get-app` again.

### Step 3 — Install it on the site

```bash
bench --site erp.fedco.ng install-app ng_compliance
bench --site erp.fedco.ng migrate
bench build --app ng_compliance
bench restart                 # production: sudo supervisorctl restart all
```

Installing adds custom fields (Employee → *Nigeria Statutory*; Salary Structure Assignment → *Monthly Pay (Nigeria)*;
Company → *RC Number*, *Registered Address*; Sales Invoice → *NRS IRN*), the two print formats, and makes them the
default print formats for Salary Slip and Sales Invoice.

### Step 4 — Load the chart of accounts

Pick the route that matches the company:

**A. Company exists but has no transactions yet** — replace the chart completely:
1. **Accounting → Chart of Accounts Importer**, choose the company.
2. Attach `ng_compliance/data/fedco_coa_importer.csv` (download it from the GitHub repo) → *Import*.
3. Then set the default accounts:
   ```bash
   bench --site erp.fedco.ng execute ng_compliance.setup.coa.set_company_defaults --kwargs "{'company': 'FEDCO West Africa Limited'}"
   ```

**B. Company already has postings** — add the FEDCO chart alongside (nothing is deleted; same-named accounts are numbered and reused):

```bash
bench --site erp.fedco.ng execute ng_compliance.setup.coa.import_chart \
  --kwargs "{'company': 'FEDCO West Africa Limited'}"
```

Add `'renumber_existing': 1` to give same-named standard accounts that already carry a number (e.g. `1110 - Cash`)
their FEDCO number (`10001 - Cash`); renumbering is refused if anything was posted in the last 5 minutes. Add
`'disable_unused_standard': 1` to disable old Standard-chart leaf accounts that have no postings. Then move open
balances from old accounts to the FEDCO ones with a Journal Entry and review the result in *Chart of Accounts*.

### Step 5 — Run the rest of the setup

```bash
bench --site erp.fedco.ng execute ng_compliance.setup.accounts.setup_nigeria_accounts --kwargs "{'company': 'FEDCO West Africa Limited'}"
bench --site erp.fedco.ng execute ng_compliance.setup.payroll.setup_nigeria_payroll --kwargs "{'company': 'FEDCO West Africa Limited', 'year': 2026}"
bench --site erp.fedco.ng execute ng_compliance.setup.ess.setup_ess --kwargs "{'company': 'FEDCO West Africa Limited'}"
```

Or all four steps (route B chart included) in one go:

```bash
bench --site erp.fedco.ng execute ng_compliance.setup.all.run --kwargs "{'company': 'FEDCO West Africa Limited'}"
```

Every step is safe to re-run. Read the printed log — lines starting with `!` need attention.

> **Existing payroll setups:** if *Salary Component* records named *Basic Salary*, *Housing Allowance*, *PAYE*, etc.
> already exist, the payroll step updates their type, formula and accounts to the Nigerian setup. Existing salary
> structures and slips are left alone; new assignments use **Nigeria Monthly (NTA 2025)**.

### Step 6 — Check before the first live run

1. **Company**: TIN, RC number, registered address (filled from the profile — check them).
2. **Print**: open any Salary Slip → *Print* → it should show the FEDCO payslip. Choose *No Letter Head*.
3. **Dry run**: assign one employee (Step 7 below), create a Payroll Entry, compare the slip with the
   calculator `/api/method/ng_compliance.api.paye_preview?monthly_gross=1200000&monthly_basic=1200000&include_nhf=0`
   → `monthly_tax` 184340. Delete the draft slips afterwards.
4. **VAT**: create a draft Sales Invoice for a customer with Tax Category *NG Domestic* → template *NG VAT 7.5%*;
   *NG Export* → *NG VAT Zero-Rated Export*. Print it.

### Updating the app later

```bash
cd ~/frappe-bench
bench --site erp.fedco.ng backup
cd apps/ng_compliance && git pull upstream main && cd ../..
# bench names the GitHub remote "upstream". If git reports "dubious ownership", run once:
#   git config --global --add safe.directory "$(pwd)/apps/ng_compliance"
bench --site erp.fedco.ng migrate
bench build --app ng_compliance
bench restart
```

### If you make the repo private later

Give the server a read-only deploy key and switch the app's remote to SSH:

```bash
ssh-keygen -t ed25519 -C "erp-server ng_compliance" -f ~/.ssh/ng_compliance_deploy -N ""
cat ~/.ssh/ng_compliance_deploy.pub    # GitHub: repo → Settings → Deploy keys → Add (write access off)
printf 'Host github.com\n  IdentityFile ~/.ssh/ng_compliance_deploy\n  IdentitiesOnly yes\n' >> ~/.ssh/config
chmod 600 ~/.ssh/config
cd ~/frappe-bench/apps/ng_compliance
git remote set-url upstream git@github.com:tokosi/ng_compliance.git
git pull upstream main
```

### Docker (frappe_docker) or Frappe Cloud

* **frappe_docker**: add the repo to your `apps.json`
  (`{"url": "https://github.com/tokosi/ng_compliance.git", "branch": "main"}`), rebuild the custom image,
  redeploy, then run `bench --site <site> install-app ng_compliance` and Steps 4–6 inside the backend container
  (`docker compose exec backend bash`).
* **Frappe Cloud**: Bench group → *Apps* → *Add app* → public GitHub URL `https://github.com/tokosi/ng_compliance`
  (branch `main`) → deploy → install on the site. Run Steps 4–5 from *Site → Console* using the same
  `ng_compliance.setup...` functions.

---

## Part 3 — Day-to-day

### Employees
1. **Employee** → *Nigeria Statutory*: Staff type, TIN, **PAYE State** (state of residence; *Tax Office* fills itself,
   e.g. Ondo → ODIRS), PFA, RSA PIN, **NHF opt-in** (+ NHF No.). Also Bank name, Account no., Branch (work location),
   Department, Designation, email, Leave and Expense approvers.
2. **Salary Structure Assignment**: Structure *Nigeria Monthly (NTA 2025)*, Income Tax Slab *Nigeria NTA 2025*,
   From date, then *Monthly Pay (Nigeria)*: Basic, COLA, Housing, Transport, Other allowances, NHIS/life premium,
   HMO premium (defaults to ₦1,250), Exchange rate (expatriates). *Base* is calculated. Typing only *Base* pays it all as
   Basic.
   **Opening balances (important):** Frappe HR computes PAYE cumulatively over the payroll year. If ERPNext's first
   payslip for someone is not January, fill *Taxable Earnings Till Date* (chargeable income already paid this year,
   i.e. gross minus pension/NHF/NHIS minus rent relief) and *Tax Deducted Till Date* (PAYE already deducted). Example:
   ₦1.2m basic paid Jan–Aug outside ERPNext → 8 × ₦1,104,000 = ₦8,832,000 and 8 × ₦184,340 = ₦1,474,720; September
   PAYE is then ₦184,340. Without them, September would tax only Sept–Dec income (lower PAYE). The assignment's
   *From Date* must fall inside the payroll year for the openings to count.
3. **Each month**: Overtime, Variable pay/bonus and Loan/other deductions go in as **Additional Salary** before running payroll.
4. Re-run `setup_ess` after adding employees so they get logins.

### Rent relief (employee via ESS)
Employee → **Employee Tax Exemption Declaration** → Payroll Period *Nigeria 2026* → Sub category *Rent Relief* →
**Annual Rent Paid**. The app sets the relief to min(20% × rent, ₦500,000). HR checks the tenancy agreement/receipts and
submits; PAYE reflects it from the next run. No declaration, no relief (CRA was abolished).

### Monthly payroll
Payroll Entry → *Get Employees* → *Create Salary Slips* → review → *Submit Salary Slips*.

**Frappe HR older than v16.12** (no "Employer Contribution" component type — the payroll setup log says which mode
it used): employer pension, NSITF, ITF and HMO are shown on the payslip but not posted automatically. After submitting
the slips, click **Nigeria → Post Employer Contributions** on the Payroll Entry. It creates one Journal Entry
(Dr 60001 / Cr 20014, 20016, 20017, 20008) and won't post twice. On v16.12+ this happens automatically.

Postings:

| | Debit | Credit |
|---|---|---|
| Earnings | 60001 Staff Costs | 20004 Salary Control Account |
| Pension 8% / NHF / NHIS / PAYE / Loans | 20004 | 20014 / 20015 / 20008 / 20011 / 10023 |
| Employer Pension 10% / NSITF / ITF / HMO | 60001 | 20014 / 20016 / 20017 / 20008 |

Then **Nigeria Statutory Remittance** report (tick *Summarise by State* for each State IRS) and pay the liabilities.

| Remittance | Due |
|---|---|
| PAYE → State IRS of residence | 10th of the following month |
| Pension (8% + 10%) → PFA | within 7 working days of paying salaries |
| NHF → FMBN · NSITF | monthly |
| ITF | annually (1% of annual payroll) |
| VAT (VAT 002) → NRS | 21st of the following month |

### VAT
* Set each **Customer**'s Tax Category: *NG Domestic* (7.5%), *NG Export* (zero-rated), *NG Exempt*.
* Set each **Supplier**'s Tax Category: *NG Domestic* (input VAT → 10022), *NG Import* (customs VAT → 10021),
  *NG Non-resident Supplier* (reverse charge: input 10022 / output 20013, net zero on the invoice).
* Mixed invoices: put *NG VAT Exempt* / *NG VAT Zero Rated* Item Tax Templates on the items.
* Input VAT on purchases used for **exempt** supplies is not recoverable — book it to the expense, don't use the input template.
* Month end: **Nigeria VAT Return** report → file VAT 002 on the NRS portal by the 21st.
* Fiscalisation: when NRS e-invoicing issues an IRN, enter it in *NRS Invoice Reference (IRN)* on the invoice (prints on the VAT invoice).

### ESS (mobile)
`https://<site>/hrms` → *Add to Home Screen*. Leave, check-in, expense claims, advances, payslips (FEDCO design,
password-protected email: first name + birth year, e.g. `Ngozi1990`) and rent declarations.

---

## Changing things

| To change | Edit | Then |
|---|---|---|
| Rates (pension, NHF, NSITF, ITF, HMO, group life) | `ng_compliance/data/fedco_profile.json` → `payroll_parameters` | push, update, re-run `setup_nigeria_payroll`, cancel & amend the salary structure |
| Chart of accounts | the CoA workbook → `python3 tools/build_coa.py CoA.xlsx` | commit, update, re-run `import_chart` |
| Payslip / VAT invoice design | `ng_compliance/templates/print_formats/*.html` → `python3 tools/build_print_formats.py` | commit, update, `migrate` |
| Tax bands | `ng_compliance/paye.py` + cancel & amend the *Nigeria NTA 2025* slab | |

## Chart of accounts — changes made to the draft

* **10002 was used twice** (Bank – Naira, Bank – USD). *Bank – USD* is now **10005** (USD account).
* **Added** (needed for payroll and tax postings): 20008 HMO & Group Life Premiums Payable, 20014 Statutory Payables –
  Pension, 20015 – NHF, 20016 – NSITF, 20017 – ITF, 20019 – CIT & Development Levy.
* 50004 and 50011–50014 have headline code **H15 (Cost of Sales)** but headline name *Administration & General
  Expenses*; they're kept under **H15**. Move them to H16 in the workbook if A&G was intended.
* USD accounts: 10005, 10026 Trade Receivables – Export Customers (FX), 20005 Foreign Currency Trade Liability.
* Local input VAT goes to **10022 Export VAT Recoverable** (input VAT on an exporter's purchases is refundable);
  customs VAT on imports to **10021**. Change `vat_input_local` in the profile if you prefer otherwise.

## Notes & limits

* Minimum-wage earners: with 8% pension, ₦70,000/month sits inside the ₦800,000 nil band, so PAYE is nil.
* NSITF/ITF are computed on the structure's monthly emoluments (not on overtime/bonus Additional Salary).
* WHT rates are the 2024 Regulations' resident rates (double where the supplier has no TIN) — confirm with your adviser.
* The ₦ sign uses the print font (Inter in Frappe v16). If your PDF server shows a box instead, install the Inter font
  on the server or replace `₦` with `N` in the templates.
