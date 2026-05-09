from pathlib import Path

from flask import Flask, render_template, request, send_file, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from scrape_ssgdfs import export_excel, scrape

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_prefix=1, x_proto=1, x_host=1)
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"


@app.get("/")
def index():
    return render_template("index.html", rows=[])


@app.post("/generate")
def generate():
    keyword = (request.form.get("keyword") or "").strip()
    if not keyword:
        return render_template("index.html", error="请输入关键词", rows=[])

    try:
        rows = scrape(keyword)
    except Exception as exc:
        return render_template("index.html", error=f"抓取失败: {exc}", keyword=keyword, rows=[])

    if not rows:
        return render_template("index.html", keyword=keyword, rows=[], no_data=True)

    output = export_excel(rows, keyword, OUTPUT_DIR)
    download_url = url_for("download", filename=output.name)
    return render_template(
        "index.html",
        keyword=keyword,
        total=len(rows),
        rows=rows,
        download_url=download_url,
        file_name=output.name,
    )


@app.get("/download/<path:filename>")
def download(filename: str):
    file_path = OUTPUT_DIR / filename
    if not file_path.exists():
        return "文件不存在", 404
    return send_file(file_path, as_attachment=True, download_name=filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
