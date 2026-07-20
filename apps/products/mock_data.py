"""Executable mirror of docs/catalog/master-product-catalog.md."""

CATALOG_VERSION = "2026.07.15"

CATEGORIES = [
    {"slug": "vegetable-seedlings", "name": "Vegetable seedlings", "description": "Hardened seedlings for kitchen gardens and commercial vegetable production.", "count": 6, "image_variant": "vegetable", "image_480": "images/home/categories/vegetable-seedlings-480.webp", "image_800": "images/home/categories/vegetable-seedlings-800.webp", "image_alt": "Mixed tomato, capsicum and cabbage seedlings in nursery trays"},
    {"slug": "fruit-seedlings", "name": "Fruit seedlings", "description": "Nursery-raised fruit plugs, vines and small fruiting plants selected for Kenyan growing regions.", "count": 3, "image_variant": "fruit", "image_480": "images/home/categories/fruit-seedlings-480.webp", "image_800": "images/home/categories/fruit-seedlings-800.webp", "image_alt": "Grafted fruit seedlings arranged in black nursery bags"},
    {"slug": "tree-seedlings", "name": "Tree seedlings", "description": "Grafted orchard, agroforestry and indigenous trees for productive, resilient farms.", "count": 3, "image_variant": "tree", "image_480": "images/home/categories/tree-seedlings-480.webp", "image_800": "images/home/categories/tree-seedlings-800.webp", "image_alt": "Rows of agroforestry tree seedlings under nursery shade netting"},
    {"slug": "herbs-ornamentals", "name": "Herbs & ornamentals", "description": "Useful herbs and flowering plants for homes and landscapes.", "count": 0, "image_variant": "ornamental", "image_480": "images/home/categories/herbs-ornamentals-480.webp", "image_800": "images/home/categories/herbs-ornamentals-800.webp", "image_alt": "Coriander, rosemary, basil, celery and marigolds at a nursery"},
]

BRANCHES = ("Bomet Main Nursery", "Sotik Collection Point", "Kericho Collection Point")

