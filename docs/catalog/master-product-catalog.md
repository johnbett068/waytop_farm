# WayTop Farm Master Product Catalog

Status: **Approved frontend source of truth — mock commercial values require business confirmation**  
Catalog version: `2026.07.15`  
Scope: twelve authentic nursery products selected for the current WayTop discovery experience.

This document governs every product identity used by the homepage, Shop, Product Detail, Category, Search and all future Wishlist, Cart, Checkout, POS, Inventory and Reporting features. Pages may select or arrange catalog products, but must never define a product independently.

## Governance rules

### Product naming

- Use the commercial cultivar, hybrid or species name in the product name.
- Preserve breeder notation such as `F1` and official cultivar capitalization.
- Do not publish generic names such as “Tomato,” “Onion” or “Cabbage.”
- For species sold without a named cultivar, use the accepted botanical species, for example `Grevillea robusta`.
- Common market terminology may appear in descriptions, but must not replace the governed identity.
- `Fordhook Giant` is Swiss chard, not true spinach; the catalog uses the botanically honest name.
- `Gloria Star F1` is the supported Kenya Seed cultivar name; it replaces the ambiguous `Gloria F1` label.

### Category conventions

| Slug | Public name | Definition |
|---|---|---|
| `vegetable-seedlings` | Vegetable seedlings | Nursery-raised leafy, brassica, onion-family and fruiting vegetable transplants |
| `fruit-seedlings` | Fruit seedlings | Fruit crops sold as plugs, vines, shrubs or small fruiting plants, excluding orchard trees |
| `tree-seedlings` | Tree seedlings | Grafted orchard trees and seed-propagated agroforestry/indigenous tree species |
| `herbs-ornamentals` | Herbs & ornamentals | Reserved valid category; no approved products in this catalog version |

Watermelon is grouped under Fruit seedlings for customer discovery because WayTop sells a transplant, although botanically and agronomically it is a cucurbit vegetable crop. This merchandising category must not replace crop-family data in the future database.

### Image conventions

- Every product has one individual lowercase kebab-case WebP path.
- Product images live under `static/products/<group>/`, matching their governed `products/<group>/<filename>.webp` static path.
- Sprites, unrelated stock images, reused logos and generic placeholders are prohibited.
- Current generated mock photographs are marked **Replace Before Production**. Replacement photographs must show the named seedling or planting material, use truthful nursery conditions, contain no text/watermarks and be approved for usage rights and botanical accuracy.
- Recommended production capture: landscape or square, at least 1,200 px on the shortest edge, sRGB WebP, consistent natural light, clean nursery background.

### Commercial-value conventions

- All ranges are mock retail ranges in Kenyan shillings and are not quotations.
- A price is meaningless without its unit of sale.
- Final prices may be branch- and effective-date-specific and belong in future price-list records, not permanently on `Product`.
- Nursery availability is a planning classification, not a live stock quantity or promise.

## Approved products

### WTP-VEG-001 — Anna F1 Tomato

- **Product Name:** Anna F1 Tomato
- **Variety:** Anna F1
- **Category:** Vegetable seedlings
- **Product Type:** Fruiting vegetable transplant; indeterminate greenhouse tomato
- **Short Description:** Vigorous, hardened tomato seedlings for greenhouse production and carefully managed open-field systems.
- **Unit of Sale:** Tray of 128 seedlings
- **Typical Price Range (Mock):** KES 2,300–2,900 per tray
- **Growing Season:** Year-round with protected production or reliable irrigation; avoid severe cold and prolonged heavy rain.
- **Days to Maturity:** Approximately 90–120 days after transplanting, dependent on environment and management.
- **Recommended Growing Regions:** Cool and moderate Kenyan highland greenhouse zones; site assessment required for open field.
- **Nursery Availability:** Regular batch; advance booking recommended for commercial quantities.
- **Image Filename:** `products/vegetables/anna-f1-tomato.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-VEG-001`; cultivar must remain distinct from Rio Grande/Kilele; requires crop-system attribute and batch traceability.

