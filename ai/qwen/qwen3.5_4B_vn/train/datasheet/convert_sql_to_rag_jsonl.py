from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _resolve_default_sql() -> Path:
    env_value = os.environ.get("QWEN_SQL_DUMP", "").strip()
    if env_value:
        return Path(env_value)

    candidates = [
        Path(r"D:\hustmedia\python\llms\media_tech\ai\datasheet\database.sql"),
        Path("/root/media_tech/ai/datasheet/database.sql"),
        Path(__file__).with_name("database.sql"),
        Path(__file__).with_name("dbbk0807v1.sql"),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


DEFAULT_SQL = _resolve_default_sql()
DEFAULT_OUT = Path(__file__).with_name("rag_media_tech.jsonl")

SKIP_TABLES = {
    "cache",
    "cache_locks",
    "failed_jobs",
    "job_batches",
    "jobs",
    "migrations",
    "password_reset_tokens",
    "personal_access_tokens",
    "sessions",
}

TABLE_FIELDS: Dict[str, Sequence[str]] = {
    "bookings": (
        "store_id",
        "type",
        "customer_name",
        "customer_phone",
        "customer_email",
        "notes",
        "cancel_reason",
        "booking_at",
        "time_slot",
        "table_ref",
        "area_ref",
        "guests",
        "staff_note",
        "assigned_to",
        "items",
        "total",
        "status",
    ),
    "media_highlights": (
        "store_id",
        "media_key",
        "type",
        "tag",
        "title",
        "author",
        "sort_order",
    ),
    "signature_dishes": (
        "store_id",
        "store_menu_id",
        "dish_key",
        "tag",
        "title",
        "description",
        "base_price",
        "toppings",
        "sizes",
        "cover_position",
        "tab_config",
        "use_tabs",
        "is_available",
        "is_best_seller",
        "rating",
        "stock_quantity",
        "sort_order",
        "modal_size",
        "display_ratio",
        "grid_col_span",
        "grid_row_span",
    ),
    "store_menus": (
        "store_id",
        "name",
        "layout",
        "layout_cols",
        "layout_tablet",
        "layout_tablet_cols",
        "layout_mobile",
        "layout_mobile_cols",
        "layout_mode",
        "sort_order",
    ),
    "stores": (
        "slug",
        "store_type",
        "is_homepage",
        "name",
        "seo_title",
        "seo_description",
        "seo_keywords",
        "location",
        "address",
        "rating_score",
        "rating_text",
        "review_count",
        "opening_hours",
        "phone",
        "email",
        "payment_title",
        "payment_provider",
        "background_mode",
        "background_type",
        "layout_mode",
        "main_layout",
        "store_card_type",
    ),
    "users": ("name", "email", "is_admin", "note", "last_accessed_store_id"),
    "store_user": ("user_id", "store_id", "role", "can_edit_booking"),
    "store_applications": ("user_id", "name", "slug", "address", "phone", "status", "admin_note"),
    "store_change_requests": (
        "store_id",
        "user_id",
        "requested_changes",
        "current_values",
        "status",
        "note",
        "admin_note",
    ),
}

SKIP_COLUMNS = {
    "id",
    "created_at",
    "updated_at",
    "deleted_at",
    "password",
    "remember_token",
    "email_verified_at",
    "thumbnail",
    "image",
    "images",
    "video_url",
    "video_preview_url",
    "background_video_url",
    "store_card_bg_video_url",
    "background_images",
    "store_info_qr_bg_image",
    "payment_qr_code_image",
    "avatar",
    "menu_all_tab_image",
    "store_card_bg_image",
    "store_card_hoplink",
}

JSON_IGNORE_KEYS = {
    "image",
    "images",
    "thumbnail",
    "video_url",
    "video_preview_url",
    "background_video_url",
    "store_card_bg_video_url",
    "store_info_qr_bg_image",
    "payment_qr_code_image",
}

JSON_TEXT_KEYS = {
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

LABELS = {
    "store_id": "Mã cửa hàng",
    "store_menu_id": "Mã menu",
    "user_id": "Mã người dùng",
    "type": "Loại",
    "status": "Trạng thái",
    "name": "Tên",
    "slug": "Slug",
    "title": "Tiêu đề",
    "description": "Mô tả",
    "note": "Ghi chú",
    "notes": "Ghi chú",
    "admin_note": "Ghi chú quản trị",
    "customer_name": "Tên khách",
    "customer_phone": "Số điện thoại",
    "customer_email": "Email",
    "booking_at": "Thời gian đặt",
    "time_slot": "Khung giờ",
    "guests": "Số khách",
    "cancel_reason": "Lý do huỷ",
    "staff_note": "Ghi chú nhân viên",
    "assigned_to": "Người phụ trách",
    "table_ref": "Bàn",
    "area_ref": "Khu vực",
    "total": "Tổng tiền",
    "rating_score": "Điểm đánh giá",
    "rating_text": "Mô tả đánh giá",
    "review_count": "Số lượt đánh giá",
    "opening_hours": "Giờ mở cửa",
    "phone": "Điện thoại",
    "email": "Email",
    "address": "Địa chỉ",
    "location": "Vị trí",
    "store_type": "Loại cửa hàng",
    "layout": "Bố cục",
    "layout_mode": "Chế độ bố cục",
    "layout_cols": "Số cột",
    "layout_tablet": "Bố cục tablet",
    "layout_tablet_cols": "Số cột tablet",
    "layout_mobile": "Bố cục mobile",
    "layout_mobile_cols": "Số cột mobile",
    "role": "Vai trò",
    "can_edit_booking": "Có thể sửa booking",
    "is_admin": "Quản trị viên",
    "is_homepage": "Trang chủ",
    "is_available": "Còn hàng",
    "is_best_seller": "Bán chạy",
    "use_tabs": "Dùng tabs",
    "auto_play": "Tự chạy",
    "is_swiper": "Dùng swiper",
    "swiper_interval": "Khoảng lặp",
    "sort_order": "Thứ tự",
    "base_price": "Giá cơ bản",
    "cover_position": "Vị trí ảnh bìa",
    "modal_size": "Kích thước modal",
    "display_ratio": "Tỷ lệ hiển thị",
    "grid_col_span": "Số cột lưới",
    "grid_row_span": "Số hàng lưới",
    "tab_config": "Cấu hình tab",
    "sizes": "Kích cỡ",
    "toppings": "Topping",
    "booking_data": "Dữ liệu đặt bàn",
    "items": "Mặt hàng",
    "current_values": "Giá trị hiện tại",
    "requested_changes": "Thay đổi yêu cầu",
    "media_key": "Khóa media",
    "dish_key": "Khóa món",
    "author": "Tác giả",
}


def normalize_ws(value: str) -> str:
    return " ".join(value.split())


def repair_mojibake(value: str) -> str:
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


def humanize_column(column: str) -> str:
    return LABELS.get(column, column.replace("_", " ").strip().capitalize())


def normalize_text_value(value: Any) -> Any:
    if isinstance(value, str):
        value = normalize_ws(repair_mojibake(value))
        return value
    if isinstance(value, list):
        cleaned = [normalize_text_value(item) for item in value]
        return [item for item in cleaned if item not in ("", None, [], {})]
    if isinstance(value, dict):
        cleaned_dict: Dict[str, Any] = {}
        for key, item in value.items():
            cleaned_item = normalize_text_value(item)
            if cleaned_item not in ("", None, [], {}):
                cleaned_dict[key] = cleaned_item
        return cleaned_dict
    return value


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


def _looks_like_url_or_asset(value: str) -> bool:
    lowered = value.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("www.")
        or any(lowered.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".mp4", ".mov"))
    )


