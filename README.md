# SSGDFS 爬虫工具（Python）

支持两种方式：
- 命令行抓取并导出 Excel
- Web 页面输入关键词后生成并下载 Excel

## 安装依赖
建议使用 Python 3.12，并在项目目录下创建虚拟环境：

```bash
python -m venv .venv
./.venv/bin/python -m ensurepip --upgrade
./.venv/bin/python -m pip install --upgrade pip
```

安装项目依赖时，建议直接使用官方 PyPI 源。
部分国内镜像可能缺少 `playwright==1.52.0`，会导致安装失败。

```bash
./.venv/bin/python -m pip install -i https://pypi.org/simple -r requirements.txt
./.venv/bin/python -m playwright install chromium
```

## 方式1：命令行
```bash
./.venv/bin/python scrape_ssgdfs.py Aesop
```
输出示例：`ssgdfs_Aesop_时间戳.xlsx`

## 方式2：Web 页面
1. 启动服务
```bash
./.venv/bin/python app.py
```
2. 浏览器打开
```text
http://127.0.0.1:5000
```
3. 输入关键词 -> 点击“生成” -> 点击“导出 Excel”

## 输出目录
- 命令行：当前目录
- Web 页面：`outputs/` 目录

## 说明
- 目标站存在风控，脚本已补充风控页识别；若仍被拦截，稍后重试或先手动访问站点首页再执行。
- 搜索结果页显示的总数与最终导出条数可能有 1 条左右差异，这是当前去重逻辑按商品编码和展示字段合并后的结果。