### WTP-VEG-002 — California Wonder Capsicum

- **Product Name:** California Wonder Capsicum
- **Variety:** California Wonder
- **Category:** Vegetable seedlings
- **Product Type:** Fruiting vegetable transplant; open-pollinated sweet pepper
- **Short Description:** Hardy, blocky sweet-pepper seedlings suitable for open-field and protected production.
- **Unit of Sale:** Tray of 128 seedlings
- **Typical Price Range (Mock):** KES 2,500–3,200 per tray
- **Growing Season:** Warm periods with dependable irrigation and protection from waterlogging/cold stress.
- **Days to Maturity:** About 75–90 days after transplanting.
- **Recommended Growing Regions:** Warm mid-altitude areas and irrigated highlands with suitable temperatures.
- **Nursery Availability:** Regular batch.
- **Image Filename:** `products/vegetables/california-wonder-capsicum.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-VEG-002`; store OPV status; do not create separate “green” and “red” products because fruit colour changes with maturity.

### WTP-VEG-003 — Gloria Star F1 Cabbage

- **Product Name:** Gloria Star F1 Cabbage
- **Variety:** Gloria Star F1
- **Category:** Vegetable seedlings
- **Product Type:** Brassica transplant; hybrid heading cabbage
- **Short Description:** Uniform, compact-heading cabbage seedlings for productive cool-season fields.
- **Unit of Sale:** Tray of 128 seedlings
- **Typical Price Range (Mock):** KES 1,700–2,200 per tray
- **Growing Season:** Cooler seasons with dependable moisture.
- **Days to Maturity:** 75–85 days after transplanting.
- **Recommended Growing Regions:** Cool highlands including suitable areas of Bomet, Kericho, Nakuru and Nyandarua.
- **Nursery Availability:** Seasonal regular batch; may become limited during peak demand.
- **Image Filename:** `products/vegetables/gloria-star-f1-cabbage.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-VEG-003`; breeder cultivar is `Gloria Star F1`; retain hybrid flag and head-crop specifications.

### WTP-VEG-004 — Fordhook Giant Swiss Chard

- **Product Name:** Fordhook Giant Swiss Chard
- **Variety:** Fordhook Giant
- **Category:** Vegetable seedlings
- **Product Type:** Leafy vegetable transplant; Swiss chard (`Beta vulgaris`)
- **Short Description:** Heat-tolerant leafy seedlings with large dark-green leaves for repeated harvesting.
- **Unit of Sale:** Tray of 128 seedlings
- **Typical Price Range (Mock):** KES 1,400–1,900 per tray
- **Growing Season:** Most of the year with fertile soil and reliable moisture.
- **Days to Maturity:** Approximately 60–70 days after transplanting.
- **Recommended Growing Regions:** Widely adaptable Kenyan production zones with adequate water.
- **Nursery Availability:** Regular batch.
- **Image Filename:** `products/vegetables/fordhook-giant-swiss-chard.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-VEG-004`; search synonyms may include “spinach,” but the canonical crop is Swiss chard.

### WTP-VEG-005 — Improved Sukuma Wiki

- **Product Name:** Improved Sukuma Wiki
- **Variety:** Thousand Headed
- **Category:** Vegetable seedlings
- **Product Type:** Leafy vegetable transplant; collard/kale market class
- **Short Description:** Hardy sukuma wiki seedlings for steady household and commercial leaf production.
- **Unit of Sale:** Tray of 128 seedlings
- **Typical Price Range (Mock):** KES 1,200–1,700 per tray
- **Growing Season:** Year-round where irrigation or reliable rainfall is available.
- **Days to Maturity:** Approximately 45–60 days to first leaf harvest.
- **Recommended Growing Regions:** Most Kenyan production zones with locally appropriate moisture and pest management.
- **Nursery Availability:** Regular batch.
- **Image Filename:** `products/vegetables/improved-sukuma-wiki.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-VEG-005`; keep public product name and cultivar separate; repeated-harvest crop.

