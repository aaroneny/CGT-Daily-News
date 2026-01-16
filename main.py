import feedparser
import datetime
import pytz
from deep_translator import GoogleTranslator
from time import mktime

# --- 核心配置区 ---

# 1. 升级版 RSS 源：锁定 PR Newswire, Business Wire, GlobeNewswire (一手企业通稿)
# 使用 when:1d 强制只搜24小时内，并组合你的核心关键词
# 语法说明：(来源1 OR 来源2) AND (关键词组合)
RSS_URLS = [
    # 综合搜索：限定在一手通稿平台，搜索 FDA, IND, CAR-T, In vivo 等关键词
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com+OR+site:globenewswire.com)+AND+(CAR-T+OR+%22Cell+Therapy%22+OR+%22Gene+Therapy%22+OR+%22In+vivo%22+OR+IND+OR+FDA)+when:1d&hl=en-US&gl=US&ceid=US:en",
    
    # 补充搜索：防止漏网之鱼，针对 In vivo CAR-T 的全网最新（不仅仅是通稿）
    "https://news.google.com/rss/search?q=%22In+vivo+CAR-T%22+when:1d&hl=en-US&gl=US&ceid=US:en"
]

# 2. 关键词过滤（白名单）- 只要标题包含这些词中的任意一个，就保留
KEYWORDS = [
    "FDA", "IND", "approval", "cleared", "clinical trial", "trial start", 
    "dosed", "fast track", "orphan drug", "submission", "pipeline", 
    "In vivo", "CAR-T", "TCR-T", "NK", "gene editing", "LNP", "delivery"
]

# 3. 排除词（黑名单）- 过滤掉非研发类的噪音
EXCLUDE_WORDS = [
    "market size", "market report", "share", "forecast", "outlook", 
    "stock", "dividend", "loss", "profit", "quarterly result", "lawsuit"
]

def is_recent(published_parsed):
    """
    严格检查新闻时间是否在过去 24 小时内
    """
    if not published_parsed:
        return False
    
    # 将 RSS 时间转换为 UTC datetime
    news_time = datetime.datetime.fromtimestamp(mktime(published_parsed)).replace(tzinfo=pytz.utc)
    current_time = datetime.datetime.now(pytz.utc)
    
    # 计算时间差
    diff = current_time - news_time
    
    # 也就是 24 小时 (86400秒)
    if diff.total_seconds() <= 86400:
        return True
    return False

def fetch_news():
    news_items = []
    seen_links = set()
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print("正在扫描全球最新一手通稿 (Past 24h)...")

    for url in RSS_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            
            # 1. 严格的时间筛选
            if not is_recent(entry.published_parsed):
                continue
            
            if link in seen_links:
                continue
            seen_links.add(link)

            # 2. 关键词筛选
            if any(k.lower() in title.lower() for k in KEYWORDS) and \
               not any(e.lower() in title.lower() for e in EXCLUDE_WORDS):
                
                # 清理标题
                clean_title_en = title.rsplit(' - ', 1)[0]
                
                try:
                    title_zh = translator.translate(clean_title_en)
                except:
                    title_zh = "翻译暂不可用"

                # 记录发布时间 (转换为北京时间显示)
                news_dt = datetime.datetime.fromtimestamp(mktime(entry.published_parsed)).replace(tzinfo=pytz.utc)
                beijing_dt = news_dt.astimezone(pytz.timezone('Asia/Shanghai'))
                date_str = beijing_dt.strftime('%m-%d %H:%M')

                news_items.append({
                    "title_zh": title_zh,
                    "title_en": clean_title_en,
                    "link": link,
                    "date_str": date_str,
                    "timestamp": news_dt.timestamp() # 用于后续排序
                })
    
    # 按时间倒序排列（最新的在最上面）
    news_items.sort(key=lambda x: x["timestamp"], reverse=True)
    return news_items

def update_readme(news_items):
    beijing_tz = pytz.timezone('Asia/Shanghai')
    today_str = datetime.datetime.now(beijing_tz).strftime("%Y-%m-%d")
    now_str = datetime.datetime.now(beijing_tz).strftime("%H:%M")
    
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    # 我们每天只生成当天的板块，或者直接覆盖
    # 这里采用“累加模式”，并在顶部显示“今日最新”
    
    header_marker = "## 🚀 今日最新 (Latest 24h)"
    
    # 如果要保留历史记录，可以在这里做逻辑，这里为了简洁，我演示“每次更新覆盖最新列表”
    # 但保留下方的“历史归档”结构（如果需要可以教你怎么做归档）
    # 目前逻辑：刷新整个 README 的新闻区域
    
    if header_marker not in content:
        # 初始化
        new_content_top = f"# 🧬 全球 CGT 每日情报\n\n{header_marker}\n> 更新于北京时间: {today_str} {now_str}\n\n"
        old_content = "" # 或者保留原有的介绍
    else:
        new_content_top = content.split(header_marker)[0] + f"{header_marker}\n> 更新于北京时间: {today_str} {now_str}\n\n"

    news_list = ""
    for item in news_items:
        # 增加时间标签
        news_list += f"- `[{item['date_str']}]` **{item['title_zh']}**<br><small>*{item['title_en']}* [🔗Source]({item['link']})</small>\n"
    
    if not news_items:
        news_list += "- 截至目前，过去24小时内全球主要通稿平台暂无相关重磅发布。\n"

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(new_content_top + news_list)

if __name__ == "__main__":
    items = fetch_news()
    update_readme(items)
