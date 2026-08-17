"""第七次全国人口普查 — Agent tools + Workbench 图鉴数据."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

_DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "census_7th.json"


@lru_cache(maxsize=1)
def load_census() -> dict[str, Any]:
    with _DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _growth(p: float, p10: float) -> float:
    if not p10:
        return 0.0
    return round((p - p10) / p10 * 100.0, 2)


def _province_summary(name: str, row: dict[str, Any]) -> dict[str, Any]:
    a = row.get("a") or [0, 0, 0, 0]
    return {
        "province": name,
        "region": row.get("r"),
        "pop_wan": row.get("p"),
        "pop_2010_wan": row.get("p10"),
        "growth_pct_vs_2010": _growth(float(row.get("p") or 0), float(row.get("p10") or 0)),
        "age_pct": {
            "0_14": a[0] if len(a) > 0 else None,
            "15_59": a[1] if len(a) > 1 else None,
            "60_plus": a[2] if len(a) > 2 else None,
            "65_plus": a[3] if len(a) > 3 else None,
        },
        "gender_ratio": row.get("g"),
        "urban_pct": row.get("u"),
        "density": row.get("d"),
        "household_size": row.get("h"),
        "edu_per_100k": {
            "university": (row.get("e") or [None])[0],
            "high_school": (row.get("e") or [None, None])[1],
            "middle_school": (row.get("e") or [None, None, None])[2],
            "primary": (row.get("e") or [None, None, None, None])[3],
        },
        "top_cities": [
            {"city": c[0], "pop_wan": c[1]}
            for c in sorted(row.get("c") or [], key=lambda x: -float(x[1]))[:8]
        ],
    }


def _national_summary(data: dict[str, Any]) -> dict[str, Any]:
    nat = data.get("national") or {}
    a = nat.get("age") or []
    return {
        "source": data.get("source"),
        "as_of": data.get("as_of"),
        "pop_wan": nat.get("pop"),
        "pop_2010_wan": nat.get("pop10"),
        "growth_pct_vs_2010": _growth(float(nat.get("pop") or 0), float(nat.get("pop10") or 0)),
        "age_pct": {
            "0_14": a[0] if len(a) > 0 else None,
            "15_59": a[1] if len(a) > 1 else None,
            "60_plus": a[2] if len(a) > 2 else None,
            "65_plus": a[3] if len(a) > 3 else None,
        },
        "gender_ratio": nat.get("gender"),
        "urban_pct": nat.get("urban"),
        "household_size": nat.get("household"),
        "province_count": len(data.get("provinces") or {}),
    }


def _find_province(provinces: dict[str, Any], name: str) -> tuple[str, dict[str, Any]] | None:
    q = (name or "").strip()
    if not q:
        return None
    if q in provinces:
        return q, provinces[q]
    for k, v in provinces.items():
        if q in k or k in q:
            return k, v
    return None


def _find_city(
    provinces: dict[str, Any], city: str, province: str = ""
) -> dict[str, Any] | None:
    q = (city or "").strip()
    if not q:
        return None
    scope: list[tuple[str, dict[str, Any]]] = []
    if province:
        hit = _find_province(provinces, province)
        if hit:
            scope = [hit]
    else:
        scope = list(provinces.items())
    for pname, row in scope:
        for c in row.get("c") or []:
            cname = str(c[0])
            if q == cname or q in cname or cname in q:
                return {
                    "province": pname,
                    "city": cname,
                    "pop_wan": c[1],
                    "province_pop_wan": row.get("p"),
                    "share_of_province_pct": round(
                        float(c[1]) / float(row.get("p") or 1) * 100.0, 2
                    ),
                    "region": row.get("r"),
                }
    return None


_SORT_KEYS = {
    "pop": "p",
    "p": "p",
    "人口": "p",
    "growth": "growth",
    "增长率": "growth",
    "urban": "u",
    "u": "u",
    "城镇化": "u",
    "aging": "a2",
    "a2": "a2",
    "老龄化": "a2",
    "gender": "g",
    "g": "g",
    "性别比": "g",
    "density": "d",
    "d": "d",
    "密度": "d",
}


async def tool_population_census_lookup(
    province: str = "",
    city: str = "",
    sort_by: str = "pop",
    top_n: int = 8,
    national: bool = False,
) -> dict[str, Any]:
    """Lookup 7th national census stats (province / city / ranking / national)."""
    data = load_census()
    provinces = data.get("provinces") or {}
    top_n = max(1, min(int(top_n or 8), 31))

    if national and not province and not city:
        return {"ok": True, "scope": "national", "national": _national_summary(data)}

    if city:
        found = _find_city(provinces, city, province)
        if not found:
            return {
                "ok": False,
                "error": f"未找到城市：{city}" + (f"（省={province}）" if province else ""),
                "hint": "可先不填 province，或用完整市名如 深圳 / 成都",
            }
        return {
            "ok": True,
            "scope": "city",
            "city": found,
            "atlas_url": f"/static/population-atlas.html?province={found['province']}&city={found['city']}",
            "open_atlas": True,
            "province": found["province"],
            "city_name": found["city"],
        }

    if province:
        hit = _find_province(provinces, province)
        if not hit:
            return {
                "ok": False,
                "error": f"未找到省份：{province}",
                "hint": "例如：广东、浙江、上海",
            }
        name, row = hit
        return {
            "ok": True,
            "scope": "province",
            "province": _province_summary(name, row),
            "national": _national_summary(data),
            "atlas_url": f"/static/population-atlas.html?province={name}",
            "open_atlas": True,
            "province_name": name,
        }

    # Ranking list
    key = _SORT_KEYS.get((sort_by or "pop").strip().lower(), "p")
    rows = []
    for name, row in provinces.items():
        growth = _growth(float(row.get("p") or 0), float(row.get("p10") or 0))
        a = row.get("a") or [0, 0, 0]
        sort_val = {
            "p": float(row.get("p") or 0),
            "growth": growth,
            "u": float(row.get("u") or 0),
            "a2": float(a[2] if len(a) > 2 else 0),
            "g": float(row.get("g") or 0),
            "d": float(row.get("d") or 0),
        }[key]
        rows.append(
            {
                "province": name,
                "region": row.get("r"),
                "pop_wan": row.get("p"),
                "growth_pct_vs_2010": growth,
                "urban_pct": row.get("u"),
                "aging_60_pct": a[2] if len(a) > 2 else None,
                "gender_ratio": row.get("g"),
                "density": row.get("d"),
                "_sort": sort_val,
            }
        )
    rows.sort(key=lambda r: -float(r["_sort"]))
    for r in rows:
        r.pop("_sort", None)
    return {
        "ok": True,
        "scope": "ranking",
        "sort_by": key,
        "top_n": top_n,
        "items": rows[:top_n],
        "national": _national_summary(data),
        "atlas_url": "/static/population-atlas.html",
        "open_atlas": True,
        "note": "可再查具体 province / city；需要可视化时用 open_population_atlas",
    }


async def tool_open_population_atlas(
    province: str = "",
    city: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Open the population atlas visualization in the workbench UI."""
    data = load_census()
    provinces = data.get("provinces") or {}
    pname = ""
    cname = ""
    if province:
        hit = _find_province(provinces, province)
        if hit:
            pname = hit[0]
    if city:
        found = _find_city(provinces, city, pname or province)
        if found:
            pname = found["province"]
            cname = found["city"]
    qs = []
    if pname:
        qs.append(f"province={pname}")
    if cname:
        qs.append(f"city={cname}")
    url = "/static/population-atlas.html" + (("?" + "&".join(qs)) if qs else "")
    return {
        "ok": True,
        "open_atlas": True,
        "present_atlas": True,
        "url": url,
        "province": pname,
        "city": cname,
        "note": (note or "第七次人口普查结构图鉴已打开").strip(),
        "source": data.get("source"),
    }
