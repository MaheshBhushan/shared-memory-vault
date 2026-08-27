# Configuration

The installer writes one JSON file:

- Linux: `$XDG_CONFIG_HOME/shared-memory-vault/config.json`
- Windows: `%APPDATA%\SharedMemoryVault\config.json`

Fields: `vault_path`, `state_path`, `runtime_path`, `endpoint`, `host_identifier`, `enabled_adapters`, and `synthesis_provider`. Set `SHARED_MEMORY_CONFIG` to isolate or override configuration. Missing optional provenance stays null; it is never fabricated.
