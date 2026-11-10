import json
import os

from pydantic import BaseModel, Field

__all__ = [
    'DigestDataSection',
    'ImagesDataSection',
    'Data',
]


class DigestDataSection(BaseModel):
    highlights: list[dict] = Field(default_factory=list)
    commentary: list[dict] = Field(default_factory=list)


class ImagesDataSection(BaseModel):
    intro: str | None = None
    highlights: list[dict] = Field(default_factory=list)
    commentary: list[dict] = Field(default_factory=list)


class Data(BaseModel):
    date: str
    page_count: int = 0
    pages: dict[str, dict] = Field(default_factory=dict)
    digest: DigestDataSection | None = None
    images: ImagesDataSection = Field(default_factory=ImagesDataSection)

    @property
    def summary(self) -> str:
        first_page = self.pages.get('01')
        header = (
            f'# [{self.date}]({first_page["html_url"]})'
            if first_page else f'# {self.date}'
        )
        summary = f'{header}\n\n今日 {self.page_count} 版'
        for page in self.pages.values():
            summary += f'\n\n## [{page["title"]}]({page["html_url"]})\n'
            for article in page['articles']:
                summary += f'\n- [{article["title"]}]({article["url"]})'
        return summary

    @classmethod
    def load(cls, path: str) -> 'Data':
        with open(path, 'r', encoding='utf-8') as f:
            return cls.model_validate(json.load(f))

    def save(self, path: str) -> None:
        tmp_path = f'{path}.tmp'
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(self.model_dump(), f, indent=4, ensure_ascii=False)
        os.replace(tmp_path, path)
