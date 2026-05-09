import re
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
from playwright.sync_api import sync_playwright


def parse_ref_code(text: str) -> str:
    """
    提取 RefNO 的代码部分（方括号内），用于兼容只看代码的场景。
    """
    if not text:
        return ""
    m = re.match(r"^\[?\[([^\]]+)\]", text)
    return m.group(1).strip() if m else ""


def open_search_page(page, keyword: str, start_count: int) -> None:
    url = (
        "https://www.ssgdfs.com/cn/search/resultsTotal"
        f"?startCount={start_count}&offShop=&suggestReSearchReq=true"
        f"&orReSearchReq=true&query={keyword}"
    )
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1800)

    body_text = page.inner_text("body") if page.locator("body").count() else ""
    if any(s in body_text for s in ["temporary connection issue", "连接问题", "연결에 문제가"]):
        raise RuntimeError("命中风控页，请稍后重试或先手动访问站点后再执行。")


def extract_page_items(page, keyword: str):
    return page.evaluate(
        r"""
        ([kw]) => {
          const rows = [];
          const cards = Array.from(document.querySelectorAll('li.prodCont'));
          for (const li of cards) {
            const brand = (li.querySelector('.brandName')?.textContent || '').trim();
            const name = (li.querySelector('.prodName')?.textContent || '').trim();
            const price = (li.querySelector('.saleDollar')?.textContent || '').replace(/\s+/g, '');
            const a = li.querySelector('a[data-param3]');
            const dataParam3 = a ? (a.getAttribute('data-param3') || '') : '';
            const onclick = a ? (a.getAttribute('onclick') || '') : '';

            let goosCd = '';
            const m = onclick.match(/goos_cd\s*:\s*'([^']+)'/i);
            if (m) goosCd = m[1];

            rows.push({
              keyword: kw,
              brand,
              name,
              price,
              dataParam3,
              goosCd
            });
          }

          const totalMatch = (document.body?.innerText || '').match(/(\d+)\s*个结果/);
          const totalCount = totalMatch ? Number(totalMatch[1]) : 0;
          const listCount = Number(document.querySelector('#filterSelects')?.getAttribute('data-list-count') || 40);
          return { rows, totalCount, listCount };
        }
        """,
        [keyword],
    )


def scrape(keyword: str):
    all_rows = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        open_search_page(page, keyword, 0)
        first = extract_page_items(page, keyword)
        all_rows.extend(first["rows"])

        total = first["totalCount"] or len(first["rows"])
        page_size = first["listCount"] or 40

        for start in range(page_size, total, page_size):
            open_search_page(page, keyword, start)
            data = extract_page_items(page, keyword)
            all_rows.extend(data["rows"])
            print(f"已抓取分页 startCount={start}，累计 {len(all_rows)}")

        browser.close()

    cleaned = []
    for row in all_rows:
        cleaned.append(
            {
                "关键词": row.get("keyword", ""),
                "品牌": row.get("brand", ""),
                "商品名": row.get("name", ""),
                "销售价": row.get("price", ""),
                "RefNO": parse_ref_code(row.get("dataParam3", "")),
                "商品编码": row.get("goosCd", ""),
            }
        )

    cleaned = [r for r in cleaned if r["商品名"] or r["RefNO"] or r["商品编码"]]
    return cleaned


def export_excel(rows, keyword: str, output_dir: Path | None = None) -> Path:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_keyword = re.sub(r'[\\/:*?"<>|]', "_", keyword)
    base_dir = output_dir if output_dir is not None else Path.cwd()
    base_dir.mkdir(parents=True, exist_ok=True)
    output = base_dir / f"ssgdfs_{safe_keyword}_{ts}.xlsx"
    pd.DataFrame(rows).to_excel(output, index=False)
    return output


def main():
    keyword = " ".join(sys.argv[1:]).strip()
    if not keyword:
        keyword = input("请输入搜索关键词: ").strip()
    if not keyword:
        print("关键词不能为空")
        sys.exit(1)

    rows = scrape(keyword)
    if not rows:
        print("未抓取到数据")
        sys.exit(2)

    out = export_excel(rows, keyword)
    print(f"完成，共 {len(rows)} 条，文件: {out}")


if __name__ == "__main__":
    main()

