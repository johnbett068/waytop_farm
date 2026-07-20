# Homepage Hero concept exploration

## Decision criteria

Each direction was evaluated against immediate nursery recognition, WayTop brand memorability, product-discovery value, Kenyan context, accessibility, responsive resilience, performance and compatibility with the future catalog backend.

## Concept A — Editorial nursery split

### Composition

- Strong two-line brand promise and primary actions on the left.
- One carefully cropped nursery photograph on the right.
- Small Bomet location caption beneath the photograph.

### Strengths

- Calm editorial hierarchy.
- Straightforward responsive collapse.
- Authentic commissioned photography could become highly ownable.

### Weaknesses

- Photography still carries most of the differentiation.
- A generic or generated nursery image makes the brand less memorable.
- Uses valuable right-side space for atmosphere rather than product evidence.

### Decision

Selected after the rendered catalog-showcase review, with an important refinement: the visual is one portrait nursery showcase with restrained operational annotations, while trust is communicated through careful nursery language and compact chips beneath the actions. Product discovery remains immediately below the Hero.

## Concept B — Living catalog showcase

### Composition

- Premium light agricultural surface with restrained field-line geometry.
- Brand promise, Bomet context and two clear actions on the left.
- A layered product showcase on the right using real catalog records: product photography, actual variety names, unit pricing, stock state and branch summary.
- The existing Trust component overlaps the lower edge to connect promise with operational reassurance.

### Strengths

- Instantly communicates nursery, ecommerce and healthy seedlings.
- Turns the right side into useful evidence rather than scenery.
- Uses the same mock records that power Shop and Product Detail, avoiding Hero-only invented products.
- Future backend integration only replaces the read source; the visual contract remains stable.
- Product cards create a recognizable, ownable WayTop first impression.

### Risks and controls

- Too many cards could feel like a dashboard. The implementation is limited to one primary and two supporting products.
- Availability can change. The future backend must supply branch-aware read projections and must not treat Hero display as a reservation.

### Decision

Rejected after implementation and responsive review. Although architecturally sound, the cards made the Hero resemble a software dashboard, obscured the emotional focal point and placed prices and stock information before the visitor had established trust in WayTop.

## Concept C — Image-free agricultural identity

### Composition

- Oversized typography on a cream and green surface.
- Abstract leaf, propagation-tray and contour-field geometry built in CSS/SVG.
- Compact trust statements and location marker.

### Strengths

- Very fast and highly art-directable.
- Avoids dependence on generic photography.
- Strong typographic brand confidence.

### Weaknesses

- Does not prove seedling quality quickly enough for first-time visitors.
- Risks resembling a premium SaaS or agricultural consultancy rather than a working nursery.
- Abstract crop graphics require a stronger established visual identity than WayTop currently has.

### Decision

Rejected. It is a useful future campaign direction but weaker for the primary ecommerce entry point.

## Final selected concept contract

- The Hero contains only the brand promise, supporting copy, two actions, one nursery visual and evidence-safe trust indicators.
- Products, prices, inventory and branch stock remain in Category, Shop and Product Detail experiences.
- The telephone action uses the globally configured business contact.
- The nursery image is meaningful content and requires descriptive alternative text.
- The separate Trust section is not rendered because it would duplicate the Hero's trust chips and showcase annotations.
