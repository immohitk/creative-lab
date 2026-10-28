# C02 — Creative Lab Clock

## Project Goal
Build Creative Lab Clock in two versions:
1. Responsive web application.
2. Standalone Windows desktop application using Electron.

Both versions should share the clock UI and core logic where practical.

## Core Features
- Live local time, including seconds.
- Current date and weekday.
- 12-hour and 24-hour formats.
- Correct AM/PM display in 12-hour mode.
- Dark and light themes.
- Responsive, accessible interface.
- Windows desktop app with its own independent window.
- Windows installer and local install/uninstall verification.

## Technology
- HTML5, CSS3 and JavaScript.
- Electron and electron-builder.
- Node.js built-in test runner.

## Out of Scope
- User accounts, backend or database.
- Cloud synchronisation.
- Weather, alarms and calendar integrations.
- Analytics, telemetry and automatic updates.
- Microsoft Store publishing.

## Testing
- Verify clock formatting and time updates.
- Test date and weekday behaviour.
- Verify themes, responsiveness and keyboard accessibility.
- Verify Electron window behaviour and security settings.
- Build and test the Windows installer.

## Definition of Done
- Web app works as specified.
- Desktop app runs independently of a development server.
- Automated tests pass.
- Windows installer builds and is verified locally.
- README and screenshots are complete.
- Only intended source files and configuration are committed.
- Push happens only after final verification.
