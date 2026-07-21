#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Convert a MariaDB/MySQL dump into a 2-layer RAG JSONL corpus.

2-layer convention used here:
- document: the human-readable text that will be embedded.
- metadata: the filter/join layer used by local cosine, Chroma, or Qdrant.

Designed for shop/product/media style data:
stores -> shop_profile/shop_media
store_menus -> menu
signature_dishes -> product/product_media
media_highlights -> shop_media
categories/store_categories -> category filters

Default behavior intentionally skips operational/private tables such as bookings,
users, store_user, permissions, cache, jobs, sessions.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SQL = SCRIPT_DIR / "database.sql"
DEFAULT_OUT = SCRIPT_DIR / "rag_media_tech.jsonl"
DEFAULT_REPORT = SCRIPT_DIR / "rag_media_tech_report.json"


DEFAULT_SKIP_TABLES = {
    "bookings",
    "users",
    "store_user",
    "store_applications",
    "store_change_requests",
    "store_inquiries",
    "cache",
    "cache_locks",
    "failed_jobs",
    "job_batches",
    "jobs",
    "migrations",
    "password_reset_tokens",
    "personal_access_tokens",
    "sessions",
    "extend_role_group_permission",
    "extend_role_seen",
    "extend_roles",
    "group_permission_user",
    "group_permissions",
    "user_extend_role",
}

PUBLIC_TABLES = {
    "stores",
    "store_menus",
    "signature_dishes",
    "media_highlights",
    "categories",
    "store_categories",
    "settings",
    "system_media",
}

ASSET_COLUMNS = {
    "avatar",
    "seo_image",
    "menu_all_tab_image",
    "store_info_qr_bg_image",
    "payment_qr_code_image",
    "background_image",
    "background_images",
    "background_video_url",
    "info_bg_image",
    "store_card_bg_image",
    "store_card_bg_video_url",
    "thumbnail",
    "image",
    "images",
    "video_url",
    "video_preview_url",
}

TEXT_JSON_KEYS = {
    "title",
    "description",
    "name",
    "label",
    "text",
    "caption",
    "content",
    "note",
    "tag",
    "author",
}

MEDIA_FIELD_LABELS = {
    "avatar": "ảnh đại diện cửa hàng",
    "seo_image": "ảnh SEO cửa hàng",
    "menu_all_tab_image": "ảnh tab tất cả menu",
    "store_info_qr_bg_image": "ảnh nền QR thông tin cửa hàng",
    "payment_qr_code_image": "ảnh mã QR thanh toán",
    "background_image": "ảnh nền cửa hàng",
    "background_images": "bộ ảnh nền cửa hàng",
    "background_video_url": "video nền cửa hàng",
    "info_bg_image": "ảnh nền phần thông tin",
    "store_card_bg_image": "ảnh nền thẻ cửa hàng",
    "store_card_bg_video_url": "video nền thẻ cửa hàng",
    "thumbnail": "ảnh thumbnail",
    "image": "ảnh sản phẩm",
    "images": "bộ ảnh sản phẩm",
    "video_url": "video",
    "video_preview_url": "video preview",
}


def normalize_ws(value: str) -> str:
    return " ".join(str(value).replace("\r", " ").replace("\n", " ").split())


