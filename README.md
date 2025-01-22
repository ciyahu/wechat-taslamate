

# 环境参数必须与teslamate一致
# 登录ip:7777管理推送
# 注册一个qq邮箱，在微信里打开邮箱提醒，打开pop3/stmp服务
# 密码为随机发信密码


version: "3"

services:
  wechat-teslamate:
    image: crpi-imfm7cwd6erou87s.cn-hangzhou.personal.cr.aliyuncs.com/ciyahu/can:wechat-teslamate-latest
    restart: always
    environment:
      - DATABASE_USER=teslamate            # same as teslamate
      - DATABASE_PASS=123456               # same as teslamate
      - DATABASE_NAME=teslamate:5432            # same as teslamate
      - DATABASE_HOST=database             # same as teslamate
      - MQTT_BROKER_HOST=mosquitto         # same as teslamate
      - EMAIL_ADDRESS=example@qq.com       # QQ email address
      - EMAIL_PASSWORD=ursaaaatbcfrbdjc    # QQ email send mail password 
      - WEB_PASSWORD=teslamate
    ports:
      - 7777:7777