def summarize_json_text(value: Any) -> str:
    fragments: List[str] = []

    def walk(item: Any, key: Optional[str] = None) -> None:
        if key and key in JSON_IGNORE_KEYS:
            return
        if isinstance(item, dict):
            for sub_key, sub_value in item.items():
                if sub_key in JSON_IGNORE_KEYS:
                    continue
                if sub_key in JSON_TEXT_KEYS:
                    walk(sub_value, sub_key)
                elif isinstance(sub_value, (dict, list)):
                    walk(sub_value, sub_key)
            return
        if isinstance(item, list):
            for sub_item in item:
                walk(sub_item, key)
            return
        if isinstance(item, str):
            text = normalize_ws(repair_mojibake(item))
            if text and not _looks_like_url_or_asset(text) and (key in JSON_TEXT_KEYS or key is None):
                fragments.append(text)

    walk(normalize_text_value(value))

    cleaned: List[str] = []
    seen = set()
    for fragment in fragments:
        if fragment and fragment not in seen:
            seen.add(fragment)
            cleaned.append(fragment)
    return ", ".join(cleaned[:20])


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
            if not line.startswith("`"):
                continue
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


def format_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        parsed = parse_jsonish(value)
        if parsed is not value:
            return summarize_json_text(parsed)
        return normalize_ws(repair_mojibake(value))
    if isinstance(value, (dict, list)):
        return summarize_json_text(value)
    return normalize_ws(str(value))


def looks_useful(column: str, value: Any) -> bool:
    if value is None:
        return False
    if column in SKIP_COLUMNS:
        return False
    if isinstance(value, str):
        if not value.strip():
            return False
        if column.endswith("_id") and column not in {"store_id", "user_id", "store_menu_id"}:
            return False
        if len(value.strip()) < 2 and column not in {"role", "type", "status", "is_admin"}:
            return False
        return True
    return True