### WTP-VEG-006 — Red Creole Onion Seedlings

- **Product Name:** Red Creole Onion Seedlings
- **Variety:** Red Creole
- **Category:** Vegetable seedlings
- **Product Type:** Onion-family transplant; short-day red bulb onion
- **Short Description:** Hardened red-onion seedlings ready for careful shallow transplanting.
- **Unit of Sale:** Bundle of 100 seedlings
- **Typical Price Range (Mock):** KES 700–1,000 per bundle
- **Growing Season:** Preferably dry periods with controlled irrigation for bulb development and curing.
- **Days to Maturity:** Approximately 90–120 days after transplanting.
- **Recommended Growing Regions:** Warm, relatively dry irrigated onion-growing zones; local day length and disease pressure must be assessed.
- **Nursery Availability:** Seasonal batch; commonly limited at peak planting time.
- **Image Filename:** `products/vegetables/red-creole-onion-seedlings.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-VEG-006`; bundle quantity differs from tray products; quantity/pack-size validation is required.

### WTP-FRT-001 — Sukari F1 Watermelon

- **Product Name:** Sukari F1 Watermelon
- **Variety:** Sukari F1
- **Category:** Fruit seedlings
- **Product Type:** Cucurbit plug seedling; hybrid watermelon
- **Short Description:** Carefully raised watermelon plugs for warm, well-drained production fields.
- **Unit of Sale:** Individual plug seedling
- **Typical Price Range (Mock):** KES 50–90 per seedling
- **Growing Season:** Warm, dry periods with irrigation; do not transplant into cold or waterlogged soil.
- **Days to Maturity:** Approximately 75–90 days after transplanting.
- **Recommended Growing Regions:** Warm low- and mid-altitude Kenyan zones with well-drained soils.
- **Nursery Availability:** Pre-order batch only because cucurbit seedlings have a narrow transplant window.
- **Image Filename:** `products/fruits/sukari-f1-watermelon.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-FRT-001`; enforce pre-order/dispatch-age rules and careful handling instructions.

### WTP-FRT-002 — Red Oratia Tree Tomato

- **Product Name:** Red Oratia Tree Tomato
- **Variety:** Red Oratia
- **Category:** Fruit seedlings
- **Product Type:** Tamarillo fruit seedling (`Solanum betaceum`)
- **Short Description:** Selected tree-tomato seedlings for cool, sheltered and well-drained highland sites.
- **Unit of Sale:** Individual nursery seedling
- **Typical Price Range (Mock):** KES 140–220 per seedling
- **Growing Season:** Onset of reliable rains or any suitable period with assured irrigation.
- **Days to Maturity:** First meaningful fruiting commonly begins around 12–24 months; planting material and management cause major variation.
- **Recommended Growing Regions:** Kenyan highlands around 1,500–3,000 m, including suitable parts of Rift Valley and Central Kenya.
- **Nursery Availability:** Regular small batch.
- **Image Filename:** `products/fruits/red-oratia-tree-tomato.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-FRT-002`; distinguish seedling, cutting and grafted planting material as variants, not vague product claims.

### WTP-FRT-003 — KPF 12 Passion Fruit

- **Product Name:** KPF 12 Passion Fruit
- **Variety:** KPF 12
- **Category:** Fruit seedlings
- **Product Type:** Passion-fruit vine seedling; Kenyan-developed hybrid
- **Short Description:** Vigorous passion-fruit seedlings for prepared trellises and clean production sites.
- **Unit of Sale:** Individual nursery seedling
- **Typical Price Range (Mock):** KES 120–200 per seedling
- **Growing Season:** Onset of rains or with assured irrigation after site and disease-risk assessment.
- **Days to Maturity:** Approximately 8–12 months to first commercial harvest under suitable management.
- **Recommended Growing Regions:** Suitable Kenyan highland and mid-altitude passion-fruit zones; site-specific advice required.
- **Nursery Availability:** Pre-order batch.
- **Image Filename:** `products/fruits/kpf-12-passion-fruit.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-FRT-003`; trellis requirement and planting-material health/traceability are mandatory attributes.

