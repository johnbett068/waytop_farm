# Stage 1 customer accounts implementation

## Scope and existing architecture

Reused accounts.User (AbstractUser), customers.Customer, CustomerAddress and inventory.InventoryLocation. Staff authentication remains in accounts/views.py with the original login/profile/logout routes. Existing Order.customer, Order.location, contact snapshots, pricing, inventory and payment services were not changed. Public checkout remains the existing unavailable placeholder.

## Ownership and migration

Created and applied customers.0002_customer_account_and_picking_location. Its only operations add Customer.owner (nullable OneToOneField to AUTH_USER_MODEL, PROTECT, reverse customer_profile) and Customer.preferred_picking_location (nullable ForeignKey to InventoryLocation, PROTECT).

Nullability preserves unowned legacy customers and incomplete preferences. Ownership uniqueness is enforced in the database. No data migration, contact matching, historical order update or default branch assignment exists. Customer admin retains its prior contact/address editing and shows ownership as read-only. No duplicate domain models were introduced. accounts.User changed only its descriptive docstring, not its schema.

## Public account experience

- /accounts/create-account/: username/password, full name, Kenyan phone and optional email. Django password validation and hashing apply. One transaction creates a new normal User and a new Customer. No groups or permissions are assigned. New profile/location preferences are not guessed.
- /accounts/sign-in/: separate customer authentication form; only active non-staff accounts with an active owned Customer are accepted. Successful sign-in goes to My Account.
- /accounts/my-account/: authenticated ownership determines the profile. Editable buyer fields are name, phone, optional email, county, town/area, locality/landmark and preferred picking location.
- /accounts/sign-out/: CSRF-protected POST logout. Existing staff logout is unchanged.
- The public header and mobile navigation link to customer accounts; staff see their dashboard link. Sign-in links to registration; My Account provides sign-out.

CustomerAddress is reused as the active default personal-location record. The existing mandatory address_line constraint was preserved and surfaced as Locality / landmark. County and town/area remain required. The page explicitly distinguishes personal location from picking preference; it adds no delivery or tracking meaning. Customer email remains the authoritative buyer contact; profile updates do not change login username or authentication credentials.

Picking choices are existing locations with is_active=True and allows_saleable_stock=True. Current real rows Bomet and Bondet meet those existing rules. The selector begins blank. Labels display names, not internal identifiers. Invalid/inactive/non-saleable selections fail validation, and eligibility is rechecked in the transaction before saving. An empty configuration shows an explanatory message.

Completeness is calculated by missing_profile_fields(user) from active ownership, name, valid phone, an active default personal location and eligible preferred picking location. Email is optional. No completeness boolean is stored.

## Security

Profile routes contain no customer ID and ignore submitted owner/customer/address IDs. Customer and address writes are atomic, locked and scoped through the authenticated owner. Missing/inactive profiles are denied rather than created silently. Registration rejects privilege fields by using an explicit form whitelist. Existing dashboard and POS staff checks remain unchanged. No automatic linking by matching name, email, phone or username was introduced.

## Verification

93 account/customer/POS/booking/navigation regression tests passed. Two additional tests passed for database-level ownership uniqueness and migration preservation of a legacy User, Customer and CustomerAddress with matching email but no authoritative ownership.

One isolated Chrome browser test passed: home navigation, registration, no default picking location, complete profile save/reload, Bomet selection, logout/login, customer dashboard denial and staff login/dashboard success. Verified 1440x900 desktop and 390x844 mobile, no horizontal overflow and no JavaScript page errors. Screenshots are .tmp/customer-stage1/profile-desktop.png and profile-mobile.png. All test accounts/locations were confined to Django test databases; none were created in the real database.

Before implementation, makemigrations --check reported No changes detected; all existing migrations were applied. After implementation and migration, makemigrations --check again reported No changes detected, showmigrations showed the new migration applied with all prior migrations still applied, and Django system checks passed.

## Real database preservation

Before migration, SQLite backup and SHA-256 were recorded at .tmp/customer-stage1/before.sqlite3 and before.sha256. Original-column row counts and fingerprints were recorded for every existing table in before.json.

After migration, all original values and row counts matched across 56 tables (excluding django_migrations, which gained the expected migration record). The comparison includes all old Customer columns and all existing authentication, order, payment, product, stock, movement, reservation and allocation records. No customer was assigned ownership or a preferred branch.

Important unchanged counts: Users 1; Customers 0; CustomerAddress 0; InventoryLocation 2; Products 2; Orders 6; Payments 6; StockLots 3; StockPositions 3. Legacy non-empty Customer preservation was additionally verified by the migration test.

Database SHA-256 before: 0a397ec96c32ed191b6615325e71890c25909827fe8e1fe5ca518a5904fbc17e
Database SHA-256 after: b3826c947a8a96bdf23c5b2b0bb7f05378ea92fbb107142089335fbb4c17f19b

The physical database changed as expected for the approved schema migration. Existing business data did not change. The detailed comparison is .tmp/customer-stage1/preservation.json.

## Files changed or added

- apps/accounts/models.py (identity docstring)
- apps/accounts/urls.py
- apps/accounts/customer_forms.py
- apps/accounts/customer_views.py
- apps/accounts/test_customer_accounts.py
- apps/accounts/test_customer_browser.py
- apps/customers/models.py
- apps/customers/admin.py
- apps/customers/accounts.py
- apps/customers/test_account_migration.py
- apps/customers/migrations/0002_customer_account_and_picking_location.py
- templates/accounts/customer_base.html
- templates/accounts/customer_register.html
- templates/accounts/customer_login.html
- templates/accounts/customer_profile.html
- templates/accounts/customer_field.html
- templates/includes/navbar.html
- static/css/customer-account.css
- docs/reviews/customer-accounts-stage1.md
- db.sqlite3 (approved additive migration only)

## Remaining scope

No unresolved Stage 1 blocker. The address-line requirement is retained rather than silently relaxed. No public-collection eligibility flag was added; the approved existing active/saleable semantics are used.

Stage 2 was NOT implemented: no public checkout submission, order creation, public payment, reservation/allocation flow, order history, delivery, driver/route/GPS/shipment tracking or proof of delivery. Existing domain services retain their current behavior until a separately approved Stage 2 changes the public ordering boundary. Existing architecture documents describing guest-capable Ecommerce should be read with this new account foundation and the separately approved future account-required checkout requirement in mind; the old creation service has not been changed during Stage 1.
