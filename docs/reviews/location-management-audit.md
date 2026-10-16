# Location management audit

## Existing domain

`inventory.InventoryLocation` (introduced in `inventory/0001_initial`) is the
canonical ledger endpoint. Fields: UUID identity, unique stable code (50 chars),
name (160 chars), is_active, allows_saleable_stock, and created/updated timestamps.
Code and name cannot be empty; names are not unique. Model saves validate and
normalize names/codes; codes cannot change and instance deletion is prohibited.

StockPosition is unique by item/location/lot and protects its Location. Movement
lines protect source/destination Locations; adjustment requests also reference
Location. Acquisitions retain destination through their authoritative movement
line. Lots have no direct Location: a lot can span positions at multiple endpoints.
Reservations/allocations use StockPositions rather than a separate branch balance.

Receipt and movement services reject inactive Locations. Availability also
requires allows_saleable_stock. Acquire Stock originally selected all active
Locations, ordered by code; it did not filter by Supplier, Product, or saleability.
Existing movement and availability tests exercise those controls.

Documentation defines a broader ledger endpoint, including stores, staging,
transit and future branch hierarchy. The implemented model has no branch,
hierarchy, coordinates, address, or warehouse classification. A physical branch/site
can safely be configured as an endpoint, without redefining every endpoint as a
Branch or changing Production Areas. The branches app has no model/migrations;
its placeholder view references a missing template. Inventory admin is read-only.
There was no working Location management form or staff route.

Read-only local inspection found zero Locations, StockPositions, movement lines,
and adjustment requests. No existing meaning or historical relationship requires
migration. All existing migrations were applied and schema checks reported no drift.

## Implementation boundary

Inventory Locations list/add/edit exposes only Branch / Location name. No optional
fields were needed to unblock this workflow; no schema changes were made. Existing
add_inventorylocation/change_inventorylocation permissions control changes, with
inventory.view required for the screens. Internal codes are generated without
user input. Internal active/saleability defaults remain intact; editing changes
only name. Repeated create submissions reuse their generated Location identity.

Acquire Stock keeps `filter(is_active=True)`, orders by name/pk and labels choices
with names only. Supplier and Product do not affect this queryset. History displays
the existing source/destination Location relationships; receipt and StockPosition
writes still belong exclusively to the movement service.

No Branch model, hierarchy, warehouse features, new status controls, or business
records are introduced. Test and browser Locations exist only in isolated databases.

## Changed paths and verification

- `apps/inventory/forms.py`: name-only management form and name-labelled Location choices.
- `apps/inventory/location_services.py`: permission-checked create/rename operations.
- `apps/inventory/staff_views.py`: Location list/create/edit views.
- `apps/dashboard/urls.py`: `/dashboard/inventory/locations/`, `new/`, and UUID `edit/` routes.
- `templates/dashboard/inventory/locations_live.html`: Location list.
- `templates/dashboard/inventory/location_form_live.html`: create/edit form.
- `templates/dashboard/components/inventory_shortcuts.html`: Locations navigation entry.
- `templates/dashboard/inventory/history_live.html`: source/destination names.
- `apps/inventory/test_locations.py`: eight management and acquisition regression tests.

Focused Location/acquisition/Supplier tests: 30 passed. Full SQLite suite: 372 run,
359 passed, 13 skipped. PostgreSQL was not used. Browser verification on an isolated
copy created and renamed a Location, selected it in Acquire Stock, omitted Supplier,
and posted six seedlings visible at that Location in On-Hand Stock and History.
The final name input styling was also visually checked in Chrome.

Before/after migration checks: no changes detected; all existing migrations applied.
No migration was created/applied. The real database's SHA-256 remained
`00111E9CA17392260CEF260A44ABF6004FEA818C72E0FAD1F76DF5EA4F2420EB`.
No fake Locations or other test business records were written to the real database.
