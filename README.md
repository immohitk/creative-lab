# Creative Lab

A collection of thoughtfully designed web templates, interactive components, and standalone desktop applications.

Creative Lab is a development portfolio focused on building practical, polished, and reusable software projects. Each project has its own scope, technology choices, documentation, and quality requirements.

## Project Categories

### 1. Web Templates

Responsive website templates and landing pages built for different products, services, and use cases.

### 2. Interactive Components

Standalone interactive utilities and components designed around focused functionality and usability.

### 3. Desktop Applications

Independent desktop software built with technologies selected according to each project's requirements.

### 4. Design

Supporting UI/UX work, including wireframes, interface concepts, design systems, prototypes, and application layouts.

## Current Projects

### Web Templates

#### W01 — Mobile App Landing Page

`web/templates/mobile-app-01/`

A premium, light-themed mobile application landing page built with Astro.

**Highlights**

- Minimal, typography-led visual design.
- Hero section and mobile app preview.
- Product highlights and feature storytelling.
- Three-step workflow section.
- Responsive desktop, tablet, and mobile layouts.
- Semantic HTML, visible keyboard focus, and reduced-motion support.

**Technology:** Astro, HTML5, CSS3, minimal JavaScript.

#### W02 — Beyond: Mobile App Landing Page 02

`web/templates/mobile-app-02/`

A dark editorial-style mobile app landing page featuring bold typography, near-black surfaces, and electric lime accents.

**Highlights**

- Responsive navigation and hero section.
- Product highlights and benefits.
- Feature storytelling and app showcase.
- Three-step workflow.
- SEO metadata and social-sharing tags.
- Responsive layouts and reduced-motion support.
- Desktop and mobile screenshots.

**Technology:** Astro, HTML, CSS, JavaScript.

**Documented status:** Completed template; final repository QA in progress.

### Interactive Components

#### C01 — Calculator

`components/calculator-01/`

A responsive calculator with a standalone Windows desktop application powered by Electron.

**Highlights**

- Basic arithmetic with operator precedence.
- Decimal and negative-number input.
- Live calculation preview.
- Keyboard and on-screen keypad input.
- Locally stored calculation history.
- Clear, backspace, and error recovery.
- Windows NSIS installer.

**Technology:** HTML, CSS, JavaScript, Electron, Node.js.

#### C02 — Creative Lab Clock

`components/digital-clock-02/`

A minimal digital clock available as a browser interface and a Windows desktop application.

**Highlights**

- Live local time with seconds.
- 12-hour and 24-hour formats.
- Current date and weekday.
- Midnight, Light, and Forest themes.
- Persistent theme and time-format preferences.
- Keyboard and mouse interaction.
- Windows desktop application with a custom icon.

**Technology:** HTML5, CSS3, JavaScript, Node.js, Electron, Electron Builder.

#### C03 — Creative Lab Floating Clock

`components/floating-clock-03/`

A customizable floating Windows desktop clock with a transparent, frameless interface.

**Highlights**

- Live time and date display.
- Draggable, non-resizable clock window.
- System-tray Show, Hide, Settings, and Exit controls.
- Multiple background and gradient styles.
- Customizable time and date typography.
- Appearance, size, and depth customization.
- Persistent preferences and window position.
- Single-instance behaviour and off-screen position recovery.

**Technology:** HTML, CSS, JavaScript, Node.js, Electron.

## Repository Structure

```text
creative-lab/
├── web/
│   └── templates/
│       ├── mobile-app-01/
│       └── mobile-app-02/
│
├── components/
│   ├── calculator-01/
│   ├── digital-clock-02/
│   └── floating-clock-03/
│
├── desktop/
├── design/
├── assets/
├── tests/
├── README.md
├── LICENSE
└── .gitignore
```

Each project maintains its own implementation files and relevant documentation. Project-specific scope, acceptance criteria, tests, screenshots, and release assets are kept with the respective project where applicable.

## Technology Stack

Technologies are selected according to individual project requirements.

**Web Development**

- HTML5
- CSS3
- JavaScript
- Astro
- Bootstrap, where applicable

**Desktop Development**

- Python
- PySide6
- Node.js
- Electron
- Electron Builder

**Design and Development Tools**

- Figma
- Git
- GitHub

## Project Documentation

Individual project directories may contain:

- `README.md` — project overview, setup, usage, and technical details.
- `SCOPE.md` — project vision, features, technology, and boundaries.
- `ACCEPTANCE-CRITERIA.md` — verifiable requirements and release checks.
- `tests/` — automated tests where applicable.
- `screenshots/` — project visuals and interface previews.
- `release/` — local build and installer output where applicable.

Refer to each project's documentation for its specific setup, testing, and release instructions.

## Development Philosophy

Creative Lab follows these principles:

- Quality over quantity.
- Clearly defined project scope.
- Practical functionality.
- Clean and maintainable implementation.
- Consistent user experience.
- Accessibility and responsive design where relevant.
- Appropriate testing and verification.
- Honest project documentation.
- Independent project identity and organization.

The objective is to create useful, polished projects rather than unnecessary complexity or duplicate implementations.

## Repository Status

Creative Lab is an actively maintained development portfolio. Existing projects are documented individually, and new projects are introduced progressively.

Project completion and release status are determined by their actual implementation, testing, documentation, and release evidence.

## License

See the `LICENSE` file for applicable usage terms.
