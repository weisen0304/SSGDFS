# SSGDFS 爬虫工具（Python）

支持两种方式：
- 命令行抓取并导出 Excel
- Web 页面输入关键词后生成并下载 Excel

## 安装依赖
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## 方式1：命令行
```bash
python scrape_ssgdfs.py 伊索
```
输出示例：`ssgdfs_伊索_时间戳_py.xlsx`

## 方式2：Web 页面
1. 启动服务
```bash
python app.py
```
2. 浏览器打开
```text
http://127.0.0.1:5000
```
3. 输入关键词 -> 点击“生成” -> 点击“导出 Excel”

## 输出目录
- 命令行：当前目录
- Web 页面：`outputs/` 目录
