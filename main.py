import os
import re
import time
import json
import zipfile
import warnings

import requests
from PyPDF2 import PdfFileMerger


class Day:
    LOCALTIME = time.localtime()
    YEAR = str(LOCALTIME.tm_year).zfill(4)
    MONTH = str(LOCALTIME.tm_mon).zfill(2)
    DAY = str(LOCALTIME.tm_mday).zfill(2)
    DATE = ''.join([YEAR, MONTH, DAY])

    DIR = os.path.join('Download', DATE)
    PAGES_FILE_PATH = os.path.join(DIR, f'{DATE}.zip')
    MERGED_FILE_PATH = os.path.join(DIR, f'{DATE}.pdf')

    PAGE_COUNT = requests.get(
        f'http://paper.people.com.cn/rmrb/html/{YEAR}-{MONTH}/{DAY}/nbs.D110000renmrb_01.htm'
    ).text.count('pageLink')

    if not os.path.isdir(DIR):
        os.makedirs(DIR)


class Page:
    def __init__(self, page: str):
        self.page = page
        self.html = requests.get(
            f'http://paper.people.com.cn/rmrb/html/{Day.YEAR}-{Day.MONTH}/{Day.DAY}/nbs.D110000renmrb_{self.page}.htm'
        ).text
        self.pdf = requests.get(
            (
                'http://paper.people.com.cn/rmrb/images/{0}-{1}/{2}/{3}/rmrb{0}{1}{2}{3}.pdf'
                    .format(Day.YEAR, Day.MONTH, Day.DAY, page)
            )
        ).content
        self.path = os.path.join(Day.DIR, f'{self.page}.pdf')

    def __str__(self) -> str:
        return (
            f'{self.__class__.__name__}'
            f'[date={Day.DATE}, page={self.page}, title={self.title}]'
        )

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def title(self):
        return re.findall('<p class="left ban">(.*?)</p>', self.html)[0]

    @property
    def articles(self):
        return [
            i.strip() for i in
            re.findall('<a href=nw.*?>(?P<name>.*?)</a>', self.html)
        ]

    def save_pdf(self):
        with open(self.path, 'wb') as f:
            f.write(self.pdf)


def main():
    warnings.filterwarnings('ignore')
    pages = [Page(str(i + 1).zfill(2)) for i in range(Day.PAGE_COUNT)]
    pages_file = zipfile.ZipFile(Day.PAGES_FILE_PATH, 'w')
    merged_file = PdfFileMerger(False)
    data = {
        'date': Day.DATE,
        'page_count': str(Day.PAGE_COUNT),
        'pages_file_path': Day.PAGES_FILE_PATH,
        'merged_file_path': Day.MERGED_FILE_PATH,
        'release_body': f'# {Day.DATE}\n\n今日 {Day.PAGE_COUNT} 版'
    }

    # Process
    for page in pages:
        # Save pdf
        page.save_pdf()

        # Pages file
        pages_file.write(page.path, os.path.basename(page.path))

        # Merged file
        merged_file.append(page.path)

        # Data
        data['release_body'] += f'\n\n## {page.title}\n'
        for article in page.articles:
            data['release_body'] += f'\n- {article}'

        # Info
        print(f'Processed {page}')

    # Save
    pages_file.close()
    merged_file.write(Day.MERGED_FILE_PATH)
    merged_file.close()
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


if __name__ == '__main__':
    main()