PRODUCTS = [
    {"slug":"anna-f1-tomato","name":"Anna F1 Tomato","variety":"Anna F1","category":"Vegetable seedlings","category_slug":"vegetable-seedlings","price":2560,"price_display":"2,560","unit":"tray of 128","short":"Vigorous tomato seedlings for greenhouse and carefully managed production.","description":"Uniform, hardened Anna F1 tomato seedlings raised under careful nursery management for reliable establishment after transplanting.","planting":"Year-round under protection or with reliable irrigation; avoid severe cold and prolonged heavy rain.","duration":"90–120 days after transplanting","stock":"in-stock","stock_label":"In stock","image_variant":"tomato","specs":{"Growth habit":"Indeterminate","Spacing":"60 × 45 cm","Best suited":"Greenhouse production","Seedling age":"4–5 weeks"},"guide":["Prepare well-drained beds enriched with mature compost.","Transplant late afternoon and water immediately.","Stake early and maintain regular scouting for pests."]},
    {"slug":"california-wonder-capsicum","name":"California Wonder Capsicum","variety":"California Wonder","category":"Vegetable seedlings","category_slug":"vegetable-seedlings","price":2880,"price_display":"2,880","unit":"tray of 128","short":"Uniform sweet pepper seedlings with strong transplant establishment.","description":"Healthy capsicum seedlings suited to protected or open-field production where temperatures are moderate and irrigation is dependable.","planting":"Warm months; transplant after cold stress and heavy rain risk has reduced.","duration":"75–90 days to first picking","stock":"in-stock","stock_label":"In stock","image_variant":"capsicum","specs":{"Crop type":"Sweet pepper","Spacing":"60 × 45 cm","Best suited":"Open field or greenhouse","Seedling age":"6–8 weeks"},"guide":["Use fertile, well-drained soil with a pH near 6.0–6.8.","Transplant without burying the stem too deeply.","Mulch and irrigate consistently to reduce blossom-end rot risk."]},
    {"slug":"gloria-star-f1-cabbage","name":"Gloria Star F1 Cabbage","variety":"Gloria Star F1","category":"Vegetable seedlings","category_slug":"vegetable-seedlings","price":1920,"price_display":"1,920","unit":"tray of 128","short":"Compact, uniform cabbage seedlings for cool highland production.","description":"Strong Gloria Star F1 seedlings selected for uniform field establishment and dependable head development in suitable Kenyan highland conditions.","planting":"Best in cooler seasons and highland areas with dependable moisture.","duration":"75–85 days after transplanting","stock":"low-stock","stock_label":"Low stock","image_variant":"cabbage","specs":{"Head type":"Round, compact","Spacing":"60 × 60 cm","Best suited":"Cool highlands","Seedling age":"4–5 weeks"},"guide":["Incorporate compost and prepare a fine, firm bed.","Transplant healthy seedlings at recommended spacing.","Scout frequently for diamondback moth and aphids."]},
    {"slug":"fordhook-giant-swiss-chard","name":"Fordhook Giant Swiss Chard","variety":"Fordhook Giant","category":"Vegetable seedlings","category_slug":"vegetable-seedlings","price":1600,"price_display":"1,600","unit":"tray of 128","short":"Leafy, heat-tolerant Swiss chard seedlings for repeated harvesting.","description":"Fast-establishing Fordhook Giant Swiss chard seedlings suitable for irrigated kitchen gardens and market production.","planting":"Most of the year with reliable moisture; especially suitable where heat tolerance is valuable.","duration":"60–70 days after transplanting","stock":"in-stock","stock_label":"In stock","image_variant":"spinach","specs":{"Crop identity":"Swiss chard","Harvest":"Multiple pickings","Spacing":"30 × 30 cm","Seedling age":"3–4 weeks"},"guide":["Prepare fertile beds with good organic matter.","Maintain even moisture without waterlogging.","Harvest outer leaves regularly to encourage growth."]},
    {"slug":"improved-sukuma-wiki","name":"Improved Sukuma Wiki","variety":"Thousand Headed","category":"Vegetable seedlings","category_slug":"vegetable-seedlings","price":1400,"price_display":"1,400","unit":"tray of 128","short":"Reliable collard seedlings for household and market production.","description":"Hardy Thousand Headed collard seedlings raised for steady leaf production under good crop nutrition and regular harvesting.","planting":"Year-round where irrigation is available.","duration":"45–60 days to first harvest","stock":"in-stock","stock_label":"In stock","image_variant":"kale","specs":{"Crop identity":"Collard (sukuma wiki)","Harvest":"Multiple pickings","Spacing":"60 × 45 cm","Seedling age":"4–5 weeks"},"guide":["Transplant into fertile soil after hardening.","Top-dress after establishment based on soil needs.","Remove older leaves cleanly and monitor aphids."]},
    {"slug":"red-creole-onion","name":"Red Creole Onion Seedlings","variety":"Red Creole","category":"Vegetable seedlings","category_slug":"vegetable-seedlings","price":850,"price_display":"850","unit":"bundle of 100","short":"Hardened red onion seedlings ready for careful transplanting.","description":"Popular red onion variety supplied as uniform seedlings for well-drained fields with controlled irrigation.","planting":"Dry periods with controlled irrigation are preferred for bulb development.","duration":"90–120 days after transplanting","stock":"low-stock","stock_label":"Low stock","image_variant":"onion","specs":{"Bulb colour":"Deep red","Spacing":"10 × 8 cm","Best suited":"Warm, dry production","Seedling age":"6–8 weeks"},"guide":["Use fine, well-drained soil without fresh manure.","Plant shallowly and avoid damaging roots.","Reduce irrigation as bulbs mature and necks begin to fall."]},
    {"slug":"sukari-f1-watermelon","name":"Sukari F1 Watermelon","variety":"Sukari F1","category":"Fruit seedlings","category_slug":"fruit-seedlings","price":75,"price_display":"75","unit":"seedling","short":"Carefully raised watermelon plugs for warm production zones.","description":"Strong Sukari F1 watermelon seedlings for growers seeking uniform establishment in warm, well-drained fields.","planting":"Warm, dry periods with irrigation; avoid cold or waterlogged soils.","duration":"75–90 days after transplanting","stock":"preorder","stock_label":"Pre-order","image_variant":"watermelon","specs":{"Crop family":"Cucurbit","Spacing":"2 × 1 m","Best suited":"Warm low and mid-altitudes","Seedling age":"3–4 weeks"},"guide":["Prepare wide planting stations with decomposed manure.","Handle roots carefully during transplanting.","Support pollinators and reduce irrigation near maturity."]},
    {"slug":"hass-avocado","name":"Hass Avocado","variety":"Hass","category":"Tree seedlings","category_slug":"tree-seedlings","price":350,"price_display":"350","unit":"grafted seedling","short":"Grafted Hass avocado trees for suitable Kenyan production sites.","description":"Healthy grafted Hass seedlings supplied with guidance on site suitability, pollination planning and establishment care.","planting":"At the onset of reliable rains or any time with assured irrigation.","duration":"3–4 years to first bearing","stock":"in-stock","stock_label":"In stock","image_variant":"avocado","specs":{"Propagation":"Grafted","Spacing":"7 × 7 m","Best suited":"Site assessment required","Container":"Large nursery sleeve"},"guide":["Confirm drainage and local avocado suitability before planting.","Dig and refill planting holes ahead of transplanting.","Protect the young tree from wind and water consistently."]},
    {"slug":"tree-tomato-red-oratia","name":"Red Oratia Tree Tomato","variety":"Red Oratia","category":"Fruit seedlings","category_slug":"fruit-seedlings","price":180,"price_display":"180","unit":"seedling","short":"Selected tree tomato seedlings for cool, well-drained highlands.","description":"Nursery-raised Red Oratia seedlings suited to protected highland sites with reliable water and wind management.","planting":"Onset of rains in cool highland production areas.","duration":"12–24 months to first meaningful fruiting","stock":"in-stock","stock_label":"In stock","image_variant":"tree-tomato","specs":{"Fruit colour":"Red","Spacing":"2.5 × 2.5 m","Best suited":"1,500–3,000 m highlands","Container":"Medium nursery sleeve"},"guide":["Choose a sheltered site with deep, well-drained soil.","Plant at the original nursery depth.","Stake young plants and maintain a clean mulch ring."]},
    {"slug":"kpf-12-passion-fruit","name":"KPF 12 Passion Fruit","variety":"KPF 12","category":"Fruit seedlings","category_slug":"fruit-seedlings","price":150,"price_display":"150","unit":"seedling","short":"Kenyan-bred passion fruit seedlings ready for trained production systems.","description":"Vigorous KPF 12 passion fruit seedlings for growers with prepared trellising and a planned disease-management programme.","planting":"Start of rains or with assured irrigation in suitable production zones.","duration":"8–12 months to first harvest","stock":"preorder","stock_label":"Pre-order","image_variant":"passion","specs":{"Crop type":"Passion fruit hybrid","Spacing":"3 × 2 m","Best suited":"Suitable Kenyan highland and mid-altitude zones","Support":"Trellis required"},"guide":["Install trellising before or immediately after planting.","Use clean, well-drained sites away from old diseased vines.","Train one main leader and maintain field hygiene."]},
    {"slug":"grevillea-robusta","name":"Grevillea Robusta","variety":"Grevillea robusta","category":"Tree seedlings","category_slug":"tree-seedlings","price":50,"price_display":"50","unit":"seedling","short":"Versatile agroforestry trees for boundaries, shade and timber.","description":"Well-rooted Grevillea seedlings suited to farm boundaries and agroforestry systems where spacing and future canopy management are planned.","planting":"At the onset of reliable rains.","duration":"15–20 years for a timber objective on suitable sites","stock":"in-stock","stock_label":"In stock","image_variant":"grevillea","specs":{"Use":"Agroforestry and timber","Spacing":"Purpose-dependent","Best suited":"850–2,500 m","Container":"Nursery sleeve"},"guide":["Plan spacing to avoid future crop shading.","Plant during reliable rainfall and firm soil gently.","Protect from livestock and prune according to intended use."]},
    {"slug":"croton-megalocarpus","name":"Croton Megalocarpus","variety":"Croton megalocarpus","category":"Tree seedlings","category_slug":"tree-seedlings","price":60,"price_display":"60","unit":"seedling","short":"Indigenous multipurpose tree seedlings for farm landscapes.","description":"Indigenous Croton seedlings for biodiversity, shade, wind protection and long-term farm landscape value.","planting":"At the onset of the long or short rains.","duration":"Long-term perennial tree","stock":"out-of-stock","stock_label":"Currently unavailable","image_variant":"croton","specs":{"Use":"Shade and biodiversity","Spacing":"Site-dependent","Best suited":"High and mid-altitudes","Type":"Indigenous tree"},"guide":["Choose a permanent location with adequate canopy room.","Plant at the onset of dependable rainfall.","Protect from browsing livestock during establishment."]},
]

