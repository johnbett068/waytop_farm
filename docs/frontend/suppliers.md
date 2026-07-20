# Supplier Management frontend

## Supplier profile

A supplier is an external organization/person approved or considered for goods/services sourcing. The frontend exposes stable supplier code, legal/display name, type, lifecycle status, preferred flag, products/services supplied, contacts, phone/email, county/address context, expected lead time, due-diligence documents and performance projection.

Preferred is an explicit reviewed designation, not an automatic award. Active means eligible for governed sourcing; inactive preserves historical quotations/orders. “Under review” is a governance condition orthogonal to active/inactive lifecycle.

## Directory and detail

The directory supports search plus type, status and county filtering. Cards prioritize supplier type, product capability, lead time, contact and rating. Detail composes profile/contact data, performance snapshot, recent purchase orders and document placeholders.

Personal/contact data is scope- and field-protected in the future contract. Email/phone fixtures use non-production/example data.

## Performance

Performance shows transparent, time-bounded projections:

- on-time deliveries;
- rejected deliveries/lines;
- average lead time;
- order accuracy;
- quality rating;
- Procurement commercial spend;
- trend direction.

Scores never become hidden supplier-selection rules. Future Reporting defines denominator, period, timezone, exclusions, data freshness and recalculation. Procurement retains source PO/delivery/inspection facts.

## Documents

Quotation, invoice, delivery note, receipt, inspection report and supplier due-diligence files are attachment placeholders only. No upload/storage exists. Future metadata includes type, version, issuer, dates, related supplier/order/delivery, access class, checksum, retention and audit actor. An invoice is matching evidence; Procurement does not post it to Accounting.
