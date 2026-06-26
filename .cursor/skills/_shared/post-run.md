# Post-run — paste script output

After the wrapper script completes:

1. **Paste** the `summary` field from stdout JSON, or the full stdout when the wrapper uses `--summary-only`
2. **Link** `canvasPath` when present — tell the user to open the `.canvas.tsx` file beside chat
3. **Link** the sprint report path from the summary when present

## Do not

- Compose status summaries in prose — scripts own the format
- Write or edit `.canvas.tsx` React files — `epic_estimation.py --write-canvas` owns canvas files
- Call MCP `open_resource` for canvases — it can hang; use a markdown file link instead
- Compute schedule or stage dates in chat — pipeline owns all date math
