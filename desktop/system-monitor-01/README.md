# CL System Monitor

**A local-first Windows desktop application for real-time system monitoring and application-health diagnostics.**

CL System Monitor is a read-only Windows desktop application developed by Creative Lab. It provides visibility into CPU, memory, storage, network and running processes through a graphical dashboard, resource-history charts and monitoring-health diagnostics.

## Project Information

| Field              | Details                                                     |
| ------------------ | ----------------------------------------------------------- |
| Project ID         | D01                                                         |
| Product Name       | CL System Monitor                                           |
| Publisher          | Creative Lab                                                |
| Category           | Windows Desktop Application                                 |
| Version            | 0.1.0                                                       |
| Target Platform    | Windows 10/11, x64                                          |
| Python Requirement | Python 3.14+                                                |
| Development Status | Development roadmap complete; release readiness in progress |

## Features

### 1. System Overview

- Live CPU utilization.
- Physical memory utilization.
- Combined disk-volume utilization.
- Network download and upload throughput.
- Monitoring-service status and data freshness.

### 2. CPU Monitoring

- Overall CPU utilization.
- Logical processor count.
- Per-core utilization.
- CPU utilization history chart.

### 3. Memory Monitoring

- Used, available and free physical memory.
- Swap usage and utilization.
- Memory utilization history chart.

### 4. Disk and Storage Monitoring

- Combined storage capacity, used space and free space.
- Individual volume and partition information.
- Device, mount point and filesystem details.
- Per-volume capacity and utilization.
- Combined storage-utilization history.

**Current limitation:** Disk read/write throughput is not currently collected.

### 5. Network Monitoring

- Download and upload throughput.
- Per-interface received and sent traffic counters.
- Individual network-interface measurements.
- Download and upload history charts.
- Interface counter-reset and measurement-baseline handling.

### 6. Process Monitoring

- Running process inventory.
- Process ID, name, CPU usage, memory usage and status.
- Executable path when accessible.
- Windows service associations when available.
- Process classification:
  - System
  - Service
  - Application
  - Unclassified
- Search by process name, PID or executable path.
- Category filtering.
- Sorting by name, PID, category, CPU, memory, status or executable path.
- Top CPU-consuming and memory-consuming processes.

Process classification includes confidence and explanatory reasons. The inventory is read-only and displays a maximum of 250 filtered processes.

### 7. Performance History

- CPU, memory, disk and network metric histories.
- Timestamped history samples.
- Bounded in-memory history buffers.
- Up to 120 samples per metric.

**Current limitation:** History is held in memory and is not persisted between application sessions. Configurable retention and historical exports are not implemented.

### 8. Monitoring Diagnostics

- Overall monitoring-health severity.
- Coordinator status and error information.
- Individual monitoring-service health.
- Worker states and measurement availability.
- Data freshness and last-update information.
- Consecutive collection failures.
- Sampling interval and service revision information.

Diagnostics describe the health of the application's monitoring services. They are not malware scans, security assessments, hardware benchmarks or predictive failure analysis.

### 9. System Information

The application collects a system profile covering:

- Operating system.
- Machine information.
- Processor.
- Memory.
- Storage.
- Network interfaces.

Collection takes place in a background thread, separately from continuous resource monitoring.

## Technology Stack

| Technology   | Purpose                          |
| ------------ | -------------------------------- |
| Python 3.14+ | Application logic                |
| PySide6      | Desktop graphical interface      |
| psutil       | System and process monitoring    |
| pytest       | Automated testing                |
| PyInstaller  | Standalone application packaging |
| Inno Setup   | Windows installer generation     |

## Installation

### Windows Installer

Download and run:

`CL-System-Monitor-Setup-0.1.0.exe`

The installer provides:

- CL System Monitor application installation.
- Start Menu shortcut.
- Optional desktop shortcut.
- Uninstaller registration.
- Optional launch after installation.

The installer is configured for 64-bit Windows.

### Standalone Application

The packaged application can also be launched directly:

`CLSystemMonitor.exe`

The standalone distribution includes the application runtime and required dependencies.

## Development Setup

### Requirements

- Windows 10/11, 64-bit.
- Python 3.14 or newer.
- Git.

### Setup

Clone the repository and enter the project directory:

```powershell
git clone https://github.com/immohitk/creative-lab
cd creative-lab/desktop/system-monitor-01
```

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the project in editable mode:

```powershell
python -m pip install -e .
```

Install development dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Launch the application:

```powershell
python -m system_monitor
```

Alternatively, use the installed command:

```powershell
system-monitor
```

### Run Tests

```powershell
pytest -q
```

Run tests with warnings treated as errors:

```powershell
pytest -q -W error
```

## Privacy and Operating Principles

CL System Monitor follows a local-first, read-only monitoring approach.

- Monitoring and system-information collection take place locally.
- No account is required.
- No application-level cloud upload or external analytics integration is implemented.
- Process information is collected for observation, not process control.
- The application does not terminate, suspend or modify processes.
- The application does not intentionally modify Windows system configuration.
- Monitoring results are presented with availability and error states rather than treating unavailable readings as zero.

Some process and system information may be inaccessible because of Windows permissions or process protection. Such cases can result in partial or unavailable measurements.

## Current Limitations

The following capabilities are not implemented in version 0.1.0:

- Persistent performance history or SQLite storage.
- CSV, JSON or HTML report exports.
- Configurable history retention.
- User-facing sampling-interval settings.
- User-configurable diagnostic thresholds.
- Light/dark theme selection.
- Disk read/write throughput monitoring.
- Process termination or management controls.
- Predictive diagnostics or security scanning.

## Development Roadmap

The original 17-topic CL System Monitor development roadmap is formally complete.

| Topics | Area                                                                                 | Status   |
| ------ | ------------------------------------------------------------------------------------ | -------- |
| 01–14  | Product foundation, architecture, monitoring, interface, diagnostics and reliability | Complete |
| 15     | Automated Testing & Compatibility Verification                                       | Complete |
| 16     | Packaging, Installer, Documentation & Release Assets                                 | Complete |
| 17     | Final Repository Audit, Release Commit & Push                                        | Complete |

All 17 development topics have been implemented, tested and closed.

### Release Status

The original 17-topic development roadmap is complete.

Public binary distribution is currently on hold pending review of applicable third-party licensing and redistribution requirements.
## Project Structure

```text
system-monitor-01/
├── assets/
├── src/
│   └── system_monitor/
│       ├── application/
│       ├── collectors/
│       ├── coordinator/
│       ├── models/
│       ├── presentation/
│       ├── services/
│       └── workers/
├── tests/
├── installer.iss
├── pyproject.toml
└── README.md
```

## License

CL System Monitor is licensed under the MIT License.

Copyright (c) 2026 Mohit Kumar.

See the root Creative Lab repository `LICENSE` file for the complete license terms.
