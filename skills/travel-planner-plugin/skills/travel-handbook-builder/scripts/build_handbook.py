#!/usr/bin/env python3
"""Render a reviewed trip as a small, offline travel handbook."""

from __future__ import annotations

import argparse
from datetime import date
from hashlib import sha256
from html import escape
import json
import math
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit


PAGES = ("index.html", "route.html", "food.html", "places.html")
COLORS = ("#256b69", "#b45635", "#6b5d9e", "#a67c2d", "#3472a1", "#a34d72")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def html(value: object) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def required_text(item: dict, key: str, where: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{where}.{key} 必须是非空文字")
    return value.strip()


def optional_text(item: dict, key: str) -> str:
    value = item.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{key} 必须是文字")
    return value.strip()


def checked_url(value: str, where: str) -> str:
    if not value:
        return ""
    parsed = urlsplit(value)
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{where} 必须是无凭据的 https 链接")
    return value


def check_coord(stop: dict, where: str) -> None:
    lat, lon = stop.get("latitude"), stop.get("longitude")
    if lat is None and lon is None:
        return
    if lat is None or lon is None:
        raise ValueError(f"{where} 的经纬度必须成对提供")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (lat, lon)):
        raise ValueError(f"{where} 的经纬度必须是有限数字")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"{where} 的经纬度超出范围")
    required_text(stop, "coordinate_system", where)
    required_text(stop, "coordinate_kind", where)
    checked_url(required_text(stop, "coordinate_source_url", where), f"{where}.coordinate_source_url")


def validate(plan: object) -> dict:
    if not isinstance(plan, dict):
        raise ValueError("输入顶层必须是 JSON 对象")
    required_text(plan, "title", "trip")
    required_text(plan, "destination", "trip")
    status = required_text(plan, "review_status", "trip")
    if status not in {"passed", "draft"}:
        raise ValueError("review_status 只能是 passed 或 draft")
    days = plan.get("days")
    if not isinstance(days, list) or not days:
        raise ValueError("days 必须是非空数组")
    seen_dates: set[str] = set()
    seen_ids: set[str] = set()
    for day_index, day in enumerate(days, 1):
        where = f"days[{day_index}]"
        if not isinstance(day, dict):
            raise ValueError(f"{where} 必须是对象")
        day_date = required_text(day, "date", where)
        try:
            date.fromisoformat(day_date)
        except ValueError as error:
            raise ValueError(f"{where}.date 必须是 YYYY-MM-DD") from error
        if day_date in seen_dates:
            raise ValueError(f"重复的日期：{day_date}")
        seen_dates.add(day_date)
        required_text(day, "title", where)
        stops = day.get("stops")
        if not isinstance(stops, list):
            raise ValueError(f"{where}.stops 必须是数组")
        for stop_index, stop in enumerate(stops, 1):
            spot = f"{where}.stops[{stop_index}]"
            if not isinstance(stop, dict):
                raise ValueError(f"{spot} 必须是对象")
            stop_id = required_text(stop, "id", spot)
            if not ID_RE.fullmatch(stop_id) or stop_id in seen_ids:
                raise ValueError(f"{spot}.id 格式错误或重复：{stop_id}")
            seen_ids.add(stop_id)
            required_text(stop, "name", spot)
            stop_time = optional_text(stop, "time")
            if stop_time and not TIME_RE.fullmatch(stop_time):
                raise ValueError(f"{spot}.time 必须是 HH:MM")
            checked_url(optional_text(stop, "source_url"), f"{spot}.source_url")
            check_coord(stop, spot)
    for group in ("foods", "places"):
        values = plan.get(group, [])
        if not isinstance(values, list):
            raise ValueError(f"{group} 必须是数组")
        for index, item in enumerate(values, 1):
            where = f"{group}[{index}]"
            if not isinstance(item, dict):
                raise ValueError(f"{where} 必须是对象")
            required_text(item, "name", where)
            checked_url(optional_text(item, "source_url"), f"{where}.source_url")
            photo = item.get("photo")
            if photo is not None:
                if not isinstance(photo, dict) or not isinstance(photo.get("reuse_allowed"), bool):
                    raise ValueError(f"{where}.photo.reuse_allowed 必须是布尔值")
                checked_url(optional_text(photo, "source_url"), f"{where}.photo.source_url")
                if photo["reuse_allowed"]:
                    required_text(photo, "rights_note", f"{where}.photo")
    questions = plan.get("open_questions", [])
    if not isinstance(questions, list) or any(not isinstance(q, str) for q in questions):
        raise ValueError("open_questions 必须是文字数组")
    return plan


