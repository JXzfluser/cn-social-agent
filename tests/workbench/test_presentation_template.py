from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "templates" / "web-presentation"


def test_template_files_exist():
    required = [
        "package.json",
        "vite.config.ts",
        "index.html",
        "src/main.tsx",
        "src/App.tsx",
        "src/config.ts",
        "src/themes.ts",
        "src/narrations.ts",
        "src/stage.css",
        "src/chapters/index.ts",
        "src/chapters/ch01-demo.tsx",
    ]
    for rel in required:
        assert (ROOT / rel).is_file(), rel


def test_package_name():
    import json
    data = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    assert data["name"] == "cn-web-presentation"
