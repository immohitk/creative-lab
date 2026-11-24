# Installation Guide

## CL System Monitor

**Version:** 0.1.0
**Publisher:** Creative Lab
**Platform:** Windows 10/11, 64-bit

## 1. System Requirements

- 64-bit Windows operating system.
- Administrator permission for installation.
- Approximately 200 MB of free disk space recommended.

Python is not required when installing through the packaged installer.

**Compatibility note:** Windows 10 has been tested. Windows 11 compatibility has not yet been independently verified.

## 2. Download

Download the installer:

`CL-System-Monitor-Setup-0.1.0.exe`

The installer is distributed through the Creative Lab repository's release assets.

## 3. Installation

1. Locate and run `CL-System-Monitor-Setup-0.1.0.exe`.
2. Approve the Windows User Account Control prompt.
3. Follow the Inno Setup installation wizard.
4. The application is installed in:

   `C:\Program Files\CL System Monitor`

5. Complete the installation.

The installer creates a Start Menu shortcut. It also offers an optional desktop shortcut, which is unchecked by default.

The installer provides an option to launch CL System Monitor after installation.

## 4. Launching the Application

You can launch CL System Monitor using either:

- The Start Menu shortcut named **CL System Monitor**.
- The desktop shortcut, if you selected that option during installation.

## 5. Uninstallation

To uninstall CL System Monitor:

1. Close the application.
2. Open Windows Settings.
3. Navigate to **Apps → Installed apps**.
4. Find **CL System Monitor**.
5. Select Uninstall and follow the prompts.

You can also use the application's registered Windows uninstaller.

## 6. Standalone Distribution

The standalone application build is generated as an onedir package.

The executable is:

`CLSystemMonitor.exe`

Keep the complete `CLSystemMonitor` distribution directory together. Do not copy or distribute only the executable, because it depends on supporting runtime files and resources included in that directory.

## 7. Troubleshooting

### Windows displays a security warning

Windows may display a security or reputation warning when running an installer that is not signed with a trusted code-signing certificate.

Only proceed when the installer was obtained from a trusted Creative Lab release source.

### The application does not start

- Confirm that the installation completed successfully.
- Try launching the application again from the Start Menu.
- Check whether Windows Security or endpoint protection has blocked application files.

### Monitoring information is unavailable

Some Windows process and system information may be restricted by operating-system permissions or unavailable for individual processes. This can result in partial monitoring information.

## 8. Privacy

CL System Monitor is designed as a local-first desktop application.

System monitoring information is collected locally. The application does not require a user account or cloud service for its normal operation.
