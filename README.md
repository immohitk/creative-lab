# Creative Lab

A collection of modern, reusable web templates, interactive web components,
small functional desktop applications, and selected UI/UX designs.

Creative Lab is focused on building small, polished projects that demonstrate
practical frontend development, interaction design, Python desktop development,
and visual design skills.

The repository is intentionally focused on useful, reusable work rather than
large SaaS products.

## Categories

### 1. Web Templates

Reusable responsive websites and landing pages built for different use cases.

Examples include:

- Mobile app landing pages
- Developer websites
- Portfolio pages
- Restaurant and café websites
- Small business websites
- Event and hackathon pages
- Open-source project pages
- Education and course pages
- Fitness websites
- Blog layouts
- Ecommerce and product showcase pages

Templates are designed to be visually polished, responsive, accessible, and
easy to customize.

### 2. Interactive Web Components

Small browser-based components and utilities focused on interaction and
frontend implementation.

Examples include:

- Calculators
- Digital clocks
- Stopwatches
- Countdown timers
- Unit converters
- Password generators
- Password strength checkers
- Color pickers
- JSON formatters and viewers
- QR generators
- Text utilities
- Markdown previews
- Modals
- Toast notifications
- Accordions
- Tabs
- Dropdowns
- Navigation components
- Sidebars
- Search interfaces
- Multi-step forms
- OTP interfaces
- Carousels
- Progress components
- Dashboard cards
- Timelines
- Kanban interfaces
- Pomodoro tools
- Expense calculators
- BMI calculators
- Regex testers
- API response viewers
- Small random generators

The goal is to keep components focused, reusable, and easy to understand.

### 3. Desktop Applications

Small functional desktop applications developed with Python.

The desktop track focuses on practical utilities rather than large enterprise
applications.

Examples include:

- System monitors
- Network monitors
- Password vaults
- Download managers
- Disk analyzers
- Clipboard managers
- Desktop notes
- Backup managers
- Process managers
- Log viewers
- Markdown editors
- Local database browsers

Python desktop applications may use PySide6 or another appropriate GUI
technology depending on the project.

### 4. Design

Design work supports the development of the other Creative Lab projects.

Figma may be used for:

- Wireframes
- Responsive layouts
- Design systems
- Typography systems
- Component design
- Desktop application interfaces
- Prototypes
- Visual exploration

Design work is used where it adds value to the project rather than being
created as a separate collection of unrelated mockups.

## Repository Structure

    creative-lab/
    ├── web/
    │   └── templates/
    │       ├── mobile-app-01/
    │       ├── mobile-app-02/
    │       └── ...
    │
    ├── components/
    │   ├── calculator-01/
    │   ├── digital-clock-01/
    │   └── ...
    │
    ├── desktop/
    │   ├── system-monitor-01/
    │   ├── network-monitor-01/
    │   └── ...
    │
    ├── design/
    │   └── ...
    │
    ├── assets/
    │   └── ...
    │
    ├── README.md
    ├── LICENSE
    └── .gitignore

## Technology

Creative Lab uses technologies according to the needs of each project.

### Web

- HTML5
- CSS3
- JavaScript
- Bootstrap
- Astro

### Desktop

- Python
- PySide6
- psutil
- Other Python libraries when required

### Design

- Figma

### Development

- Git
- GitHub
- VS Code
- GitHub Actions where useful

Not every project uses every technology.

Libraries and frameworks are selected based on the actual requirements of the
project rather than being added only to increase the technology list.

## Development Principles

Creative Lab follows a simple development philosophy.

### Small Scope, High Quality

Projects are intentionally small enough to finish properly.

The focus is on:

- Clean implementation
- Good visual hierarchy
- Responsive layouts
- Usable interactions
- Accessibility
- Performance
- Documentation
- Reusability

### Modern but Practical

Modern design does not mean excessive animations, gradients, effects, or
dependencies.

Projects should remain:

- Clear
- Fast
- Accessible
- Responsive
- Easy to customize

### Original Implementation

Existing websites, design galleries, and marketplaces may be used as
inspiration.

Final implementations should be independently designed and developed rather
than copied.

### Real Functionality

Interactive components and desktop applications should work as demonstrated.

Features should not be added only to make a project appear larger.

### No Unnecessary Complexity

