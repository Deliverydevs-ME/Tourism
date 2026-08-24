# tourism/overrides/request_for_quotation.py

from erpnext.buying.doctype.request_for_quotation.request_for_quotation import (
    RequestforQuotation,
)

from tourism.request_for_quotation import get_rfq_reply_to_sender


class CustomRequestforQuotation(RequestforQuotation):
    """Overrides ERPNext's Request for Quotation so the supplier email has
    Reply-To equal to From (the outgoing system account) instead of the
    logged-in user who submitted the RFQ.
    """

    def send_email(self, data, sender, subject, message, attachments):
        # Send as the outgoing account address so From and Reply-To match.
        sender = get_rfq_reply_to_sender() or sender
        super().send_email(data, sender, subject, message, attachments)
