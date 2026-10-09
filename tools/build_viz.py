"""Копирует визуализации из source-viz/ в viz/ и добавляет в каждую кнопку «← Все визуализации».

Исходники в source-viz/ не трогаются. Запуск из корня сайта:
    python3 tools/build_viz.py
"""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source-viz"
DST = ROOT / "viz"
MARK = "<!-- site-backlink -->"

BACKLINK = MARK + """
<a href="index.html" aria-label="Все визуализации"
   style="position:fixed;left:max(12px,env(safe-area-inset-left,0px));bottom:calc(12px + env(safe-area-inset-bottom,0px));z-index:2147483000;
          display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 16px;border-radius:999px;
          background:rgba(24,24,32,.88);color:#fff;text-decoration:none;
          font:500 12px/1 'JetBrains Mono',Menlo,Consolas,monospace;letter-spacing:.06em;
          box-shadow:0 8px 20px -10px rgba(24,24,32,.6);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)">
  <span aria-hidden="true" style="font-size:15px">←</span> ВСЕ ВИЗУАЛИЗАЦИИ
</a>
"""


def main() -> None:
    manifest = json.loads((ROOT / "data" / "visualizations.json").read_text(encoding="utf-8"))
    wanted = {item["file"] for item in manifest["items"]}
    missing = [f for f in wanted if not (SRC / f).exists()]
    if missing:
        raise SystemExit(f"Нет исходников для: {', '.join(sorted(missing))}")

    for name in sorted(wanted):
        html = (SRC / name).read_text(encoding="utf-8")
        if MARK not in html:
            idx = html.lower().rfind("</body>")
            html = html[:idx] + BACKLINK + html[idx:] if idx != -1 else html + BACKLINK
        (DST / name).write_text(html, encoding="utf-8")
        print("ok", name)


if __name__ == "__main__":
    main()