### WTP-TRE-001 — Hass Avocado

- **Product Name:** Hass Avocado
- **Variety:** Hass
- **Category:** Tree seedlings
- **Product Type:** Grafted orchard tree
- **Short Description:** Grafted Hass avocado trees supplied after site-suitability and pollination planning.
- **Unit of Sale:** Individual grafted seedling
- **Typical Price Range (Mock):** KES 300–500 per seedling
- **Growing Season:** Onset of reliable rains or any period with assured irrigation and drainage.
- **Days to Maturity:** Perennial; grafted trees commonly begin bearing around 3–4 years, depending on site and management.
- **Recommended Growing Regions:** Suitable Kenyan avocado zones; confirm altitude, frost risk, drainage, water and rootstock suitability.
- **Nursery Availability:** Regular grafted batch; commercial orchard orders require advance booking.
- **Image Filename:** `products/trees/hass-avocado.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-TRE-001`; graft/rootstock identity, source nursery and traceability must be recorded; never represent a seed-grown plant as true-to-type Hass.

### WTP-TRE-002 — Grevillea Robusta

- **Product Name:** Grevillea Robusta
- **Variety:** `Grevillea robusta` (species)
- **Category:** Tree seedlings
- **Product Type:** Seed-propagated agroforestry tree
- **Short Description:** Multipurpose farm-tree seedlings for boundaries, timber, shade management and wind protection.
- **Unit of Sale:** Individual nursery seedling
- **Typical Price Range (Mock):** KES 35–80 per seedling
- **Growing Season:** Plant at the onset of reliable rains.
- **Days to Maturity:** Perennial; timber objective typically 15–20 years on suitable sites.
- **Recommended Growing Regions:** About 850–2,500 m, especially well-drained coffee/tea and highland farming zones.
- **Nursery Availability:** Regular forestry batch.
- **Image Filename:** `products/trees/grevillea-robusta.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-TRE-002`; scientific name, seed provenance and intended-use guidance are required; crop-shading risk must be disclosed.

### WTP-TRE-003 — Croton Megalocarpus

- **Product Name:** Croton Megalocarpus
- **Variety:** `Croton megalocarpus` (species)
- **Category:** Tree seedlings
- **Product Type:** Indigenous multipurpose tree seedling
- **Short Description:** Indigenous farm-tree seedlings for biodiversity, shade, wind protection and long-term landscape value.
- **Unit of Sale:** Individual nursery seedling
- **Typical Price Range (Mock):** KES 40–90 per seedling
- **Growing Season:** Plant at the onset of dependable long or short rains.
- **Days to Maturity:** Perennial; no short annual-crop maturity value applies.
- **Recommended Growing Regions:** Suitable mid- and high-altitude Kenyan sites with well-drained soils.
- **Nursery Availability:** Seasonal forestry batch; temporarily unavailable in the current mock projection.
- **Image Filename:** `products/trees/croton-megalocarpus.webp` — **Replace Before Production**
- **Future Database Notes:** SKU `WTP-TRE-003`; scientific name and seed provenance are required; retain indigenous-species classification.

## Future database mapping

The catalog will seed normalized records; it must not become one oversized table.

| Catalog concept | Future model/field |
|---|---|
| Governed identity, slug, description | `Product` |
| Cultivar/hybrid/species and planting-material type | `ProductVariant` and controlled attributes |
| Vegetable/Fruit/Tree grouping | `Category` |
| Tray, bundle or individual seedling | `UnitOfMeasure` and `PackDefinition` |
| Typical mock range | Documentation only; final amount belongs to `PriceList`/`ProductPrice` |
| Image path and approval | `ProductImage` with alt text, order, rights and approval status |
| Season, regions and crop guidance | Published `GrowingProfile`/`PlantingGuide` records |
| Nursery availability | `BranchStock` read projection derived from immutable inventory movements |
| SKU | Immutable business identifier, unique database constraint |
| Seed/graft provenance | Lot/batch traceability records |