def repair_mojibake(value: str) -> str:
    """Repair common UTF-8 decoded as latin1/cp1252 mojibake, but keep normal text unchanged."""
    if not value:
        return value
    suspicious = ("Ã", "Ä", "Æ", "á»", "áº", "Ã¡", "Ã¨", "Ã¬", "Ã³", "Ê", "Þ")
    if not any(token in value for token in suspicious):
        return value
    for encoding in ("latin1", "cp1252"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired and repaired != value:
            return repaired
    return value


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_ws(repair_mojibake(value))
    if isinstance(value, (int, float, bool)):
        return normalize_ws(str(value))
    return normalize_ws(json.dumps(value, ensure_ascii=False))


def parse_jsonish(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def flatten_json_text(value: Any, limit: int = 30) -> str:
    """Extract readable text from nested JSON without carrying asset URLs as semantic text."""
    fragments: List[str] = []

    def walk(item: Any, key: Optional[str] = None) -> None:
        if key in ASSET_COLUMNS:
            return
        item = parse_jsonish(item)
        if isinstance(item, dict):
            for k, v in item.items():
                if k in ASSET_COLUMNS:
                    continue
                if k in TEXT_JSON_KEYS or isinstance(v, (dict, list)):
                    walk(v, k)
            return
        if isinstance(item, list):
            for v in item:
                walk(v, key)
            return
        if isinstance(item, str):
            text = clean_text(item)
            if text and not looks_like_asset(text):
                fragments.append(text)
            return
        if item not in (None, "", [], {}):
            fragments.append(clean_text(item))

    walk(value)

    seen = set()
    out: List[str] = []
    for f in fragments:
        if f and f not in seen:
            seen.add(f)
            out.append(f)
        if len(out) >= limit:
            break
    return ", ".join(out)


def looks_like_asset(value: str) -> bool:
    lowered = value.strip().lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("www.")
        or lowered.startswith("/")
        or any(lowered.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov", ".m3u8", ".svg"))
    )


def extract_asset_urls(value: Any) -> List[str]:
    """Extract URLs/asset strings from JSON/string/list/dict."""
    urls: List[str] = []

    def push(v: str) -> None:
        text = clean_text(v)
        if text and (looks_like_asset(text) or "youtube.com" in text.lower() or "youtu.be" in text.lower()):
            urls.append(text)

    def walk(item: Any) -> None:
        item = parse_jsonish(item)
        if isinstance(item, dict):
            for v in item.values():
                walk(v)
            return
        if isinstance(item, list):
            for v in item:
                walk(v)
            return
        if isinstance(item, str):
            push(item)
            return

    walk(value)
    seen = set()
    out: List[str] = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def asset_kind(url_or_field: str) -> str:
    lower = url_or_field.lower()
    if any(token in lower for token in ("video", ".mp4", ".mov", "youtube.com", "youtu.be", ".m3u8")):
        return "video"
    if any(lower.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")):
        return "image"
    return "media"


def sql_unescape(value: str) -> str:
    out: List[str] = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        if i >= len(value):
            out.append("\\")
            break
        nxt = value[i]
        mapping = {
            "0": "\0",
            "b": "\b",
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "Z": "\x1a",
            "\\": "\\",
            "'": "'",
            '"': '"',
        }
        out.append(mapping.get(nxt, nxt))
        i += 1
    return "".join(out)


def extract_table_columns(sql_text: str) -> Dict[str, List[str]]:
    tables: Dict[str, List[str]] = {}
    create_re = re.compile(r"CREATE TABLE `([^`]+)` \((.*?)\) ENGINE=", re.S)
    for match in create_re.finditer(sql_text):
        table = match.group(1)
        cols: List[str] = []
        for raw_line in match.group(2).splitlines():
            line = raw_line.strip()
            if line.startswith("`"):
                col = line.split("`", 2)[1]
                cols.append(col)
        tables[table] = cols
    return tables


def split_tuples(values_sql: str) -> List[str]:
    tuples: List[str] = []
    depth = 0
    in_string = False
    i = 0
    start: Optional[int] = None

    while i < len(values_sql):
        ch = values_sql[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == "'":
                if i + 1 < len(values_sql) and values_sql[i + 1] == "'":
                    i += 2
                    continue
                in_string = False
            i += 1
            continue

        if ch == "'":
            in_string = True
            i += 1
            continue

        if ch == "(":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0 and start is not None:
                tuples.append(values_sql[start:i])
                start = None
        i += 1

    return tuples


def parse_tuple(tuple_sql: str) -> List[Optional[str]]:
    fields: List[Optional[str]] = []
    buf: List[str] = []
    in_string = False
    i = 0

    while i < len(tuple_sql):
        ch = tuple_sql[i]
        if in_string:
            if ch == "\\":
                if i + 1 < len(tuple_sql):
                    buf.append(sql_unescape(tuple_sql[i : i + 2]))
                    i += 2
                else:
                    buf.append("\\")
                    i += 1
                continue
            if ch == "'":
                if i + 1 < len(tuple_sql) and tuple_sql[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                in_string = False
                i += 1
                continue
            buf.append(ch)
            i += 1
            continue

        if ch == "'":
            in_string = True
            i += 1
            continue

        if ch == ",":
            token = "".join(buf).strip()
            fields.append(None if token.upper() == "NULL" or token == "" else token)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    token = "".join(buf).strip()
    fields.append(None if token.upper() == "NULL" or token == "" else token)
    return fields


def iter_insert_statements(sql_text: str) -> Iterable[Tuple[str, str]]:
    insert_re = re.compile(r"INSERT INTO `([^`]+)` VALUES\s*(.*?);", re.S)
    for match in insert_re.finditer(sql_text):
        yield match.group(1), match.group(2)


def load_sql_rows(sql_path: Path, include_operational: bool = False) -> Dict[str, List[Dict[str, Any]]]:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    table_columns = extract_table_columns(sql_text)

    rows_by_table: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for table, values_sql in iter_insert_statements(sql_text):
        if not include_operational and table in DEFAULT_SKIP_TABLES:
            continue
        columns = table_columns.get(table)
        if not columns:
            continue
        for tuple_sql in split_tuples(values_sql):
            values = parse_tuple(tuple_sql)
            if len(values) != len(columns):
                continue
            row = {col: normalize_value(value) for col, value in zip(columns, values)}
            rows_by_table[table].append(row)

    return dict(rows_by_table)


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        repaired = repair_mojibake(value)
        parsed = parse_jsonish(repaired)
        if parsed is not repaired:
            return normalize_value(parsed)
        return normalize_ws(repaired)
    if isinstance(value, list):
        return [normalize_value(v) for v in value if normalize_value(v) not in ("", None, [], {})]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            cleaned = normalize_value(v)
            if cleaned not in ("", None, [], {}):
                out[k] = cleaned
        return out
    return value


def row_id(row: Dict[str, Any], fallback: str) -> str:
    return clean_text(row.get("id")) or fallback


def as_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = clean_text(value).replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def is_true(value: Any) -> bool:
    return clean_text(value).lower() in {"1", "true", "yes", "y", "on"}


def join_bits(*bits: Any) -> str:
    return " ".join(clean_text(bit) for bit in bits if clean_text(bit))


def sentence(label: str, value: Any) -> str:
    text = flatten_json_text(value) if isinstance(value, (dict, list)) else clean_text(value)
    return f"{label}: {text}." if text else ""


def metadata_base(
    *,
    source: str,
    source_table: str,
    tier1: str,
    tier2: str,
    doc_type: str,
    entity_id: str,
    parent_id: str = "",
    path: str = "",
) -> Dict[str, Any]:
    return {
        "source": source,
        "source_table": source_table,
        "tier1": tier1,
        "tier2": tier2,
        "doc_type": doc_type,
        "entity_id": entity_id,
        "parent_id": parent_id,
        "path": path,
    }


def clean_metadata(meta: Dict[str, Any]) -> Dict[str, Any]:
    """
    Keep metadata compatible with Chroma/Qdrant/local filters:
    string, int, float, bool only. Lists/dicts are converted to readable strings.
    """
    out: Dict[str, Any] = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, bool):
            out[k] = v
            continue
        if isinstance(v, int):
            out[k] = v
            continue
        if isinstance(v, float):
            out[k] = v
            continue
        if isinstance(v, (dict, list)):
            text = flatten_json_text(v)
            if not text:
                text = clean_text(v)
            if text:
                out[k] = text
            continue
        text = clean_text(v)
        if text:
            out[k] = text
    return out


def make_record(record_id: str, document: str, metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    doc = clean_text(document)
    if len(doc) < 12:
        return None
    return {
        "id": record_id,
        "document": doc,
        "metadata": clean_metadata(metadata),
    }


def build_corpus(rows: Dict[str, List[Dict[str, Any]]], source_name: str) -> List[Dict[str, Any]]:
    stores = {clean_text(r.get("id")): r for r in rows.get("stores", [])}
    menus = {clean_text(r.get("id")): r for r in rows.get("store_menus", [])}
    categories = {clean_text(r.get("id")): r for r in rows.get("categories", [])}

    store_category_names: Dict[str, List[str]] = defaultdict(list)
    for sc in rows.get("store_categories", []):
        sid = clean_text(sc.get("store_id"))
        cid = clean_text(sc.get("category_id"))
        cname = clean_text(categories.get(cid, {}).get("name"))
        if sid and cname:
            store_category_names[sid].append(cname)

    docs: List[Dict[str, Any]] = []

    # 1) Shop profile records
    for sid, store in stores.items():
        shop_name = clean_text(store.get("name"))
        categories_text = ", ".join(store_category_names.get(sid, []))
        doc = join_bits(
            "Thông tin cửa hàng.",
            sentence("Tên cửa hàng", shop_name),
            sentence("Slug", store.get("slug")),
            sentence("Loại cửa hàng", store.get("store_type") or categories_text),
            sentence("Danh mục", categories_text),
            sentence("Mô tả SEO", store.get("seo_description")),
            sentence("Từ khóa SEO", store.get("seo_keywords")),
            sentence("Khu vực", store.get("location")),
            sentence("Địa chỉ", store.get("address")),
            sentence("Giờ mở cửa", store.get("opening_hours")),
            sentence("Điểm đánh giá", store.get("rating_score")),
            sentence("Mô tả đánh giá", store.get("rating_text")),
            sentence("Số lượt đánh giá", store.get("review_count")),
            sentence("Số điện thoại", store.get("phone")),
            sentence("Email", store.get("email")),
            sentence("Kiểu layout", store.get("layout_mode")),
            sentence("Kiểu thẻ cửa hàng", store.get("store_card_type")),
        )
        meta = metadata_base(
            source=source_name,
            source_table="stores",
            tier1="shop",
            tier2="profile",
            doc_type="shop_profile",
            entity_id=f"shop:{sid}",
            parent_id="",
            path=f"shop/{sid}",
        )
        meta.update({
            "shop_id": sid,
            "shop_name": shop_name,
            "slug": store.get("slug"),
            "area": store.get("location"),
            "address": store.get("address"),
            "category": categories_text or store.get("store_type"),
            "rating_score": as_number(store.get("rating_score")) if as_number(store.get("rating_score")) is not None else "",
            "review_count": as_number(store.get("review_count")) if as_number(store.get("review_count")) is not None else "",
        })
        rec = make_record(f"shop:{sid}:profile", doc, meta)
        if rec:
            docs.append(rec)

        # 2) Shop asset/media records from store columns
        for field in (
            "avatar",
            "seo_image",
            "menu_all_tab_image",
            "store_info_qr_bg_image",
            "payment_qr_code_image",
            "background_image",
            "background_images",
            "background_video_url",
            "info_bg_image",
            "store_card_bg_image",
            "store_card_bg_video_url",
        ):
            urls = extract_asset_urls(store.get(field))
            for idx, url in enumerate(urls, start=1):
                mtype = asset_kind(url or field)
                label = MEDIA_FIELD_LABELS.get(field, field)
                doc = join_bits(
                    f"Media cửa hàng {shop_name}.",
                    f"Đây là {label}.",
                    sentence("Tên cửa hàng", shop_name),
                    sentence("Khu vực", store.get("location")),
                    sentence("Địa chỉ", store.get("address")),
                    sentence("Mô tả liên quan", store.get("seo_description")),
                )
                mid = f"shop:{sid}:media:{field}:{idx}"
                meta = metadata_base(
                    source=source_name,
                    source_table="stores",
                    tier1="media",
                    tier2="shop_media",
                    doc_type="media",
                    entity_id=mid,
                    parent_id=f"shop:{sid}",
                    path=f"shop/{sid}/media/{field}/{idx}",
                )
                meta.update({
                    "shop_id": sid,
                    "shop_name": shop_name,
                    "media_scope": "shop",
                    "media_type": mtype,
                    "media_field": field,
                    "url": url,
                    "area": store.get("location"),
                    "category": categories_text or store.get("store_type"),
                })
                rec = make_record(mid, doc, meta)
                if rec:
                    docs.append(rec)

    # 3) Category docs
    for cid, cat in categories.items():
        name = clean_text(cat.get("name"))
        doc = join_bits(
            "Thông tin danh mục cửa hàng.",
            sentence("Tên danh mục", name),
            sentence("Slug", cat.get("slug")),
            sentence("Thứ tự", cat.get("sort_order")),
        )
        meta = metadata_base(
            source=source_name,
            source_table="categories",
            tier1="category",
            tier2="profile",
            doc_type="category",
            entity_id=f"category:{cid}",
            parent_id=f"category:{clean_text(cat.get('parent_id'))}" if clean_text(cat.get("parent_id")) else "",
            path=f"category/{cid}",
        )
        meta.update({
            "category_id": cid,
            "category_name": name,
            "slug": cat.get("slug"),
            "is_active": is_true(cat.get("is_active")),
            "show_on_homepage": is_true(cat.get("show_on_homepage")),
        })
        rec = make_record(f"category:{cid}:profile", doc, meta)
        if rec:
            docs.append(rec)

    # 4) Menu records
    for menu in rows.get("store_menus", []):
        mid = clean_text(menu.get("id"))
        sid = clean_text(menu.get("store_id"))
        store = stores.get(sid, {})
        shop_name = clean_text(store.get("name"))
        menu_name = clean_text(menu.get("name"))
        doc = join_bits(
            "Thông tin menu/thực đơn của cửa hàng.",
            sentence("Tên cửa hàng", shop_name),
            sentence("Tên menu", menu_name),
            sentence("Layout", menu.get("layout")),
            sentence("Chế độ layout", menu.get("layout_mode")),
            sentence("Thứ tự hiển thị", menu.get("sort_order")),
        )
        meta = metadata_base(
            source=source_name,
            source_table="store_menus",
            tier1="shop",
            tier2="menu",
            doc_type="menu",
            entity_id=f"menu:{mid}",
            parent_id=f"shop:{sid}",
            path=f"shop/{sid}/menus/{mid}",
        )
        meta.update({
            "shop_id": sid,
            "shop_name": shop_name,
            "menu_id": mid,
            "menu_name": menu_name,
            "area": store.get("location"),
            "category": ", ".join(store_category_names.get(sid, [])),
        })
        rec = make_record(f"menu:{mid}:profile", doc, meta)
        if rec:
            docs.append(rec)

    # 5) Product records + product media records
    for dish in rows.get("signature_dishes", []):
        did = clean_text(dish.get("id"))
        sid = clean_text(dish.get("store_id"))
        menu_id = clean_text(dish.get("store_menu_id"))
        store = stores.get(sid, {})
        menu = menus.get(menu_id, {})
        shop_name = clean_text(store.get("name"))
        product_name = clean_text(dish.get("title"))
        menu_name = clean_text(menu.get("name"))
        price = clean_text(dish.get("base_price"))

        doc = join_bits(
            "Thông tin sản phẩm/món/dịch vụ.",
            sentence("Tên cửa hàng", shop_name),
            sentence("Khu vực", store.get("location")),
            sentence("Địa chỉ", store.get("address")),
            sentence("Tên menu", menu_name),
            sentence("Tên sản phẩm", product_name),
            sentence("Tag", dish.get("tag")),
            sentence("Mô tả sản phẩm", dish.get("description")),
            sentence("Giá", price),
            sentence("Topping", dish.get("toppings")),
            sentence("Kích cỡ", dish.get("sizes")),
            sentence("Cấu hình tab", dish.get("tab_config")),
            sentence("Bán chạy", "có" if is_true(dish.get("is_best_seller")) else ""),
            sentence("Còn hàng", "có" if is_true(dish.get("is_available")) else ""),
            sentence("Đánh giá", dish.get("rating")),
            sentence("Tồn kho", dish.get("stock_quantity")),
        )
        meta = metadata_base(
            source=source_name,
            source_table="signature_dishes",
            tier1="product",
            tier2="profile",
            doc_type="product",
            entity_id=f"product:{did}",
            parent_id=f"shop:{sid}",
            path=f"shop/{sid}/products/{did}",
        )
        meta.update({
            "shop_id": sid,
            "shop_name": shop_name,
            "product_id": did,
            "product_key": dish.get("dish_key"),
            "product_name": product_name,
            "menu_id": menu_id,
            "menu_name": menu_name,
            "area": store.get("location"),
            "category": menu_name or ", ".join(store_category_names.get(sid, [])),
            "tag": dish.get("tag"),
            "price": price,
            "is_best_seller": is_true(dish.get("is_best_seller")),
            "is_available": is_true(dish.get("is_available")),
            "rating": as_number(dish.get("rating")) if as_number(dish.get("rating")) is not None else "",
        })
        rec = make_record(f"product:{did}:profile", doc, meta)
        if rec:
            docs.append(rec)

        for field in ("image", "thumbnail", "video_preview_url", "images"):
            urls = extract_asset_urls(dish.get(field))
            for idx, url in enumerate(urls, start=1):
                mtype = asset_kind(url or field)
                label = MEDIA_FIELD_LABELS.get(field, field)
                doc = join_bits(
                    f"Media sản phẩm {product_name} tại {shop_name}.",
                    f"Đây là {label}.",
                    sentence("Tên cửa hàng", shop_name),
                    sentence("Tên menu", menu_name),
                    sentence("Tên sản phẩm", product_name),
                    sentence("Mô tả sản phẩm", dish.get("description")),
                    sentence("Giá", price),
                )
                pmid = f"product:{did}:media:{field}:{idx}"
                meta = metadata_base(
                    source=source_name,
                    source_table="signature_dishes",
                    tier1="media",
                    tier2="product_media",
                    doc_type="media",
                    entity_id=pmid,
                    parent_id=f"product:{did}",
                    path=f"shop/{sid}/products/{did}/media/{field}/{idx}",
                )
                meta.update({
                    "shop_id": sid,
                    "shop_name": shop_name,
                    "product_id": did,
                    "product_name": product_name,
                    "menu_id": menu_id,
                    "menu_name": menu_name,
                    "media_scope": "product",
                    "media_type": mtype,
                    "media_field": field,
                    "url": url,
                    "area": store.get("location"),
                    "category": menu_name or ", ".join(store_category_names.get(sid, [])),
                })
                rec = make_record(pmid, doc, meta)
                if rec:
                    docs.append(rec)

    # 6) Shop media_highlights records
    for media in rows.get("media_highlights", []):
        hid = clean_text(media.get("id"))
        sid = clean_text(media.get("store_id"))
        store = stores.get(sid, {})
        shop_name = clean_text(store.get("name"))
        title = clean_text(media.get("title"))
        urls: List[str] = []
        for field in ("thumbnail", "video_url", "video_preview_url", "images"):
            urls.extend(extract_asset_urls(media.get(field)))
        url = urls[0] if urls else ""
        url_text = " | ".join(urls[:10])

        doc = join_bits(
            "Media nổi bật của cửa hàng.",
            sentence("Tên cửa hàng", shop_name),
            sentence("Khu vực", store.get("location")),
            sentence("Tiêu đề media", title),
            sentence("Tag", media.get("tag")),
            sentence("Loại media", media.get("type")),
            sentence("Tác giả", media.get("author")),
            sentence("Ảnh hoặc video", url_text),
        )
        mid = f"highlight:{hid}"
        meta = metadata_base(
            source=source_name,
            source_table="media_highlights",
            tier1="media",
            tier2="shop_media",
            doc_type="media",
            entity_id=mid,
            parent_id=f"shop:{sid}",
            path=f"shop/{sid}/media_highlights/{hid}",
        )
        meta.update({
            "shop_id": sid,
            "shop_name": shop_name,
            "media_id": hid,
            "media_key": media.get("media_key"),
            "media_scope": "shop",
            "media_type": media.get("type") or asset_kind(url),
            "title": title,
            "tag": media.get("tag"),
            "author": media.get("author"),
            "url": url,
            "url_list": url_text,
            "area": store.get("location"),
            "category": ", ".join(store_category_names.get(sid, [])),
        })
        rec = make_record(f"media_highlight:{hid}:profile", doc, meta)
        if rec:
            docs.append(rec)

    # Stable de-dup by id
    seen = set()
    unique_docs: List[Dict[str, Any]] = []
    for doc in docs:
        if doc["id"] in seen:
            continue
        seen.add(doc["id"])
        unique_docs.append(doc)

    return unique_docs


def write_jsonl(records: Sequence[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_report(records: Sequence[Dict[str, Any]], report_path: Path) -> None:
    counts_by_doc_type = Counter(r["metadata"].get("doc_type", "") for r in records)
    counts_by_tier2 = Counter(r["metadata"].get("tier2", "") for r in records)
    counts_by_table = Counter(r["metadata"].get("source_table", "") for r in records)
    report = {
        "total_records": len(records),
        "counts_by_doc_type": dict(counts_by_doc_type),
        "counts_by_tier2": dict(counts_by_tier2),
        "counts_by_source_table": dict(counts_by_table),
        "sample_ids": [r["id"] for r in records[:20]],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def convert(sql_path: Path, out_path: Path, report_path: Optional[Path] = None, include_operational: bool = False) -> List[Dict[str, Any]]:
    rows = load_sql_rows(sql_path, include_operational=include_operational)
    records = build_corpus(rows, source_name=sql_path.name)
    write_jsonl(records, out_path)
    if report_path:
        write_report(records, report_path)
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert SQL dump to 2-layer RAG JSONL for shop/product/media search.")
    parser.add_argument("--sql", type=Path, default=DEFAULT_SQL, help="Input .sql dump path. Defaults to ./database.sql.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output .jsonl path. Defaults to ./rag_media_tech.jsonl.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT, help="Optional report .json path. Defaults to ./rag_media_tech_report.json.")
    parser.add_argument("--include-operational", action="store_true", help="Include operational/private tables. Off by default.")
    args = parser.parse_args()

    if not args.sql.is_file():
        raise FileNotFoundError(f"SQL dump not found: {args.sql}")
    records = convert(
        sql_path=args.sql,
        out_path=args.out,
        report_path=args.report,
        include_operational=args.include_operational,
    )
    print(f"wrote {len(records)} records to {args.out}")
    if args.report:
        print(f"wrote report to {args.report}")


if __name__ == "__main__":
    main()
