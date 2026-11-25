# Releasing CL System Monitor

## 1. Purpose

This document defines the release procedure for CL System Monitor.

The goal is to produce a tested Windows x64 application distribution and installer while keeping generated files, development artifacts and private project documents out of the Git repository.

### Current Release Status

CL System Monitor development is complete.

However, development completion and public distribution approval are separate milestones.

**Public binary distribution is currently on hold** pending review of applicable licensing and redistribution requirements.

Building, testing or locally installing the application does not, by itself, authorize public distribution.



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

Successful local installation is a development verification result, not public release approval.

## 6. Release Asset Review

Before publication, verify:

- [ ] Installer filename and version are correct.
- [ ] Executable and installer are built from the same source revision.
- [ ] Installer has been tested on the target Windows environment.
- [ ] No temporary or development files are included.
- [ ] Release notes describe the actual changes.
- [ ] Known limitations are documented.
- [ ] Required licence and third-party notice materials are included.
- [ ] Release candidate checksums are generated and recorded.
- [ ] Applicable licensing and redistribution requirements have been reviewed and resolved.

Keep the complete installer as the primary distribution asset.

Do not publish release assets while any mandatory release or redistribution requirement remains unresolved.

## 7. Third-Party Licensing and Redistribution

Third-party licensing and redistribution review is a mandatory condition for public binary distribution.



The review must cover:

- [ ] Inventory every third-party component included in the final application payload.
- [ ] Record component names, versions, origins and bundled locations.
- [ ] Identify the applicable licence for each shipped component.
- [ ] Obtain and include required licence texts, copyright notices, conditions and disclaimers.
- [ ] Verify redistribution permissions for Qt, PySide6 and Shiboken6.
- [ ] Review applicable Qt LGPL requirements, including shared-library replacement or relinking obligations where applicable.
- [ ] Review source-code availability, replacement capability and relevant user restrictions where required.
- [ ] Verify Microsoft runtime redistribution requirements for the exact bundled runtime files.
- [ ] Verify the OpenSSL licence and required notices for the bundled version.
- [ ] Review Python runtime redistribution requirements.
- [ ] Include applicable psutil and PyInstaller notices and exceptions.
- [ ] Distinguish shipped runtime components from build-only and development dependencies.
- [ ] Compare the final third-party notices against the actual packaged distribution and installer.
- [ ] Record unresolved licensing questions and obtain appropriate legal review where necessary.

The presence of `THIRD-PARTY-NOTICES.md` alone does not establish that all redistribution obligations have been satisfied.

Record the component inventory, licence evidence, review decisions and supporting materials as release audit evidence.

**Release-blocking condition:** Do not publish the installer while any required redistribution permission, licence notice, source-code obligation or other applicable compliance requirement remains unresolved.



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

Publishing is permitted only after:

- All applicable release and redistribution requirements have been satisfied.
- Licensing and redistribution obligations have been reviewed and resolved.
- Required notices and supporting materials have been prepared.
- Final release candidate verification has passed.
- The final repository audit has been completed.
- Explicit release approval has been obtained.

The release should include:

- Version number.
- Release notes.
- Approved Windows x64 installer.
- Required third-party licence and notice materials.
- Source-code or other supporting materials where required.
- SHA-256 checksums for published assets.

The installer should be available from the project's official release location.

Do not treat a locally generated installer as an approved public release asset.

## 11. Post-release Verification

After publishing:

- [ ] Confirm the release page is accessible.
- [ ] Confirm the installer asset is available.
- [ ] Verify the published filename and version.
- [ ] Verify published SHA-256 checksums against the approved release candidate.
- [ ] Download and test the published installer.
- [ ] Confirm the installed application launches correctly.
- [ ] Confirm the published notices and supporting materials are accessible.
- [ ] Record the final release commit and published asset details.

Record any release issues for the next development cycle.
