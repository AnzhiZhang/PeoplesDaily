import os
import re
import json
import zipfile
import datetime

import requests

from pypdf import PdfWriter

__all__ = [
    'TodayPeopleDaily',
]

DATA_DIR = 'data'
TIME_DELTA = datetime.timedelta(hours=8)
HOME_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/nbs.D110000renmrb_01.htm'
PAGE_HTML_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/nbs.D110000renmrb_{}.htm'
PAGE_PDF_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/images/{0}-{1}/{2}/{3}/rmrb{0}{1}{2}{3}.pdf'
ARTICLE_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/{}'


class Page:
    def __init__(self, today: 'TodayPeopleDaily', page: str):
        self.today = today
        self.page = page

        self.path = None
        self.html_url = None
        self.html = None
        self.pdf = None

        self.get_page()

    def get_page(self):
        self.path = os.path.join(self.today.dir_path, f'{self.page}.pdf')
        self.html_url = PAGE_HTML_URL_TEMPLATE.format(
            self.today.year,
            self.today.month,
            self.today.day,
            self.page
        )
        self.html = requests.get(self.html_url).content.decode('utf-8')
        pdf_url = PAGE_PDF_URL_TEMPLATE.format(
            self.today.year,
            self.today.month,
            self.today.day,
            self.page
        )
        self.pdf = requests.get(pdf_url).content

    @property
    def title(self):
        return re.findall('<p class="left ban">(.*?)</p>', self.html)[0]

    @property
    def articles(self):
        return [
            (
                i[1].strip(),
                ARTICLE_URL_TEMPLATE.format(
                    self.today.year,
                    self.today.month,
                    self.today.day,
                    i[0]
                )
            ) for i in
            re.findall('<a href=(nw.*?)>(.*?)</a>', self.html)
        ]

    def save_pdf(self):
        with open(self.path, 'wb') as f:
            f.write(self.pdf)


class TodayPeopleDaily:
    def __init__(self):
        self.now = None
        self.year = None
        self.month = None
        self.day = None
        self.date = None

        self.home_url = None
        self.page_count = None

        self.dir_path = None
        self.pages_file_path = None
        self.merged_file_path = None
        self.release_body = None

        self.init()

    def init(self):
        self.now = datetime.datetime.now(datetime.UTC) + TIME_DELTA
        self.year = str(self.now.year).zfill(4)
        self.month = str(self.now.month).zfill(2)
        self.day = str(self.now.day).zfill(2)
        self.date = '-'.join([self.year, self.month, self.day])

        self.home_url = HOME_URL_TEMPLATE.format(
            self.year,
            self.month,
            self.day
        )
        self.page_count = requests.get(self.home_url).text.count('pageLink')

        self.dir_path = os.path.join(DATA_DIR, self.date)
        self.pages_file_path = os.path.join(self.dir_path, f'{self.date}.zip')
        self.merged_file_path = os.path.join(self.dir_path, f'{self.date}.pdf')
        self.release_body = (
            f'# [{self.date}]({self.home_url})'
            f'\n\n今日 {self.page_count} 版'
        )

        if not os.path.isdir(self.dir_path):
            os.makedirs(self.dir_path)

    @property
    def data(self):
        return {
            'date': self.date,
            'page_count': str(self.page_count),
            'pages_zip_path': self.pages_file_path,
            'merged_pdf_path': self.merged_file_path,
            'release_body': self.release_body
        }

    def get_today_peoples_daily(self):
        # download pages
        pages = []
        for i in range(self.page_count):
            page_number = str(i + 1).zfill(2)
            pages.append(Page(self, page_number))

        # save file and data
        pages_zip = zipfile.ZipFile(self.pages_file_path, 'w')
        merged_pdf = PdfWriter()

        # add pages
        for page in pages:
            # save pdf
            page.save_pdf()

            # pages zip
            pages_zip.write(page.path, os.path.basename(page.path))

            # merged file
            merged_pdf.append(page.path)

            # release body
            self.release_body += f'\n\n## [{page.title}]({page.html_url})\n'
            for title, url in page.articles:
                self.release_body += f'\n- [{title}]({url})'

            # log
            print(f'added {page.title}')

        # save
        pages_zip.close()
        merged_pdf.write(self.merged_file_path)
        merged_pdf.close()
        data_path = os.path.join(self.dir_path, 'data.json')
        with open(data_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

        # clean pages pdf
        for page in pages:
            os.remove(page.path)
