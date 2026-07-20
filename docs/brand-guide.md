# WayTop Farm & Nurseries — Brand Guide

## 1. Brand Mission
WayTop Farm & Nurseries exists to help Kenyan farmers and agribusinesses grow stronger, healthier, and more profitable operations through dependable seedling supply, trusted guidance, and quality-focused nursery practices.

## 2. Brand Vision
To become Kenya’s most trusted partner for high-quality seedlings and agricultural growth solutions, empowering farmers and institutions to thrive sustainably.

## 3. Brand Voice
The brand voice should be:
- Professional
- Friendly
- Modern
- Reliable
- Natural

Tone should feel confident, practical, and supportive. Messaging should emphasize trust, quality, healthy growth, and farmer success.

## 4. Logo Usage Guidelines
- The canonical web identity is the horizontal plant-and-field mark with the WayTop wordmark and `FARM & NURSERIES` descriptor.
- Use `static/images/logo/logo.svg` on standard light surfaces. `logo-dark.svg` provides stronger dark text on pale or tinted surfaces, while `logo-light.svg` is reserved for dark solid backgrounds.
- Use `logo.webp` only as a raster fallback. Use `favicon.svg` for browser icons and `apple-touch-icon.png` for Apple home-screen bookmarks.
- Preserve the existing logo structure and approved green, field-brown and white colors.
- Do not alter proportions or distort the mark.
- Maintain clear space equal to at least one leaf width around the logo.
- Avoid placing the logo over busy imagery or low-contrast backgrounds.
- Never use the 3D stacked wordmark or metallic circular artwork as a small navigation logo; those source images lose detail and text legibility at interface sizes.
- Source raster artwork in the logo directory is archival/reference material and must not be loaded by application templates.
- Navbar sizing is controlled in CSS: 40–48px on mobile, 48–56px on tablet and 56–64px on desktop. Do not add fixed presentation dimensions to templates; intrinsic image dimensions exist only to prevent layout shift.

### Asset architecture

The SVG variants share the same geometry and aspect ratio, so swapping a contrast variant cannot shift layout. The navbar uses a `<picture>` element with SVG first and the optimized WebP as fallback. Product imagery and the company logo remain separate asset systems; product templates must never reuse brand artwork as catalog photography.

## 5. Color Palette
Primary Green
- #2E7D32
- Main brand color for primary actions, headings, and key UI emphasis.

Secondary Green
- #4CAF50
- Supporting color for highlights and secondary states.

Accent Gold
- #D4A017
- Used sparingly for call-to-action emphasis and premium details.

Background
- #F7F8F5

Text
- #1F2937

Surface
- #FFFFFF

Border
- #E5E7EB

## 6. Typography
- Heading font: Poppins
- Body font: Inter
- Use Poppins for major headings and product emphasis.
- Use Inter for body text, labels, descriptions, and UI copy.
- Maintain a strong hierarchy with generous spacing for readability.

## 7. Spacing System
Use a consistent spacing scale based on 4px increments:
- 4px
- 8px
- 12px
- 16px
- 24px
- 32px
- 48px
- 64px
- 96px

Use spacing to support rhythm, layout clarity, and breathing room between sections.

## 8. Photography Guidelines
Preferred assets should reflect:
- Bright natural lighting
- Real seedlings and nursery environments
- Kenyan farmers and agricultural settings
- Clean, uncluttered compositions
- Green-dominant palettes
- Honest, realistic imagery over overly staged visuals

Use photography that communicates quality, growth, and trust.

### Supporting Brand Image Assets
The logo folder now contains additional supporting images that can be used for:
- Digital marketing banners
- Social media cover images
- Brochure and packaging accents
- Website hero or story sections
- Printed signage and event branding

These assets should be used as supporting visuals and paired with the core logo for consistency.

## 9. Icon Guidelines
Use Lucide Icons throughout the interface.
- Keep icons simple, consistent, and legible.
- Use them for navigation, feature highlights, and product attributes.
- Maintain equal stroke weight and visual consistency.
- Prefer muted green accents for standard icons and gold for emphasis.

## 10. UI Principles
- Prioritize clarity and trust.
- Keep the interface calm, modern, and easy to scan.
- Use strong visual hierarchy to guide users.
- Balance useful information with whitespace.
- Support both desktop and mobile experiences with consistency.

## 11. Accessibility Principles
- Ensure sufficient color contrast.
- Support keyboard navigation.
- Use descriptive alt text for all meaningful images.
- Respect reduced-motion preferences.
- Keep interactive elements large enough and clearly identifiable.
- Maintain readable text sizes and spacing.

## 12. Animation Standards
- Transition duration: 200ms to 300ms for standard interactions.
- Hover behavior: subtle lift, color shift, or shadow increase.
- Scroll animations: gentle fade or slide-in effects when appropriate.
- Reduced motion support: disable non-essential animation when the user prefers reduced motion.

## 13. Component Naming Guide
Use a BEM-inspired structure for frontend consistency.

Examples:
- hero
- hero__title
- hero__actions
- product-card
- product-card__image
- product-card__body
- branch-card
- testimonial-card

## 14. Responsive Design Standards
### Mobile
- Container width: 100%
- Single-column layouts
- Touch-friendly spacing and controls

### Tablet
- Container width: 720px to 960px
- Two-column layouts where appropriate

### Laptop
- Container width: 960px to 1200px
- Clear content grouping and balanced whitespace

### Desktop
- Container width: up to 1400px
- Multi-column layouts with strong visual hierarchy

### Grid Rules
- Use a 12-column grid system where appropriate.
- Maintain consistent gutters.
- Avoid overly dense content on smaller screens.

### Spacing Rules
- Increase spacing on larger screens.
- Tighten spacing on mobile while preserving readability.
- Keep section rhythm consistent across pages.
