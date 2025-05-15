# 两种部署方法
# 1.直接部署做好的镜像：
#    把YML文件里的内容添加到teslamate的YML文件里
#    环境参数必须与teslamate一致
#    登录ip:7777管理推送
#    注册一个qq邮箱，在微信里打开邮箱提醒，打开pop3/stmp服务
#    密码为随机发信密码
#    Docker-compose up -d 后邮箱可以正常接收推送
# 2.自行下载制作镜像：
#    下载所有文件，用docker make镜像，部署
#    运行后可在config/env文件中修改地图key,去腾讯位置平台申请一个个人免费key填进去
![微信图片_20250515110256](https://github.com/user-attachments/assets/cdeb81d1-c5d1-452d-820b-cf457682d840)
