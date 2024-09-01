# People's Daily

> 每日自动获取人民日报电子版

## Usage

```bash
python main.py
```

文件将保存在 `./data` 目录下。

### 发送邮件

```bash
python ./src/send_email.py --help
```

邮件参数提供 args 提供。

### 定时任务

您还可以启动定时任务，每天自动获取电子版并发送邮件。

```bash
python ./src/schedule.py
```

邮件参数通过环境变量提供，如果提供，将同时发送邮件，否则仅下载文件。

| 环境变量 | 说明 |
| --- | --- |
| SMTP_SERVER | SMTP 服务器 |
| SMTP_PORT | SMTP 端口 |
| SMTP_SSL | 是否使用 SSL |
| SMTP_USER | SMTP 用户名 |
| SMTP_PASSWORD | SMTP 密码 |
| SENDER | 发送者 |
| RECIPIENTS | 接收者，多个用 `,` 分隔 |

### Docker

定时任务已发布在 `zhanganzhi/peoplesdaily`，数据文件挂保存在 `/peoplesdaily/data`，邮件参数通过环境变量提供。
