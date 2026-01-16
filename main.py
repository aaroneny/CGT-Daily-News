import feedparser
import datetime
import pytz
from deep_translator import GoogleTranslator

# 1. 配置数据源
RSS_URLS = [
    "https://news.google.com/rss/search?q=Cell+Gene+Therapy+FDA+IND&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=CAR-T+approval+pipeline&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=biotech+series+funding+cell+therapy&hl=en-US&gl=US&ceid=US:en"
]

# 2. 关键词过滤
KEYWORDS = ["FDA", "IND", "approval", "cleared", "clinical trial", "submission", "green light", "Series A", "Series B"]
EXCLUDE_WORDS = ["market report", "stocks", "forecast", "size", "share"] 

def fetch_news():
    news_items = []
    seen_links = set()
    
    # 初始化翻译器：自动检测源语言 -> 翻译成简体中文
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print("正在获取新闻并翻译，请稍候...") # 方便在 Action 日志中查看进度

    for url in RSS_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            pub_date = entry.published
            
            if link in seen_links:
                continue
            seen_links.add(link)

            # 过滤逻辑
            if any(k.lower() in title.lower() for k in KEYWORDS) and \
               not any(e.lower() in title.lower() for e in EXCLUDE_WORDS):
                
                # --- 新增：清理标题并翻译 ---
                # 去掉 Google News 常见的尾巴，如 " - BioSpace"
                clean_title_en = title.rsplit(' - ', 1)[0]
                
                try:
                    # 执行翻译
                    title_zh = translator.translate(clean_title_en)
                except Exception as e:
                    print(f"翻译失败: {e}")
                    title_zh = "翻译暂不可用"

                news_items.append({
                    "title_zh": title_zh,
                    "title_en": clean_title_en,
                    "link": link,
                    "date": pub_date
                })
    return news_items

def update_readme(news_items):
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    header_marker = "## 🧬 最新 CGT 行业动态"
    
    # 构建新内容头部
    if header_marker not in content:
        new_header = content + f"\n\n{header_marker}\n\n更新时间: {now}\n\n"
        old_content = ""
    else:
        # 保留 Header 之前的内容（比如项目介绍），截断旧新闻
        new_header = content.split(header_marker)[0] + f"{header_marker}\n\n更新时间: {now}\n\n"
    
    # 构建新闻列表
    news_list = ""
    for item in news_items:
        # 格式：中文标题 (英文原题)
        news_list += f"- **{item['title_zh']}** <br> <small>*{item['title_en']}* [阅读原文]({item['link']})</small>\n"
    
    if not news_items:
        news_list += "- 今日暂无符合条件的重要资讯。\n"

    # 组合最终内容
    final_content = new_header + news_list

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(final_content)

if __name__ == "__main__":
    items = fetch_news()
    update_readme(items)