Import requirements:

1. Use stable SKU and slug as idempotent natural keys during seed import.
2. Use `Decimal` for final prices; never import display-formatted strings as numeric data.
3. Create price-list rows with currency, branch/effective dates and unit.
4. Create no opening stock without a documented inventory-opening movement.
5. Validate referenced image files and approval status.
6. Preserve historical product references by archiving products instead of deleting them.
7. Require qualified approval for growing guides and certification/health claims.

## Production image replacement shot list

The current individual WebPs are generated mock media, not verified product evidence. Commission or capture these exact replacements before production:

| Filename | Required photograph |
|---|---|
| `anna-f1-tomato.webp` | Labelled Anna F1 tray at WayTop, showing uniform 4–5-week seedlings and tray size |
| `california-wonder-capsicum.webp` | Labelled California Wonder tray with characteristic healthy pepper foliage |
| `gloria-star-f1-cabbage.webp` | Labelled Gloria Star F1 tray with uniform hardened brassica seedlings |
| `fordhook-giant-swiss-chard.webp` | Labelled Fordhook Giant tray showing true Swiss-chard leaf form |
| `improved-sukuma-wiki.webp` | Labelled Thousand Headed sukuma wiki tray at transplant stage |
| `red-creole-onion-seedlings.webp` | Counted Red Creole bundle or nursery bed with a visible scale reference |
| `sukari-f1-watermelon.webp` | Labelled Sukari F1 plug tray within the safe transplant-age window |
| `red-oratia-tree-tomato.webp` | Labelled Red Oratia planting material; show whether seed-grown or grafted |
| `kpf-12-passion-fruit.webp` | Traceable KPF 12 nursery seedlings with healthy vine and root container visible |
| `hass-avocado.webp` | Traceable grafted Hass tree with graft union, rootstock label and full container visible |
| `grevillea-robusta.webp` | Verified Grevillea robusta nursery batch from recorded seed provenance |
| `croton-megalocarpus.webp` | Verified Croton megalocarpus seedling—not ornamental croton (`Codiaeum variegatum`) |

Each replacement must record photographer/owner, capture date, product batch, approval status and usage rights.

## Authoritative verification references

- [KALRO tomato training manual](https://keep.kalro.org/appfiles/media/vc_files/tomato-training-manual-8-12-20.pdf): identifies Anna F1 for greenhouse production and Rio Grande/Kilele F1 for open field.
- [Royal Seed California Wonder](https://royalseed.biz/sweet-peppers/california-wonder/): OPV identity and about 75 days from transplanting.
- [Kenya Seed cabbage varieties](https://kenyaseed.com/products/product-info/horticulture-variety-tables/cabbages): Gloria Star F1 and Pruktor F1 cultivar identities and maturity ranges.
- [Royal Seed Fordhook Giant](https://royalseed.biz/leafies/fordhook-giant/): identifies the crop as Swiss chard and gives a 60–70-day maturity range.
- [AFA Tree Tomato Growers Manual](https://www.afa.go.ke/download/2994/?tmstv=1744263290): Red Oratia identity and Kenyan highland requirements.
- [KALRO avocado varieties](https://agrificsapp.kalro.org/file_uploads/Avocado%20varieties.pdf): Hass/Fuerte identities and Kenyan production context.
- [KEFRI Grevillea robusta guide](https://kefri.org/assets/publications/extension/Grevillea%20Robust%20in%20Kenya.pdf): ecological range, propagation and agroforestry uses.
- [KEFRI dryland tree survival guide](https://www.kefri.org/JICA/PDF/Guidelines/IMPROVING%20TREE%20SURVIVAL%20IN%20THE%20DRYLANDS%20OF%20KENYA.pdf): Croton megalocarpus planting context.

## Approval boundary

Variety authenticity has been checked against the references above. Mock prices, WayTop branch availability, contact details, generated photographs and farm-specific growing recommendations still require WayTop management and qualified agronomic approval before production.
