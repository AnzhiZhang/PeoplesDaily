import os
import json
import logging
import zipfile
import datetime
import urllib.parse
from logging import Logger

import requests
from bs4 import BeautifulSoup
from pypdf import PdfWriter

from .exceptions import NoPagesFoundError
from .status import Status, load_status, save_status

__all__ = [
    'Article',
    'Page',
    'TodayPeopleDaily',
]

pypdf_logger = logging.getLogger("pypdf")
pypdf_logger.setLevel(logging.ERROR)

DATA_DIR = 'data'
TIME_DELTA = datetime.timedelta(hours=8)


def get_page_html_url(today: 'TodayPeopleDaily', page: str):
    # get page html url
    if today.date < datetime.date(2024, 12, 1):
        template = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/nbs.D110000renmrb_{}.htm'
    elif today.date >= datetime.date(2024, 12, 1):
        template = 'http://paper.people.com.cn/rmrb/pc/layout/{}{}/{}/node_{}.html'
    else:
        raise ValueError(f'Page HTML URL template not found for {today.date}')

    # return
    return template.format(today.year, today.month, today.day, page)


class Article:
    def __init__(self, title: str, url: str):
        self.title = title
        self.url = url


class Page:
    def __init__(self, today: 'TodayPeopleDaily', page: str):
        self.__today: 'TodayPeopleDaily' = today
        self.__page: 'str' = page
        self.__path: str = os.path.join(today.dir_path, f'{page}.pdf')

        self.__html_url: str | None = None
        self.__html: str | None = None
        self.__soup: BeautifulSoup | None = None
        self.__title: str | None = None
        self.__pdf_url: str | None = None

        self.__articles: list['Article'] | None = None

    def get_page(self):
        # get html and pdf
        self.__html_url = get_page_html_url(self.__today, self.__page)
        self.__html = requests.get(self.__html_url).content.decode('utf-8')
        self.__soup = BeautifulSoup(self.__html, 'html.parser')
        self.__title = self.__soup.find(
            'p', attrs={'class': 'left ban'}
        ).text.strip()
        self.__pdf_url = self.__get_pdf_url()

        # save pdf
        with open(self.__path, 'wb') as f:
            f.write(requests.get(self.__pdf_url).content)

        # get articles
        self.__articles = self.__get_articles()

    def to_data(self) -> dict:
        return {
            'title': self.__title,
            'html_url': self.__html_url,
            'articles': [
                {'title': a.title, 'url': a.url} for a in self.__articles
            ],
        }

    @classmethod
    def from_data(
            cls,
            today: 'TodayPeopleDaily',
            page_num: str,
            data: dict
    ) -> 'Page':
        page = cls(today, page_num)
        page.__html_url = data['html_url']
        page.__title = data['title']
        page.__articles = [
            Article(a['title'], a['url']) for a in data['articles']
        ]
        return page

    def __get_pdf_url(self):
        url_p = self.__soup.find('p', attrs={'class': 'right btn'})
        url = url_p.find('a').get('href')
        url = urllib.parse.urljoin(self.__html_url, url)
        return url

    def __get_articles(self) -> list[Article]:
        # get news list
        news_list = self.__soup.find('ul', attrs={'class': 'news-list'})

        # parse articles
        articles = []
        for i in news_list.find_all('li'):
            a = i.find('a')
            articles.append(Article(
                title=a.text.strip(),
                url=urllib.parse.urljoin(self.__html_url, a.get('href'))
            ))

        # return
        return articles

    @property
    def path(self):
        return self.__path

    @property
    def page(self):
        return self.__page

    @property
    def html_url(self):
        return self.__html_url

    @property
    def title(self):
        return self.__title

    @property
    def articles(self) -> list[Article]:
        return self.__articles


