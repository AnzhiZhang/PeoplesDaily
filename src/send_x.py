import datetime
import json
import math
import time
import unicodedata
from pathlib import Path

import requests

from .config import Config, XConfigSection
from .peoples_daily import DATA_DIR, TodayPeopleDaily

__all__ = [
    'send_x',
]

API = 'https://api.x.com/2'


def weighted_length(text: str) -> int:
    """Count X characters conservatively, without truncating text."""
    return sum(
        1
        if (
            ord(c) <= 0x10FF
            or 0x2000 <= ord(c) <= 0x200D
            or 0x2010 <= ord(c) <= 0x201F
            or 0x2032 <= ord(c) <= 0x2037
        )
        else 2
        for c in unicodedata.normalize('NFC', text)
    )


def build_post(date: str, page_count: int, intro: str) -> str:
    issue_date = datetime.date.fromisoformat(date)
    weekday = '一二三四五六日'[issue_date.weekday()]
    text = (
        '人民日报今日速读\n'
        f'{issue_date:%Y年%m月%d日} 星期{weekday}｜今日{page_count}版\n\n'
        f'{intro}'
    )
    if weighted_length(text) > 280:
        raise ValueError('X post exceeds 280 weighted characters')
    return text


class XAPIError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class XClient:
    def __init__(
        self,
        config: XConfigSection,
        token_path: str | Path = Path(DATA_DIR) / 'x_token.json',
    ):
        if not config.client_id.strip():
            raise ValueError('Missing X credentials: x.client_id')

        self.config = config
        self.token_path = Path(token_path)
        self.access_token = ''
        self.refresh = config.refresh_token
        self.expires_at = 0.0

        # load cached tokens
        if self.token_path.is_file():
            try:
                saved = json.loads(self.token_path.read_text('utf-8'))
                if saved['client_id'] == config.client_id:
                    access = saved['access_token']
                    refresh = saved['refresh_token']
                    expires_at = float(saved['expires_at'])
                    if not (
                        isinstance(access, str)
                        and access
                        and isinstance(refresh, str)
                        and refresh
                        and math.isfinite(expires_at)
                        and expires_at > 0
                    ):
                        raise ValueError('Invalid token cache')
                    self.access_token = access
                    self.refresh = refresh
                    self.expires_at = expires_at
            except (OSError, ValueError, KeyError, TypeError):
                raise XAPIError('Could not read X token cache') from None
        if not self.refresh.strip():
            raise ValueError('Missing X credentials: x.refresh_token')
        self.session = requests.Session()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.session.close()

    def response_data(self, response) -> dict:
        if not 200 <= response.status_code < 300:
            detail = ''
            try:
                data = response.json()
                detail = str(
                    data.get('detail')
                    or data.get('error_description')
                    or data.get('title')
                    or data.get('error')
                    or ''
                )
            except ValueError:
                pass
            for secret in (
                self.config.client_secret,
                self.access_token,
                self.refresh,
                self.config.refresh_token,
            ):
                if secret:
                    detail = detail.replace(secret, '[redacted]')
            raise XAPIError(
                f'X API HTTP {response.status_code}: {detail[:250]}',
                response.status_code,
            )
        try:
            return response.json()
        except ValueError:
            raise XAPIError('X API returned an invalid JSON response') from None

    def refresh_token(self) -> None:
        # authenticate confidential clients using HTTP Basic
        auth = (
            (self.config.client_id, self.config.client_secret)
            if self.config.client_secret
            else None
        )
        requested_at = time.time()
        try:
            response = requests.post(
                API + '/oauth2/token',
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': self.refresh,
                    'client_id': self.config.client_id,
                },
                auth=auth,
                timeout=(10, 30),
                allow_redirects=False,
            )
        except requests.RequestException:
            raise XAPIError(
                'X token refresh connection failed; no automatic retry'
            ) from None

        # validate refreshed tokens
        tokens = self.response_data(response)
        token = tokens.get('access_token')
        refresh = tokens.get('refresh_token', self.refresh)
        try:
            expires_in = float(tokens.get('expires_in', 0))
        except (TypeError, ValueError):
            expires_in = 0
        if (
            not isinstance(token, str)
            or not token
            or not isinstance(refresh, str)
            or not refresh
            or not math.isfinite(expires_in)
            or expires_in <= 0
            or str(tokens.get('token_type', '')).casefold() != 'bearer'
        ):
            raise XAPIError('X token refresh returned incomplete credentials')
        saved = {
            'client_id': self.config.client_id,
            'access_token': token,
            'refresh_token': refresh,
            'expires_at': requested_at + expires_in,
        }

        # persist rotated credentials before using the new access token
        temporary = self.token_path.with_suffix('.json.tmp')
        try:
            self.token_path.parent.mkdir(parents=True, exist_ok=True)
            temporary.touch(mode=0o600, exist_ok=True)
            temporary.chmod(0o600)
            temporary.write_text(
                json.dumps(saved, ensure_ascii=False, indent=4),
                encoding='utf-8',
            )
            temporary.replace(self.token_path)
        except OSError:
            raise XAPIError(
                'Could not save refreshed X credentials; publishing stopped'
            ) from None
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

        self.access_token = token
        self.refresh = refresh
        self.expires_at = saved['expires_at']

    def request(self, method: str, endpoint: str, **kwargs) -> dict:
        # refresh before expiry, allowing time for the next API request
        if not self.access_token or time.time() >= self.expires_at - 60:
            self.refresh_token()

        # remember file positions before the first multipart request
        streams = []
        for value in kwargs.get('files', {}).values():
            stream = value[1] if isinstance(value, tuple) else value
            if hasattr(stream, 'tell'):
                streams.append((stream, stream.tell()))
        for attempt in range(2):
            self.session.headers.update(
                {'Authorization': f'Bearer {self.access_token}'}
            )
            try:
                response = self.session.request(
                    method,
                    API + endpoint,
                    timeout=(10, 60),
                    allow_redirects=False,
                    **kwargs,
                )
            except requests.RequestException:
                raise XAPIError(
                    'X API connection failed or timed out'
                ) from None
            if response.status_code != 401 or attempt:
                return self.response_data(response)

            # an explicit 401 is safe to retry once after refreshing
            self.refresh_token()
            for stream, position in streams:
                stream.seek(position)
        raise XAPIError('X authorization failed', 401)

    def account(self) -> dict:
        data = self.request('GET', '/users/me')['data']
        if not data.get('id') or not data.get('username'):
            raise XAPIError('X account response is incomplete')
        expected = self.config.username.lstrip('@').casefold()
        if expected and data['username'].casefold() != expected:
            raise ValueError(
                f'X account mismatch: authenticated as @{data["username"]}'
            )
        return data

    def upload_image(self, path: Path) -> str:
        if not 0 < path.stat().st_size <= 5 * 1024 * 1024:
            raise ValueError(
                f'X image must be between 1 byte and 5 MB: {path.name}'
            )
        with path.open('rb') as stream:
            data = self.request(
                'POST',
                '/media/upload',
                data={'media_category': 'tweet_image'},
                files={'media': (path.name, stream, 'image/png')},
            )['data']
        media_id = str(data.get('id', ''))
        if not media_id.isdigit():
            raise XAPIError('X image upload returned no media ID')
        deadline = time.monotonic() + 60
        while data.get('processing_info'):
            info = data['processing_info']
            state = info.get('state')
            if state == 'succeeded':
                break
            if state == 'failed':
                raise XAPIError('X image processing failed')
            if (
                state not in ('pending', 'in_progress')
                or time.monotonic() >= deadline
            ):
                raise XAPIError('X image processing did not complete')
            time.sleep(min(max(float(info.get('check_after_secs', 1)), 0.1), 5))
            data = self.request(
                'GET', '/media/upload', params={'media_id': media_id}
            )['data']
        return media_id

    def publish(self, text: str, media_ids: list[str]) -> str:
        response = self.request(
            'POST',
            '/tweets',
            json={'text': text, 'media': {'media_ids': media_ids}},
        )
        post_id = str(response.get('data', {}).get('id', ''))
        if not post_id.isdigit():
            raise XAPIError('X create-post response returned no post ID')
        return post_id


def send_x(config: Config, today_peoples_daily: TodayPeopleDaily) -> str:
    # skip if already sent
    if today_peoples_daily.status.x_post_id:
        url = f'https://x.com/i/status/{today_peoples_daily.status.x_post_id}'
        today_peoples_daily.logger.info(
            f'X publish skipped (already posted): {url}'
        )
        return url

    # build post from shared image content
    text = build_post(
        today_peoples_daily.data.date,
        today_peoples_daily.data.page_count,
        today_peoples_daily.data.images.intro
    )

    # publish to x
    with XClient(config.x) as client:
        account = client.account()
        today_peoples_daily.logger.debug(
            f'Publishing {today_peoples_daily.data.date} '
            f'to @{account["username"]}'
        )
        media_ids = [
            client.upload_image(path)
            for path in today_peoples_daily.image_paths
        ]
        post_id = client.publish(text, media_ids)
        url = f'https://x.com/i/status/{post_id}'

    # update status
    today_peoples_daily.status.x_post_id = post_id

    # log
    today_peoples_daily.logger.info(f'X post created: {url}')
    return url
