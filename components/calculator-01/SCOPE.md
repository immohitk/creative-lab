# C01 — Web Calculator Scope

## Project Goal

Build a polished, responsive calculator using HTML, CSS and JavaScript. Package it as a Windows desktop application using Electron, with a local Windows installer for personal development and testing.

## Core Features

- Addition, subtraction, multiplication and division.
- Decimal numbers and negative results.
- Clear (AC) and backspace (⌫).
- Equals button and consecutive calculations.
- Keyboard input for numbers and operators.
- Enter and = to calculate.
- Backspace to delete and Escape to clear.
- Safe handling of invalid expressions and division by zero.
- Responsive layout for mobile and desktop.
- Accessible button names, visible focus indicators and readable feedback.
- Standard mathematical precedence: multiplication and division before addition and subtraction.
- README with features, setup, usage, keyboard shortcuts, screenshots and installer instructions.
- Electron desktop application and Windows installer.
- Local installation, launch and uninstall verification.

## Technology

- HTML5
- CSS3
- JavaScript
- Electron for the desktop application
- A compatible Windows installer packaging tool

Use only necessary dependencies. Do not introduce a frontend framework unless a demonstrated requirement justifies it.

## Calculation Behaviour

- After a result, pressing an operator continues from that result.
- After a result, entering a new digit starts a fresh calculation.
- Repeated decimal points in the same number must be prevented or handled safely.
- Division by zero must produce readable feedback, not a displayed Infinity or NaN result.
- Invalid or incomplete expressions must not crash the application.
- Do not use eval() to execute user-provided expressions.

## Out of Scope

- Scientific calculator functions.
- Accounts, backend, database or cloud synchronisation.
- Microsoft Store publishing.
- Automatic updates, telemetry or analytics.
- A guarantee that Windows Defender or SmartScreen will never show a warning.

## Windows Installer and Security

The installer is intended for local Windows installation and testing. Build and test it using normal Windows security settings.

Do not disable Microsoft Defender, bypass SmartScreen or instruct users to ignore security warnings. If a warning occurs, verify the build and investigate the detection.

Unsigned or low-reputation applications can still trigger security warnings. A warning-free installation on every PC cannot be guaranteed.

## Definition of Done
- Core arithmetic tests and acceptance criteria pass.

- Core arithmetic and input behaviour pass the acceptance criteria.
- Keyboard interactions and edge cases are tested.
- Responsive layout and accessibility basics are checked.
- The Electron app launches without the development server.
- The Windows installer builds and installs locally.
- Installation, launch and uninstall are tested.
- README and screenshots are complete.
- Intended source files and configuration are committed; generated build output and installer binaries are not committed by default.
