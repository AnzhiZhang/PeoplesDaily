# People's Daily

> 每日自动获取人民日报电子版

## 使用方式

### 简单使用

```bash
python main.py
```

文件将保存在 `./data` 目录。

提供日期作为命令行参数可以获取指定日期的电子版。

```bash
python main.py 2021-01-01
```

### 定时任务

您还可以启动定时任务，每天自动获取电子版并发送邮件。在配置文件中启用 `cron_enabled` 后运行即可。

## 配置

配置文件位于 `config.yaml`，默认内容如下：

```yaml
cron_enabled: false
write_github_output: false
oss:
  enabled: false
  access_key_id: ''
  access_key_secret: ''
  endpoint: ''
  bucket_name: ''
  is_cname: false
  region: ''
  pretty_endpoint: null
email:
  enabled: true
  smtp_server: ''
  smtp_port: 0
  smtp_use_ssl: false
  smtp_user: ''
  smtp_password: ''
  sender: ''
  recipients: []
  with_attachment: false
  unsubscribe_address: null
```

配置说明如下：

| 参数 | 说明 |
| --- | --- |
| cron_enabled | 是否启用定时任务模式 |
| write_github_output | 是否将数据写入 GitHub 仓库 |
| oss.enabled | 是否启用 OSS 上传 |
| oss.access_key_id | OSS Access Key ID |
| oss.access_key_secret | OSS Access Key Secret |
| oss.endpoint | OSS Endpoint |
| oss.bucket_name | OSS Bucket Name |
| oss.is_cname | OSS 是否使用自定义域名 |
| oss.region | OSS Region |
| oss.pretty_endpoint | OSS 自定义域名 |
| email.enabled | 是否启用邮件发送 |
| email.smtp_server | SMTP 服务器 |
| email.smtp_port | SMTP 端口 |
| email.smtp_use_ssl | 是否使用 SSL |
| email.smtp_user | SMTP 用户名 |
| email.smtp_password | SMTP 密码 |
| email.sender | 发送者 |
| email.recipients | 接收者列表 |
| email.with_attachment | 是否发送附件 |
| email.unsubscribe_address | 接收退订邮件的地址 |

该模式下，可以通过标准输入使用以下命令：

- `exit` 退出程序
- `threads` 查看当前所有线程
- `get YYYY-MM-DD` 获取指定日期

## Docker

Docker 镜像发布在 Docker Hub 上，容器名为 `zhanganzhi/peoplesdaily`。

使用以下命令拉取镜像：

```bash
docker pull zhanganzhi/peoplesdaily
```

数据文件保存在 `/peoplesdaily/data`，配置文件保存在 `/peoplesdaily/config.yaml`。
