# Homepage specification

## 1. Purpose

The homepage introduces WayTop Farm & Nurseries, establishes trust and helps a visitor discover the nursery's seedling range or contact the team. It is the public entry point for customers, farmers, institutions and other growers.

## 2. Target users

- Public visitors
- Prospective and returning customers
- Farmers and institutional buyers researching seedlings

Authentication is not required.

## 3. Business rules

- The centralized catalog groups products into categories.
- Homepage products are curated and do not represent the complete catalog.
- Price is displayed in Kenyan shillings and includes the sales unit.
- Availability is branch-specific and must be confirmed before an order is accepted.
- Nursery certification or performance claims must be supported by current business records before production publication.
- Trust content is rendered once through concise Hero chips and showcase annotations; a second trust section must not duplicate it immediately below.
- “Quality nursery practices” remains the public wording until a current certification record authorizes a stronger certification claim.
- The Phase 1A enquiry action initiates a phone call; ecommerce ordering is intentionally unavailable until its milestone is complete.

## 4. Displayed data

| Data | Type and format | Relationship |
|---|---|---|
| Business name and location | Text | Organization and primary branch |
| Contact telephone | Kenyan E.164-compatible telephone link | Organization contact channel |
| Category name, slug and description | Text | Category has many products |
| Product name and description | Text | Product belongs to category |
| Category label | Text | Product category |
| Price | Decimal rendered as `KES 2,560` | Product/price list |
| Sales unit | Text, e.g. `tray of 128` | Product unit of measure |
| Availability message | Status text | Product availability at branch |
| Trust statements and statistics | Text/integer | Organization evidence source |
| Approved testimonial attribution and review | Text | Future customer review; not rendered until evidence and publishing approval exist |

Phase 1A uses realistic in-view mock collections. They are not persisted.

## 5. User actions

- Navigate to homepage sections using desktop or mobile navigation.
- Skip directly to main content using the keyboard skip link.
- Call the nursery through telephone links.
- Explore seedling categories and featured seedlings.
- Open a featured product detail page to review its full planting and availability specification.
- Return home from branded error states.

Telephone actions rely on device support. The page has no form validation or destructive actions.

## 6. Page states

- **Success:** full marketing content and mock catalog collections render.
- **Loading:** reusable loading component is available for future asynchronous sections.
- **Empty:** categories and featured products render contextual empty states when collections are empty.
- **Server error:** branded HTTP 500 template.
- **Offline:** global live-region banner appears when the browser reports a lost connection.
- **Permission denied:** reusable component and branded HTTP 403 template; not expected on the public homepage.
- **Not found:** branded HTTP 404 template.
- **Partial availability:** individual product availability messages communicate limited stock.

## 7. Reusable components

- Application header, top bar, mobile drawer and footer
- Responsive horizontal brand lockup with SVG-first delivery and WebP fallback
- Editorial Hero with one responsive nursery showcase, operational annotations and compact trust chips
- Category photography supplied through category mock-data fields rather than CSS-specific class names
- Buttons, cards, badges, section headings and availability status
- Loading, empty, error, offline and permission-denied states
- Branded 403, 404 and 500 pages
- Responsive grid and container primitives

## 8. Future models

- `OrganizationProfile`
- `Branch`
- `ContactChannel`
- `Category`
- `Product`
- `ProductVariant`
- `UnitOfMeasure`
- `PriceList` and `ProductPrice`
- `BranchStock` (read projection)
- `Review`
- `HomepageFeature` or curated merchandising configuration

Final model boundaries will be validated against Shop and Product Detail specifications before backend implementation.

## 9. Permissions

- Anyone may view the homepage and use contact actions.
- Catalog managers may later select featured categories and products.
- Branch inventory staff manage availability through inventory workflows, never through the homepage.
- Authorized content staff may manage approved marketing copy and testimonials.
- No homepage action creates, edits, deletes or approves business records.

## 10. Backend contract

- **Django view:** `apps.core.views.home`
- **URL:** `/`, named `core:home`
- **Method:** `GET`
- **Request:** no body; future branch preference may come from session or query string.
- **Template:** `core/home.html`
- **Context:** `categories[]` and `featured_products[]` with the fields documented above.
- **Validation:** only active, web-visible and correctly priced products may be returned in production.
- **Business service:** future `HomepageCatalogService` provides curated, branch-aware read data.
- **Side effects:** none. Homepage access must never reserve or deduct inventory.
- **Caching:** future response/fragment caching must vary when branch-specific availability is introduced.

## 11. Future integrations

- Catalog and branch inventory
- Product search and merchandising
- Customer reviews
- Analytics with consent controls
- Content management
- Ecommerce cart and product detail routes
- WhatsApp or managed enquiry channel after business contact details are approved

## 12. Acceptance criteria

- Responsive from small mobile screens through desktop.
- Keyboard-accessible navigation, skip link and focus management.
- Semantic landmarks, headings and meaningful labels.
- Reusable components and design tokens used.
- Realistic Kenyan product, price and location data used.
- Required applicable states implemented.
- No links to unbuilt pages.
- Page specification, workflow and backend contract complete.
- Automated checks cover rendering, context, broken legacy links and the 404 page.

