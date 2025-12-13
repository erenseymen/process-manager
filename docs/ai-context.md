# AI Context

This file contains important context about the codebase for future AI sessions.

## Architecture

### Stats Package Structure (Added 2025-12-14)
The application uses a modular stats package located in `src/stats/` instead of monolithic files.
- `src/stats/__init__.py`: Re-exports main stats classes (`SystemStats`, `GPUStats`, etc.).
- `src/stats/gpu/`: Vendor-specific GPU implementations (`nvidia.py`, `intel.py`, `amd.py`) accessed via a `GPUStats` facade.
- `src/stats/system.py`, `src/stats/ports.py`, `src/stats/io.py`: Dedicated modules for specific subsystems.

### UI Styling (Added 2025-12-14)
CSS is loaded from `data/style.css`.
- Development: Loads from `../data/style.css` relative to source.
- Production: Loads from `/app/share/...` or `/usr/share/...`.
- Fallback: Uses `constants.APP_CSS` (legacy).
