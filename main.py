import feedparser
import datetime
import pytz
from deep_translator import GoogleTranslator
from time import mktime
import re

# --- 1. 高精 RSS 源配置 ---
# 我们构建了 3 个针对性的搜索组合，全部限定在 24 小时内 (when:1d)
RSS_URLS = [
    # [通道 A] In vivo CAR-T 与 下一代细胞治疗 (最核心)
    # 搜索逻辑：必须包含 "In vivo" 且必须包含 (CAR-T 或 基因编辑 或 LNP)，锁定企业通稿
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com+OR+site:globenewswire.com)+AND+%22In+vivo%22+AND+(%22CAR-T%22+OR+%22Gene+Editing%22+OR+%22LNP%22+OR+%22Vector%22)+when:1d&hl=en-US&gl=US&ceid=US:en",

    # [通道 B] 常规 CAR-T 企业重大进展 (排除科普文章)
    # 搜索逻辑：CAR-T + (IND 或 临床 或 FDA 或 融资)，排除市场报告
    "https://news.google.com/rss/search?q=(site:businesswire.com+OR+site:prnewswire.com+OR+site:globenewswire.com)+AND+%22CAR-T%22+AND+(IND+OR+FDA+OR+Clinical+OR+Pipeline+OR+Dosed)+when:1d&hl=en-US&gl=US&ceid=US:en",

    # [通道 C] FDA 监管与审批特别通道 (包含 FDA 官网)
    # 搜索逻辑：FDA + (细胞治疗 或 基因治疗) + (指南 或 批准 或 暂停)
    "https://news.google.com/rss/search?q=(site:fda.gov+OR+site:businesswire.com+OR+site:prnewswire.com)+AND+FDA+AND+(%22Cell+Therapy%22+OR+%22Gene+Therapy%22)+AND+(Guidance+OR+Approval+OR+IND+OR+Hold)+when:1d&hl=en-US&gl=US&ceid=US:en"
]

# --- 2. 关键词白名单 (命一即可) ---
KEYWORDS = [
    # 核心技术
    "In vivo", "In-vivo", "CAR-T", "CAR T", "Chimeric Antigen Receptor",
    "T-cell", "NK Cell", "TCR-T", "LNP", "Viral Vector", "AAV",
    
    # 监管与审批 (FDA)
    "FDA", "CBER", "IND", "BLA", "Fast Track", "Orphan Drug", "RMAT",
    "Approval", "Approved", "Cleared", "Green light", "Guidance", "Guideline",
    "Clinical Hold", "Complete Response Letter", "CRL",
    
    # 临床关键节点
    "Phase 1", "Phase I", "First Patient Dosed", "Trial Start", "Top-line data"
]

# --- 3. 噪音黑名单 ---
EXCLUDE_WORDS = [
    "Market size", "Market report", "Growth analysis", "CAGR", "Forecast", # 市场报告
    "Lawsuit", "Class action", "Investigation", # 律师事务所通稿
    "Dividend", "Quarterly results", "Financial results", # 纯财报
    "Skincare", "Cosmetic", "Veterinary" # 排除无关领域
]

def is_recent(published_parsed):
    """严格的24小时熔断检查"""
    if not published_parsed: return False
    news_time = datetime.datetime.fromtimestamp(mktime(published_parsed)).replace(tzinfo=pytz.utc)
    current_time = datetime.datetime.now(pytz.utc)
    return (current_time - news_time).total_seconds() <= 86400

def highlight_title(title):
    """视觉增强：为重点词添加 Emoji 或 加粗"""
    # 标记 In vivo
    if re.search(r"In\s*vivo", title, re.IGNORECASE):
        title = "🔥 " + title
    # 标记 FDA/Approval
    if re.search(r"FDA|Approval|Approved|IND", title, re.IGNORECASE):
        title = "🏛️ " + title
    return title

def fetch_news():
    news_items = []
    seen_links = set()
    translator = GoogleTranslator(source='auto', target='zh-CN')

    print("正在根据特定策略扫描 FDA 与 In vivo CAR-T 资讯...")

    for url in RSS_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            title = entry.title
            link = entry.link
            
            # 1. 时间清洗
            if not is_recent(entry.published_parsed): continue
            # 2. 去重
            if link in seen_links: continue
            seen_links.add(link)

            # 3. 关键词双重校验
            if any(k.lower() in title.lower() for k in KEYWORDS) and \
               not any(e.lower() in title.lower() for e in EXCLUDE_WORDS):
                
                # 清理并翻译
                clean_title_en = title.rsplit(' - ', 1)[0]
                try:
                    title_zh = translator.translate(clean_title_en)
                except:
                    title_zh = "翻译暂不可用"

                # 格式化时间
                news_dt = datetime.datetime.fromtimestamp(mktime(entry.published_parsed)).replace(tzinfo=pytz.utc)
                beijing_dt = news_dt.astimezone(pytz.timezone('Asia/Shanghai'))
                
                news_items.append({
                    "title_zh": highlight_title(title_zh), # 中文标题加高亮
                    "title_en": clean_title_en,
                    "link": link,
                    "date_str": beijing_dt.strftime('%m-%d %H:%M'),
                    "timestamp": news_dt.timestamp()
                })
    
    news_items.sort(key=lambda x: x["timestamp"], reverse=True)
    return news_items

def update_readme(news_items):
    beijing_tz = pytz.timezone('Asia/Shanghai')
    today_str = datetime.datetime.now(beijing_tz).strftime("%Y-%m-%d")
    
    with open("README.md", "r", encoding="utf-8") as f:
        content = f.read()

    header_marker = "## 🧬 每日精选：In vivo CAR-T & FDA"
    new_header = f"{header_marker}\n> 更新日期: {today_str} (筛选标准: In vivo / CAR-T / FDA Approval / IND)\n\n"
    
    # 构建新闻列表表格或列表
    news_list = ""
    for item in news_items:
        news_list += f"- `[{item['date_str']}]` **{item['title_zh']}**\n  <br><small>🇬🇧 *{item['title_en']}* [🔗原文]({item['link']})</small>\n"
    
    if not news_items:
        news_list += "- 过去24小时内未监测到符合「In vivo CAR-T」或「FDA重大审批」的一手通稿。\n"

    # 逻辑：保留 README 头部介绍，替换新闻区域
    if header_marker in content:
        final_content = content.split(header_marker)[0] + new_header + news_list
    else:
        final_content = content + "\n\n" + new_header + news_list

    with open("README.md", "w", encoding="utf-8") as f:
        f.write(final_content)

if __name__ == "__main__":
    items = fetch_news()
    update_readme(items)
