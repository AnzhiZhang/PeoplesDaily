import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from pydantic import BaseModel

from .config import Config
from .peoples_daily import Article, Page, TodayPeopleDaily

__all__ = [
    'generate_digest',
]

# pages whose articles are always read in full, regardless of selection
ALWAYS_READ_PAGES = {'01'}

# articles longer than this are compressed before summarizing
COMPRESS_THRESHOLD = 8000

SELECT_PROMPT = """你是《人民日报》的编辑助手。下面是今天报纸的文章标题列表，每行格式为“[编号] 版面 | 标题”。
请选出值得阅读全文、用于撰写今日要闻摘要的文章。

优先选择：重要政策与会议、经济数据与改革举措、重大国内外事件、本报评论员文章、社论、人民时评等评论文章。
通常跳过：副刊、文艺作品、图片说明、广告、地方性小新闻、内容重复的报道。

以 JSON 格式返回：{"article_ids": [编号, ...]}"""

COMPRESS_PROMPT = """你是《人民日报》的编辑助手。下面是一篇长文章的全文，请将其压缩到 2000 字以内，供后续撰写每日摘要使用。

要求：
1. 保留核心内容、关键数字、具体措施和政策表述。
2. 保留最有信息量的几句原话引语，引语内容一字不改，并注明说话人。
3. 忠实于原文，不添加原文没有的信息，不加入自己的评价。

以 JSON 格式返回：{"content": "压缩后的文章"}"""

SUMMARIZE_PROMPT = """你是一名资深时政编辑，为关注中国政策动向的读者撰写《人民日报》每日摘要。下面是今天报纸的若干篇文章全文，每篇以“[编号] 版面 | 标题”开头。
请以 JSON 格式返回：
{
  "highlights": [
    {"article_ids": [编号, ...], "title": "标题", "paragraphs": ["段落", ...]}
  ],
  "commentary": [{"article_id": 编号, "point": "核心观点"}]
}

highlights 为今日要点，要求：
1. 条数：只写真正重要的事，通常 2 到 3 条，按重要性从高到低排序。最多 5 条，宁缺毋滥。
2. 合并：同一事件的多篇报道合并为一条。article_ids 列出最主要的 1 到 3 篇文章，主要文章放在第一位；评论文章不列入。
3. title：一句话点明这件事的实质，而不是复述事件名称，不超过 25 字。例如写“央行下调存款准备金率，释放长期资金约1万亿元”，而不是“央行宣布降准”。
4. paragraphs：2 到 3 段，合计不超过 300 字。讲清发生了什么、为什么重要，多写关键数字和具体措施，不写空泛的套话。可以引用原话，并注明说话人。

commentary 为评论风向，要求：
1. 0 到 2 条，只从评论员文章、社论、人民时评等评论文章中选取，没有合适的评论文章时返回空列表。
2. point 用两三句话讲清评论针对什么、核心观点和立场，不超过 120 字。

通用要求：
1. 编号必须是下文出现的编号。
2. 忠实于原文，不添加原文没有的信息，不加入自己的评价。"""


class Selection(BaseModel):
    article_ids: list[int]


class Compressed(BaseModel):
    content: str


class Highlight(BaseModel):
    article_ids: list[int]
    title: str
    paragraphs: list[str]


class Commentary(BaseModel):
    article_id: int
    point: str


class DigestResult(BaseModel):
    highlights: list[Highlight]
    commentary: list[Commentary] = []


def chat_json(client: OpenAI, model: str, system: str, user: str) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        response_format={'type': 'json_object'},
    )
    return response.choices[0].message.content


def index_articles(
        daily: TodayPeopleDaily
) -> dict[int, tuple[Page, Article]]:
    # number all articles across pages, starting from 1
    indexed = {}
    for page in daily.pages:
        for article in page.articles:
            indexed[len(indexed) + 1] = (page, article)
    return indexed


