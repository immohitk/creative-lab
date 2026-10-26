# C01 — Acceptance Criteria

## 1. Arithmetic

| Test       | Expected Result |
| ---------- | --------------- |
| 12 + 8     | 20              |
| 15 - 7     | 8               |
| 6 \* 4     | 24              |
| 20 / 5     | 4               |
| 0.5 + 0.25 | 0.75            |
| -5 + 2     | -3              |
| 2 + 3 \* 4 | 14              |

## 2. Input and State

- AC resets the display and calculation state.
- Backspace removes the last entered character.
- Backspace on empty input does not crash.
- Repeated decimal points are rejected or safely normalized.
- Incomplete expressions do not crash the app.
- After a result, an operator continues from that result.
- After a result, a new digit starts a fresh calculation.
- Repeated equals behaves consistently and does not corrupt state.

## 3. Errors

- Division by zero produces clear, readable feedback.
- Infinity and NaN are not shown as normal user-facing results.
- Invalid input does not execute arbitrary code.
- The user can recover from an error and start a new calculation.
- Normal interactions do not produce uncaught application errors.

## 4. Keyboard

- Digits and the decimal point enter values.
- +, -, \* and / select arithmetic operations.
- Enter and = calculate.
- Backspace deletes the last entered character.
- Escape clears the current calculation.
- Keyboard input and on-screen buttons use the same calculation logic.

## 5. Responsive Design and Accessibility

- At a 320px viewport width, the page has no unintended horizontal scrolling.
- Calculator controls remain visible and usable on mobile and desktop.
- All controls have accessible names.
- Keyboard focus is visible and follows a sensible order.
- Results and errors are readable and are not communicated by colour alone.

## 6. Desktop Application and Installer

- The Electron app launches successfully.
- Renderer code does not receive unnecessary Node.js access.
- The app works without a development server running.
- The Windows installer builds successfully.
- The installed application launches and passes core calculator tests.
- Uninstallation completes successfully.
- Windows security warnings, if any, are investigated; no warning-free guarantee is assumed.

## 7. Documentation and Release

- README describes features, requirements, setup, tests and build commands.
- README explains installation, uninstall, keyboard controls and known limitations.
- Generated build output, caches, local secrets and installer binaries are not committed by default.
- All required tests pass before the final GitHub push.

## Release Rule

Do not mark C01 as complete until the functional tests, desktop packaging checks, installer lifecycle checks and documentation checks have been verified.
