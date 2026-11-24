# Releasing CL System Monitor

## 1. Purpose

This document defines the release procedure for CL System Monitor.

The goal is to produce a tested Windows x64 application distribution and installer while keeping generated files, development artifacts and private project documents out of the Git repository.

## 2. Release Identity

Current release identity:

| Property        | Value                               |
| --------------- | ----------------------------------- |
| Product         | CL System Monitor                   |
| Publisher       | Creative Lab                        |
| Current version | 0.1.0                               |
| Executable      | `CLSystemMonitor.exe`               |
| Installer       | `CL-System-Monitor-Setup-0.1.0.exe` |
| Architecture    | Windows x64                         |

## 3. Pre-release Checks

Before packaging:

- [ ] Confirm the intended release version.
- [ ] Review application changes.
- [ ] Confirm application branding and icon.
- [ ] Confirm dependencies and build environment.
- [ ] Run the complete test suite.
- [ ] Run tests with warnings treated as errors.
- [ ] Review test failures and warnings.
- [ ] Check source formatting and whitespace errors.

Run:

```powershell
pytest -q
pytest -q -W error
git diff --check
```

Do not proceed with packaging if required checks fail.

## 4. Build the Application

Follow `BUILDING.md` to generate the PyInstaller onedir distribution.

Verify that:

- `CLSystemMonitor.exe` exists.
- Supporting runtime files are present.
- The application icon and bundled resources are included.
- The application launches successfully.
- Monitoring functionality works.
- Shutdown completes cleanly.

## 5. Build the Installer

Compile `installer.iss` using Inno Setup 6.

Expected output:

`release\CL-System-Monitor-Setup-0.1.0.exe`

Verify the installer:

- [ ] Installs successfully.
- [ ] Uses the expected product name and publisher.
- [ ] Installs into the intended directory.
- [ ] Creates the Start Menu shortcut.
- [ ] Offers the optional desktop shortcut.
- [ ] Launches the application when requested.
- [ ] Uninstalls successfully.

## 6. Release Asset Review

Before publishing, verify:

- [ ] Installer filename and version are correct.
- [ ] Executable and installer are built from the same source revision.
- [ ] Installer has been tested on the target Windows environment.
- [ ] No temporary or development files are included.
- [ ] Release notes describe the actual changes.
- [ ] Known limitations are documented.

Keep the complete installer as the primary distribution asset.

## 7. Third-Party Licensing and Redistribution

Before distributing the application or installer:

- [ ] Maintain an inventory of third-party components included in the final application payload.
- [ ] Identify the applicable licence for each bundled component.
- [ ] Include required licence texts, copyright notices, conditions and disclaimers.
- [ ] Verify redistribution permissions for Qt, PySide6 and Shiboken6.
- [ ] Verify applicable Qt LGPL requirements, including shared-library replacement or relinking obligations where applicable.
- [ ] Verify the OpenSSL licence and required notices for the bundled version.
- [ ] Review Python runtime and Microsoft runtime redistribution requirements.
- [ ] Include the applicable psutil and PyInstaller notices.
- [ ] Confirm that build-only and development dependencies have not been incorrectly represented as shipped components.
- [ ] Review the final notices against the actual packaged distribution.
- [ ] Obtain appropriate legal review before public distribution where licensing obligations remain uncertain.

Do not publish the installer while any required redistribution permission, licence notice or compliance obligation remains unresolved.

Record the component inventory, licence sources and review results as release audit evidence.

## 8. Git Repository Review

Review the repository before committing release-related changes.

```powershell
git status --short --untracked-files=all
git diff --check
git diff
```

Ensure generated directories are excluded:

- `build/`
- `dist/`
- `release/`
- `.venv/`
- Python caches
- Temporary test and build files

Only commit intended source files, configuration, assets and approved public documentation.

Private planning and architecture documents must remain excluded unless explicitly approved.

## 9. Release Commit

After testing and reviewing the complete diff:

1. Stage only approved files.
2. Review the staged changes.
3. Create the release commit with an accurate message.
4. Verify the resulting commit and repository status.

Do not amend previous topic commits or rewrite history without explicit approval.

## 10. Publishing

Publish the release assets only after the final repository audit and explicit release approval.

The release should include:

- Version number.
- Release notes.
- Windows x64 installer.
- Any additional approved distribution assets.

The installer should be available from the project's official release location.

## 11. Post-release Verification

After publishing:

- [ ] Confirm the release page is accessible.
- [ ] Confirm the installer asset is available.
- [ ] Verify the published filename and version.
- [ ] Download and test the published installer.
- [ ] Confirm the installed application launches correctly.

Record any release issues for the next development cycle.
