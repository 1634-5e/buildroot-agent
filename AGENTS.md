# AGENTS.md

This file contains guidelines for agentic coding assistants working on this buildroot-agent repository.

## Build Commands

### C/Makefile (buildroot-agent)
- `make` - Build the agent binary to `bin/buildroot-agent`
- `make clean` - Clean build artifacts (obj/, bin/)
- `make install DESTDIR=/path` - Install to target directory
- `make uninstall` - Remove installed files
- `make release` - Build release version with stripped symbols
- `make package` - Create tarball package in dist/
- `make DEBUG=1` - Build with debug symbols (-O0 -g3)
- `make STATIC=1` - Build with static linking
- `make CC=arm-linux-gnueabihf-gcc` - Cross-compile for ARM
- `make help` - Show all available targets

### Python (buildroot-server)
- `cd buildroot-server && python3 server_example.py` - Run server
- `pip install websockets` - Install dependencies
- Use `ruff check` or `ruff format` if available for linting/formatting

### TypeScript/React (buildroot-web)
- `cd buildroot-web && npm run dev` - Start development server on port 3000
- `cd buildroot-web && npm run build` - Production build (typecheck + Vite build)
- `cd buildroot-web && npm run preview` - Preview production build
- `cd buildroot-web && npm run lint` - Run ESLint

## Code Style Guidelines

### C Code (buildroot-agent)
- **Naming conventions**:
  - Types: `snake_case_t` suffix (e.g., `agent_context_t`, `system_status_t`)
  - Enums: `ENUM_NAME_CONSTANT` with `_t` suffix for enum type
  - Macros: `UPPER_CASE_WITH_UNDERSCORES` (e.g., `DEFAULT_SERVER_URL`)
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

### TypeScript/React (buildroot-web)
- **Naming**:
  - Components: `PascalCase` (e.g., `Terminal`, `FileExplorer`)
  - Functions/variables: `camelCase`
  - Types/interfaces: `PascalCase` (e.g., `Device`, `SystemStatus`)
  - Enums: `PascalCase` with `UPPER_CASE` members
- **Imports**: Use `@/` alias for absolute imports from `src/`
- **Components**: Functional components with hooks, no class components
- **State management**: Use Zustand via `useAppStore()` hook
- **Context**: Use `useWebSocket()` for WebSocket operations
- **TypeScript**: Strict mode enabled, all files must type-check
- **Linting**: ESLint with React rules, fix errors before committing
- **Props**: Define interfaces for component props
- **Side effects**: Use `useEffect()` with proper dependency arrays
- **Refs**: Use `useRef()` for DOM elements and mutable values

## Testing

No formal test suite exists yet. To run tests:
- For Python: `python -m pytest` (if tests are added)
- For TypeScript: Add test commands to package.json if needed

## Cross-Compilation

For embedded targets, specify the cross-compiler:
```bash
make CC=arm-linux-gnueabihf-gcc STRIP=arm-linux-gnueabihf-strip
```

## Protocol Compatibility

Message types are defined in both C (`include/agent.h`) and TypeScript (`src/types/index.ts`):
- Hexadecimal values: `0x01`, `0x10`, `0xF0`
- Keep them synchronized when modifying protocol
- C uses `msg_type_t` enum, TS uses `MessageType` enum
