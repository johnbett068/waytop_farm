# Product search specification

## 1. Purpose

Help visitors locate seedlings quickly when they know a crop or variety name.

## 2. Target users

Public customers, including mobile users who need quick catalog access.

## 3. Business rules

- Search matches public product names and varieties in Phase 1B.
- Empty queries represent all visible products; unsupported terms return a helpful empty state.
- Search results preserve stock visibility but do not promise or reserve quantities.
- Sorting and filtering operate on the current result set.

## 4. Displayed data

Query text, result count, shared product-card fields, filter facets, selected filters, sort order and page number.

## 5. User actions

Enter/submit a query, refine results, clear filters, sort, paginate, open a product and use browser navigation. Submission is keyboard accessible and does not reload during the mock implementation.

## 6. Page states

Initial all-products guidance, matching results, empty search results, skeleton loading, simulated error, offline, partial availability and 404 for invalid downstream links.

## 7. Reusable components

Search form, catalog result count, product card, filters, sort, pagination, skeleton and global empty/error states.

## 8. Future models

Uses catalog models; optional future `SearchSynonym`, `SearchQueryEvent` and curated redirect models require privacy and operational justification.

## 9. Permissions

Public read access. Search configuration and synonyms require catalog-manager permission. Query analytics require approved privacy controls.

## 10. Backend contract

- View: `apps.products.views.search`
- URL: `/products/search/`, `products:search`
- Method/query: `GET ?q=&category=&status=&max_price=&sort=&page=&branch=`
- Response: normalized query, paginated read models, facets and total count
- Validation: length limits, allowlisted facets/sort, safe escaping and bounded page size
- Service: future `CatalogSearchService`; PostgreSQL search initially, external search only if justified
- Side effects: none beyond optional consented analytics

## 11. Future integrations

Synonyms for Kenyan crop terminology, typo tolerance, search suggestions, branch availability and analytics.

## 12. Acceptance criteria

Search works by crop/variety, empty results are constructive, filters/sort/pagination compose correctly, accessible labels/live counts exist, states are complete and no business mutation occurs.
