import os
import re
import json
import uuid
import zipfile
import argparse
import datetime

import requests
from pypdf import PdfWriter

DATA_DIR = 'data'
TIME_DELTA = datetime.timedelta(hours=8)
HOME_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/nbs.D110000renmrb_01.htm'
PAGE_HTML_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/nbs.D110000renmrb_{}.htm'
PAGE_PDF_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/images/{0}-{1}/{2}/{3}/rmrb{0}{1}{2}{3}.pdf'
ARTICLE_URL_TEMPLATE = 'http://paper.people.com.cn/rmrb/html/{}-{}/{}/{}'


class Today:
    def __init__(self):
        self.now = datetime.datetime.now(datetime.UTC)
        self.year = str(self.now.year).zfill(4)
        self.month = str(self.now.month).zfill(2)
        self.day = str(self.now.day).zfill(2)
        self.date = '-'.join([self.year, self.month, self.day])

        self.dir_path = os.path.join(DATA_DIR, self.date)
        self.pages_file_path = os.path.join(self.dir_path, f'{self.date}.zip')
        self.merged_file_path = os.path.join(self.dir_path, f'{self.date}.pdf')

        self.home_url = HOME_URL_TEMPLATE.format(
            self.year,
            self.month,
            self.day
        )
        self.page_count = requests.get(self.home_url).text.count('pageLink')

        if not os.path.isdir(self.dir_path):
            os.makedirs(self.dir_path)


class Page:
    def __init__(self, today: Today, page: str):
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


def get_today_peoples_daily():
    # get today
    today = Today()

    # download pages
    pages = []
    for i in range(today.page_count):
        page_number = str(i + 1).zfill(2)
        pages.append(Page(today, page_number))

    # save file and data
    pages_zip = zipfile.ZipFile(today.pages_file_path, 'w')
    merged_pdf = PdfWriter()
    data = {
        'date': today.date,
        'page_count': str(today.page_count),
        'pages_zip_path': today.pages_file_path,
        'merged_pdf_path': today.merged_file_path,
        'release_body': (
            f'# [{today.date}]({today.home_url})'
            f'\n\n今日 {today.page_count} 版'
        )
    }

    # add pages
    for page in pages:
        # save pdf
        page.save_pdf()

        # pages zip
        pages_zip.write(page.path, os.path.basename(page.path))

        # merged file
        merged_pdf.append(page.path)

        # data
        data['release_body'] += f'\n\n## [{page.title}]({page.html_url})\n'
        for title, url in page.articles:
            data['release_body'] += f'\n- [{title}]({url})'

        # log
        print(f'added {page.title}')

    # save
    pages_zip.close()
    merged_pdf.write(today.merged_file_path)
    merged_pdf.close()
    data_path = os.path.join(today.dir_path, 'data.json')
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    # clean pages pdf
    for page in pages:
        os.remove(page.path)

    # return data
    return data


def write_multiline_output(fh, name, value):
    delimiter = uuid.uuid4()
    print(f'{name}<<{delimiter}', file=fh)
    print(value, file=fh)
    print(delimiter, file=fh)


def main():
    # setup parser
    parser = argparse.ArgumentParser(
        description="Get today people's daily",
    )
    parser.add_argument(
        "--write-github-output",
        action=argparse.BooleanOptionalAction,
        dest="write_github_output",
        help="Write GitHub output",
    )

    # parse arguments
    args = parser.parse_args()
    write_github_output = args.write_github_output

    # get today peoples daily
    data = get_today_peoples_daily()

    # set output
    if write_github_output:
        with open(os.environ['GITHUB_OUTPUT'], 'a') as fh:
            for name, value in data.items():
                if '\n' in value:
                    write_multiline_output(fh, name, value)
                else:
                    print(f'{name}={value}', file=fh)


if __name__ == '__main__':
    main()
