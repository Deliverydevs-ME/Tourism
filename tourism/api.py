import frappe
from frappe import _
from frappe.utils import cint

## New repo testing
@frappe.whitelist()
def get_suppliers_by_multiple_filters(supplier_group=None, tag=None, city=None, country=None):
	"""
	Returns suppliers matching ALL provided filter conditions (AND logic).
	Uses custom_city field for city filtering.
	Returns list of dicts with supplier name, contact, and email.
	"""
	filters = {"disabled": 0}

	# Handle "null" string from JavaScript
	if supplier_group and supplier_group != "null":
		filters["supplier_group"] = supplier_group

	if city and city != "null":
		filters["custom_city"] = city

	if country and country != "null":
		filters["country"] = country

	# Get suppliers matching the basic filters
	suppliers = frappe.get_all("Supplier", filters=filters, pluck="name")

	# If tag filter is provided, intersect with tagged suppliers
	if tag and tag != "null":
		tagged_suppliers = frappe.get_all(
			"Tag Link",
			filters={"document_type": "Supplier", "tag": ["like", f"%{tag}%"]},
			pluck="document_name"
		)
		# Intersect: keep only suppliers that are in both lists
		suppliers = [s for s in suppliers if s in tagged_suppliers]

	# Fetch contact details for each supplier
	result = []
	for supplier in suppliers:
		contact_info = get_supplier_contact(supplier)
		result.append({
			"supplier": supplier,
			"contact": contact_info.get("contact"),
			"email_id": contact_info.get("email_id")
		})

	return result


@frappe.whitelist()
def get_supplier_contact(supplier):
	"""
	Get contact and email for a supplier from Dynamic Link.
	"""
	if not supplier:
		return {"contact": None, "email_id": None}

	# First check if supplier has a primary contact set
	supplier_doc = frappe.get_value("Supplier", supplier, ["supplier_primary_contact", "email_id"], as_dict=True)
	if supplier_doc and supplier_doc.get("supplier_primary_contact"):
		contact = frappe.get_value("Contact", supplier_doc.supplier_primary_contact, "email_id")
		return {
			"contact": supplier_doc.supplier_primary_contact,
			"email_id": contact or supplier_doc.get("email_id")
		}

	# Otherwise, find contact via Dynamic Link
	contact = frappe.db.sql("""
		SELECT c.name, c.email_id
		FROM `tabContact` c
		JOIN `tabDynamic Link` dl ON dl.parent = c.name
		WHERE dl.link_doctype = 'Supplier' AND dl.link_name = %s
		LIMIT 1
	""", supplier, as_dict=True)

	if contact:
		return {
			"contact": contact[0].name,
			"email_id": contact[0].email_id
		}

	return {"contact": None, "email_id": None}

@frappe.whitelist()
def get_ticket_purchase_invoices(project):
    if not project:
        return []

    config = frappe.get_doc("TravelApp Config", "TravelApp Config")
    ticket_item = getattr(config, "ticket_item", None)
    if not ticket_item:
        return []

    rows = frappe.get_all(
        "Purchase Invoice",
        filters={
            "project": project,
            "custom_sales_invoice": ["is", "not set"],
            "custom_ticket_for": ["!=", "For Staff"],
            "custom_purchase_invoice_for_": ticket_item
        },
        fields=[
            "name",
            "supplier",
            "custom_passenger",
            "custom_ticket_number",
            "custom_airline",
            "custom_net_fare",
            "custom_route",
            "custom_full_route",
            "custom_sectors",
            "custom_ticket_margin",
            "custom_basic_fare",
            "custom_airline_tax",
            "custom_receivable",
            "custom_payable",
            "custom_income",
            "custom_psfr_amount",
            "custom_psf_amount",
            "custom_wht_amount",
            "custom_commision",
            "custom_penalty__margin",
            "custom_penalty_margin",
            "custom_ticket_remarks",
            "custom_total_fare",
            "custom_taxes1",
            "custom_fare_and_airline",
            "project",
            "custom_sst_amount",
            "custom_tour_from",
            "custom_tour_to",
            "is_return"
        ],
        limit_page_length=100,
        order_by="is_return desc, name asc"
    )

    # Group by ticket number; prefer is_return == 1
    best = {}
    for r in rows:
        ticket = (r.get("custom_ticket_number") or "").strip()
        # If no ticket number, treat it as unique (use name as key)
        key = ticket if ticket else f"__no_ticket__::{r['name']}"
        is_ret = 1 if int(r.get("is_return") or 0) == 1 else 0

        if key not in best:
            best[key] = r
        else:
            # If current best is not a return but this one is, replace
            if int(best[key].get("is_return") or 0) != 1 and is_ret == 1:
                best[key] = r
            # If both are returns or both are non-returns, keep the first (or
            # add a tie-break rule here if you want latest/earliest)

    return list(best.values())




