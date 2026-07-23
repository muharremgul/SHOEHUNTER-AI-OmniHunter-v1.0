# ShoeHunter Playwright MCP

This folder contains the project-local Microsoft Playwright MCP runner.

Installed package:

- `@playwright/mcp@0.0.78`

Useful local commands:

```powershell
.\scripts\start-playwright-mcp.ps1
.\scripts\start-playwright-mcp.ps1 -Mode mobile
.\scripts\start-playwright-mcp.ps1 -Port 8932
```

Default endpoint:

`http://127.0.0.1:8931/mcp`

Recommended usage in this project:

- product page UI inspection,
- price and campaign evidence checks,
- mobile product page checks,
- size and stock selector inspection,
- manual validation before creating or changing a store engine.

This runner is intentionally isolated under `tools/` and should not be used as the main production radar engine.