def source_link(url: str) -> str:
    return f'<a href="{html(url)}" target="_blank" rel="noopener noreferrer">查看来源</a>' if url else '<span class="muted">来源待核实</span>'


CSS = """
:root{color-scheme:light;--ink:#243637;--muted:#647779;--teal:#256b69;--paper:#f5f3ec;--card:#fff;--line:#dce4df}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 system-ui,-apple-system,"Microsoft YaHei",sans-serif}
a{color:var(--teal)}.wrap{max-width:1100px;margin:auto;padding:18px}.top{background:#183d40;color:#fff}.top .wrap{display:flex;justify-content:space-between;align-items:center;gap:16px}.top a{color:#fff;text-decoration:none}
nav{display:flex;gap:10px;flex-wrap:wrap}nav a{padding:5px 10px;border:1px solid #ffffff55;border-radius:999px}.hero{padding:28px 0 12px}.eyebrow{letter-spacing:.12em;text-transform:uppercase;color:var(--teal);font-size:.8rem;font-weight:700}
h1{font-size:clamp(1.9rem,4vw,3.2rem);line-height:1.15;margin:.2em 0}h2{font-size:1.35rem;margin:1.7em 0 .6em}h3{font-size:1.08rem;margin:.2em 0}.muted{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}.card,.notice,.mapbox{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px;box-shadow:0 4px 18px #193a3d0a}
.notice{border-left:5px solid #c88738}.tag{display:inline-block;padding:3px 9px;border-radius:999px;background:#e4f0eb;color:#235652;font-size:.85rem}.tag.draft{background:#fff0d9;color:#825319}
.meta{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:.91rem}.stack{display:grid;gap:12px}.step{border-left:4px solid var(--teal);padding-left:14px}.step .time{font-weight:700;color:var(--teal)}
.filters{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.filters button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 13px;cursor:pointer;font:inherit}.filters button[aria-pressed=true]{background:var(--teal);color:#fff}
.mapbox{overflow:auto}.mapbox svg{display:block;width:100%;height:auto}.mapbox text{font:13px system-ui,sans-serif;fill:#234}.route-note{font-size:.9rem;color:var(--muted)}
.photo{width:100%;max-height:260px;object-fit:cover;border-radius:10px;margin:9px 0}footer{border-top:1px solid var(--line);margin-top:36px;padding:22px 0;color:var(--muted);font-size:.9rem}
@media(max-width:640px){.top .wrap{display:block}.top nav{padding-top:8px}.wrap{padding:14px}.card,.notice,.mapbox{padding:14px}}
"""


def page(title: str, subtitle: str, content: str) -> str:
    nav = ''.join(f'<a href="{name}">{label}</a>' for name, label in (
        ("index.html", "概览"), ("route.html", "每日行程"), ("food.html", "美食"), ("places.html", "景点")))
    return f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html(title)}</title><style>{CSS}</style></head><body>