@frappe.whitelist()
def sales_invoice_on_submit(doc, method):
    """Triggered on Sales Invoice submit via hooks.py"""
    if not doc.get("custom_ticket_purchase_invoices"):
        return

    for row in doc.custom_ticket_purchase_invoices:
        if row.get("purchase_invoice"):
            try:
                frappe.db.set_value(
                    "Purchase Invoice",
                    row.purchase_invoice,
                    "custom_sales_invoice",
                    doc.name
                )
            except Exception as e:
                frappe.log_error(frappe.get_traceback(), f"Failed to update Purchase Invoice {row.purchase_invoice}")


@frappe.whitelist()
def purchase_invoice_validate(doc, method):
    """
    Enforce that a ticket number has at most one *live* (draft or submitted)
    non-return Purchase Invoice.

    Cancelled invoices (docstatus 2) do NOT count. This is what makes the
    cancel-and-amend flow work: when a ticket invoice is cancelled and amended,
    the cancelled original is ignored, so the amendment is allowed - but a
    genuinely duplicate ticket number still cannot be posted, because any other
    live invoice with the same ticket is caught.
    """
    # Get the configured ticket item code
    ticket_item_code = frappe.db.get_single_value("TravelApp Config", "ticket_item")

    # Only apply this check for invoices marked against the ticket item
    if doc.custom_purchase_invoice_for_ != ticket_item_code:
        return

    ticket_no = (doc.custom_ticket_number or "").strip()
    if not ticket_no:
        return

    # Any other *live* (docstatus < 2), non-return Purchase Invoice that already
    # holds this ticket number. Cancelled invoices - including the amendment's
    # own cancelled original - are excluded by the docstatus filter.
    live_dups = frappe.get_all(
        "Purchase Invoice",
        filters={
            "custom_purchase_invoice_for_": ticket_item_code,
            "custom_ticket_number": ticket_no,
            "docstatus": ["<", 2],
            "is_return": 0,
            "name": ["!=", doc.name],
        },
        pluck="name",
    )

    is_return = getattr(doc, "is_return", False)
    has_return_against = bool(getattr(doc, "return_against", None))

    # A return / debit note is allowed against a single live original invoice.
    if is_return or has_return_against:
        if len(live_dups) > 1:
            frappe.throw(_(
                "Cannot create return: multiple live Purchase Invoices exist "
                "for ticket {0} ({1})."
            ).format(ticket_no, ", ".join(live_dups)))
        return

    # A normal (non-return) invoice must be the only live one for this ticket.
    if live_dups:
        frappe.throw(_(
            "A Purchase Invoice for ticket {0} already exists (Invoice {1})."
        ).format(ticket_no, live_dups[0]))



@frappe.whitelist()
def get_customer_primary_contact_details(contact_person):
    """
    Fetch primary contact details and linked custom fields from the Contact associated with the given Customer.
    """
    if not contact_person:
        return {}

    # Get the Contact linked to the Customer
    contact = frappe.get_doc(
        "Contact",contact_person
    )

    # if not contact_links:
    #     return {}

    # contact_name = contact_links[0].parent
    # contact = frappe.get_doc("Contact", contact_name)

    # Find matching email from 'Contact Email' table inside doc
    email = ""
    if contact.email_ids:
        for row in contact.email_ids:
            if row.parent == contact.name:
                email = row.email_id
                break

    # Find matching phone from 'Contact Phone' table inside doc
    phone = ""
    if contact.phone_nos:
        for row in contact.phone_nos:
            if row.parent == contact.name:
                phone = row.phone
                break

    return {
        "custom_designation": contact.get("designation"),
        "custom_department": contact.get("department"),
        "custom_branch": contact.get("custom_branch"),
        "contact_email": email,
        "contact_mobile": phone
    }