def select_articles(
        client: OpenAI,
        model: str,
        indexed: dict[int, tuple[Page, Article]]
) -> list[int]:
    # always read pages
    always = [
        i for i, (page, _) in indexed.items()
        if page.page in ALWAYS_READ_PAGES
    ]

    # let model select from the rest by title
    candidates = {
        i: (page, article) for i, (page, article) in indexed.items()
        if page.page not in ALWAYS_READ_PAGES
    }
    selected = []
    if candidates:
        user = '\n'.join(
            f'[{i}] {page.title} | {article.title}'
            for i, (page, article) in candidates.items()
        )
        content = chat_json(client, model, SELECT_PROMPT, user)
        selection = Selection.model_validate_json(content)

        # drop ids not in candidates
        selected = [i for i in selection.article_ids if i in candidates]

    # merge, keep paper order
    return sorted(set(always) | set(selected))


def fetch_article_content(url: str) -> str:
    html = requests.get(url, timeout=30).content.decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    # both old and new layouts put the body in #ozoom
    ozoom = soup.find(id='ozoom')
    if ozoom is None:
        return ''

    paragraphs = [p.get_text(strip=True) for p in ozoom.find_all('p')]
    return '\n'.join(p for p in paragraphs if p)


def compress_article(client: OpenAI, model: str, content: str) -> str:
    result = chat_json(client, model, COMPRESS_PROMPT, content)
    return Compressed.model_validate_json(result).content


def summarize_articles(
        client: OpenAI,
        model: str,
        indexed: dict[int, tuple[Page, Article]],
        contents: dict[int, str]
) -> DigestResult:
    user = '\n\n'.join(
        f'[{i}] {indexed[i][0].title} | {indexed[i][1].title}\n{content}'
        for i, content in contents.items()
    )
    content = chat_json(client, model, SUMMARIZE_PROMPT, user)
    result = DigestResult.model_validate_json(content)

    # drop items referring to articles not provided
    for h in result.highlights:
        h.article_ids = [i for i in h.article_ids if i in contents]
    result.highlights = [h for h in result.highlights if h.article_ids]
    result.commentary = [c for c in result.commentary if c.article_id in contents]
    if not result.highlights:
        raise ValueError('Digest has no valid highlights')

    return result


def generate_digest(
        config: Config,
        today_peoples_daily: TodayPeopleDaily
) -> None:
    logger = today_peoples_daily.logger

    # skip if already generated
    if (
            today_peoples_daily.status.digest_generated
            and today_peoples_daily.digest is not None
    ):
        logger.info('Digest skipped (already done)')
        return

    # construct client
    client = OpenAI(
        base_url=config.digest.base_url,
        api_key=config.digest.api_key,
        timeout=300,
    )
    model = config.digest.model

    # select articles
    indexed = index_articles(today_peoples_daily)
    selected = select_articles(client, model, indexed)
    logger.info(f'Digest selected {len(selected)}/{len(indexed)} articles')

    # fetch contents
    contents = {}
    for i in selected:
        article = indexed[i][1]
        content = fetch_article_content(article.url)
        if len(content) > COMPRESS_THRESHOLD:
            logger.info(f'Compressing {len(content)} chars: {article.title}')
            content = compress_article(client, model, content)
        if content:
            contents[i] = content
        else:
            logger.warning(f'Empty content: {article.title} ({article.url})')
    if not contents:
        raise ValueError('No article content fetched for digest')

    # summarize
    result = summarize_articles(client, model, indexed, contents)

    # resolve ids to titles and urls
    today_peoples_daily.digest = {
        'highlights': [
            {
                'title': h.title,
                'paragraphs': h.paragraphs,
                'sources': [
                    {
                        'title': indexed[i][1].title,
                        'url': indexed[i][1].url,
                    }
                    for i in h.article_ids
                ],
            }
            for h in result.highlights
        ],
        'commentary': [
            {
                'title': indexed[c.article_id][1].title,
                'point': c.point,
                'url': indexed[c.article_id][1].url,
            }
            for c in result.commentary
        ],
    }

    # persist data and status
    today_peoples_daily.save_data()
    today_peoples_daily.status.digest_generated = True
    today_peoples_daily.save_status()

    # log
    logger.info(
        f'Generated digest with {len(result.highlights)} highlights '
        f'and {len(result.commentary)} commentary'
    )
