"""Embed token_analysis.json into token_analysis.html as inline data.

This allows the HTML file to work when opened directly via file:// protocol
(where fetch() is blocked by CORS). The embedded data is used as a fallback
when fetch fails.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "viewer" / "token_analysis.html"
JSON_PATH = ROOT / "data" / "latest" / "token_analysis.json"

EMBED_START = "<!-- EMBEDDED_DATA_START -->"
EMBED_END = "<!-- EMBEDDED_DATA_END -->"


def main() -> None:
    if not JSON_PATH.exists():
        print(f"Error: {JSON_PATH} not found. Run token_analysis.py first.")
        raise SystemExit(1)

    html = HTML_PATH.read_text()
    data = json.loads(JSON_PATH.read_text())

    # Strip per_sample to keep HTML size reasonable (it can be huge)
    data.pop("per_sample", None)

    script_block = f"""{EMBED_START}
<script>window.__EMBEDDED_DATA__ = {json.dumps(data, separators=(",", ":"))};</script>
{EMBED_END}"""

    # Remove any previous embedded block
    if EMBED_START in html:
        start = html.index(EMBED_START)
        end = html.index(EMBED_END) + len(EMBED_END)
        html = html[:start] + html[end:]

    # Insert before closing </body>
    html = html.replace("</body>", script_block + "\n</body>")

    HTML_PATH.write_text(html)
    print(f"Embedded data into {HTML_PATH} ({len(data['per_model'])} models)")


if __name__ == "__main__":
    main()
