# Category pages specification

## 1. Purpose

Let visitors understand WayTop's major crop groups and browse a focused product collection.

## 2. Target users

Public customers and growers who know the type of crop they need.

## 3. Business rules

- A public product belongs to a public category.
- Category counts reflect visible products, not unpublished inventory records.
- A valid category may temporarily contain no products due to seasonality or catalog preparation.
- Category browsing never reserves branch inventory.

## 4. Displayed data

Category name, slug, description, representative visual and visible-product count. Category Detail also displays the shared product fields documented for Shop.

## 5. User actions

Open a category from the listing, filter/sort/page within populated categories, open a product, return through breadcrumbs, or explore the broader catalog when empty.

## 6. Page states

Populated listing, no categories, populated category, category with no products, loading/filter empty/error states for populated categories, offline and 404 for an unknown slug.

## 7. Reusable components

Category card, catalog layout, product card, breadcrumbs, filters, pagination and global page states.

## 8. Future models

`Category` with name, slug, description, image, display order, active flag and parent relationship if later justified; `Product` and catalog visibility records.

## 9. Permissions

Public read access. Catalog managers create/edit/order categories; only privileged staff archive them. Products and historical sales must not be deleted through category management.

## 10. Backend contract

- Views: `categories`, `category`
- URLs: `/products/categories/` and `/products/category/<slug>/`
- Methods: `GET`
- Response: visible categories or one category plus a paginated product read collection
- Validation: active slug; unknown/non-public categories return 404
- Service: future `CategoryCatalogService`
- Side effects: none

## 11. Future integrations

Catalog administration, search facets, seasonal merchandising and category SEO metadata.

## 12. Acceptance criteria

Responsive, semantic category cards, meaningful empty state, correct breadcrumbs, shared catalog controls, keyboard accessibility, realistic data and documented contract.
