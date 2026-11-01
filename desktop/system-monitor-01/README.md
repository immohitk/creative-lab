# Creative Lab System Monitor

A Windows desktop application for real-time system monitoring, performance history, and evidence-based diagnostics.

## Project Information

| Field | Details |
|---|---|
| Project ID | D01 |
| Project Name | Creative Lab System Monitor |
| Category | Desktop Application |
| Target Platform | Windows |
| Primary Audience | Everyday Windows users, power users, and developers |
| Development Status | Scope and research |
| Version | V1 (Planned) |

## Product Vision

Help users understand what their computer is doing, identify unusual resource usage, investigate performance problems, and generate useful diagnostic reports.

The application will provide a simple experience by default while allowing users to access deeper technical information when needed.

## Core Product Principles

- **Clarity:** Present important information first and advanced details progressively.
- **Evidence-based diagnostics:** Explain warnings using actual measurements, thresholds, and duration.
- **Local-first privacy:** Keep monitoring data and history on the user's computer.
- **Lightweight operation:** Minimize the application's CPU, memory, and storage overhead.
- **Honest reporting:** Distinguish between zero, unavailable, unsupported, and access-denied readings.
- **Read-only monitoring:** Observe and explain system activity without modifying processes or system configuration.

## Planned V1 Features

### 1. System Overview
- Live CPU, memory, disk, and network summaries.
- Recent resource usage trends.
- Top resource-consuming processes.
- Evidence-based system status indicators.

### 2. CPU Monitoring
- Overall CPU utilization.
- Per-core utilization.
- Frequency information where available.
- Live and historical usage charts.

### 3. Memory Monitoring
- Total and used physical memory.
- Available memory.
- Swap/page-file information where supported.
- Memory usage history.

### 4. Disk and Storage Monitoring
- Mounted volumes and storage capacity.
- Used and available space.
- Read/write activity where supported.
- Storage activity history.

### 5. Network Monitoring
- Network interface information.
- Upload and download speeds.
- Cumulative network traffic.
- Interface-level traffic history.

### 6. Process Monitoring
- Running process list.
- CPU and memory usage.
- Process search, filtering, and sorting.
- Recent resource peaks where supported.

### 7. Performance History
- Configurable sampling interval.
- Historical resource timelines.
- Configurable data retention.
- Local history storage.

### 8. Performance Diagnostics
- Rule-based performance warnings.
- Warning severity and triggering evidence.
- Duration of detected conditions.
- Suggested investigation steps.

### 9. Diagnostic Reports
- Local HTML reports.
- CSV data exports.
- System summary and resource history.
- Top processes and detected warnings.

### 10. Settings and User Experience
- Refresh interval.
- Diagnostic thresholds.
- History retention.
- Light and dark themes.
- Application preferences.

## Proposed Technology Stack

| Technology | Planned Purpose |
|---|---|
| Python | Application logic |
| PySide6 | Desktop graphical interface |
| psutil | Primary system information and monitoring library |
| SQLite | Local performance history |
| pytest | Automated testing |
| Windows packaging tools | Application distribution |

Final dependency versions and architecture will be established during the architecture phase.

## Privacy and Safety

- No account requirement.
- No automatic cloud uploads.
- No automatic collection for external analytics.
- No process termination or modification.
- No system-setting modification.
- Ordinary monitoring should not require administrator privileges.
- Users control diagnostic report exports.

## Development Roadmap

Development follows the approved 17-topic D01 roadmap:

1. Product Scope, Requirements & Research
2. Technical Architecture & Repository Design
3. Repository Foundation & Development Environment
4. System Information & Hardware Identification
5. CPU Monitoring Service
6. Memory Monitoring Service
7. Disk & Storage Monitoring Service
8. Network Monitoring Service
9. Process Monitoring Service
10. Monitoring Coordinator, Background Workers & History Storage
11. Main Window & Dashboard Foundation
12. Monitoring Panels, Charts & Data Presentation
13. Diagnostics, Settings & User Experience
14. Diagnostic Reports, Reliability, Performance & Error Handling
15. Automated Testing, Windows Compatibility & QA
16. Packaging, Installer, Documentation & Release Assets
17. Final Repository Audit, Release Commit & Push

## Project Status

**Current phase:** Topic 01 — Product Scope, Requirements & Research.

This repository document describes the planned product. It does not indicate that the features have already been implemented or verified.

## License

See the root Creative Lab repository license.
