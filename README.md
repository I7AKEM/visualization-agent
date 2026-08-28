# AntV × Insightor — research spike

Hands-on evaluation of the AntV ecosystem (AI-visualization stack) for **Insightor**,
a data agent built on Vanna 2.0 for executive leaders in government, with
Arabic-first output.

**Read [REPORT.md](./REPORT.md) for the findings.** This README is just how to run
the demos.

## What's here

```
data/     sample "SQL tool output" — monthly transactions per Saudi region (Arabic), service breakdown
demos/    01-render-charts.mjs   render 4 chart types from CSV, Arabic labels, via @antv/gpt-vis-ssr
          02-insights.mjs        automatic insight extraction + chart recommendation via @antv/ava
          03-mcp-e2e.mjs         drive @antv/mcp-server-chart over real MCP (stdio), rendering kept local
          render-server.mjs      self-hosted replacement for AntV's cloud renderer (VIS_REQUEST_SERVER)
          css-noop.cjs           Node preload: @antv/s2 requires .css files; this makes them no-ops
fonts/    Noto Sans Arabic (regular + bold)
out/      rendered PNGs (committed as evidence)
```

## Run it

Requires Node 20+ (tested on 22). Arabic text needs the font visible to the OS:

```sh
npm install
mkdir -p ~/.local/share/fonts && cp fonts/*.ttf ~/.local/share/fonts/ && fc-cache -f

node -r ./demos/css-noop.cjs demos/01-render-charts.mjs   # charts → out/*.png
node -r ./demos/css-noop.cjs demos/02-insights.mjs        # insights → stdout
node -r ./demos/css-noop.cjs demos/03-mcp-e2e.mjs         # MCP end-to-end → out/mcp-*.png
```

## Use it with Claude yourself

```sh
# fully private: point the MCP server at your own renderer
node -r ./demos/css-noop.cjs demos/render-server.mjs &    # port 3100

claude mcp add antv-charts --env VIS_REQUEST_SERVER=http://127.0.0.1:3100 \
  -- npx -y @antv/mcp-server-chart
```

Then ask Claude to chart anything. Without `VIS_REQUEST_SERVER`, chart data goes to
AntV's public cloud (`antv-studio.alipay.com`) — never do that with government data.
