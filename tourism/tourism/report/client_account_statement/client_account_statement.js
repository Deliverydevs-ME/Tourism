// Copyright (c) 2026, OsamaASidd and contributors
// For license information, please see license.txt

frappe.query_reports["Client Account Statement"] = {
    "filters": [
        {
            "fieldname": "party",
            "label": __("Customer"),
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 0
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.month_start()
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today()
        }
    ]
};



