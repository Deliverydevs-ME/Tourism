# Copyright (c) 2026, OsamaASidd and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

from erpnext.accounts.report.general_ledger.general_ledger import execute as gl_execute


def execute(filters=None):
	# Exact duplicate of the standard General Ledger (same columns, same
	# filters) - the only difference is that each row's debit/credit is
	# netted down to the single side that actually hit the account, e.g. a
	# voucher debiting 5000 and crediting 500 reads as 4500 debit, not both.
	# Balance is untouched since debit - credit is unchanged by netting.
	filters = frappe._dict(filters or {})
	columns, data = gl_execute(filters)

	for row in data:
		_net(row, "debit", "credit")
		_net(row, "debit_in_account_currency", "credit_in_account_currency")

	return columns, data


def _net(row, debit_field, credit_field):
	net = flt(row.get(debit_field)) - flt(row.get(credit_field))
	if net >= 0:
		row[debit_field] = net
		row[credit_field] = 0
	else:
		row[debit_field] = 0
		row[credit_field] = -net
