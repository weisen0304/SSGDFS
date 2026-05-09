import json
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, request, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from scrape_ssgdfs import export_excel, scrape

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1, x_proto=1, x_host=1)
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
HISTORY_FILE = OUTPUT_DIR / "generation_history.jsonl"
CACHE_TTL_SECONDS = 900
MAX_HISTORY_SHOW = 30

# 简单内存缓存：{ keyword: {"ts": float, "rows": list[dict]} }
SCRAPE_CACHE = {}


def format_duration(duration_ms: int) -> str:
    total_seconds = max(0, int(duration_ms // 1000))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def append_history(keyword: str, total: int, file_name: str, source: str, duration_ms: int) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "keyword": keyword,
        "total": total,
        "file_name": file_name,
        "source": source,
        "duration_ms": duration_ms,
        "duration_text": format_duration(duration_ms),
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_history(limit: int = MAX_HISTORY_SHOW) -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    records = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    records.reverse()
    for r in records:
        file_name = r.get("file_name") or ""
        file_path = OUTPUT_DIR / file_name if file_name else None
        r["file_exists"] = bool(file_path and file_path.exists())
        r["download_url"] = url_for("download", filename=file_name) if file_name else ""
    return records


@app.get("/")
def index():
    return render_template("index.html", rows=[], history=read_history())


@app.post("/generate")
def generate():
    start = time.time()
    keyword = (request.form.get("keyword") or "").strip()
    if not keyword:
        return render_template("index.html", error="请输入关键词", rows=[], history=read_history())

    cache_hit = False
    try:
        now = time.time()
        cache_item = SCRAPE_CACHE.get(keyword)
        if cache_item and (now - cache_item["ts"] <= CACHE_TTL_SECONDS):
            rows = cache_item["rows"]
            cache_hit = True
        else:
            rows = scrape(keyword)
            SCRAPE_CACHE[keyword] = {"ts": now, "rows": rows}
    except Exception as exc:
        return render_template("index.html", error=f"抓取失败: {exc}", keyword=keyword, rows=[], history=read_history())

    if not rows:
        return render_template("index.html", keyword=keyword, rows=[], no_data=True, history=read_history())

    output = export_excel(rows, keyword, OUTPUT_DIR)
    download_url = url_for("download", filename=output.name)
    duration_ms = int((time.time() - start) * 1000)
    source = "cache" if cache_hit else "fresh"
    append_history(keyword, len(rows), output.name, source, duration_ms)

    return render_template(
        "index.html",
        keyword=keyword,
        total=len(rows),
        rows=rows,
        download_url=download_url,
        file_name=output.name,
        cache_hit=cache_hit,
        duration_ms=duration_ms,
        duration_text=format_duration(duration_ms),
        history=read_history(),
    )


@app.post("/clear-cache")
def clear_cache():
    SCRAPE_CACHE.clear()
    return render_template("index.html", rows=[], history=read_history(), message="缓存已清空")


@app.post("/clear-history")
def clear_history():
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    return render_template("index.html", rows=[], history=[], message="生成记录已清空")


@app.post("/clear-history-and-files")
def clear_history_and_files():
    deleted = 0
    missing = 0
    if HISTORY_FILE.exists():
        lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            file_name = (record.get("file_name") or "").strip()
            if not file_name:
                continue
            target = OUTPUT_DIR / file_name
            if target.exists() and target.is_file():
                target.unlink()
                deleted += 1
            else:
                missing += 1
        HISTORY_FILE.unlink()
    return render_template(
        "index.html",
        rows=[],
        history=[],
        message=f"记录已清空，已删除Excel {deleted} 个，缺失 {missing} 个",
    )


@app.post("/delete-history-item")
def delete_history_item():
    keyword = (request.form.get("keyword") or "").strip()
    record_time = (request.form.get("record_time") or "").strip()
    file_name = (request.form.get("file_name") or "").strip()

    if not HISTORY_FILE.exists():
        return render_template("index.html", rows=[], history=[], message="记录文件不存在")

    kept = []
    removed = 0
    lines = HISTORY_FILE.read_text(encoding="utf-8").splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            # 非法行保留，避免误删
            kept.append(line)
            continue

        same = (
            (record.get("keyword") or "") == keyword
            and (record.get("time") or "") == record_time
            and (record.get("file_name") or "") == file_name
        )
        if same and removed == 0:
            removed += 1
            continue
        kept.append(json.dumps(record, ensure_ascii=False))

    HISTORY_FILE.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    msg = "单条记录已删除" if removed else "未找到要删除的记录"
    return render_template("index.html", rows=[], history=read_history(), message=msg)


@app.get("/download/<path:filename>")
def download(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return "文件不存在", 404
    return send_file(file_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
