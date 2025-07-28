# Gcore MCP Server
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server.svg?type=shield)](https://app.fossa.com/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server?ref=badge_shield)


MCP (Model Context Protocol) server for Gcore API. This server provides tools for interacting with Gcore Cloud API via LLM assistants.

## Usage

**Note:** As we have multiple resources available, providing all of them at once to the LLM can overwhelm it and lead to confusion among the tools. It is recommended to specify only the necessary resources for your task to ensure optimal performance and clarity.

### Integration with Cursor IDE

Add the server to your Cursor IDE configuration file (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "gcore-mcp-server": {
      "command": "uvx",
      "args": ["--from", "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git", "gcore-mcp-server"],
      "env": {
        "GCORE_API_KEY": "4***1",
        "GCORE_TOOLS": "instances,management,cloud.gpu_baremetal_clusters.*"
      }
    }
  }
}
```

**Note:** You can find instructions on how to obtain a Gcore API Key [here](https://gcore.com/docs/account-settings/create-use-or-delete-a-permanent-api-token).

**Optional variables:**
- `GCORE_API_URL`: "https://api.gcore.com",
- `GCORE_CLOUD_PROJECT_ID`: "1",
- `GCORE_CLOUD_REGION_ID`: "76",
- `GCORE_CLIENT_ID`: "2",

## Configuration

### Tool Selection

The server uses a **unified configuration approach** via the `GCORE_TOOLS` environment variable. This single variable can contain a mix of predefined toolset names and custom patterns:

```bash
# Mixed toolsets and patterns
export GCORE_TOOLS="instances,management,cloud.gpu_baremetal_clusters.*,dns.records.create"

# Only toolsets
export GCORE_TOOLS="instances,management"

# Only patterns  
export GCORE_TOOLS="cloud.*,waap.*"

# Default behavior (if not set)
# Uses "management,instances" toolsets for HTTP mode, "management" for stdio
```

#### Configuration Modes

1. **Default Mode** (no configuration)
   - HTTP transport: Uses `management,instances` toolsets
   - stdio transport: Uses `management` toolset

2. **Toolset Mode** (predefined tool collections)
   - Use predefined toolset names: `instances`, `management`, `ai_ml`, etc.
   - Example: `GCORE_TOOLS="instances,management"`

3. **Pattern Mode** (custom tool filtering)
   - Use wildcard patterns to match tool names from the Gcore SDK
   - Exact matches: `cloud.instances.create`, `dns.records.delete`
   - Wildcard matches: `cloud.*`, `waap.*`, `cloud.gpu_baremetal_clusters.*`
   - Example: `GCORE_TOOLS="cloud.instances.*,waap.*"`

4. **Combined Mode** (toolsets + patterns)
   - Mix predefined toolsets with custom patterns
   - Toolset definitions have priority over pattern matches
   - Example: `GCORE_TOOLS="instances,cloud.gpu_baremetal_clusters.*"`

#### Available Toolsets

The system includes several predefined toolsets for common workflows:

- **`management`**: Core account and project management
- **`instances`**: Virtual machine operations  
- **`volumes`**: Storage management
- **`networks`**: Network and security management
- **`baremetal`**: Bare metal server operations
- **`gpu_baremetal`**: GPU cluster management
- **`ai_ml`**: AI/ML inference services
- **`cleanup`**: Deletion and cleanup operations
- **`list`**: List/read-only operations

#### Pattern Syntax

Patterns support wildcard matching using `*`:

- **Exact matches**: `cloud.instances.create` matches only that specific method
- **Wildcard matches**: `cloud.instances.*` matches all instance methods
- **Broad wildcards**: `cloud.*` matches all cloud service methods
- **Service-specific**: `waap.*` matches all WAAP methods

#### Priority System

When using combined mode:
1. **Toolset tools** are included first (highest priority)
2. **Pattern-matched tools** are added second
3. **Duplicates are removed** while preserving order
4. Toolset definitions take precedence over pattern matches

#### Examples

```bash
# Development: Get specific tools for testing
export GCORE_TOOLS="cloud.instances.create,cloud.instances.delete,cloud.volumes.create"

# Full cloud management
export GCORE_TOOLS="management,instances,volumes,networks"

# GPU cluster operations with custom additions  
export GCORE_TOOLS="gpu_baremetal,cloud.instances.create,waap.*"

# All services with wildcard
export GCORE_TOOLS="cloud.*,waap.*"

# Minimal setup
export GCORE_TOOLS="instances"
```

## Running in a Temporary Environment (One-off Execution)

If you want to run the server without installing it persistently (e.g., for a quick test or a single use), you can use `uvx`. This command fetches the package, runs the specified script in a temporary environment, and then discards the environment.


To run the latest version from the main branch:
```bash
uvx --from "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git" gcore-mcp-server
```

To run a specific version (e.g., `v0.1.1`):
```bash
uvx --from "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git@v0.1.1" gcore-mcp-server
```
Remember to set any required environment variables (like `GCORE_API_KEY`, `GCORE_TOOLS`, etc.) before running the command.

## Persistent Installation (Installing as a Tool)

For detailed installation instructions for `uv`, please refer to the [official `uv` installation guide](https://docs.astral.sh/uv/getting-started/installation/).

You can install `gcore-mcp-server` as a command-line tool using `uv`. This makes the command available globally in your terminal without needing to specify the source each time.

To install the latest version from the main branch:
```bash
uv tool install "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git"
```

To install a specific version (e.g., `v0.1.0`):
```bash
uv tool install "gcore-mcp-server@git+https://github.com/G-Core/gcore-mcp-server.git@v0.1.0"
```

After installation, `uv` will make the `gcore-mcp-server` command available. If it's not immediately found, you might need to run `uv tool update-shell` or ensure `uv`'s tool bin directory is in your `PATH`.

Once installed, you can run it like any other command:
```bash
gcore-mcp-server
```

## Development

### Local Development Setup

```bash
# Clone the repository
git clone https://github.com//G-Core/gcore-mcp-server.git
cd gcore-mcp-server

# Install development dependencies
uv venv
source .venv/bin/activate
uv sync --dev
```

### Debugging and Testing

For debugging and development, it's recommended to use the MCP Inspector:

```bash
npx @modelcontextprotocol/inspector
```

The MCP Inspector provides a web interface to test and debug your MCP server interactively, allowing you to:
- Explore available tools and their schemas
- Test tool calls with different parameters
- View real-time communication between client and server
- Debug authentication and connection issues

To use it with your local development server:
1. Start your MCP server locally
2. Run the inspector and connect to your server
3. Use the web interface to test your tools



## License
[![FOSSA Status](https://app.fossa.com/api/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server.svg?type=large)](https://app.fossa.com/projects/git%2Bgithub.com%2FG-Core%2Fgcore-mcp-server?ref=badge_large)