## 13. Homepage polish design decisions

- The established “Healthy Seedlings for Healthy Harvests” headline remains because it is concise, memorable and connects nursery quality to the customer's outcome.
- The selected Hero is a trust-led editorial split. It pairs a concise outcome-focused promise with one authentic nursery visual rather than using either a full-width background or ecommerce widgets.
- Hero actions use the primary brand action and a restrained contact action. This clarifies priority while retaining telephone support for customers who are not ready to browse independently.
- The navbar remains a light surface for logo legibility, but reduced vertical space, a subtle brand border and compact top bar make it flow directly into the Hero.
- Trust information uses three compact chips beneath the actions, while the nursery showcase carries restrained location and product-range annotations. These replace the former full-width trust rail and make the composition denser without adding unsupported claims.
- The branded eyebrow and emphasized first paragraph mention establish ownership immediately; expanded token-based green glows warm the editorial whitespace without adding decorative content.
- The global container already caps content at 72rem (1152px), which is tighter than the proposed 1280–1440px range. It was retained because it prevents wide-screen drift more effectively and remains shared across the application shell.
- The final whitespace audit reduced oversized section padding instead of adding duplicate badges or marketing claims. Product discovery now begins sooner, and a subtle token-based agricultural surface and one-pixel connector provide continuity from the Hero into the catalog.
- The final homepage art direction carries the editorial quality beyond the Hero: categories use an asymmetric photographic mosaic, product merchandising sits on a softly lit gallery surface, the WayTop rationale becomes a high-contrast green chapter, and the ordering journey uses oversized step numerals. These treatments preserve the same content, routes and backend contract while avoiding a generic repeated-card rhythm.
- Two dedicated decorative edge ribbons span the homepage header and Hero. Each combines a 72–120px blue/sage light field, blurred translucent layers and three curved SVG strokes, then fades before product discovery. They are presentation-only, remain outside document semantics and sit behind all interactive and textual content.
- The edge ribbons use a deliberately stronger 80–128px light field and higher-contrast curves after rendered review. The navbar surface is one tone deeper—mist blue through pale green—so the header reads as a distinct premium layer instead of merging into the Hero.
- Primary navigation derives its active state from Django's resolved URL name. Home is therefore active only on the homepage, with the same contract applied to desktop and mobile navigation.
- The sticky header uses a translucent surface, restrained shadow and backdrop blur; search is a circular control and the account action retains clear visual priority.
- The navigation is an intentionally visible premium surface: layered warm-white, mist-blue, sage and cream lighting gives it depth before scrolling, while large blurred mesh ribbons enter from both outer edges and fade toward the content. The logo sits on a glass highlight, navigation uses a gradient active marker, and the green gradient CTA is the strongest control. The sticky state increases glass blur, saturation and elevation without changing structure.
- Section rhythm intentionally varies: Trust is compact, Categories and Why WayTop use warm agricultural surfaces, while Products and How It Works use clear white reading surfaces.
- Category photography is specific to vegetable, fruit, tree, and herb/ornamental nursery stock. The previous approach of cropping the same Hero image four times was rejected because it concealed category differences.
- Featured product photography was retained after review because it already depicts the correct crop and nursery stage.

## 14. Rejected approaches

- Unsupported “certified” language was replaced with “nursery-raised.” Certification wording may return only after current documentary evidence and content approval exist.
- Mock testimonials, invented customer identities and unsupported volume/experience statistics are not rendered. Fabricated social proof would damage trust and create legal and reputational risk.
- Full-width photography, the catalog-card prototype and a purely abstract image-free direction were rejected for the reasons recorded in `docs/frontend/hero-concepts.md`.
- Scroll-parallax and JavaScript reveal effects were rejected for this sprint. They add motion and execution cost without improving the discovery task.
- Decorative waves between every section were rejected in favor of restrained surface and spacing changes.

## 15. Accessibility and performance notes

- Hero nursery and category photography have subject-specific alternative text.
- Decorative inline icons are excluded from the accessibility tree; the adjacent text carries their meaning.
- Existing keyboard focus treatment remains visible across navigation, cards and calls to action.
- Motion is limited to short hover feedback and a gentle showcase float; all motion is neutralized when reduced motion is requested.
- The primary Hero nursery image loads normally because it is visible above the fold; supporting product and category images are lazy-loaded.
- Category and product images are lazy-loaded below the fold. Category `srcset` and `sizes` attributes prevent desktop source files from being downloaded unnecessarily on smaller screens.
- All new photography is optimized WebP. Presentation colors and shadows are referenced through design tokens.
- The approved phone number is stored once in Django settings and exposed globally through `apps.core.context_processors.business_contact` as display and telephone-URI forms.

## 16. Future recommendations

- Replace generated nursery photography with commissioned WayTop photography when a consistent shoot is available, preserving the current aspect ratios and crop requirements.
- Add approved customer stories only through a future evidence-backed content workflow with consent, attribution and publication status.
- Self-host the approved brand font files if external font delivery becomes a measurable performance or privacy concern.
