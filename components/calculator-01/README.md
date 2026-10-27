# C01 — Calculator

A responsive calculator built with HTML, CSS, and JavaScript, packaged as a Windows desktop application using Electron.

## Features

- Basic arithmetic with operator precedence
- Decimal and negative-number input
- Live calculation preview
- Keyboard and on-screen keypad input
- Calculation history stored locally
- Clear, backspace, and error recovery
- Responsive layout and visible keyboard focus
- Windows desktop installer using NSIS

## Requirements

- Node.js 24.x
- npm 11 or newer
- Windows for building and testing the Windows installer

The supported Node.js and npm versions are declared in `package.json`.

## Project Structure

```text
calculator-01/
├── desktop/
│   └── main.js
├── src/
│   ├── calculator.js
│   ├── engine.js
│   ├── index.html
│   └── styles.css
├── ACCEPTANCE-CRITERIA.md
├── SCOPE.md
├── package.json
└── package-lock.json
```

Automated engine tests are located at `../../tests/engine.test.js`.

## Setup

Run commands from the repository root:

```powershell
npm --prefix components/calculator-01 install
```

## Development

Start the Electron application:

```powershell
npm --prefix components/calculator-01 start
```

## Tests

Run the automated tests:

```powershell
npm --prefix components/calculator-01 test
```

The current automated suite covers basic arithmetic, decimal and negative numbers, multiplication precedence, division by zero, and invalid or incomplete expressions.

Also follow the manual checks in `ACCEPTANCE-CRITERIA.md` before releasing.

## Build

Create an unpacked desktop build:

```powershell
npm --prefix components/calculator-01 run pack
```

Build the Windows NSIS installer:

```powershell
npm --prefix components/calculator-01 run dist
```

Build output is written to `components/calculator-01/release/`. The installer filename includes the application version, for example `C01 Calculator Setup 1.0.0.exe`.

## Install and Uninstall

Run the generated installer and follow its prompts to choose the installation directory. Launch the installed application and verify core calculations.

To uninstall, use the Windows Start Menu uninstall entry or Windows Settings under Installed apps. Verify that the application is removed.

The Windows build is not code-signed by default. Windows may display a publisher or security warning. Verify the installer source before running it.

## Security

The Electron window disables Node.js integration and enables context isolation and sandboxing. The application loads its local HTML entry point.

Review Electron security guidance and rerun the dependency audit after dependency changes:

```powershell
npm --prefix components/calculator-01 audit
```

## Known Limitations

- Automated tests currently focus on the calculation engine; UI, keyboard, responsive, and installer checks also require manual verification.
- The Windows installer is not code-signed by default.
- The current automated suite does not cover every item in the acceptance criteria.

## Release Checklist

- [ ] Automated tests pass.
- [ ] Dependency audit has no known vulnerabilities.
- [ ] Arithmetic, input, keyboard, and error-handling checks pass.
- [ ] The layout is usable at a 320px viewport width.
- [ ] The Electron app launches with the intended security settings.
- [ ] The Windows installer builds and the installed app launches independently of the development process.
- [ ] Uninstallation is verified.
- [ ] README and acceptance criteria are reviewed.
- [ ] Generated installer/build output is not committed unless explicitly intended.
- [ ] Final changes are committed and pushed to GitHub.