A project should use the simplest appropriate technology for its requirements.

A framework or library should not be introduced only for resume keywords.

## Naming Convention

Projects use a type-based naming convention:

    <type>-<two-digit-number>

Examples:

    mobile-app-01
    mobile-app-02
    calculator-01
    digital-clock-01
    system-monitor-01

This keeps the repository organized and allows multiple variations of the
same project type.

## Web Template Standards

Web templates should generally include:

- Responsive desktop, tablet, and mobile layouts
- Clear visual hierarchy
- Semantic HTML
- Keyboard-accessible interactions
- Visible focus states
- Appropriate contrast
- Responsive typography
- Optimized assets
- Minimal unnecessary JavaScript
- Reasonable loading performance
- Reduced-motion support where animations are used
- Project-specific documentation
- Screenshots or other visual documentation

Templates should remain easy to reuse and customize.

## Desktop Application Standards

Desktop applications should focus on:

- Functional workflows
- Clear interfaces
- Sensible error handling
- Maintainable Python structure
- Appropriate type hints where useful
- Testing where practical
- Clean user feedback
- Practical documentation

Python projects may use tools such as:

    pyproject.toml
    pytest
    Ruff

when appropriate for the project.

## Design Approach

Figma is treated as a supporting design tool rather than a requirement for
every project.

For projects where visual planning is valuable, the design process may include:

    Idea
      ↓
    Wireframe
      ↓
    Visual Design
      ↓
    Responsive Design
      ↓
    Implementation
      ↓
    Testing
      ↓
    Polish

The final implementation should remain faithful to the intended user
experience while allowing practical adjustments during development.

## Project Development Workflow

Projects generally follow this cycle:

    Plan
      ↓
    Define Scope
      ↓
    Design
      ↓
    Build MVP
      ↓
    Implement Core Features
      ↓
    Test
      ↓
    Responsive & Accessibility QA
      ↓
    Performance & UX Polish
      ↓
    Documentation
      ↓
    Screenshots / Demo
      ↓
    Git Cleanup
      ↓
    Commit
      ↓
    Release

Each development task should represent meaningful work.

Commits should describe the actual change being made rather than artificially
splitting work into unnecessary commits.

## Git Workflow

Creative Lab projects use meaningful commits.

Examples:

    chore: initialize mobile app template
    feat: establish mobile app template design system
    feat: build mobile app template hero
    feat: build product feature sections
    feat: add workflow and app showcase
    feat: complete mobile app landing page
    feat: polish mobile app template interactions
    fix: improve mobile app template accessibility and metadata
    docs: finalize mobile app template

Projects are not pushed after every individual development task.

The normal workflow is:

    Development
      ↓
    Individual meaningful commits
      ↓
    Testing
      ↓
    Final cleanup
      ↓
    Final project commit
      ↓
    Push

## Current Projects

### Web Templates

#### Mobile App Landing Page

Location:

    web/templates/mobile-app-01/

A premium, responsive mobile app landing page built with Astro.

Current characteristics:

- Light premium visual direction
- Typography-led layout
- Responsive design
- CSS-based mobile app mockups
- Minimal JavaScript
- Subtle motion
- Accessibility considerations
- Reduced-motion support
- Static Astro output

More templates will be added progressively.

## Project Status

Creative Lab is in active development.

The repository will grow incrementally as individual projects are completed,
tested, documented, and released.

Current priority:

    Web Templates
        ↓
    Interactive Web Components
        ↓
    Desktop Applications
        ↓
    Supporting Design Work

This order may change according to project requirements.

## Customization

Most projects are intended to be adapted rather than used unchanged.

Depending on the project, customization may include:

- Branding
- Typography
- Colors
- Content
- Images
- Components
- Layout
- Navigation
- Interactive behavior
- Application-specific functionality

Each completed project should contain its own README when additional setup or
usage information is required.

## Attribution

Projects may contain a subtle attribution such as:

    Designed & Developed by Mohit Kumar · Creative Lab

Attribution should remain visually unobtrusive and should not interfere with
the user experience.

## License

See the repository `LICENSE` file for applicable usage and distribution terms.

Individual projects may contain additional project-specific documentation
where necessary.

## Status

🚧 **Creative Lab is actively under development.**

New templates, components, desktop applications, and design work will be added
progressively.
