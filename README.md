# GitHub Actions Remote MCP Runner

Run an interactive, remote-controlled GitHub Actions runner powered by Model Context Protocol (MCP) and Cloudflare Tunnels.

## Features
- **MCP Server:** Compatible with MCP AI agents (Claude Desktop, Cursor, Hermes, etc.).
- **Cloudflare Tunnel:** Free, secure, zero-config public endpoint via `*.trycloudflare.com`.
- **Cross-Platform:** Run on `ubuntu-latest` or `windows-latest`.
- **Tools Built-in:**
  - `execute_command`: Run any bash/PowerShell commands with stdout/stderr capture.
  - `read_file`: Inspect files and logs on the runner.
  - `write_file`: Create scripts or configuration files dynamically.
  - `system_info`: Inspect runner specs, environment variables, and status.

## How to Start the Runner
1. Go to **Actions** -> **Cloudflare MCP Runner** -> **Run workflow**.
2. Set your optional `auth_token` and choose your OS (`ubuntu-latest` or `windows-latest`).
3. View the workflow run log — look for the `trycloudflare.com` URL printed in the output.