<header class="top"><div class="wrap"><strong>行迹手册</strong><nav aria-label="页面导航">{nav}</nav></div></header>
<main class="wrap"><div class="hero"><div class="eyebrow">{html(subtitle)}</div><h1>{html(title)}</h1></div>{content}</main>
<footer><div class="wrap">本手册按提供的行程生成。页面为静态快照，动态信息以标注的核实状态为准。</div></footer></body></html>'''


def render_index(plan: dict) -> str:
    passed = plan["review_status"] == "passed"
    status = "已复核" if passed else "草案 · 待复核"
    count = sum(len(day["stops"]) for day in plan["days"])
    cards = ''.join(f'<a class="card" href="{file}"><h3>{label}</h3><p>{detail}</p></a>' for file, label, detail in (
        ("route.html", "每日行程", f"{len(plan['days'])} 天、{count} 个行程节点，含位置示意与时间线"),
        ("food.html", "美食指南", f"{len(plan.get('foods', []))} 条已收集的餐饮信息"),
        ("places.html", "景点卡片", "看点、来源与可分享的图片")))
    info = ''.join(f'<p><strong>{label}：</strong>{html(optional_text(plan, key))}</p>' for key, label in (
        ("summary", "行程概况"), ("budget_note", "预算口径"), ("weather_note", "天气提醒")) if optional_text(plan, key))
    questions = plan.get("open_questions", [])
    open_items = '<ul>' + ''.join(f'<li>{html(q)}</li>' for q in questions) + '</ul>' if questions else '<p>当前没有列出的待决问题。</p>'
    note = optional_text(plan, "review_note")
    content = f'<div class="meta"><span>{html(plan["destination"])}</span><span>{html(optional_text(plan,"date_range"))}</span><span class="tag {"" if passed else "draft"}">{status}</span></div>'
    content += f'<section class="notice"><h2>复核状态</h2><p>{html(note) if note else status}</p></section>'
    content += f'<section><h2>打开手册</h2><div class="grid">{cards}</div></section>'
    content += f'<section><h2>出行摘要</h2><div class="card">{info or "<p>请查看每日行程。</p>"}</div></section>'
    content += f'<section><h2>待确认</h2><div class="card">{open_items}</div></section>'
    return page(plan["title"], "旅行概览", content)


def point_xy(lat: float, lon: float, bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    min_lat, max_lat, min_lon, max_lon = bounds
    x = 48 + 704 * ((lon - min_lon) / (max_lon - min_lon) if max_lon > min_lon else .5)
    y = 42 + 336 * (1 - (lat - min_lat) / (max_lat - min_lat) if max_lat > min_lat else .5)
    return x, y


def render_map(plan: dict) -> str:
    points = [s for d in plan["days"] for s in d["stops"] if s.get("latitude") is not None]
    if not points:
        return '<div class="notice">没有经核实的坐标。完整顺序仍显示在下方时间线中。</div>'
    systems = {s["coordinate_system"] for s in points}
    if len(systems) != 1:
        return '<div class="notice">输入地点使用不同坐标系，暂不绘制位置示意。请先核对并统一坐标。</div>'
    bounds = (min(s["latitude"] for s in points), max(s["latitude"] for s in points),
              min(s["longitude"] for s in points), max(s["longitude"] for s in points))
    layers = []
    for day_idx, day in enumerate(plan["days"]):
        color = COLORS[day_idx % len(COLORS)]
        parts = []
        for i in range(len(day["stops"]) - 1):
            a, b = day["stops"][i:i + 2]
            if a.get("latitude") is None or b.get("latitude") is None:
                continue
            x1, y1 = point_xy(a["latitude"], a["longitude"], bounds)
            x2, y2 = point_xy(b["latitude"], b["longitude"], bounds)
            parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="3" stroke-dasharray="7 5"/>')
        for stop_idx, stop in enumerate(day["stops"], 1):
            if stop.get("latitude") is None:
                continue
            x, y = point_xy(stop["latitude"], stop["longitude"], bounds)
            label = html(f"第 {day_idx + 1} 天第 {stop_idx} 站：{stop['name']}")
            parts.append(f'<g><title>{label}</title><circle cx="{x:.1f}" cy="{y:.1f}" r="15" fill="{color}" stroke="white" stroke-width="3"/><text x="{x:.1f}" y="{y + 4:.1f}" text-anchor="middle" fill="white" style="fill:white;font-weight:700">{stop_idx}</text></g>')
        layers.append(f'<g data-day-block="d{day_idx}">{"".join(parts)}</g>')
    missing = sum(s.get("latitude") is None for d in plan["days"] for s in d["stops"])
    note = f' · {missing} 个无坐标节点未绘入' if missing else ''
    return f'<div class="mapbox"><svg viewBox="0 0 800 420" role="img" aria-label="按日期显示的地点位置示意"><rect x="0" y="0" width="800" height="420" rx="18" fill="#eef4ef"/><path d="M0 105H800 M0 210H800 M0 315H800 M200 0V420 M400 0V420 M600 0V420" stroke="#d7e3db" stroke-width="1"/>{"".join(layers)}</svg><p class="route-note">位置示意 · 坐标系 {html(next(iter(systems)))} · 虚线只表示行程相邻地点，不代表道路或交通耗时{note}</p></div>'


def render_route(plan: dict) -> str:
    buttons = '<button type="button" data-filter="all" aria-pressed="true">全部</button>' + ''.join(
        f'<button type="button" data-filter="d{i}" aria-pressed="false">{html(day["date"])} · 第{i+1}天</button>'
        for i, day in enumerate(plan["days"]))
    sections = []
    for day_idx, day in enumerate(plan["days"]):
        steps = []
        for stop in day["stops"]:
            detail = ''.join(f'<p><strong>{label}：</strong>{html(optional_text(stop, key))}</p>' for key, label in (
                ("description", "安排"), ("transport_note", "接驳"), ("booking_note", "预约")) if optional_text(stop, key))
            coord_url = optional_text(stop, "coordinate_source_url")
            coord_link = f'<a href="{html(coord_url)}" target="_blank" rel="noopener noreferrer">位置来源</a>' if coord_url else ""
            steps.append(f'<div class="step"><div class="time">{html(optional_text(stop,"time") or "时间待定")}</div><h3>{html(stop["name"])}</h3><div class="meta"><span>{html(optional_text(stop,"kind"))}</span>{source_link(optional_text(stop,"source_url"))}{coord_link}</div>{detail}</div>')
        note = f'<p>{html(optional_text(day,"notes"))}</p>' if optional_text(day, "notes") else ""
        sections.append(f'<section class="card" data-day-block="d{day_idx}"><h2>{html(day["date"])} · {html(day["title"])}</h2>{note}<div class="stack">{"".join(steps) or "<p>当天活动待定。</p>"}</div></section>')
    script = '''<script>document.querySelectorAll("[data-filter]").forEach(button=>button.addEventListener("click",()=>{const key=button.dataset.filter;document.querySelectorAll("[data-filter]").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));document.querySelectorAll("[data-day-block]").forEach(block=>{block.style.display=(key==="all"||block.dataset.dayBlock===key)?"":"none"})}));</script>'''
    content = f'<p class="muted">按输入的日程顺序展示；时间与交通说明来自同一版行程快照。</p><div class="filters" aria-label="筛选日期">{buttons}</div>{render_map(plan)}<div class="stack">{"".join(sections)}</div>{script}'
    return page("每日行程", plan["title"], content)


def render_food(plan: dict) -> str:
    cards = []
    for item in plan.get("foods", []):
        details = ''.join(f'<p><strong>{label}：</strong>{html(optional_text(item,key))}</p>' for key, label in (
            ("area", "区域"), ("description", "推荐理由"), ("price_note", "价格口径"), ("status", "状态")) if optional_text(item, key))
        cards.append(f'<article class="card"><h2>{html(item["name"])}</h2>{details}{source_link(optional_text(item,"source_url"))}</article>')
    content = '<p class="muted">餐饮候选不会自动加入每天的行程。价格与营业信息以所标日期和来源为准。</p>'
    content += f'<div class="grid">{"".join(cards)}</div>' if cards else '<div class="notice">当前没有已收集的美食资料。</div>'
    return page("美食指南", plan["title"], content)


def copy_photo(photo: dict, input_dir: Path, output_dir: Path) -> str:
    if not photo.get("reuse_allowed"):
        return ""
    raw = required_text(photo, "path", "photo")
    relative = Path(raw)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("photo.path 必须是 JSON 同目录下的相对路径")
    source = (input_dir / relative).resolve()
    if not source.is_relative_to(input_dir.resolve()) or not source.is_file():
        raise ValueError(f"图片不存在或超出输入目录：{raw}")
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"} or source.stat().st_size > 10_000_000:
        raise ValueError(f"图片格式不支持或超过 10 MB：{raw}")
    media = output_dir / "media"
    media.mkdir(exist_ok=True)
    digest = sha256(source.read_bytes()).hexdigest()[:16]
    target = media / f"{digest}{source.suffix.lower()}"
    if not target.exists():
        shutil.copyfile(source, target)
    return f"media/{target.name}"


def render_places(plan: dict, input_dir: Path, output_dir: Path) -> str:
    places = plan.get("places") or []
    if not places:
        seen = set()
        places = []
        for day in plan["days"]:
            for stop in day["stops"]:
                if stop["name"] not in seen and stop.get("kind") not in {"餐饮", "住宿", "酒店", "交通", "车站", "休息"}:
                    seen.add(stop["name"])
                    places.append(stop)
    cards = []
    for item in places:
        photo = item.get("photo") or {}
        photo_url = copy_photo(photo, input_dir, output_dir) if photo else ""
        img = f'<img class="photo" src="{html(photo_url)}" alt="{html(item["name"])}" loading="lazy">' if photo_url else ""
        credit = f'<p class="muted">图片：{html(optional_text(photo,"credit"))}</p>' if photo_url and optional_text(photo, "credit") else ""
        photo_note = f'<p>{html(optional_text(photo,"note"))}</p>' if photo and optional_text(photo, "note") else ""
        photo_source = source_link(optional_text(photo, "source_url")) if photo and optional_text(photo, "source_url") else ""
        cards.append(f'<article class="card"><h2>{html(item["name"])}</h2>{img}{credit}<p>{html(optional_text(item,"description"))}</p>{photo_note}<div class="meta">{source_link(optional_text(item,"source_url"))}{photo_source}</div></article>')
    content = '<p class="muted">景点内容沿用已核实资料；无分享许可的照片仅给来源链接或文字说明。</p>'
    content += f'<div class="grid">{"".join(cards)}</div>' if cards else '<div class="notice">当前没有景点卡片资料。</div>'
    return page("景点卡片", plan["title"], content)


def build(input_path: Path, output_dir: Path, force: bool = False) -> None:
    plan = validate(json.loads(input_path.read_text(encoding="utf-8")))
    if output_dir.exists() and not force and any((output_dir / name).exists() for name in PAGES):
        raise ValueError("输出页面已存在；确认要更新时加 --force")
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = {
        "index.html": render_index(plan),
        "route.html": render_route(plan),
        "food.html": render_food(plan),
        "places.html": render_places(plan, input_path.parent, output_dir),
    }
    for name, content in rendered.items():
        (output_dir / name).write_text(content, encoding="utf-8")
    print(f"Generated {len(rendered)} pages.")


def main() -> None:
    parser = argparse.ArgumentParser(description="从已复核行程生成离线旅行手册")
    parser.add_argument("input", type=Path, help="UTF-8 行程 JSON")
    parser.add_argument("output", type=Path, help="输出目录")
    parser.add_argument("--force", action="store_true", help="更新已有的四个页面")
    args = parser.parse_args()
    try:
        build(args.input.resolve(), args.output.resolve(), args.force)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(1, f"生成失败：{error}\n")


if __name__ == "__main__":
    main()