def field_pairs(table: str, row: Dict[str, Any]) -> List[Tuple[str, Any]]:
    fields = TABLE_FIELDS.get(table) or row.keys()
    pairs: List[Tuple[str, Any]] = []
    for col in fields:
        if col not in row:
            continue
        value = row[col]
        if looks_useful(col, value):
            pairs.append((col, value))
    return pairs


def format_pairs(pairs: Sequence[Tuple[str, Any]]) -> str:
    parts: List[str] = []
    for col, value in pairs:
        formatted = format_value(value)
        if formatted:
            parts.append(f"{humanize_column(col)}: {formatted}")
    return "; ".join(parts)


def json_text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return summarize_json_text(value)
    if isinstance(value, str):
        parsed = parse_jsonish(value)
        if parsed is not value:
            return summarize_json_text(parsed)
        return normalize_ws(repair_mojibake(value))
    return normalize_ws(str(value))


def build_text(table: str, row: Dict[str, Any]) -> str:
    clean_row = {col: normalize_text_value(value) for col, value in row.items()}
    pairs = field_pairs(table, clean_row)

    if table == "bookings":
        bits = ["Thông tin booking"]
        for col in ("customer_name", "customer_phone", "booking_at", "time_slot", "guests", "status", "cancel_reason", "notes"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "signature_dishes":
        bits = ["Thông tin món ăn"]
        for col in ("title", "description", "base_price", "status", "rating", "is_best_seller", "is_available"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "store_menus":
        bits = ["Thông tin thực đơn"]
        for col in ("name", "layout", "layout_mode", "sort_order"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "stores":
        bits = ["Thông tin cửa hàng"]
        for col in ("name", "store_type", "address", "location", "phone", "email", "opening_hours", "rating_score", "rating_text", "review_count"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "media_highlights":
        bits = ["Thông tin nổi bật"]
        for col in ("title", "tag", "author", "sort_order"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "users":
        bits = ["Thông tin người dùng"]
        for col in ("name", "email", "note", "is_admin", "last_accessed_store_id"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "store_user":
        bits = ["Thông tin phân quyền cửa hàng"]
        for col in ("user_id", "store_id", "role", "can_edit_booking"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "store_applications":
        bits = ["Thông tin đăng ký cửa hàng"]
        for col in ("name", "slug", "address", "phone", "status", "admin_note"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    if table == "store_change_requests":
        bits = ["Thông tin yêu cầu thay đổi"]
        for col in ("store_id", "status", "note", "admin_note", "requested_changes", "current_values"):
            value = clean_row.get(col)
            if looks_useful(col, value):
                bits.append(f"{humanize_column(col)}: {json_text(value)}")
        if len(bits) == 1:
            bits.append(format_pairs(pairs))
        return " | ".join([bit for bit in bits if bit])

    parts: List[str] = [f"Thông tin {table.replace('_', ' ')}"]
    for col, value in pairs:
        formatted = json_text(value)
        if formatted:
            parts.append(f"{humanize_column(col)}: {formatted}")

    if len(parts) == 1:
        for col, value in row.items():
            if looks_useful(col, value):
                formatted = json_text(value)
                if formatted:
                    parts.append(f"{humanize_column(col)}: {formatted}")

    return " | ".join(parts)


def iter_insert_statements(sql_text: str) -> Iterable[Tuple[str, str]]:
    insert_re = re.compile(r"INSERT INTO `([^`]+)` VALUES\s*(.*?);", re.S)
    for match in insert_re.finditer(sql_text):
        yield match.group(1), match.group(2)


def convert(sql_path: Path, out_path: Path) -> int:
    sql_text = sql_path.read_text(encoding="utf-8", errors="replace")
    table_columns = extract_table_columns(sql_text)

    rows: List[Dict[str, Any]] = []
    for table, values_sql in iter_insert_statements(sql_text):
        if table in SKIP_TABLES:
            continue
        columns = table_columns.get(table)
        if not columns:
            continue
        for row_index, tuple_sql in enumerate(split_tuples(values_sql), start=1):
            values = parse_tuple(tuple_sql)
            if len(values) != len(columns):
                continue
            row = dict(zip(columns, values))
            text = build_text(table, row).strip()
            if not text:
                continue
            row_id = row.get("id") or f"{table}-{row_index}"
            rows.append(
                {
                    "id": f"{table}-{row_id}",
                    "text": text,
                    "metadata": {
                        "source": sql_path.name,
                        "table": table,
                    },
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for item in rows:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a MySQL dump to a RAG JSONL corpus.")
    parser.add_argument("--sql", type=Path, default=DEFAULT_SQL, help="Input SQL dump path.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output JSONL path.")
    args = parser.parse_args()

    count = convert(args.sql, args.out)
    print(f"wrote {count} rows to {args.out}")


if __name__ == "__main__":
    main()
