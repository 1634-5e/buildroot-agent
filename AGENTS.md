# AGENTS.md

This file contains guidelines for agentic coding assistants working on this buildroot-agent repository.

## 目录结构
- agent: buildroot-agent
- server: buildroot-server
- web: buildroot-web

## 版本信息

### 运行环境 (buildroot-agent)
- 系统: buildroot2015.08.1
- gcc: 4.9
- openssl: 1.1.1
- cmake: 2.8.12.2

### 技术栈 (buildroot-agent)
- 通信: tcp socket

### 开发依赖 (buildroot-web)
- vue: ^3.4.21
- vue-tsc: ^2.0.7
- xterm
- shacdn/ui
- tailwindcss

## Build Commands

### C/CMake (buildroot-agent)
- `cd buildroot-agent && cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake` - Configure for cross-compilation
- `cd buildroot-agent && cmake --build build` - Build the agent binary to `build/bin/buildroot-agent`
- `cd buildroot-agent && rm -rf build` - Clean build artifacts
- `cd buildroot-agent && cmake --install build --prefix /path` - Install to target directory
- `cd buildroot-agent && cmake --build build --target release` - Build release version with stripped symbols
- `cd buildroot-agent && cpack` - Create tarball package
- `./buildroot-agent/scripts/build.sh` - Quick build script
- `./buildroot-agent/scripts/release.sh` - Quick release build
- `./buildroot-agent/scripts/install.sh /path` - Quick install script

**Options:**
- `-DCMAKE_BUILD_TYPE=Debug` - Build with debug symbols
- `-DSTATIC_LINK=ON` - Build with static linking

### Python (buildroot-server)
- `cd buildroot-server && python3 server_example.py` - Run server
- `pip install websockets` - Install dependencies
- Use `ruff check` or `ruff format` if available for linting/formatting

## Code Style Guidelines

### C Code (buildroot-agent)
- **Naming conventions**:
  - Types: `snake_case_t` suffix (e.g., `agent_context_t`, `system_status_t`)
  - Enums: `ENUM_NAME_CONSTANT` with `_t` suffix for enum type
  - Macros: `UPPER_CASE_WITH_UNDERSCORES` (e.g., `DEFAULT_SERVER_ADDR`)
  - Functions: `snake_case()` (e.g., `agent_init()`, `set_log_level()`)
  - Global variables: `g_prefix_` (e.g., `g_agent_ctx`, `g_log_level`)
  - Static functions: Mark with `static` keyword
- **File organization**: Headers in `include/`, sources in `src/`
- **Comments**: Use Chinese for documentation/comments, English for code
- **Logging**: `LOG_INFO("message", args...)`, `LOG_DEBUG()`, `LOG_WARN()`, `LOG_ERROR()`
- **Error handling**: Return -1 on error, 0 on success; check return values
- **Headers**: Include project header `"agent.h"` before standard headers where appropriate
- **Memory**: Use `calloc()` for allocation, always `free()` after use
- **Threading**: Use `pthread_mutex_t` for synchronization, check return values

### Python Code (buildroot-server)
- **Imports**: Built-ins first, then third-party, then local modules
- **Naming**:
  - Classes: `PascalCase` (e.g., `FileTransferSession`, `MessageType`)
  - Functions/variables: `snake_case`
  - Constants: `UPPER_CASE`
- **Type hints**: Use `typing` module (Dict, Set, Optional, List, Tuple, Any)
- **Data classes**: Use `@dataclass` decorator with `field(default_factory=...)`
- **Logging**: Configure with `logging.basicConfig()`, use `logger.info()`, `logger.error()`
- **Async**: Use `asyncio`, `async/await` for WebSocket operations
- **Error handling**: Use try/except, catch specific exceptions where possible

## Testing

No formal test suite exists yet. To run tests:
- For Python: `python -m pytest` (if tests are added)
- For TypeScript: Add test commands to package.json if needed

## Cross-Compilation

The buildroot-agent uses CMake with a toolchain file for cross-compilation:
```bash
cd buildroot-agent
cmake -B build -DCMAKE_TOOLCHAIN_FILE=cmake/arm-buildroot.cmake
cmake --build build
```

The toolchain file `cmake/arm-buildroot.cmake` configures:
- Cross-compiler: arm-buildroot-linux-uclibcgnueabi-gcc
- Sysroot: /workspaces/buildroot-agent/package/armhf-sysroot
- Library search paths for OpenSSL, pthread, libutil

## Protocol Compatibility

Message types are defined in both C (`include/agent.h`) and TypeScript (`src/types/index.ts`):
- Hexadecimal values: `0x01`, `0x10`, `0xF0`
- Keep them synchronized when modifying protocol
- C uses `msg_type_t` enum, TS uses `MessageType` enum