BRANCH_AVAILABILITY = {
    "in-stock": [(BRANCHES[0], "Available today", "in-stock"), (BRANCHES[1], "Collection in 2–3 days", "low-stock"), (BRANCHES[2], "Transfer on request", "preorder")],
    "low-stock": [(BRANCHES[0], "Limited quantities", "low-stock"), (BRANCHES[1], "Transfer on request", "preorder"), (BRANCHES[2], "Not currently available", "out-of-stock")],
    "preorder": [(BRANCHES[0], "Next nursery batch", "preorder"), (BRANCHES[1], "Pre-order only", "preorder"), (BRANCHES[2], "Pre-order only", "preorder")],
    "out-of-stock": [(branch, "Not currently available", "out-of-stock") for branch in BRANCHES],
}

CATALOG_METADATA = {
    "anna-f1-tomato": ("products/vegetables/anna-f1-tomato.webp", "Greenhouse production in cool and moderate highland zones"),
    "california-wonder-capsicum": ("products/vegetables/california-wonder-capsicum.webp", "Warm mid-altitude and irrigated highland production zones"),
    "gloria-star-f1-cabbage": ("products/vegetables/gloria-star-f1-cabbage.webp", "Cool highland areas including Bomet, Kericho, Nakuru, Nyandarua and neighbouring zones"),
    "fordhook-giant-swiss-chard": ("products/vegetables/fordhook-giant-swiss-chard.webp", "Widely adaptable with reliable water and fertile soil"),
    "improved-sukuma-wiki": ("products/vegetables/improved-sukuma-wiki.webp", "Most Kenyan production zones with suitable moisture management"),
    "red-creole-onion": ("products/vegetables/red-creole-onion-seedlings.webp", "Warm, dry and irrigated onion-growing zones"),
    "sukari-f1-watermelon": ("products/fruits/sukari-f1-watermelon.webp", "Warm low- and mid-altitude zones with well-drained soils"),
    "hass-avocado": ("products/trees/hass-avocado.webp", "Site-specific Kenyan avocado zones; confirm altitude, drainage and local suitability"),
    "tree-tomato-red-oratia": ("products/fruits/red-oratia-tree-tomato.webp", "Cool highlands around 1,500–3,000 m with good drainage"),
    "kpf-12-passion-fruit": ("products/fruits/kpf-12-passion-fruit.webp", "Suitable highland and mid-altitude passion-fruit zones after site assessment"),
    "grevillea-robusta": ("products/trees/grevillea-robusta.webp", "About 850–2,500 m; well-drained farms in highland and coffee/tea zones"),
    "croton-megalocarpus": ("products/trees/croton-megalocarpus.webp", "Mid- and high-altitude sites with well-drained soils"),
}

