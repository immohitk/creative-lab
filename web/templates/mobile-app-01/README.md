# Mobile App Landing Page

A premium, responsive mobile app landing page template built with Astro.

This template is part of **Creative Lab**, a collection of reusable web templates, interactive components, and small desktop applications.

## Overview

Mobile App Landing Page is a product-focused landing page designed for showcasing a mobile application.

The design follows a light, minimal visual direction with strong typography, generous spacing, subtle motion, and a responsive layout across desktop, tablet, and mobile screens.

The template is intentionally static and lightweight, making it suitable for marketing pages, app launches, product showcases, and portfolio projects.

## Design Direction

- Light premium visual style
- Typography-led hierarchy
- Minimal interface
- Product-focused storytelling
- Generous whitespace
- Subtle accent color
- Soft cards and restrained shadows
- Responsive layout
- Short, non-blocking entrance animations

## Page Sections

### 1. Navigation

- Brand identity
- Primary section links
- Main call-to-action

### 2. Hero

- Product headline
- Supporting description
- Primary and secondary actions
- Mobile app preview

### 3. Product Highlights

- Discover
- Plan
- Save
- Explore

### 4. Feature Storytelling

- Discover places
- Plan journeys
- Save adventures

### 5. How It Works

- Three-step workflow
- Supporting benefits
- App interface showcase

### 6. Final CTA

- Closing message
- Primary action
- Secondary navigation

### 7. Footer

- Navigation links
- Project attribution

## Tech Stack

- **Astro 7**
- **HTML5**
- **CSS3**
- **Minimal JavaScript**
- **Responsive CSS**
- **Git / GitHub**

Astro is used for the static page structure while keeping client-side JavaScript minimal.

## Project Structure

    mobile-app-01/
    ├── public/
    ├── src/
    │   ├── components/
    │   │   ├── Features.astro
    │   │   ├── FinalCta.astro
    │   │   ├── Hero.astro
    │   │   ├── Highlights.astro
    │   │   └── Workflow.astro
    │   ├── layouts/
    │   │   └── MainLayout.astro
    │   ├── pages/
    │   │   └── index.astro
    │   └── styles/
    │       └── global.css
    ├── .gitignore
    ├── astro.config.mjs
    ├── package.json
    ├── package-lock.json
    ├── tsconfig.json
    └── README.md

## Getting Started

### Requirements

- Node.js `22.12.0` or newer
- npm

### Install Dependencies

    npm install

### Start Development Server

    npm run dev

The development server runs at:

    http://localhost:4321/

### Build for Production

    npm run build

The production output is generated inside:

    dist/

### Preview the Production Build

    npm run preview

## Accessibility

The template includes basic accessibility considerations:

- Semantic HTML structure
- Logical heading hierarchy
- Keyboard-visible focus states
- Accessible navigation labels
- Decorative interface mockups hidden from assistive technologies
- Reduced-motion support through `prefers-reduced-motion`

The template should still be tested with real browsers, keyboard navigation, and assistive technologies when adapted for production use.

## Responsive Design

The layout adapts across:

- Desktop
- Tablet
- Mobile

Responsive behavior includes:

- Responsive typography
- Flexible content layouts
- Mobile-friendly CTA buttons
- Scaled app mockups
- Adjusted section spacing
- Mobile navigation behavior

## Performance

The page is designed to remain lightweight:

- Static Astro output
- Minimal client-side JavaScript
- No unnecessary third-party libraries
- CSS-based interface mockups
- No external image dependencies
- Small production HTML output

The production build currently generates a static page with the compiled stylesheet.

For production deployment, performance should be validated with browser audits and real-device testing.

## Customization

The template can be adapted by changing:

- Brand name
- Logo or brand mark
- Typography
- Accent color
- Hero content
- Feature sections
- App preview content
- CTA labels
- Footer links
- Content and messaging

Global visual tokens are defined in:

    src/styles/global.css

These include:

- Colors
- Typography
- Spacing
- Borders
- Shadows
- Motion values

## Reusability

The page is organized into independent Astro components so sections can be modified, reordered, removed, or reused in other landing pages.

Main components:

- `Navbar`
- `Hero`
- `Highlights`
- `Features`
- `Workflow`
- `FinalCta`

## Project Scope

This project is intentionally a **static landing-page template**.

It does not include:

- Backend services
- Authentication
- Database integration
- Payment processing
- Real app-store integration
- User accounts
- SaaS functionality
- Complex client-side application logic

The mobile interface shown on the page is a visual product mockup rather than a functional mobile application.

## Development

The project uses Astro's static build output.

Development workflow:

1. Install dependencies.
2. Start the development server.
3. Develop and test the template locally.
4. Build the production version.
5. Verify the generated output.
6. Review responsive behavior and accessibility.
7. Prepare documentation and screenshots.

## Browser & Device Testing

The template should be checked across:

- Desktop browsers
- Tablet-sized layouts
- Mobile-sized layouts
- Keyboard navigation
- Reduced-motion preferences

Particular attention should be given to:

- Navigation
- CTA buttons
- Typography
- Phone mockups
- Section spacing
- Footer layout
- Mobile responsiveness

## Attribution

Designed & Developed by **Mohit Kumar · Creative Lab**

The attribution is intentionally kept subtle within the template footer.

## License

This project is part of the **Creative Lab** portfolio and is intended to demonstrate reusable web design and development work.

See the repository license for applicable usage terms.