class TodayPeopleDaily:
    def __init__(self, logger: Logger, date: datetime.date = None):
        if date is None:
            date = datetime.datetime.now(datetime.UTC) + TIME_DELTA
            date = date.date()

        self.logger = logger
        self.date = date

        self.year = str(date.year).zfill(4)
        self.month = str(date.month).zfill(2)
        self.day = str(date.day).zfill(2)
        self.date_str = '-'.join([self.year, self.month, self.day])

        self.dir_path = None
        self.pages_zip_name = None
        self.pages_zip_path = None
        self.merged_pdf_name = None
        self.merged_pdf_path = None
        self.data_json_name = None
        self.data_json_path = None
        self.status_json_name = None
        self.status_json_path = None

        self.home_url = None

        self.page_count = None
        self.summary = None
        self.pages: list['Page'] = []

        self.oss_merged_pdf_url = None

        self.status: Status | None = None

        self.init()

    def init(self):
        # path
        self.dir_path = os.path.join(DATA_DIR, self.year, self.month, self.day)
        self.pages_zip_name = f'{self.date_str}.zip'
        self.pages_zip_path = os.path.join(self.dir_path, self.pages_zip_name)
        self.merged_pdf_name = f'{self.date_str}.pdf'
        self.merged_pdf_path = os.path.join(
            self.dir_path,
            self.merged_pdf_name
        )
        self.data_json_name = 'data.json'
        self.data_json_path = os.path.join(self.dir_path, self.data_json_name)
        self.status_json_name = 'status.json'
        self.status_json_path = os.path.join(
            self.dir_path,
            self.status_json_name
        )

        # home url
        self.home_url = get_page_html_url(self, '01')

        # create dir
        if not os.path.isdir(self.dir_path):
            os.makedirs(self.dir_path)

        # load status (fresh Status if file missing or corrupt)
        self.status = load_status(self.status_json_path, self.logger)

    @property
    def data(self):
        return {
            'date': self.date_str,
            'pages_zip_path': self.pages_zip_path,
            'merged_pdf_path': self.merged_pdf_path,
            'page_count': str(self.page_count),
            'summary': self.summary,
            'pages': {p.page: p.to_data() for p in self.pages},
        }

    def get_today_peoples_daily(self):
        # restore from disk if download phase already completed
        if self.status.downloaded:
            try:
                with open(self.data_json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.page_count = int(data['page_count'])
                self.summary = data['summary']
                self.pages = [
                    Page.from_data(self, page_num, page_data)
                    for page_num, page_data in data['pages'].items()
                ]
                self.logger.info(
                    f'Download skipped (already done), '
                    f'restored {self.page_count} pages from disk'
                )
                return
            except (json.JSONDecodeError, OSError, KeyError, ValueError) as e:
                self.logger.warning(
                    f'Failed to restore from {self.data_json_path}, '
                    f'falling through to full download: {e}'
                )

        # get page count
        self.page_count = requests.get(self.home_url).text.count('pageLink')

        # check page count
        if self.page_count == 0:
            raise NoPagesFoundError('No pages found')
        else:
            self.logger.info(f'今日 {self.page_count} 版')

        # summary
        self.summary = (
            f'# [{self.date_str}]({self.home_url})'
            f'\n\n今日 {self.page_count} 版'
        )

        # download pages
        self.pages = []
        for i in range(self.page_count):
            page_number = str(i + 1).zfill(2)
            self.pages.append(Page(self, page_number))

        # save file and data
        pages_zip = zipfile.ZipFile(self.pages_zip_path, 'w')
        merged_pdf = PdfWriter()

        # add pages
        for page in self.pages:
            # save pdf
            page.get_page()

            # pages zip
            pages_zip.write(page.path, os.path.basename(page.path))

            # merged pdf
            merged_pdf.append(page.path, page.title)

            # summary
            self.summary += f'\n\n## [{page.title}]({page.html_url})\n'
            for article in page.articles:
                self.summary += f'\n- [{article.title}]({article.url})'

            # log
            self.logger.info(f'{self.date}: added "{page.title}" into pages')

        # save
        pages_zip.close()
        merged_pdf.write(self.merged_pdf_path)
        merged_pdf.close()
        with open(self.data_json_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

        # clean pages pdf
        for page in self.pages:
            os.remove(page.path)

        # mark download phase done
        self.status.downloaded = True
        self.save_status()

        # log
        self.logger.info(f"Got People's Daily for {self.date_str}")

    def set_oss_url(self, url: str):
        self.oss_merged_pdf_url = url

    def save_status(self):
        save_status(self.status, self.status_json_path)
