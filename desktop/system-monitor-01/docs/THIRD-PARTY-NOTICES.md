# Third-Party Notices

**Product:** CL System Monitorq
**Version:** 0.1.0
**Publisher:** Creative Lab
**Platform:** Windows x64

This document records third-party software identified during the packaging and redistribution review of CL System Monitor.

The licences and notices below apply to their respective components, not automatically to the entire application.

## 1. psutil

- **Component:** psutil
- **Version:** 7.2.2
- **Usage:** System and process monitoring
- **Licence:** BSD 3-Clause
- **Copyright:** Copyright (c) 2009, Jay Loden, Dave Daeschler, Giampaolo Rodola

The BSD 3-Clause licence permits redistribution in source and binary forms, subject to its conditions.

The complete licence text, including its copyright notice, conditions and disclaimer, must accompany binary distributions.

The names of the authors and contributors must not be used to endorse or promote derived products without prior written permission.

## 2. Qt and Qt for Python

- **Qt runtime version:** 6.12.0
- **PySide6:** 6.12.0
- **PySide6 Addons:** 6.12.0
- **PySide6 Essentials:** 6.12.0
- **PySide6 PDF:** 6.12.0.140
- **Shiboken6:** 6.12.0
- **Declared licence alternatives:** LGPL-3.0-only, GPL-2.0-only or GPL-3.0-only

The installed Python package metadata identifies these licence alternatives and includes a commercial licensing reference.

CL System Monitor is being evaluated for redistribution under the LGPL route.

The following matters remain subject to verification:

- Obtain and include the applicable LGPL licence text and required copyright notices.
- Identify the corresponding source code and source availability arrangements for the redistributed components.
- Verify the applicable requirements for shared-library replacement and reverse engineering for debugging modifications.
- Verify the redistribution conditions for PySide6 bindings, Shiboken6, Qt libraries and bundled Qt plugins.
- Test whether users can replace the relevant libraries with modified compatible versions and run the application.
- Review the final installer and documentation against the applicable licence terms.

The presence of separate Qt DLLs and Python extension modules in the onedir distribution does not, by itself, establish LGPL compliance.

The installed `LicenseRef-Qt-Commercial.txt` is a commercial licensing reference. It is not the LGPL licence text.

**Status: Pending licensing and redistribution review.**

## 3. OpenSSL

- **Version identified:** OpenSSL 3.0.19
- **Bundled components:** `libcrypto-3.dll`, `libssl-3.dll`, `_ssl.pyd`, `_hashlib.pyd`
- **Licence identified:** Apache License 2.0 for OpenSSL 3.0 and later

The OpenSSL libraries were identified in the Python runtime distribution and are included in the packaged application.

The applicable Apache 2.0 licence text and required copyright and attribution notices must be included with the redistribution.

The final notices must be checked against the actual bundled OpenSSL files and their source distribution.

**Status: Licence identified; notice integration and final verification pending.**

## 4. PyInstaller

- **Version:** 6.22.3
- **Usage:** Application packaging
- **Core licence:** GNU General Public License version 2 or later
- **Bootloader:** GPL with PyInstaller Bootloader Exception
- **Runtime hooks:** Apache License 2.0

PyInstaller's Bootloader Exception grants permission to embed its compiled bootloader and related files into combinations with other programs and distribute those combinations without restrictions arising from use of those files.

The build analysis identifies the following runtime components:

- `pyi_rth_inspect`
- `pyi_rth_pyside6`
- `_pyi_rth_utils.qt`
- `_pyi_rth_utils`

The inspected files declare Apache License 2.0.

The PyInstaller licensing file also identifies additional runtime modules and their respective licensing terms.

The applicable licence texts and notices must be retained with the release materials. Build-only components must be distinguished from components actually redistributed.

**Status: Licence terms reviewed; final notice integration pending.**

## 5. Python Runtime and Microsoft Runtime

The packaged application includes Python runtime files and Microsoft runtime libraries.

The Python distribution licence identifies Microsoft Distributable Code and describes restrictions applicable to its redistribution.

The packaged application includes Microsoft runtime DLLs, including:

- `VCRUNTIME140.dll`
- `VCRUNTIME140_1.dll`
- `MSVCP140.dll`
- `MSVCP140_1.dll`
- `MSVCP140_2.dll`

The applicable Microsoft redistribution terms, notices and distribution permissions must be verified for the exact files included in the final installer.

**Status: Pending redistribution-terms verification.**

## 6. Distribution Review

Before publishing a release:

- [ ] Confirm the final bundled component inventory.
- [ ] Include the complete applicable licence texts.
- [ ] Include required copyright and attribution notices.
- [ ] Complete the Qt/PySide6/Shiboken LGPL review.
- [ ] Verify Qt library replacement and user modification requirements.
- [ ] Complete the OpenSSL notice review.
- [ ] Complete the Microsoft runtime redistribution review.
- [ ] Verify the psutil BSD 3-Clause notice.
- [ ] Verify the PyInstaller bootloader exception and Apache notices.
- [ ] Review the final installer rather than relying only on development-environment metadata.
- [ ] Obtain legal review where necessary.

## 7. Important Disclaimer

This document is a technical inventory and release-control record. It is not legal advice, a warranty of licence compliance, or a grant of rights beyond those provided by the respective third-party licences.

Distribution must not proceed while required licensing permissions, notices or compliance obligations remain unresolved.
