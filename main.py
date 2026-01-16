import feedparser
import datetime
import pytz
from deep_translator import GoogleTranslator
from time import mktime
import re

# ================= 配置区 =================

# --- 1. 全球源 (Global / FDA / In vivo) ---
GLOBAL_RSS_URLS = [
    # In vivo CAR-T & 基因编辑 (高优先级)
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com)+AND+%22In+vivo%22+AND+(%22CAR-T%22+OR+%22Gene+Editing%22)+when:1d&hl=en-US&gl=US&ceid=US:en",
    # 常规 FDA / CAR-T 进展
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com+OR+site:fda.gov)+AND+(CAR-T+OR+%22Cell+Therapy%22)+AND+(IND+OR+FDA+OR+Approval+OR+Clinical)+when:1d&hl=en-US&gl=US&ceid=US:en"
]

# --- 2. 中国源 (China / NMPA / CDE) ---
# 搜索逻辑：搜索中文关键词 (NMPA, CDE, 获批, IND) 或 英文关于中国的报道
CHINA_RSS_URLS = [
    # 中文搜索：细胞/基因治疗 + 监管/进展
    "https://news.google.com/rss/search?q=(%E7%BB%86%E8%83%9E%E6%B2%BB%E7%96%97+OR+CAR-T+OR+%E5%9F%BA%E5%9B%A0%E6%B2%BB%E7%96%97)+AND+(NMPA+OR+CDE+OR+%E8%8E%B7%E6%89%B9+OR+%E4%B8%B4%E5%BA%8A+OR+IND)+when:1d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    # 英文搜索：China + Biotech 关键词
    "https://news.google.com/rss/search?q=China+AND+(CAR-T+OR+%22Cell+Therapy%22)+AND+(NMPA+OR+IND+OR+Approval)+when:1d&hl=en-US&gl=US&ceid=US:en"
]

# 全球关键词白名单
GLOBAL_KEYWORDS = [
    "In vivo", "CAR-T", "TCR-T", "NK", "FDA", "IND", "Approval", "Clinical", "Pipeline", "LNP"
]

# 中国关键词白名单 (包含中文)
CHINA_KEYWORDS = [
    "NMPA", "CDE", "IND", "受理", "获批", "临床", "试验", "申请", "药监局", 
    "China", "Chinese", "Approval", "Cleared", "CAR-T", "Cell Therapy"
]

# 排除噪音
EXCLUDE_WORDS = ["Market size", "Report", "Forecast", "Stock", "Dividend", "市场规模", "研报", "股价", "预测"]

# ================= 核心逻辑 =================

def is_recent(published_parsed):
    """24小时熔断机制"""
    if not published_parsed: return False
    news_time = datetime.datetime.fromtimestamp(mktime(published_parsed)).replace(tzinfo=pytz.utc)
    current_time = datetime.datetime.now(pytz.utc)
    return (current_time - news_time).total_seconds() <= 86400

def highlight_title(title):
    """视觉标记"""
    flags = []
    if re.search(r"In\s*vivo", title, re.IGNORECASE):
        flags.append("🔥In-vivo")
    if re.search(r"FDA|NMPA|Approval|获批|Approved", title, re.IGNORECASE):
        flags.append("🏛️监管")
    
    if flags:
        return f"{' '.join(flags)} | {title}"
    return title

def fetch_group_news(urls, keywords, group_name):
    """通用抓取函数：根据传入的 URL 和 关键词 获取新闻"""
    news_items = []
    seen_links = set()
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print(f"正在扫描 {group_name} 数据源...")

    for url in urls:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            
            if not is_recent(entry.published_parsed): continue
            if link in seen_links: continue
            seen_links.add(link)

            # 关键词过滤
            if any(k.lower() in title.lower() for k in keywords) and \
               not any(e.lower() in title.lower() for e in EXCLUDE_WORDS):
                
                clean_title = title.rsplit(' - ', 1)[0]
                
                # 如果是英文，翻译成中文；如果是中文，直接用
                # 简单判断：如果标题包含中文常见标点或汉字比例高，则不翻译
                is_chinese_text = bool(re.search(r'[\u4e00-\u9fa5]', clean_title))
                
                if not is_chinese_text:
                    try:
                        title_disp = translator.translate(clean_title)
                    except:
                        title_disp = clean_title
                else:
                    title_disp = clean_title # 原生中文不翻译

                news_dt = datetime.datetime.fromtimestamp(mktime(entry.published_parsed)).replace(tzinfo=pytz.utc)
                beijing_dt = news_dt.astimezone(pytz.timezone('Asia/Shanghai'))
                
                news_items.append({
                    "title_show": highlight_title(title_disp),
                    "title_origin": clean_title,
                    "link": link,
                    "date_str": beijing_dt.strftime('%H:%M'),
                    "timestamp": news_dt.timestamp()
                })
    
    news_items.sort(key=lambda x: x["timestamp"], reverse=True)
    return news_items

def generate_markdown(global_news, china_news):
    beijing_tz = pytz.timezone('Asia/Shanghai')
    now = datetime.datetime.now(beijing_tz)
    today_str = now.strftime("%Y-%m-%d")
    update_time_str = now.strftime("%H:%M")

    # 1. 静态头部 (每次重写)
    md_content = f"""# 🧬 CGT 每日情报 (Daily Brief)
> **日期**: {today_str} | **更新时间**: {update_time_str} (北京时间)
> **监控范围**: Global (In vivo/FDA) & China (NMPA/Biotech)

---

"""

    # 2. 生成 Global 板块
    md_content += "## 🌍 全球前沿 (FDA / In vivo / MNCs)\n"
    if global_news:
        for item in global_news:
            md_content += f"- `[{item['date_str']}]` **{item['title_show']}**\n  <br><small>🇬🇧 *{item['title_origin']}* [🔗Source]({item['link']})</small>\n"
    else:
        md_content += "- *当前暂无过去 24 小时内的相关重磅全球资讯。*\n"
    
    md_content += "\n---\n\n"

    # 3. 生成 China 板块
    md_content += "## 🇨🇳 中国动态 (NMPA / Domestic Players)\n"
    if china_news:
        for item in china_news:
            # 如果原文就是中文，就不显示第二行英文原题了，保持简洁
            is_origin_cn = bool(re.search(r'[\u4e00-\u9fa5]', item['title_origin']))
            if is_origin_cn:
                md_content += f"- `[{item['date_str']}]` **{item['title_show']}** [🔗阅读原文]({item['link']})\n"
            else:
                md_content += f"- `[{item['date_str']}]` **{item['title_show']}**\n  <br><small>🇬🇧 *{item['title_origin']}* [🔗Source]({item['link']})</small>\n"
    else:
        md_content += "- *当前暂无过去 24 小时内的相关中国区最新资讯。*\n"

    return md_content

def update_readme(content):
    # 覆盖写入模式 'w'，确保彻底清除旧内容
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    # 分别抓取
    global_items = fetch_group_news(GLOBAL_RSS_URLS, GLOBAL_KEYWORDS, "全球组")
    china_items = fetch_group_news(CHINA_RSS_URLS, CHINA_KEYWORDS, "中国组")
    
    # 生成并写入
    full_content = generate_markdown(global_items, china_items)
    update_readme(full_content)