CATALOG_SKUS = {
    "anna-f1-tomato": "WTP-VEG-001",
    "california-wonder-capsicum": "WTP-VEG-002",
    "gloria-star-f1-cabbage": "WTP-VEG-003",
    "fordhook-giant-swiss-chard": "WTP-VEG-004",
    "improved-sukuma-wiki": "WTP-VEG-005",
    "red-creole-onion": "WTP-VEG-006",
    "sukari-f1-watermelon": "WTP-FRT-001",
    "tree-tomato-red-oratia": "WTP-FRT-002",
    "kpf-12-passion-fruit": "WTP-FRT-003",
    "hass-avocado": "WTP-TRE-001",
    "grevillea-robusta": "WTP-TRE-002",
    "croton-megalocarpus": "WTP-TRE-003",
}

for item in PRODUCTS:
    image_filename, recommended_regions = CATALOG_METADATA[item["slug"]]
    item["image_filename"] = image_filename
    item["sku"] = CATALOG_SKUS[item["slug"]]
    item["catalog_version"] = CATALOG_VERSION
    item["recommended_regions"] = recommended_regions
    item["planting_guide"] = item.pop("guide")
    item["growing_guide"] = {
        "planting_period": item["planting"],
        "time_to_maturity": item["duration"],
        "recommended_regions": recommended_regions,
    }
    item["available_branches"] = [
        {"name": name, "message": message, "status": status}
        for name, message, status in BRANCH_AVAILABILITY[item["stock"]]
    ]
    available_names = [branch["name"] for branch in item["available_branches"] if branch["status"] != "out-of-stock"]
    item["branch_summary"] = available_names[0] if available_names else "No branch availability"

PRODUCT_BY_SLUG = {product["slug"]: product for product in PRODUCTS}
CATEGORY_BY_SLUG = {category["slug"]: category for category in CATEGORIES}


def product_page_context(product):
    """Compose mock read data without inventory or sales side effects."""
    related = [item for item in PRODUCTS if item["category_slug"] == product["category_slug"] and item["slug"] != product["slug"]][:3]
    recent = [item for item in PRODUCTS if item["slug"] != product["slug"]][-3:]
    return {"product": product, "related_products": related, "recently_viewed": recent, "branch_availability": product["available_branches"]}
