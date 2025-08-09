防止被商业化，暂不上传最新版本源码，请见谅  
程序完全本地化运行，开启穿透和中转时中转服务器仅中转已加密数据，token储存在本地  
欢迎大家分享各种体验和bug反馈  
  
#更新  
2025.8.8 bug修复，增加停车能量损失，增加管理页面ios轻应用(safari打开7777发送到桌面会生成轻应用)
2025.8.6 微信推送已支持内网穿透和ip中转，任何网络环境都可稳定使用  
  
两种方法  
# 1.直接部署镜像：  
docker-compose.yml已集成中文teslamate和依赖容器  
把docker-compose.yml放到系统任意目录，运行docker-compose up -d启动  
teslamate设置和使用请参考官网，新安装的teslamate会数据不全，充电几次后即可正常  
登录ip:7777管理推送  
![微信图片_20250809110339](https://github.com/user-attachments/assets/45f0be3e-885a-4e50-9c6f-7f415020dd98)
![微信图片_20250809110343](https://github.com/user-attachments/assets/10e3ca11-ac04-44a5-8726-aea1ab9693f8)
![微信图片_20250809110348](https://github.com/user-attachments/assets/0ecc6854-1bf2-4621-9508-53b5f0c1fdff)
![微信图片_20250809110352](https://github.com/user-attachments/assets/513ddc95-f5a1-4799-a1fd-58a8ba01a8bb)
![微信图片_20250809110356](https://github.com/user-attachments/assets/103cf59d-e793-4298-979b-ae881e0d563d)
![微信图片_20250728200248](https://github.com/user-attachments/assets/16282f0f-b69a-49f9-89c7-fbb7d53fc46b)
![微信图片_20250728200252](https://github.com/user-attachments/assets/f427c675-1bc2-4c00-b3c8-37b02b028798)
![微信图片_20250728200303](https://github.com/user-attachments/assets/0afa09aa-11dc-43a4-9f3b-3897931bec2d)
# 2.自行下载制作镜像：下载所有文件，用docker make镜像，部署  


