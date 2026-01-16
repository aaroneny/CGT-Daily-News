import feedparser
import datetime
import pytz
import re

# 1. 配置数据源 (Google News RSS 针对特定关键词)
# 你可以添加多个关键词组合
RSS_URLS = [
    "https://news.google.com/rss/search?q=Cell+Gene+Therapy+FDA+IND&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=CAR-T+approval+pipeline&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=biotech+series+funding+cell+therapy&hl=en-US&gl=US&ceid=US:en"
]

# 2. 关键词过滤 (简单的规则引擎)
# 只有包含这些关键词的新闻才会被保留
KEYWORDS = ["FDA", "IND", "approval", "cleared", "clinical trial", "submission", "green light", "Series A", "Series B"]
EXCLUDE_WORDS = ["market report", "stocks", "forecast", "size", "share"] # 排除掉无用的市场分析报告

def fetch_news():
    news_items = []
    seen_links = set() # 去重

    for url in RSS_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            pub_date = entry.published
            
            # 简单去重
            if link in seen_links:
                continue
            seen_links.add(link)

            # 过滤逻辑
            if any(k.lower() in title.lower() for k in KEYWORDS) and \
               not any(e.lower() in title.lower() for e in EXCLUDE_WORDS):
                news_items.append({
                    "title": title,
                    "link": link,
                    "date": pub_date
                })
    return news_items

def update_readme(news_items):
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
    
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    # 寻找标记位，如果没有则手动添加
    header_marker = "## 🧬 最新 CGT 行业动态"
    if header_marker not in content:
        new_content = content + f"\n\n{header_marker}\n\n更新时间: {now}\n\n"
    else:
        # 截断旧内容，保留 Header 之前的部分
        new_content = content.split(header_marker)[0] + f"{header_marker}\n\n更新时间: {now}\n\n"

    # 生成 Markdown 列表
    for item in news_items:
        # 清理 Google News 标题中的来源后缀 (例如 " - PR Newswire")
        clean_title = item['title'].rsplit(' - ', 1)[0]
        new_content += f"- **{clean_title}** ([链接]({item['link']}))\n"
    
    # 如果没有新闻
    if not news_items:
        new_content += "- 今日暂无符合条件的重要资讯。\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content)

if __name__ == "__main__":
    items = fetch_news()
    update_readme(items)
