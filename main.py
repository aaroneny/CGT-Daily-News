import feedparser
import datetime
import pytz
from deep_translator import GoogleTranslator
from time import mktime
import re
import os       # 新增
import requests # 新增

# ================= 配置区 =================

# --- 1. 全球源 (Global / FDA / In vivo) ---
GLOBAL_RSS_URLS = [
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com)+AND+%22In+vivo%22+AND+(%22CAR-T%22+OR+%22Gene+Editing%22)+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com+OR+site:fda.gov)+AND+(CAR-T+OR+%22Cell+Therapy%22)+AND+(IND+OR+FDA+OR+Approval+OR+Clinical)+when:1d&hl=en-US&gl=US&ceid=US:en"
]

# --- 2. 中国源 (China / NMPA / CDE) ---
CHINA_RSS_URLS = [
    "https://news.google.com/rss/search?q=(%E7%BB%86%E8%83%9E%E6%B2%BB%E7%96%97+OR+CAR-T+OR+%E5%9F%BA%E5%9B%A0%E6%B2%BB%E7%96%97)+AND+(NMPA+OR+CDE+OR+%E8%8E%B7%E6%89%B9+OR+%E4%B8%B4%E5%BA%8A+OR+IND)+when:1d&hl=zh-CN&gl=CN&ceid=CN:zh-Hans",
    "https://news.google.com/rss/search?q=China+AND+(CAR-T+OR+%22Cell+Therapy%22)+AND+(NMPA+OR+IND+OR+Approval)+when:1d&hl=en-US&gl=US&ceid=US:en"
]

# 关键词配置
GLOBAL_KEYWORDS = ["In vivo", "CAR-T", "TCR-T", "NK", "FDA", "IND", "Approval", "Clinical", "Pipeline", "LNP"]
CHINA_KEYWORDS = ["NMPA", "CDE", "IND", "受理", "获批", "临床", "试验", "申请", "药监局", "China", "Chinese", "Approval", "Cleared", "CAR-T", "Cell Therapy"]
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
    """通用抓取函数"""
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

            if any(k.lower() in title.lower() for k in keywords) and \
               not any(e.lower() in title.lower() for e in EXCLUDE_WORDS):
                
                clean_title = title.rsplit(' - ', 1)[0]
                is_chinese_text = bool(re.search(r'[\u4e00-\u9fa5]', clean_title))
                
                if not is_chinese_text:
                    try:
                        title_disp = translator.translate(clean_title)
                    except:
                        title_disp = clean_title
                else:
                    title_disp = clean_title

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

    md_content = f"""# 🧬 CGT 每日情报 (Daily Brief)
> **日期**: {today_str} | **更新时间**: {update_time_str} (北京时间)
> **监控范围**: Global (In vivo/FDA) & China (NMPA/Biotech)

---

"""
    md_content += "## 🌍 全球前沿 (FDA / In vivo / MNCs)\n"
    if global_news:
        for item in global_news:
            md_content += f"- `[{item['date_str']}]` **{item['title_show']}**\n  <br><small>🇬🇧 *{item['title_origin']}* [🔗Source]({item['link']})</small>\n"
    else:
        md_content += "- *当前暂无过去 24 小时内的相关重磅全球资讯。*\n"
    
    md_content += "\n---\n\n"

    md_content += "## 🇨🇳 中国动态 (NMPA / Domestic Players)\n"
    if china_news:
        for item in china_news:
            is_origin_cn = bool(re.search(r'[\u4e00-\u9fa5]', item['title_origin']))
            if is_origin_cn:
                md_content += f"- `[{item['date_str']}]` **{item['title_show']}** [🔗阅读原文]({item['link']})\n"
            else:
                md_content += f"- `[{item['date_str']}]` **{item['title_show']}**\n  <br><small>🇬🇧 *{item['title_origin']}* [🔗Source]({item['link']})</small>\n"
    else:
        md_content += "- *当前暂无过去 24 小时内的相关中国区最新资讯。*\n"

    return md_content

def update_readme(content):
    with open("README.md", "w", encoding="utf-8") as f:
        f.write(content)

# ================= 新增：微信推送函数 =================
def pushplus_notify(content):
    token = os.environ.get("PUSHPLUS_TOKEN")
    if not token:
        print("⚠️ 未检测到 PUSHPLUS_TOKEN，跳过微信推送")
        return
    
    # 获取当前日期用于标题
    beijing_tz = pytz.timezone('Asia/Shanghai')
    today_str = datetime.datetime.now(beijing_tz).strftime("%Y-%m-%d")
    
    url = "http://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": f"🧬 CGT日报 | {today_str}",
        "content": content,
        "template": "markdown",
        "channel": "wechat"
    }
    try:
        resp = requests.post(url, json=payload)
        print(f"微信推送结果: {resp.text}")
    except Exception as e:
        print(f"微信推送失败: {e}")

if __name__ == "__main__":
    # 1. 抓取数据
    global_items = fetch_group_news(GLOBAL_RSS_URLS, GLOBAL_KEYWORDS, "全球组")
    china_items = fetch_group_news(CHINA_RSS_URLS, CHINA_KEYWORDS, "中国组")
    
    # 2. 生成内容
    full_content = generate_markdown(global_items, china_items)
    
    # 3. 更新 README
    update_readme(full_content)
    
    # 4. 发送微信推送 (新增步骤)
    print("正在发送微信推送...")
    pushplus_notify(full_content)
