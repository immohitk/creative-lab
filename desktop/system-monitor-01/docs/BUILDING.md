# Building CL System Monitor

## 1. Overview

This guide explains how to build CL System Monitor from its source code on Windows.

The project uses:

- Python 3.14+
- PySide6
- psutil
- PyInstaller
- Inno Setup 6

The application is packaged as a Windows 64-bit onedir distribution, then wrapped in a Windows installer.

## 2. Prerequisites

Install the following:

- 64-bit Python 3.14 or newer.
- Git.
- Inno Setup 6.

The Python project dependencies and build tools must be installed in the project's virtual environment.

## 3. Prepare the Environment

Open PowerShell in the `desktop/system-monitor-01` directory.

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project and development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Install the packaging tool:

```powershell
python -m pip install pyinstaller==6.22.3
```

## 4. Verify the Project

Run the test suite:

```powershell
pytest -q
```

Run tests with warnings treated as errors:

```powershell
pytest -q -W error
```

Both commands should pass before creating a release build.

## 5. Build the Executable

Confirm that the application icon exists:

```powershell
Test-Path .\assets\CL-SM.ico
```

Build the application:

```powershell
pyinstaller --noconfirm --clean --distpath dist --workpath build\pyinstaller\work .\packaging\CLSystemMonitor.spec
```

The packaged application is generated in:

```text
dist/
└── CLSystemMonitor/
    ├── CLSystemMonitor.exe
    └── _internal/
```

The `_internal` directory contains supporting runtime files and bundled resources. Keep the complete distribution directory together.

## 6. Test the Executable

Launch the generated application:

```powershell
Start-Process -FilePath ".\dist\CLSystemMonitor\CLSystemMonitor.exe"
```

Verify:

- The application opens successfully.
- Product branding and application icon are correct.
- Monitoring pages operate correctly.
- Diagnostics display service health.
- The application shuts down cleanly.

## 7. Build the Windows Installer

Confirm that Inno Setup Compiler is available:

```powershell
$compiler = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
Test-Path $compiler
```

Compile the installer:

```powershell
& $compiler .\installer.iss
```

The installer is generated at:

```text
release/
└── CL-System-Monitor-Setup-0.1.0.exe
```

## 8. Test the Installer

Run the generated installer and verify:

- Installation completes successfully.
- The application is installed in the expected directory.
- Start Menu shortcut works.
- Optional desktop shortcut works when selected.
- The application launches successfully.
- Uninstallation completes successfully.

## 9. Build Artifacts

The build process generates these directories:

| Directory  | Purpose                   |
| ---------- | ------------------------- |
| `build/`   | PyInstaller working files |
| `dist/`    | Packaged application      |
| `release/` | Windows installer         |

These are generated artifacts and should not be committed to the source repository.

## 10. Release Identity

| Property           | Value                               |
| ------------------ | ----------------------------------- |
| Product            | CL System Monitor                   |
| Publisher          | Creative Lab                        |
| Version            | 0.1.0                               |
| Executable         | `CLSystemMonitor.exe`               |
| Installer          | `CL-System-Monitor-Setup-0.1.0.exe` |
| Architecture       | Windows x64                         |
| Packaging          | PyInstaller onedir                  |
| Installer compiler | Inno Setup 6                        |
