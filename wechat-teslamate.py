version = "Version beta1.0"

import os
import psycopg2
import time
import math
import json
import requests
import paho.mqtt.client as mqtt
import pdb, traceback, sys
import pytz
import smtplib
import warnings
import queue
import threading
import select
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from psycopg2 import pool
import asyncio
import asyncpg
from http.server import SimpleHTTPRequestHandler, HTTPServer
from psycopg2.extras import RealDictCursor
from psycopg2 import extras

sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore", category=DeprecationWarning)
message_queue = queue.Queue()


crlf = "\n"+"<br>"
pseudo = "❔" 
model  = "❔" 
km = "❔" 
ismaj = "❔"
etat_connu = "❔" 
locked = "❔" 
text_locked = "❔" 
temps_restant_charge = "❔" 
text_energie = "❔" 
doors_state = "❔" 
windows_state = "❔" 
trunk_state = "❔" 
frunk_state = "❔" 
latitude = "❔"
longitude = "❔"
DEBUG = "❔"
tpms_pressure_fl = "❔"  
tpms_pressure_fr = "❔"
tpms_pressure_rl = "❔"
tpms_pressure_rr = "❔"
text_sentry_mode = "❔"
outside_temp = "❔"
charge_limit_soc = "❔"
inside_temp = "❔"
update_version = "。。。"
fl_icon = "🔴"
fr_icon = "🔴"
rl_icon = "🔴"
rr_icon = "🔴"
tpms_soft_warning_fl = False
tpms_soft_warning_fr = False
tpms_soft_warning_rl = False
tpms_soft_warning_rr = False
is_user_present = False
trip_started = False
charger_voltage = "❔"
bet1 = ""
bet2 = ""
bet3 = ""
bet4 = ""
bet5 = ""
start_rated = None  # 行程开始时的 rated 值
end_rated = None    # 行程结束时的 rated 值
avg_cost = None     # 行程能耗
battery_consumption = 0
start_battery_level = None
start_ideal_battery_range = None
start_time = None
end_time = None
max_speed = 0
trip1 = 0
speed = 0
tittle = ""
text_msg = ""
text_msg2 = ""
present = "false"
charging_start_time = None
charging_end_time = None
start_battery_level_charge = None
end_battery_level_charge = None
start_range_charge = None
end_range_charge = None
charge_energy_added = 0.0
DEBUG = True
nouvelleinformation = False 
minbat=5  
usable_battery_level = -1 
hour1 = "小时"
minute = "分钟"
second1 = "秒"
UNITS = "Km"
distance = -1
trip = 0
trip1 = 0
trip2 = 0
charging_state_flag = "0"
tirets = "--------------------------------------------"
heading_angle = 0
start_charge_energy_added = 0.0
max_charger_power = 0.0
charger_power = 0
current_power = 0
db_pool = None
pool_initialized = False  # 新增标志位
newdata = None
efficiency = 0
tpms_push_count = 0  # 推送计数器
tpms_last_state = False  # 上次报警状态，False 表示全假，True 表示至少一个为真
start0 = 0
# Start
print("程序开始启动")





def initialize_db_pool():
    global db_pool, pool_initialized
    try:
        dbname = os.getenv('DATABASE_NAME')
        host = os.getenv('DATABASE_HOST')
        user = os.getenv('DATABASE_USER')
        password = os.getenv('DATABASE_PASS')

        # 检查 host 是否包含端口号
        if ':' in host:
            host, port = host.split(':', 1)  # ':' 前面的部分作为 host，后面的部分作为 port
        else:
            port = '5432'  # 默认端口

        db_pool = pool.SimpleConnectionPool(1, 10, dbname=dbname, user=user, password=password, host=host, port=port)
        print("数据库连接池初始化成功")
        pool_initialized = True  # 设置标志位为 True
        with get_connection() as conn:
            create_drive_trigger(conn)
            create_charging_trigger(conn)
    except Exception as e:
        print(f"数据库连接池初始化失败：{e}，使用的主机和端口为 {host}:{port}")
        db_pool = None
        
def get_connection():
    try:
        return db_pool.getconn()
    except Exception as e:
        print(f"获取连接失败：{e}")
        return None

def return_connection(conn):
    if conn:
        db_pool.putconn(conn)
        


def create_drive_trigger(conn):
    while not pool_initialized:  # 等待连接池初始化
        time.sleep(1)
    with conn.cursor() as cursor:
        # 创建行程触发器函数
        cursor.execute("""
        CREATE OR REPLACE FUNCTION notify_drive_update()
        RETURNS TRIGGER AS $$
        BEGIN
            -- 仅在 end_date 不为 NULL 时发送通知
            IF NEW.end_date IS NOT NULL THEN
                PERFORM pg_notify('drive_update', '行程表新增或更新操作');
            END IF;
            RETURN NEW; -- 返回新行
        END;
        $$ LANGUAGE plpgsql;
        """)

        # 创建行程触发器
        cursor.execute("""
        CREATE OR REPLACE TRIGGER drive_update_trigger
        AFTER INSERT OR UPDATE OF end_date ON drives
        FOR EACH ROW
        EXECUTE FUNCTION notify_drive_update();
        """)

        conn.commit()  # 提交事务
        print("行程触发器创建成功")

def create_charging_trigger(conn):
    while not pool_initialized:  # 等待连接池初始化
        time.sleep(1)
    with conn.cursor() as cursor:
        # 创建充电触发器函数
        cursor.execute("""
        CREATE OR REPLACE FUNCTION notify_charging_update()
        RETURNS TRIGGER AS $$
        BEGIN
            -- 仅在 end_date 不为 NULL 时发送通知
            IF NEW.end_date IS NOT NULL THEN
                PERFORM pg_notify('charging_update', '充电过程表新增或更新操作');
            END IF;
            RETURN NEW; -- 返回新行
        END;
        $$ LANGUAGE plpgsql;
        """)

        # 创建充电触发器
        cursor.execute("""
        CREATE OR REPLACE TRIGGER charging_update_trigger
        AFTER INSERT OR UPDATE OF end_date ON charging_processes
        FOR EACH ROW
        EXECUTE FUNCTION notify_charging_update();
        """)

        conn.commit()  # 提交事务
        print("充电触发器创建成功")


async def listen_for_updates():
    global newdata
    async def notify_callback(connection, pid, channel, payload):   
        global newdata 
        print(f"收到通知: 通道={channel}, 消息={payload}, 由进程 {pid} 发送")
        newdata = str(channel)
        message_queue.put(("teslamate/cars/1/manual", 1))
    try:
        print("尝试连接到数据库...")
        conn = await asyncpg.connect(
            database=os.getenv('DATABASE_NAME'),
            user=os.getenv('DATABASE_USER'),
            password=os.getenv('DATABASE_PASS'),
            host=os.getenv('DATABASE_HOST'),
            port=os.getenv('DATABASE_PORT', 5432)  # 默认端口 5432
        )
        print("数据库连接成功")

        print("尝试订阅通道...")
        await conn.add_listener('drive_update', notify_callback)
        await conn.add_listener('charging_update', notify_callback)
        print("成功订阅通道")

        while True:
            # print("保持连接活跃，等待通知...")
            await asyncio.sleep(60)  # 保持连接活跃
    except Exception as e:
        print(f"监听更新时发生错误: {e}")
    finally:
        if conn:
            await conn.close()
            print("监听程序已关闭")
def start_listening():
    asyncio.run(listen_for_updates())



threading.Thread(target=initialize_db_pool).start()
threading.Thread(target=start_listening).start()




def fetch_drive_data():
    global efficiency
    query = """
    SELECT 
        start_date, 
        end_date, 
        speed_max, 
        power_max, 
        start_ideal_range_km, 
        end_ideal_range_km, 
        start_km, 
        end_km, 
        distance, 
        start_address_id, 
        end_address_id, 
        start_rated_range_km, 
        end_rated_range_km,
        start_position.battery_level AS start_battery_level,
        end_position.battery_level AS end_battery_level,
        start_address.road AS start_address_road,
        end_address.road AS end_address_road,
        start_address.house_number AS start_address_house_number,
        end_address.house_number AS end_address_house_number,
        start_address.city AS start_address_city,
        end_address.city AS end_address_city,
        start_geofence.name AS start_geofence_name,
        end_geofence.name AS end_geofence_name,
        duration_min
    FROM drives
    LEFT JOIN positions start_position ON start_position.id = drives.start_position_id
    LEFT JOIN positions end_position ON end_position.id = drives.end_position_id
    LEFT JOIN addresses start_address ON start_address.id = drives.start_address_id
    LEFT JOIN addresses end_address ON end_address.id = drives.end_address_id
    LEFT JOIN geofences start_geofence ON start_geofence.id = drives.start_geofence_id
    LEFT JOIN geofences end_geofence ON end_geofence.id = drives.end_geofence_id
    ORDER BY end_date DESC NULLS LAST
    LIMIT 1
    """

    conn = None
    cursor = None

    try:
        # 获取数据库连接
        conn = get_connection()

        # 创建 RealDictCursor 游标
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)

        # 执行查询
        cursor.execute(query)
        result = cursor.fetchone()

        if result:
            duration_min = float(result["duration_min"])
            if duration_min == 0:
                print("里程为0，跳过")
                return None

            # 获取查询字段并添加8小时偏移
            start_date = result["start_date"] + timedelta(hours=8)
            end_date = result["end_date"] + timedelta(hours=8)
            speed_max = result["speed_max"]
            power_max = result["power_max"]
            start_ideal_range_km = result["start_ideal_range_km"]
            end_ideal_range_km = result["end_ideal_range_km"]
            start_km = result["start_km"]
            end_km = result["end_km"]
            distance = result["distance"]
            start_rated_range_km = result["start_rated_range_km"]
            end_rated_range_km = result["end_rated_range_km"]

            # 提取起始电量和结束电量
            start_battery_level = result["start_battery_level"]
            end_battery_level = result["end_battery_level"]

            # 获取地址信息
            start_geofence_name = result["start_geofence_name"]
            end_geofence_name = result["end_geofence_name"]
            start_address_road = result["start_address_road"]
            end_address_road = result["end_address_road"]
            start_address_house_number = result["start_address_house_number"]
            end_address_house_number = result["end_address_house_number"]
            start_address_city = result["start_address_city"]
            end_address_city = result["end_address_city"]

            # 组装起始地址
            start_address_parts = filter(None, [
                start_address_city,
                start_address_road,
                start_address_house_number
            ])
            start_address = " ".join(start_address_parts) if start_geofence_name is None else start_geofence_name

            # 如果地址为空，提供默认值
            if not start_address.strip():
                start_address = "地址信息不可用"

            # 组装终点地址
            end_address_parts = filter(None, [
                end_address_city,
                end_address_road,
                end_address_house_number
            ])
            end_address = " ".join(end_address_parts) if end_geofence_name is None else end_geofence_name

            # 如果地址为空，提供默认值
            if not end_address.strip():
                end_address = "地址信息不可用"

            # 计算电量差值
            battery_level_reduction = start_battery_level - end_battery_level

            # 计算行程时长
            trip_duration = end_date - start_date
            trip_duration_formatted = str(trip_duration).split(".")[0]  # 去掉微秒部分

            # 计算平均车速
            avg_speed = None
            if duration_min and distance:
                avg_speed = (distance / duration_min) * 60  # 计算每小时的平均车速

            # 调用 get_battery_health() 设置全局变量 efficiency
            get_battery_health()
            efficiency = float(efficiency)

            # 计算行程能耗
            avg_cost = None
            if start_rated_range_km is not None and end_rated_range_km is not None:
                avg_cost = (float(start_rated_range_km or 0) - float(end_rated_range_km or 0)) * (efficiency / 100)

            # 计算平均能耗
            battery_consumption = None
            if avg_cost is not None and distance is not None:
                battery_consumption = (avg_cost / float(distance)) * 1000

            # 在消息组装前增加判断，确保 duration_min 大于 0 才组装消息
            if duration_min > 0:
                # 组装消息内容
                text_msg2 = f"本次行程:{distance:.2f} KM ({start_km:.2f} KM→{end_km:.2f} KM)\n<br>"
                text_msg2 += f"行程历时:{trip_duration_formatted} ({start_date.strftime('%H:%M:%S')}→{end_date.strftime('%H:%M:%S')})\n<br>"
                
                if check_button_status(10):
                    text_msg2 += f"({start_address}→{end_address})\n<br>"  # 使用组装后的地址
                
                text_msg2 += f"电池消耗:{battery_level_reduction:.0f}% ({start_battery_level:.0f}%→{end_battery_level:.0f}%)\n<br>"
                text_msg2 += f"续航减少:{float(start_ideal_range_km or 0) - float(end_ideal_range_km or 0):.2f} KM ({start_ideal_range_km:.2f} KM→{end_ideal_range_km:.2f} KM)\n<br>"
                text_msg2 += f"最高车速:{speed_max:.2f} KM/H\u00A0\u00A0\u00A0\u00A0"
                text_msg2 += f"平均车速:{avg_speed:.2f} KM/H\n<br>" if avg_speed else "平均车速:暂无数据\n<br>"
                text_msg2 += f"消耗电量:{avg_cost:.2f} kWh\u00A0\u00A0\u00A0\u00A0" if avg_cost else "消耗电量:暂无数据\u00A0\u00A0\u00A0\u00A0"
                text_msg2 += f"平均能耗:{battery_consumption:.2f} Wh/km\n<br>" if battery_consumption else "平均能耗:暂无数据\n<br>"

                return text_msg2
            else:
                print("行程时长为0或无效，不进行消息组装。")
                return None

        else:
            print("No data found.")
            return None

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # 确保游标和连接关闭
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)




# 查询 charging_processes 表按 end_date 从大到小取第一行，并连接其他表
def fetch_charge_data():
    preferred_range = "ideal"  # 或 "rated"，根据你的需求调整
    query = f"""
    SELECT
        cp.start_date,
        cp.end_date,
        cp.charge_energy_added,
        cp.charge_energy_used,
        cp.duration_min,
        cp.start_battery_level,
        cp.end_battery_level,
        cp.cost,
        -- 使用子查询来获取最大功率
        (SELECT MAX(c.charger_power)
         FROM charges c
         WHERE c.charging_process_id = cp.id) AS max_power,
        p.latitude,
        p.longitude,
        p.odometer AS start_odometer,
        (p.odometer + (cp.charge_energy_added / cars.efficiency) * 1000) AS end_odometer,
        cp.start_{preferred_range}_range_km AS start_range_km,
        cp.end_{preferred_range}_range_km AS end_range_km,
        a.name AS address_name,
        g.name AS geofence_name,
        -- 修改查询，以确保charger_phases可以正确引用
        CASE 
            WHEN (SELECT COUNT(*) FROM charges c2 WHERE c2.charging_process_id = cp.id AND c2.charger_phases IS NOT NULL) > 0 
            THEN 'AC'
            ELSE 'DC'
        END AS charge_type
    FROM
        charging_processes cp
    LEFT JOIN positions p ON cp.position_id = p.id
    LEFT JOIN addresses a ON cp.address_id = a.id
    LEFT JOIN geofences g ON cp.geofence_id = g.id
    LEFT JOIN cars ON cp.car_id = cars.id
    ORDER BY cp.end_date DESC NULLS LAST
    LIMIT 1;
    """

    conn = None
    cursor = None

    try:
        # 从连接池获取连接
        conn = get_connection()

        # 创建 RealDictCursor 游标
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 执行查询
        cursor.execute(query)
        result = cursor.fetchone()

        if result:
            # 解析查询结果
            start_date = result["start_date"] + timedelta(hours=8)  # 加8小时
            end_date = result["end_date"] + timedelta(hours=8)  # 加8小时
            address_name = result["address_name"] or "未知位置"
            geofence_name = result["geofence_name"] or "未知地理围栏"
            charge_type = result["charge_type"]
            duration_min = result["duration_min"]
            charge_energy_added = result["charge_energy_added"]
            charge_energy_used = result["charge_energy_used"]
            efficiency = (charge_energy_added / charge_energy_used) * 100 if charge_energy_used else None
            max_power = result["max_power"]
            start_range_km = result["start_range_km"]
            end_range_km = result["end_range_km"]
            start_battery_level = result["start_battery_level"]
            end_battery_level = result["end_battery_level"]
            start_odometer = result["start_odometer"] / 1000  # 转换单位，从 m 转为 km
            end_odometer = result["end_odometer"] / 1000  # 转换单位，从 m 转为 km

            # 计算续航减少
            range_added = (end_range_km - start_range_km)  # 计算续航减少，单位是 km

            # 计算行程时长，格式为 00:00:00 (00:00:00 → 00:00:00)
            duration_timedelta = timedelta(minutes=duration_min)
            duration_str = str(duration_timedelta).split(".")[0]  # 去掉微秒部分

            # 计算平均功率
            # 平均功率 = 充入电量 / 时长 (单位是小时)，时长以分钟为单位，需要转换为小时
            average_power = (charge_energy_added / duration_min) * 60 if duration_min else None  # kWh/h
            if max_power == 4:
                max_power = 3.5
            
            # 计算平均速度 (单位：Km/h)
            if duration_min > 0:  # 避免除以0的错误
                average_speed = float(range_added) / (float(duration_min) / 60)  # 续航增加（km） / 时长（小时）
            else:
                average_speed = 0  # 如果时长为0，则平均速度设为0
                print("充入电量为0，跳过")
                return None
            # 组装消息内容
            # 使用 COALESCE 来选择地理围栏或地址
            location_display = geofence_name if geofence_name != "未知地理围栏" else address_name

            text_msg = f"时长: {duration_str} ({start_date.strftime('%H:%M:%S')}→{end_date.strftime('%H:%M:%S')})\n<br>"
            text_msg += f"续航增加: {range_added:.2f} km ({start_range_km:.2f}→{end_range_km:.2f})<br>"
            battery_level_increase = end_battery_level - start_battery_level  # 计算电池电量变化
            text_msg += f"电量增加: {battery_level_increase:.0f}% ({start_battery_level:.0f}%→{end_battery_level:.0f}%)\n<br>"
            text_msg += f"充入电量: {charge_energy_added:.2f} kWh\u00A0\u00A0"
            text_msg += f"消耗电量: {charge_energy_used:.2f} kWh<br>"
            text_msg += f"效率: {efficiency:.2f}%\u00A0\u00A0\u00A0\u00A0" if efficiency else "效率: 暂无数据\u00A0\u00A0\u00A0\u00A0"
            text_msg += f"充电方式: {charge_type}\n<br>"
            if check_button_status(10):
                text_msg += f"位置: {location_display}\n<br>"
            text_msg += f"最大功率: {max_power:.2f} kW\u00A0\u00A0\u00A0"
            text_msg += f"平均功率: {average_power:.2f} kW\n<br>" if average_power else "平均功率: 暂无数据\n<br>"
            text_msg += f"平均速度: {average_speed:.2f} Km/h\n<br>"  # 添加平均速度
            # 添加居中标题，仅在平均功率之后
            text_msg += "<div style='font-size: 14px; color: #555; line-height: 1.8; margin: 0;'>"

            # 添加居中标题
            text_msg += f"<h2 style='text-align: center; font-size: 18px; color: #4caf50; margin-bottom: 10px;'>电池信息</h2>"
            get_battery_health()

            if charge_limit_soc != "❔":
                text_msg += "充电设定:" + charge_limit_soc + "%" + "(" + "{:.2f}".format((math.floor(float(charge_limit_soc)) * float(current_range)) / 100) + "Km) "					
            text_msg += "满电:" + "{:.2f}".format(float(current_range)) + "Km<br>"
            text_msg += bet2 + bet4 + "（出厂：" + bet1 + bet3 + ")" + "<br>" + bet5

            # 结束样式
            text_msg += "</div>"

            # 打印消息内容
            # print(text_msg)
            return text_msg
        else:
            print("No data found.")
            return None

    except Exception as e:
        print(f"Error: {e}")
    finally:
        # 确保游标和连接关闭
        if cursor:
            cursor.close()
        if conn:
            return_connection(conn)





















ENV_FILE = "ciyahu.env"
BUTTON_COUNT = 11  # 按钮数量
HOST = "0.0.0.0"
PORT = 7777

# 默认值
DEFAULT_VALUES = {
    f"BUTTON_{i}": "OFF" for i in range(1, BUTTON_COUNT + 1)
}
DEFAULT_VALUES.update({
    "EXTRA_CHECKBOX_1": "OFF",
    "EXTRA_INPUT_1": "3",
    "EXTRA_CHECKBOX_2": "OFF",
    "EXTRA_INPUT_2": "120",
    "EXTRA_CHECKBOX_3": "OFF",
    "EXTRA_INPUT_3": "60"
})


# 读取 .env 文件的状态
def read_env_states():
    states = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as env_file:
            for line in env_file:
                key, value = line.strip().split("=")
                states[key] = value
    return states

# 更新 .env 文件
def update_env(states):
    # 读取当前状态
    current_states = read_env_states()
    # 合并新的状态
    current_states.update(states)
    # 写入文件
    with open(ENV_FILE, "w") as env_file:
        for key, value in current_states.items():
            env_file.write(f"{key}={value}\n")
            
            
CORRECT_PASSWORD = os.getenv('WEB_PASSWORD', 'teslamate')
# 自定义 HTTP 请求处理器
class ButtonHandler(SimpleHTTPRequestHandler):
    def check_password(self):
        """检查请求中的密码是否正确"""
        auth_header = self.headers.get("Authorization")
        return auth_header == f"Bearer {CORRECT_PASSWORD}"

    def send_unauthorized(self):
        """发送未授权响应"""
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "error", "message": "Unauthorized"}).encode("utf-8"))

    def do_GET(self):
        # 静态文件或初始 HTML 文件不需要授权
        if self.path in ["/", "/index.html", "/favicon.ico"]:
            return super().do_GET()

        # 仅 API 需要授权
        if not self.check_password():
            self.send_unauthorized()
            return

        if self.path == "/states":
            # 返回按钮和复选框状态
            states = read_env_states()
            response = {
                "buttons": [states.get(f"BUTTON_{i}", "OFF") for i in range(1, BUTTON_COUNT + 1)],
                "extras": {key: states.get(key, DEFAULT_VALUES[key]) for key in DEFAULT_VALUES}
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(response).encode("utf-8"))
        else:
            super().do_GET()

    def do_POST(self):
        if not self.check_password():
            self.send_unauthorized()
            return

        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        if self.path == "/update":
            # 更新按钮状态
            button_id = data.get("id")
            status = data.get("status", "OFF")
            if button_id is not None:
                key = f"BUTTON_{button_id + 1}"
                update_env({key: status})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))

        elif self.path == "/extra":
            # 更新复选框和输入框状态
            checkbox_key = f"EXTRA_CHECKBOX_{data['id']}"
            input_key = f"EXTRA_INPUT_{data['id']}"
            states = {
                checkbox_key: "ON" if data.get("checkbox") else "OFF",
                input_key: str(data.get("input", DEFAULT_VALUES[input_key]))
            }
            update_env(states)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            
            
            
            
            

# 初始化并启动服务器
def initialize_env_and_server():
    server = HTTPServer((HOST, PORT), ButtonHandler)
    print(f"web服务器启动成功，端口{PORT}")
    server.serve_forever()

# 启动服务器线程
threading.Thread(target=initialize_env_and_server, daemon=True).start()


def check_button_status(button_number):
    global nouvelleinformation
    try:
        # 打开 ciyahu.env 文件进行读取
        with open("ciyahu.env", "r") as env_file:
            # 将文件内容解析为字典
            env_states = dict(line.strip().split("=") for line in env_file if "=" in line)
        
        # 获取按钮状态，默认为 OFF
        button_key = f"BUTTON_{button_number}"
        
        # 如果输入的按钮是 10，返回按钮状态
        if button_number == 10:
            button_status = env_states.get(button_key, "OFF")
            return button_status == "ON"  # 如果是 "ON"，返回 True，否则返回 False
        
        # 处理按钮状态为 OFF 的情况
        if env_states.get(button_key, "OFF") == "OFF":
            nouvelleinformation = False
            print("根据用户设定，推送取消")
        
    except FileNotFoundError:
        print("Error: ciyahu.env 文件不存在")
        nouvelleinformation = False
    except Exception as e:
        print(f"Error 检查按钮状态时出错: {e}")
        nouvelleinformation = False

def get_checkbox_status_by_number(number):
    try:
        # 读取 .env 文件中的状态
        states = read_env_states()
        
        # 构造复选框的键名
        checkbox_key = f"EXTRA_CHECKBOX_{number}"
        
        # 如果该复选框不存在于文件中，返回 None
        if checkbox_key not in states:
            return None
        
        # 返回复选框的状态（如果是 "ON" 返回其对应的数值，否则返回 None）
        if states[checkbox_key] == "ON":
            # 获取对应的输入框值
            input_key = f"EXTRA_INPUT_{number}"
            input_value = states.get(input_key, None)
            
            # 将输入框的值转换为数字类型，如果缺失或无法转换，返回 0
            return int(input_value) if input_value and input_value.isdigit() else 0
        else:
            return None  # 如果复选框是 OFF，返回 None

    except FileNotFoundError:
        print("Error: ciyahu.env 文件不存在")
        return None
    except Exception as e:
        print(f"Error 读取复选框状态时出错: {e}")
        return None


def periodic_task():
    # 保存上一次的间隔值，用于检测变化
    global nouvelleinformation, tittle
    last_interval_1 = None
    last_interval_2 = None
    next_run_1 = 0
    next_run_2 = 0

    while True:
        current_time = time.time()

        # 检查复选框 2 的值，判断第一个任务是否需要执行
        interval_1 = get_checkbox_status_by_number(2)
        if interval_1 is not None:
            if interval_1 != last_interval_1:  # 如果间隔发生变化，重新计算下一次运行时间
                next_run_1 = current_time + interval_1 * 60
                last_interval_1 = interval_1
                # print(f"第一个任务的间隔发生变化，新间隔为 {interval_1} 分钟，重新计算运行时间")

            if current_time >= next_run_1:  # 到达定时时间
                # print(f"第一个任务执行，间隔为 {interval_1} 分钟")
                nouvelleinformation = True
                tittle = "定时推送"
                message_queue.put(("teslamate/cars/1/manual", 1))
                next_run_1 = current_time + interval_1 * 60  # 更新下一次运行时间
        else:
            # print("第一个任务被跳过，因为复选框 2 的返回值为 None")
            last_interval_1 = None  # 重置上次的值

        # 检查复选框 3 的值，判断第二个任务是否需要执行
        interval_2 = get_checkbox_status_by_number(3)
        if interval_2 is not None and charging_state_flag == "1":
            if interval_2 != last_interval_2:  # 如果间隔发生变化，重新计算下一次运行时间
                next_run_2 = current_time + interval_2 * 60
                last_interval_2 = interval_2
                # print(f"第二个任务的间隔发生变化，新间隔为 {interval_2} 分钟，重新计算运行时间")

            if current_time >= next_run_2:  # 到达定时时间
                # print(f"第二个任务执行，间隔为 {interval_2} 分钟，当前充电状态为 {charging_state_flag}")
                nouvelleinformation = True
                tittle = "充电中定时推送"
                message_queue.put(("teslamate/cars/1/manual", 1))
                next_run_2 = current_time + interval_2 * 60  # 更新下一次运行时间
        else:
            # print("第二个任务被跳过，因为复选框 3 的返回值为 None 或充电状态不为 '1'")
            last_interval_2 = None  # 重置上次的值

        # 等待 10 秒后再次检查状态
        # print("等待 10 秒进行下一次检查...")
        time.sleep(10)

# 启动定时任务的守护线程
threading.Thread(target=periodic_task, daemon=True).start()


        
        
        



# 定义常量
PI = 3.1415926535897932384626
A = 6378245.0
EE = 0.00669342162296594323

# WGS84 → GCJ02 (地球坐标系 → 火星坐标系)
def wgs84_to_gcj02(lat, lon):
    """
    将 WGS84 坐标转换为 GCJ02 坐标（火星坐标系）
    参数:
        lat: WGS84 坐标系纬度
        lon: WGS84 坐标系经度
    返回:
        (gcj_lat, gcj_lon): 火星坐标（纬度, 经度）
    """
    dlat = transformlat(lon - 105.0, lat - 35.0)
    dlon = transformlon(lon - 105.0, lat - 35.0)
    radlat = lat / 180.0 * PI
    magic = math.sin(radlat)
    magic = 1 - EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((A * (1 - EE)) / (magic * sqrtmagic) * PI)
    dlon = (dlon * 180.0) / (A / sqrtmagic * math.cos(radlat) * PI)
    gcj_lat = lat + dlat
    gcj_lon = lon + dlon
    return gcj_lat, gcj_lon

# 转换纬度的计算公式
def transformlat(x, y):
    """
    计算纬度的偏移量
    """
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * PI) + 320 * math.sin(y * PI / 30.0)) * 2.0 / 3.0
    return ret

# 转换经度的计算公式
def transformlon(x, y):
    """
    计算经度的偏移量
    """
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0
    return ret

# 生成百度地图地址
def generate_baidu_map_url(lat, lon):
    """
    生成百度地图跳转的 URL
    参数:
        lat: WGS84 坐标系纬度
        lon: WGS84 坐标系经度
    返回:
        url: 百度地图跳转链接
    """
    bd_lat, bd_lon =wgs84_to_gcj02(lat, lon)
    # url = f"baidumap://map?lat={bd_lat}&lng={bd_lon}&title=位置&content=位置详情"
    url = f"https://apis.map.qq.com/uri/v1/marker?marker=coord:{bd_lat},{bd_lon};title:车辆位置;addr:车辆位置&referer=myApp"
    return url


def send_email(subject, message, to_email):
    # 邮件发送者邮箱账号和密码
    sender_email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')

    # 创建一个MIMEMultipart类的实例
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject

    # 添加邮件正文
    msg.attach(MIMEText(message, 'plain'))

    # 设置SMTP服务器地址及端口
    server = smtplib.SMTP('smtp.qq.com', 587)  # 使用示例SMTP服务器地址和端口
    server.starttls()  # 启用安全传输
    server.login(sender_email, password)  # 登录邮箱
    text = msg.as_string()  # 获取msg对象的文本表示
    server.sendmail(sender_email, to_email, text)  # 发送邮件
    server.quit()  # 关闭服务器连接 
    
def send_email2(subject, message, to_email):
    # 邮件发送者邮箱账号和密码
    sender_email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')
    # 根据电池电量设置颜色
    if usable_battery_level < 20:
        battery_color = "#f44336"  # 红色
    elif usable_battery_level < 30:
        battery_color = "#ff9800"  # 橙色
    else:
        battery_color = "#4caf50"  # 绿色

    # 创建一个 MIMEMultipart 类的实例
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject


    # 添加邮件正文，启用 HTML 格式
    html_content = f"""
    <html>
        
         <body>
            <!-- 隐藏的预览内容 -->
            <div style="display: none; font-size: 0; color: transparent; max-height: 0; overflow: hidden; opacity: 0;">
                {tittle2}
            </div>

            <div style="
                background-color: #FFFAF0; 
                border-radius: 12px; 
                box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2); 
                padding: 20px; 
                max-width: 600px; 
                margin: 20px auto; 
                border: 1px solid #e0e0e0; 
                text-align: center;">
                <h2 style="
                    font-size: 18px; 
                    color: #4caf50; 
                    margin-bottom: 20px; 
                    font-weight: bold;">
                    车辆状态
                </h2>
                <p style="
                    font-size: 14px; 
                    color: #555; 
                    line-height: 1.8; 
                    margin: 0;">
                    {message}
                </p>

                <!-- 电量条 -->
                <div style="width: 100%; background: #e0e0e0; border-radius: 20px; overflow: hidden; margin: 20px 0; height: 20px; position: relative;">
                    <div style="height: 100%; background: {battery_color}; transition: width 0.4s ease; width: {str(usable_battery_level)}%;"></div>
                    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; text-align: center; line-height: 20px; font-size: 12px; color: white;">
                        电量 {str(usable_battery_level)}%
                    </div>
                </div>
                
                <div style="display: flex; justify-content: center; margin-top: 20px;">
                    <a href="{GPS}&title=车辆位置&content=车辆位置&output=html" 
                       target="_blank" 
                       style="
                            display: flex; 
                            align-items: center; 
                            padding: 5px 10px;  
                            height: 30px; 
                            line-height: 30px; 
                            background-color: #4caf50; 
                            color: white; 
                            text-decoration: none; 
                            border-radius: 15px; 
                            font-size: 14px; 
                            font-weight: bold; 
                            box-sizing: border-box; 
                            justify-content: center;">
                        位置
                        <span style="
    display: inline-block; 
    transform: rotate({heading_angle - 90}deg); 
    margin-left: 5px; 
    color: red; 
    font-size: 19.2px; /* 增大字体 20%（原为16px） */
    text-shadow: -0.5px -0.5px 0 #fff, 0.5px -0.5px 0 #fff, -0.5px 0.5px 0 #fff, 0.5px 0.5px 0 #fff;">
    ➤
</span>
                    </a>
                </div>
            </div>

            <!-- 右下角版本号 -->
            <div style="
                position: fixed; 
                bottom: 50px; /* 向上移动到距离底部 50px */
                right: 10px; 
                font-size: 12px; 
                color: #888;">
                v1.01
            </div>
        </body>
    </html>
    """
    msg.attach(MIMEText(html_content, 'html'))  # 使用 'html' 而不是 'plain'

    # 设置 SMTP 服务器地址及端口
    server = smtplib.SMTP('smtp.qq.com', 587)  # 使用示例 SMTP 服务器地址和端口
    server.starttls()  # 启用安全传输
    server.login(sender_email, password)  # 登录邮箱
    text = msg.as_string()  # 获取 msg 对象的文本表示
    server.sendmail(sender_email, to_email, text)  # 发送邮件
    server.quit()  # 关闭服务器连接
    
def send_email3(subject, trip_message, message, to_email):
    """
    :param subject: 邮件主题
    :param trip_message: 行程结束的输出信息
    :param other_message: 其他正常输出信息
    :param to_email: 接收者邮箱
    """
    # 邮件发送者邮箱账号和密码
    sender_email = os.getenv('EMAIL_ADDRESS')
    password = os.getenv('EMAIL_PASSWORD')
    # 根据电池电量设置颜色
    if usable_battery_level < 20:
        battery_color = "#f44336"  # 红色
    elif usable_battery_level < 30:
        battery_color = "#ff9800"  # 橙色
    else:
        battery_color = "#4caf50"  # 绿色

    # 创建一个 MIMEMultipart 类的实例
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = subject
    # 添加邮件正文，启用 HTML 格式
    html_content = f"""
    <html>
       <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; margin: 0; padding: 0;">
            <!-- 隐藏的预览内容 -->
            <div style="display: none; font-size: 0; color: transparent; max-height: 0; overflow: hidden; opacity: 0;">
                {tittle2}
            </div>
            
            <!-- 悬浮框，行程结束信息 -->
            <div style="
                background-color: #FFFAF0; 
                border-radius: 12px; 
                box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2); 
                padding: 10px; 
                max-width: 600px; 
                margin: 10px auto; 
                border: 1px solid #e0e0e0; 
                text-align: center;">
                <h2 style="
                    font-size: 18px; 
                    color: #4caf50; 
                    margin-bottom: 10px; 
                    font-weight: bold;">
                    {tittle3}
                </h2>
                <p style="
                    font-size: 14px; 
                    color: #555; 
                    line-height: 1.8; 
                    margin: 0;">
                    {trip_message}
                </p>
            </div>
            
            <div style="
                background-color: #FFFAF0; 
                border-radius: 12px; 
                box-shadow: 0 8px 15px rgba(0, 0, 0, 0.2); 
                padding: 10px; 
                max-width: 600px; 
                margin: 20px auto; 
                border: 1px solid #e0e0e0; 
                text-align: center;">
                <h2 style="
                    font-size: 18px; 
                    color: #4caf50; 
                    margin-bottom: 10px; 
                    font-weight: bold;">
                    车辆状态
                </h2>
                <p style="
                    font-size: 14px; 
                    color: #555; 
                    line-height: 1.8; 
                    margin: 0;">
                    {message}
                </p>

                <!-- 电量条 -->
                <div style="width: 100%; background: #e0e0e0; border-radius: 20px; overflow: hidden; margin: 20px 0; height: 20px; position: relative;">
                    <div style="height: 100%; background: {battery_color}; transition: width 0.4s ease; width: {str(usable_battery_level)}%;"></div>
                    <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; text-align: center; line-height: 20px; font-size: 12px; color: white;">
                        电量 {str(usable_battery_level)}%
                    </div>
                </div>
                
                <div style="display: flex; justify-content: center; margin-top: 20px;">
                    <a href="{GPS}&title=车辆位置&content=车辆位置&output=html" 
                       target="_blank" 
                       style="
                            display: flex; 
                            align-items: center; 
                            padding: 5px 10px;  
                            height: 30px; 
                            line-height: 30px; 
                            background-color: #4caf50; 
                            color: white; 
                            text-decoration: none; 
                            border-radius: 15px; 
                            font-size: 14px; 
                            font-weight: bold; 
                            box-sizing: border-box; 
                            justify-content: center;">
                        位置
                        <span style="
    display: inline-block; 
    transform: rotate({heading_angle - 90}deg); 
    margin-left: 5px; 
    color: red; 
    font-size: 19.2px; /* 增大字体 20%（原为16px） */
    text-shadow: -0.5px -0.5px 0 #fff, 0.5px -0.5px 0 #fff, -0.5px 0.5px 0 #fff, 0.5px 0.5px 0 #fff;">
    ➤
</span>
                    </a>
                </div>
            </div>

            <!-- 右下角版本号 -->
            <div style="
                position: fixed; 
                bottom: 50px; /* 向上移动到距离底部 50px */
                right: 10px; 
                font-size: 12px; 
                color: #888;">
                v2.01
            </div>
        </body>
    </html>
    """

    msg.attach(MIMEText(html_content, 'html'))  # 使用 'html' 而不是 'plain'

    # 设置 SMTP 服务器地址及端口
    server = smtplib.SMTP('smtp.qq.com', 587)  # 使用示例 SMTP 服务器地址和端口
    server.starttls()  # 启用安全传输
    server.login(sender_email, password)  # 登录邮箱
    text = msg.as_string()  # 获取 msg 对象的文本表示
    server.sendmail(sender_email, to_email, text)  # 发送邮件
    server.quit()  # 关闭服务器连接      


def on_connect(client, userdata, flags, rc):
	
	if rc == 0:
		print("✔️ 成功连接到MQTT代理" )
		# send_email("Tesla 状态更新", "✔️ 成功连接到MQTT代理", os.getenv('EMAIL_ADDRESS'))  # 同时发送电子邮件
	else:
		print("❌ 连接到MQTT代理失败")
		# send_email("Tesla 连接失败", "❌ 连接到MQTT代理失败", os.getenv('EMAIL_ADDRESS'))  # 同时发送电子邮件

	# Subscribing in on_connect() means that if we lose the connection and reconnect subscriptions will be renewed.
	client.subscribe("teslamate/cars/1/tpms_pressure_fl")		# 前左
	client.subscribe("teslamate/cars/1/tpms_pressure_fr")		# 前右
	client.subscribe("teslamate/cars/1/tpms_pressure_rl")		# 后左
	client.subscribe("teslamate/cars/1/tpms_pressure_rr")		# 后右
	client.subscribe("teslamate/cars/1/outside_temp")			# 车外温度
	client.subscribe("teslamate/cars/1/inside_temp")			# 车内温度
	client.subscribe("teslamate/cars/1/sentry_mode")			# 哨兵
	client.subscribe("teslamate/cars/1/version")				# 系统版本
	client.subscribe("teslamate/cars/1/display_name")         # 车机名称
	client.subscribe("teslamate/cars/1/model")                # Either "S", "3", "X" or "Y"
	client.subscribe("teslamate/cars/1/odometer")             # 里程表 
	client.subscribe("teslamate/cars/1/update_available")     # 版本更新
	client.subscribe("teslamate/cars/1/state")                # 车辆状态
	client.subscribe("teslamate/cars/1/locked")			    # 车锁状态
	client.subscribe("teslamate/cars/1/exterior_color")       # 车辆颜色
	client.subscribe("teslamate/cars/1/charge_energy_added")  # 电量增加
	client.subscribe("teslamate/cars/1/doors_open")			# 车门状态
	client.subscribe("teslamate/cars/1/windows_open")			# 车窗状态
	client.subscribe("teslamate/cars/1/trunk_open")			# 后备箱状态
	client.subscribe("teslamate/cars/1/frunk_open")			# 前备箱状态
	client.subscribe("teslamate/cars/1/battery_level")		
	client.subscribe("teslamate/cars/1/usable_battery_level") # 电量
	client.subscribe("teslamate/cars/1/plugged_in")			# 充电枪已插入
	client.subscribe("teslamate/cars/1/time_to_full_charge")  # 充满电的剩余时间
	client.subscribe("teslamate/cars/1/shift_state")			# 档位状态
	client.subscribe("teslamate/cars/1/latitude")				# 北纬
	client.subscribe("teslamate/cars/1/longitude")			# 东经
	client.subscribe("teslamate/cars/1/speed")				# 当前车速
	client.subscribe("teslamate/cars/1/est_battery_range_km")	# 实际续航
	client.subscribe("teslamate/cars/1/rated_battery_range_km")	# 剩余续航
	client.subscribe("teslamate/cars/1/ideal_battery_range_km")	# 剩余续航
	client.subscribe("teslamate/cars/1/heading")				# 车头朝向
	client.subscribe("teslamate/cars/1/update_version")		# 待更新版本
	client.subscribe("teslamate/cars/1/tpms_soft_warning_fl")	# 胎压警报前左
	client.subscribe("teslamate/cars/1/tpms_soft_warning_fr")	# 胎压警报前右
	client.subscribe("teslamate/cars/1/tpms_soft_warning_rl")	# 胎压警报后左
	client.subscribe("teslamate/cars/1/tpms_soft_warning_rr")	# 胎压警报后右
	client.subscribe("teslamate/cars/1/charging_state")		# 充电状态
	client.subscribe("teslamate/cars/1/charger_power")		# 充电功率
	client.subscribe("teslamate/cars/1/power")
	client.subscribe("teslamate/cars/1/charge_port_door_open")	# 充电口状态 
	client.subscribe("teslamate/cars/1/elevation")			# 海拔高度
	client.subscribe("teslamate/cars/1/charger_voltage")		# 电压 
	client.subscribe("teslamate/cars/1/is_climate_on")		# 空调开关
	client.subscribe("teslamate/cars/1/charge_current_request")	# 请求功率
	client.subscribe("teslamate/cars/1/charge_limit_soc")		# 充电限制
	client.subscribe("teslamate/cars/1/is_user_present") 
	client.subscribe("teslamate/cars/1/is_preconditioning")
	client.subscribe("teslamate/cars/1/charger_actual_current")
	client.subscribe("teslamate/cars/1/charger_phases")
	client.subscribe("teslamate/cars/1/charge_current_request_max")
	client.subscribe("teslamate/cars/1/scheduled_charging_start_time")
	client.subscribe("teslamate/cars/1/since")
	client.subscribe("teslamate/cars/1/healthy")
	client.subscribe("teslamate/cars/1/update_available")
	client.subscribe("teslamate/cars/1/geofence")
	client.subscribe("teslamate/cars/1/trim_badging")	
	client.subscribe("teslamate/cars/1/spoiler_type")
	client.subscribe("teslamate/cars/1/location")
	client.subscribe("teslamate/cars/1/passenger_front_door_open")
	client.subscribe("teslamate/cars/1/passenger_rear_door_open")
	client.subscribe("teslamate/cars/1/active_route_destination")
	client.subscribe("teslamate/cars/1/active_route_latitude")
	client.subscribe("teslamate/cars/1/active_route_longitude")
	client.subscribe("teslamate/cars/1/active_route")
	client.subscribe("teslamate/cars/1/center_display_state")	
	print("订阅完成")

	
def on_message(client, userdata, msg):
    try:
        topic = msg.topic
        payload = msg.payload.decode()
        
        beijing_timezone = pytz.timezone('Asia/Shanghai')  # 获取当前北京时间
        now = datetime.now(beijing_timezone)
        today = now.strftime("%y/%m/%d %H:%M:%S")  # 格式化日期时间
        topic_suffix = topic.replace("teslamate/cars/1/", "").ljust(29)
        # print(str(today) + " 接收————" + str(topic_suffix) + " : " + str(payload))
        
        message_queue.put((msg.topic, msg.payload.decode()))
    except Exception as e:
        print(f"消息处理失败：{e}")


def get_battery_health(car_id=1):
    global bet1, bet2, bet3, bet4, bet5, efficiency, current_range
    global conn_charge_cable_value, battery_heater_value  # 新增全局变量
    conn = get_connection()
    if conn is None:
        print("无法获取数据库连接")
        return

    try:
        cursor = conn.cursor()
        cursor.execute("""
            WITH EfficiencyData AS (
                SELECT
                    cars.id AS car_id,
                    ROUND(
                        (charge_energy_added / NULLIF(end_rated_range_km - start_rated_range_km, 0))::numeric * 100, 
                        3
                    ) AS derived_efficiency,
                    cars.efficiency * 100 AS car_efficiency
                FROM cars
                LEFT JOIN charging_processes ON
                    cars.id = charging_processes.car_id 
                    AND duration_min > 10
                    AND end_battery_level <= 95
                    AND start_rated_range_km IS NOT NULL
                    AND end_rated_range_km IS NOT NULL
                    AND charge_energy_added > 0
                WHERE cars.id = %s
                GROUP BY cars.id, derived_efficiency, car_efficiency
                LIMIT 1
            ),
            Aux AS (
                SELECT
                    car_id,
                    COALESCE(derived_efficiency, car_efficiency) AS efficiency
                FROM EfficiencyData
            ),
            CurrentCapacity AS (
                SELECT
                    c.rated_battery_range_km,
                    aux.efficiency,
                    c.usable_battery_level,
                    (c.rated_battery_range_km * aux.efficiency / c.usable_battery_level) AS capacity
                FROM charging_processes cp
                INNER JOIN charges c ON c.charging_process_id = cp.id
                INNER JOIN Aux aux ON cp.car_id = aux.car_id
                WHERE
                    cp.car_id = %s
                    AND cp.end_date IS NOT NULL
                    AND cp.charge_energy_added >= (aux.efficiency + 5)
                    AND c.usable_battery_level > 0
                ORDER BY cp.end_date DESC
                LIMIT 10
            ),
            MaxCapacity AS (
                SELECT 
                    c.rated_battery_range_km,
                    aux.efficiency,
                    c.usable_battery_level,
                    (c.rated_battery_range_km * aux.efficiency / c.usable_battery_level) AS capacity
                FROM charging_processes cp
                INNER JOIN charges c ON c.charging_process_id = cp.id
                INNER JOIN Aux aux ON cp.car_id = aux.car_id
                WHERE
                    cp.car_id = %s
                    AND cp.end_date IS NOT NULL
                    AND c.charge_energy_added >= aux.efficiency
                ORDER BY capacity DESC
                LIMIT 10
            ),
            MaxRange AS (
                SELECT
                    floor(extract(epoch from date) / 86400) * 86400 AS time,
                    CASE
                        WHEN sum(usable_battery_level) = 0 THEN sum(ideal_battery_range_km) * 100
                        ELSE sum(ideal_battery_range_km) / sum(usable_battery_level) * 100
                    END AS range
                FROM (
                    SELECT
                        battery_level,
                        usable_battery_level,
                        date,
                        ideal_battery_range_km
                    FROM charges c
                    INNER JOIN charging_processes p ON p.id = c.charging_process_id
                    WHERE p.car_id = %s
                    AND usable_battery_level IS NOT NULL
                ) AS data
                GROUP BY 1
                ORDER BY 2 DESC
                LIMIT 1
            ),
            CurrentRange AS (
                SELECT
                    (range * 100.0 / usable_battery_level) AS range
                FROM (
                    (
                        SELECT
                            date,
                            ideal_battery_range_km AS range,
                            usable_battery_level
                        FROM positions
                        WHERE car_id = %s
                        AND ideal_battery_range_km IS NOT NULL
                        AND usable_battery_level > 0 
                        ORDER BY date DESC
                        LIMIT 1
                    )
                    UNION ALL
                    (
                        SELECT date,
                            ideal_battery_range_km AS range,
                            usable_battery_level
                        FROM charges c
                        INNER JOIN charging_processes p ON p.id = c.charging_process_id
                        WHERE p.car_id = %s
                        AND usable_battery_level > 0
                        ORDER BY date DESC
                        LIMIT 1
                    )
                ) AS data
                ORDER BY date DESC
                LIMIT 1
            ),
            Base AS (
                SELECT NULL
            )
            SELECT
                json_build_object(
                    'car_id', MAX(EfficiencyData.car_id),
                    'efficiency', MAX(Aux.efficiency),
                    'MaxRange', MAX(MaxRange.range),
                    'CurrentRange', MAX(CurrentRange.range),
                    'MaxCapacity', MAX(MaxCapacity.capacity),
                    'CurrentCapacity', COALESCE(AVG(CurrentCapacity.capacity), 1),
                    'CurrentCapacityData', json_agg(
                        json_build_object(
                            'rated_battery_range_km', CurrentCapacity.rated_battery_range_km,
                            'efficiency', CurrentCapacity.efficiency,
                            'usable_battery_level', CurrentCapacity.usable_battery_level,
                            'calculated_capacity', CurrentCapacity.capacity
                        )
                    ),
                    'MaxCapacityData', json_agg(
                        json_build_object(
                            'rated_battery_range_km', MaxCapacity.rated_battery_range_km,
                            'efficiency', MaxCapacity.efficiency,
                            'usable_battery_level', MaxCapacity.usable_battery_level,
                            'calculated_capacity', MaxCapacity.capacity
                        )
                    )
                )
            FROM Base
                LEFT JOIN EfficiencyData ON true
                LEFT JOIN Aux ON EfficiencyData.car_id = Aux.car_id
                LEFT JOIN MaxRange ON true
                LEFT JOIN CurrentRange ON true
                LEFT JOIN MaxCapacity ON true
                LEFT JOIN CurrentCapacity ON true
            GROUP BY Base
        """, (car_id, car_id, car_id, car_id, car_id, car_id))

        # 获取查询结果
        result = cursor.fetchone()

        # 处理查询结果
        if result:
            battery_health = result[0]  # JSON 数据对象
            car_id = battery_health['car_id']
            efficiency = battery_health['efficiency']
            max_range = battery_health['MaxRange']
            current_range = battery_health['CurrentRange']
            max_capacity = battery_health['MaxCapacity']
            current_capacity = battery_health['CurrentCapacity']
            current_capacity_data = battery_health['CurrentCapacityData']
            max_capacity_data = battery_health['MaxCapacityData']

            bet1 = f"{max_range:.2f} km  "
            bet2 = f"满电续航: {current_range:.2f} km  "
            bet3 = f"{max_capacity:.2f} kWh  "
            bet4 = f"满电容量: {current_capacity:.2f} kWh<br>"
            battery_health_percentage = (current_capacity / max_capacity) * 100
            bet5 = f"电池健康度: {battery_health_percentage:.2f}% "
            range_loss = max_range - current_range
            bet5 += f" 里程损失: {range_loss:.2f} km"
            # 查询 charges 表中的 conn_charge_cable 和 battery_heater
            cursor.execute("""
                SELECT conn_charge_cable, battery_heater 
                FROM charges 
                ORDER BY date DESC 
                LIMIT 1
            """)

            charge_info = cursor.fetchone()
            if charge_info:
                conn_charge_cable_value, battery_heater_value = charge_info
                # print(f"连接电缆类型: {conn_charge_cable_value}, 电池加热器状态: {battery_heater_value}")
            else:
                print("未找到充电信息数据。")
        else:
            print("未找到相关数据。")
    except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
        print(f"数据库连接错误：{e}")
        # 尝试重新连接
        return get_battery_health(car_id)
    except Exception as e:
        print(f"读取电池健康值时出错: {e}")
    finally:
        return_connection(conn)  # 确保连接被归还
            
            
            
            
def process_message_queue():
	global pseudo, model, km, ismaj, update_version, etat_connu, locked, text_locked, trip1, text_msg, text_msg2, start0
	global temps_restant_charge, text_energie, nouvelleinformation, is_user_present, trip_started, present
	global latitude, longitude, usable_battery_level
	global doors_state, frunk_state, trunk_state, windows_state
	global distance, DEBUG, GPS, HORODATAGE, CAR_ID, UNITS
	global hour1, minute, second1
	global tpms_pressure_fl, tpms_pressure_fr, tpms_pressure_rl, tpms_pressure_rr, tpms_soft_warning_fl, tpms_soft_warning_fr, tpms_soft_warning_rl, tpms_soft_warning_rr, fl_icon, fr_icon, rl_icon, rr_icon
	global tittle, tittle2, tittle3, outside_temp, inside_temp, sentry_mode, text_sentry_mode
	global charger_voltage, charger_power, charge_limit_soc, time_to_full_charge, carversion, charging_state_flag, current_power
	global start_battery_level, start_ideal_battery_range  # 行程开始时的电池百分比和续航里程
	global start_time, end_time, max_speed, speed  # 行程开始时间、结束时间和最高车速
	global previous_battery_level  # 新增变量，记录上一次的电池百分比
	global stored_messages, heading_angle
	global charging_start_time, charging_end_time
	global start_battery_level_charge, end_battery_level_charge
	global start_range_charge, end_range_charge, start_charge_energy_added, max_charger_power
	global charge_energy_added
	global rated, trip_rated, cost, avg_cost, start_rated, end_rated, battery_consumption, newdata, tpms_push_count, tpms_last_state

	previous_battery_level = usable_battery_level
	while True:
		try:
			topic, payload = message_queue.get()
			# print(newdata)
			if nouvelleinformation == False:
				tittle = ""
			if newdata == "charging_update":  # charging_update drive_update
				tittle="✉新充电信息"
				tittle3 = "充电结算"
				nouvelleinformation = True
				
				text_msg2 = fetch_charge_data()
				if text_msg2 == None:nouvelleinformation = False
				# print(text_msg2)
				newdata = ""
			if newdata == "drive_update":
				tittle="✉新行程信息"
				tittle3 = "行程结算"
				nouvelleinformation = True
				
				text_msg2 = fetch_drive_data()
				if text_msg2 == None:nouvelleinformation = False
				# print(text_msg2)
				newdata = ""

			# get_battery_health()
			beijing_timezone = pytz.timezone('Asia/Shanghai')  # 获取当前北京时间
			now = datetime.now(beijing_timezone)
			today = now.strftime("%y/%m/%d %H:%M:%S")  # 格式化日期时间
			topic_suffix = topic.replace("teslamate/cars/1/", "").ljust(29)
			# print(str(today) + " 处理————" + str(topic_suffix) + " : " + str(payload))
			formatted_message = str(today) + " " + str(topic_suffix) + " : " + str(payload)
			# print(formatted_message)
			
			#checkbox_status, input_value = get_checkbox_and_input_status(1)
			#print(f"复选框1状态: {checkbox_status}, 输入框1值: {input_value}")
			

			if topic == "teslamate/cars/1/display_name": pseudo = "🚗 "+str(payload)                 # do we change name often ?
			# if tittle == "": tittle = pseudo
			if topic == "teslamate/cars/1/model": model = "Model "+str(payload)                       # Model is very static...
			if topic == "teslamate/cars/1/update_version": update_version = str(payload)
			if topic == "teslamate/cars/1/odometer": 
				km = str(payload)   
				trip = float(payload)
				# print(trip)                             # Car is moving, don't bother the driver
			if topic == "teslamate/cars/1/latitude": latitude = float(payload)                          # Car is moving, don't bother the driver
			if topic == "teslamate/cars/1/longitude": longitude = float(payload)                        # Car is moving, don't bother the driver
			if topic == "teslamate/cars/1/usable_battery_level":  # Car is moving, don't bother the driver
				usable_battery_level = float(payload)  # 更新电池电量
				# 检测电量从30%及以上变为30%以下
				if previous_battery_level >= 30 and usable_battery_level < 30:
					tittle = "🆕电量低于30%"
					nouvelleinformation = True
					text_msg = f"警告：当前电池电量当前为 {usable_battery_level:.2f}%\n<br>"
				# 检测电量从20%及以上变为20%以下
				if previous_battery_level >= 20 and usable_battery_level < 20:
					tittle = "🆕电量低于20%"
					nouvelleinformation = True
					text_msg = f"警告：当前电池电量当前为 {usable_battery_level:.2f}%\n<br>"

			
			
			if topic == "teslamate/cars/1/ideal_battery_range_km": distance = float(payload)             # estimated range
			
			if topic == "teslamate/cars/1/rated_battery_range_km": rated = float(payload)

			if topic == "teslamate/cars/1/tpms_soft_warning_fl":
				tpms_soft_warning_fl = str(payload)  # True/False
			if topic == "teslamate/cars/1/tpms_soft_warning_fr":
				tpms_soft_warning_fr = str(payload)  # True/False
			if topic == "teslamate/cars/1/tpms_soft_warning_rl":
				tpms_soft_warning_rl = str(payload)  # True/False
			if topic == "teslamate/cars/1/tpms_soft_warning_rr":
				tpms_soft_warning_rr = str(payload)  # True/False
			if topic == "teslamate/cars/1/tpms_pressure_fl": 
				tpms_pressure_fl = str(payload)  # 解码消息
				if len(tpms_pressure_fl) == 3:  # 判断是否只有3位
					tpms_pressure_fl += "0"  # 补充一个0
				elif len(tpms_pressure_fl) > 4:  # 如果超过4位，截取前4位
					tpms_pressure_fl = tpms_pressure_fl[:4]
			if topic == "teslamate/cars/1/tpms_pressure_fr":	
				tpms_pressure_fr = str(payload)  # 解码消息
				if len(tpms_pressure_fr) == 3:  # 判断是否只有3位
					tpms_pressure_fr += "0"  # 补充一个0
				elif len(tpms_pressure_fr) > 4:  # 如果超过4位，截取前4位
					tpms_pressure_fr = tpms_pressure_fr[:4]
			if topic == "teslamate/cars/1/tpms_pressure_rl": 
				tpms_pressure_rl = str(payload)
				if len(tpms_pressure_rl) == 3:  # 判断是否只有3位
					tpms_pressure_rl += "0"  # 补充一个0
				elif len(tpms_pressure_rl) > 4:  # 如果超过4位，截取前4位
					tpms_pressure_rl = tpms_pressure_rl[:4]
			if topic == "teslamate/cars/1/tpms_pressure_rr": 
				tpms_pressure_rr = str(payload)
				if len(tpms_pressure_rr) == 3:  # 判断是否只有3位
					tpms_pressure_rr += "0"  # 补充一个0
				elif len(tpms_pressure_rr) > 4:  # 如果超过4位，截取前4位
					tpms_pressure_rr = tpms_pressure_rr[:4]	

			# 状态检测
			current_state = (
				tpms_soft_warning_fl == "true"
				or tpms_soft_warning_fr == "true"
				or tpms_soft_warning_rl == "true"
				or tpms_soft_warning_rr == "true"
			)
			max_push_count = get_checkbox_status_by_number(1)
			# print(max_push_count)
			if max_push_count is None:
				max_push_count = 3  # 默认推送次数上限为 3

			# 状态变化检测并更新计数器
			if current_state != tpms_last_state:
				if not current_state:  # 从至少一个为真变为全假
					tpms_push_count = 0  # 清零计数器
				tpms_last_state = current_state  # 更新状态

			# 推送逻辑
			if current_state:  # 当前状态为至少一个为真
				if tpms_push_count < max_push_count:  # 使用复选框3的值作为推送次数上限
					tpms_push_count += 1
					nouvelleinformation = True
					if nouvelleinformation:
						check_button_status(8)
					warning_details = []
					if tpms_soft_warning_fl == "true":
						warning_details.append("前左轮胎")
					if tpms_soft_warning_fr == "true":
						warning_details.append("前右轮胎")
					if tpms_soft_warning_rl == "true":
						warning_details.append("后左轮胎")
					if tpms_soft_warning_rr == "true":
						warning_details.append("后右轮胎")
					tittle = "‼️"+"、".join(warning_details) + " 胎压报警"
					print(f"推送次数: {tpms_push_count}")
				else:
					print("推送次数已达限制，不再推送")

			if (tpms_pressure_fl != "❔" and tpms_pressure_fr != "❔" and tpms_pressure_rl != "❔" and tpms_pressure_rr != "❔"):
				fl_icon = "🔴" if float(tpms_pressure_fl) < 2.3 else "🟠" if float(tpms_pressure_fl) <= 2.5 else "🟢"
				fr_icon = "🔴" if float(tpms_pressure_fr) < 2.3 else "🟠" if float(tpms_pressure_fr) <= 2.5 else "🟢"
				rl_icon = "🔴" if float(tpms_pressure_rl) < 2.3 else "🟠" if float(tpms_pressure_rl) <= 2.5 else "🟢"
				rr_icon = "🔴" if float(tpms_pressure_rr) < 2.3 else "🟠" if float(tpms_pressure_rr) <= 2.5 else "🟢"
			if tpms_soft_warning_fl == "true":
				fl_icon = "❌"
			if tpms_soft_warning_fr == "true":
				fr_icon = "❌"
			if tpms_soft_warning_rl == "true":
				rl_icon = "❌"
			if tpms_soft_warning_rr == "true":
				rr_icon = "❌"



			if topic == "teslamate/cars/1/outside_temp": outside_temp	= str(payload)	         # 车外温度
			if topic == "teslamate/cars/1/inside_temp": inside_temp =	str(payload)	# 车内温度
			if topic == "teslamate/cars/1/version": carversion =	str(payload)	# 系统版本
			if topic == "teslamate/cars/1/charger_voltage": charger_voltage =	str(payload)   # 充电电压
			if topic == "teslamate/cars/1/charger_power":
				current_power = float(payload)
				if current_power > max_charger_power:
					max_charger_power = current_power
			if topic == "teslamate/cars/1/charge_limit_soc": charge_limit_soc =	str(payload)   # 充电限制
			if topic == "teslamate/cars/1/time_to_full_charge": time_to_full_charge =	float(payload)   # 达限时间
			if topic == "teslamate/cars/1/is_user_present": present =	str(payload)   # 乘客

			if topic == "teslamate/cars/1/charging_state":              # interesting info but at initial startup it gives 1 message for state and 1 message for lock
				if str(payload) == "Charging":
					if charging_state_flag != "1":
						charging_state_flag = "1"
						nouvelleinformation = True
						tittle = "🆕开始充电"
						charging_start_time = now
						start_battery_level_charge = usable_battery_level
						start_range_charge = distance
						start_charge_energy_added = charge_energy_added  # 记录开始充电时已充入的电量
						max_charger_power = 0.0  # 重置最大功率

				elif topic == "teslamate/cars/1/charging_state" and str(payload) in ["Disconnected", "Stopped"]:
					if charging_state_flag == "1":
						charging_state_flag = "0"
						get_battery_health()
						charging_end_time = now
						end_battery_level_charge = usable_battery_level
						end_range_charge = distance
						total_charge_energy_added = charge_energy_added - start_charge_energy_added
						if max_charger_power == 4.0:
							max_charger_power = 3.5                           
						if charging_start_time and charging_end_time:
							charging_duration = charging_end_time - charging_start_time  # 充电时长
							charging_hours = charging_duration.total_seconds() / 3600   # 转换为小时
							battery_percent_increase = end_battery_level_charge - start_battery_level_charge  # 电量增加百分比
							range_increase = end_range_charge - start_range_charge  # 里程增加
							average_charging_power = charge_energy_added / charging_hours  # 平均充电功率
							charging_speed = range_increase / charging_hours  # 每小时增加的里程数

							# 重置充电相关变量
							charging_start_time = None
							charging_end_time = None
							start_battery_level_charge = None
							end_battery_level_charge = None
							start_range_charge = None
							end_range_charge = None
							charge_energy_added = 0.0
							tart_charge_energy_added = 0.0
							max_charger_power = 0.0
						

			if topic == "teslamate/cars/1/time_to_full_charge": 
				temps_restant_mqtt = float(payload)		
			if topic == "teslamate/cars/1/charge_energy_added":                                                # Collect infos but don't send a message NOW
				charge_energy_added = float(payload)

			# Please send me a message :
			# --------------------------
			if topic == "teslamate/cars/1/is_preconditioning":
				if str(payload) == "true": 
					nouvelleinformation = True
					tittle = "🆕开始温度调节"

			if topic == "teslamate/cars/1/heading":
				heading_angle = float(payload)  # 提取车头角度

					
			# 记录行程开始的时间、电池百分比、续航里程
			if topic == "teslamate/cars/1/is_user_present" and str(payload) == "true":
				if not trip_started: trip_started = True  # 设置标志，表示行程已开始
			if topic == "teslamate/cars/1/is_user_present" and str(payload) == "false":
				trip_started = False  # 重置标志，表示行程未开始

			# 更新行驶过程中的最高车速
			if topic == "teslamate/cars/1/speed":
				try:
					speed = float(payload)  # 从 MQTT 消息中提取 speed 数据
					if speed > max_speed:  # 仅在当前速度大于最高车速时更新
						max_speed = speed
				except ValueError:
					pass  # 如果解析速度失败，忽略

			# 其他现有逻辑保留不变
			if topic == "teslamate/cars/1/usable_battery_level":
				usable_battery_level = float(payload)  # 更新电池百分比



				
			if topic == "teslamate/cars/1/update_available":
				if str(payload) == "true":
					if ismaj != "true":
						ismaj = "true"
						nouvelleinformation = True
						tittle = "🆕有可用更新"
				else:
					ismaj = "false"
	
			if topic == "teslamate/cars/1/state":
				if str(payload) == "online":
					if etat_connu != str("📶 车辆在线"):
						etat_connu = str("📶 车辆在线")
						nouvelleinformation = True
						if nouvelleinformation: check_button_status(4)
						tittle = "🆕车辆上线"
				elif str(payload) == "asleep":
					if etat_connu != str("💤 正在休眠"):
						etat_connu = str("💤 正在休眠")
						nouvelleinformation = True
						if nouvelleinformation: check_button_status(3)
						tittle = "🆕车辆休眠"
						# charging_state_flag = "0"
				elif str(payload) == "suspended":
					if etat_connu != str("🛏️ 车辆挂起"):
						etat_connu = str("🛏️ 车辆挂起")
						nouvelleinformation = True
						if nouvelleinformation: check_button_status(3)
						tittle = "🆕车辆挂起"
						# charging_state_flag = "0"
				elif str(payload) == "charging":
					if etat_connu != str("🔌 正在充电"):
						etat_connu = str("🔌 正在充电")
				elif str(payload) == "offline":
					if etat_connu != str("🛰️ 车辆离线"):
						etat_connu = str("🛰️ 车辆离线")
						nouvelleinformation = True
						if nouvelleinformation: check_button_status(4)
						tittle = "🆕车辆离线"
				elif str(payload) == "start":
					if etat_connu != str("🚀 正在启动"):
						etat_connu = str("🚀 正在启动")
						nouvelleinformation = True
						if nouvelleinformation: check_button_status(3)
						tittle = "🆕车辆启动"
				elif str(payload) == "driving":
					if etat_connu != str("🏁 车辆行驶"):
						etat_connu = str("🏁 车辆行驶")
						nouvelleinformation = True	
						if nouvelleinformation: check_button_status(4)
						tittle = "🆕车辆行驶"		
					etat_connu = str("🏁 车辆行驶")
				else:
					etat_connu = str("⭕ 未知状态")  # do not send messages as we don't know what to say, keep quiet and move on... :)

			if topic == "teslamate/cars/1/locked":              # interesting info but at initial startup it gives 1 message for state and 1 message for lock
				if locked != str(payload):                           # We should add a one time pointer to avoid this (golobal)
					locked = str(payload)
					if str(locked) == "true": 
						text_locked = "🔒 已锁定"
						tittle = "🆕已锁定"
						nouvelleinformation = True
					if str(locked) == "false": 
						text_locked = "🔑 已解锁"
						tittle = "🆕已解锁"
						nouvelleinformation = True

				
			if topic == "teslamate/cars/1/sentry_mode":      # 哨兵
				if str(payload) == "true": 
					text_sentry_mode = "🔴哨兵开启"
					tittle = "🆕哨兵开启"
					nouvelleinformation = True	
					if nouvelleinformation: check_button_status(9)
				elif str(payload) == "false": 
					text_sentry_mode = "⚪哨兵关闭"
					tittle = "🆕哨兵关闭"
					nouvelleinformation = True
					if nouvelleinformation: check_button_status(9)

						
			if topic == "teslamate/cars/1/doors_open":
				if str(payload) == "false": 
					doors_state = "✅ 车门已关闭"
					nouvelleinformation = True
					if nouvelleinformation: check_button_status(2)	
					tittle = "🆕关门"
				elif str(payload) == "true":
					doors_state = "❌ 车门已开启"
					nouvelleinformation = True	
					if nouvelleinformation: check_button_status(2)
					tittle = "🆕开门"

			if topic == "teslamate/cars/1/trunk_open":
				if str(payload) == "false": 
					trunk_state = "✅ 后备箱已关闭"+"\u00A0"*8
					nouvelleinformation = True
					if nouvelleinformation: check_button_status(2)	
					tittle = "🆕关后备箱"
				elif str(payload) == "true": 
					trunk_state = "❌ 后备箱已开启"+"\u00A0"*8
					nouvelleinformation = True	
					if nouvelleinformation: check_button_status(2)
					tittle = "🆕开后备箱"
			if topic == "teslamate/cars/1/frunk_open":
				if str(payload) == "false": 
					frunk_state = "✅ 前备箱已关闭"
					nouvelleinformation = True	
					if nouvelleinformation: check_button_status(2)
					tittle = "🆕关前备箱"
				elif str(payload) == "true": 
					frunk_state = "❌ 前备箱已开启"
					if nouvelleinformation: check_button_status(2)
					nouvelleinformation = True	
					tittle = "🆕开前备箱"

			if topic == "teslamate/cars/1/windows_open":	
				if str(payload) == "false": windows_state = "✅ 车窗已关闭"
				elif str(payload) == "true": windows_state = "❌️ 车窗已开启"

			if True:
			#if nouvelleinformation == True:
				# Do we have enough informations to send a complete message ?
				# if pseudo != "❔" and model != "❔" and etat_connu != "❔" and locked != "❔" and usable_battery_level != "❔" and latitude != "❔" and longitude != "❔" and distance > 0:
				if distance > 0:
					text_msg = text_msg+pseudo+" ("+model+") "
					if ismaj == "true":
						text_msg = text_msg+"(有更新"+update_version+")"+"\n"+"<br>"
					else:
						text_msg = text_msg+"\n"+"<br>"
						
				
					text_msg = text_msg+"🔋 "+str(usable_battery_level)+" %"+"\u00A0"*4
					if distance > 0 : text_msg = text_msg+"\u00A0"*3+"🏁 "+str(math.floor(distance))+" Km"+"\u00A0"*2
					text_msg = text_msg+"\u00A0"*4+"🌍"+str(km)+" km"+"\n"+"<br>"+text_locked+"\u00A0"*5+etat_connu+"\u00A0"*6+text_sentry_mode+"\n"+"<br>"
					if charging_state_flag == "1": 
					
						tittle3 = "🆕充电中"
						get_battery_health()
						text_msg2 += "当前电量: {} %  已充入电量: {:.2f} kWh<br>".format(usable_battery_level, charge_energy_added - start_charge_energy_added)
						
						if charging_start_time:
							charging_duration = now - charging_start_time
							hours = charging_duration.seconds // 3600
							minutes = (charging_duration.seconds % 3600) // 60
							text_msg2 += f"充电时间：{hours:02}:{minutes:02}  "
							
						if time_to_full_charge == 0:
							text_msg2 += "剩余时间: 获取中" + "\n" + "<br>"
						else:
							try:
								time_to_full_charge = float(time_to_full_charge)  # 确保是浮点类型
								hours = int(time_to_full_charge)  # 整除得到小时数
								minutes = int((time_to_full_charge - hours) * 60)  # 取余数得到分钟数
								text_msg2 += f"剩余时间: {hours:02}:{minutes:02}<br>"
							except ValueError:
								text_msg2 += "剩余时间: 数据格式错误" + "\n" + "<br>"

						if conn_charge_cable_value == 'GB_DC':
							text_msg2 += "充电方式：直流"
						elif conn_charge_cable_value == 'GB_AC':
							text_msg2 += "充电方式：交流"
						if battery_heater_value:
							text_msg2 += "，电池加热：开启<br>"
						else:
							text_msg2 += "，电池加热：未开启<br>"
						# conn_charge_cable_value   battery_heater_value	
						text_msg2 = text_msg2+"充电电压:"+charger_voltage+"V"+"\u00A0"*4+"充电功率:"+str(current_power)+"KW"+"\n"+"<br>"+"充电设定:"+charge_limit_soc+"%"

						if charge_limit_soc != "❔":
							text_msg2 = text_msg2 + "(" + "{:.2f}".format((math.floor(float(charge_limit_soc)) * float(current_range)) / 100) + "Km) "					
						text_msg2 = text_msg2 + "满电:" + "{:.2f}".format(float(current_range)) + "Km<br>"
						text_msg2 = text_msg2 + bet2 + bet4 + "（出厂："+ bet1 + bet3 + ")" + "<br>" + bet5
						


					# 组装胎压信息内容
					text_msg = text_msg + fl_icon + " 左前胎压: " + tpms_pressure_fl+"\u00A0"*4
					text_msg = text_msg + fr_icon + " 右前胎压: " + tpms_pressure_fr + "\n" + "<br>"
					text_msg = text_msg + rl_icon + " 左后胎压: " + tpms_pressure_rl+"\u00A0"*4
					text_msg = text_msg + rr_icon + " 右后胎压: " + tpms_pressure_rr + "\n" + "<br>"
			

			
					# Do we have some special infos to add to the standard message ?
					if doors_state != "❔": text_msg = text_msg+doors_state+"\u00A0"*12
					if windows_state != "❔": text_msg = text_msg+windows_state+crlf
					if trunk_state != "❔": text_msg = text_msg+trunk_state
					if frunk_state != "❔": text_msg = text_msg+frunk_state+crlf
					text_msg = text_msg+"🌡车内温度:"+inside_temp+"\u00A0"*8+"🌡车外温度:"+outside_temp+"\n"+"<br>"
				
				

					# 时间戳
					text_msg = text_msg+"⚙️车机系统:"+carversion+"\u00A0"*4+"🕗"+str(today)+"<br>"
					if start0 == 0:tittle = "🆕"+"\u00A0"*2+"开始监控"
					tittle = tittle+"\u00A0"*4+str(today)
				
					tittle2 = "🏁"+str(math.floor(distance))+" Km"+text_locked+text_sentry_mode+doors_state+windows_state+trunk_state+frunk_state

					GPS = generate_baidu_map_url(latitude,longitude)
					if nouvelleinformation == True:
						check_button_status(1)
					if nouvelleinformation and etat_connu == "🏁 车辆行驶":
						check_button_status(5)
					if nouvelleinformation and present == "true":
						check_button_status(6)
					if nouvelleinformation and charging_state_flag:
						check_button_status(7)
																		
						if nouvelleinformation == True:
							print (tittle)
							# print("推送内容组装完成 " + crlf + tirets +crlf +str(text_msg) + crlf + tirets + crlf)
					
							if text_msg2 is not None and text_msg2 != "":  # 如果 text_msg2 不为空（有行程结算数据）
								send_email3(tittle, text_msg2, text_msg, os.getenv('EMAIL_ADDRESS'))
								# print(text_msg2)
								print("结算邮件发送成功")
						
							else:  # 没有行程结算数据，发送常规邮件
								# tittle3 = "电池数据"
								# text_msg = text_msg+bet1+bet2+bet3+bet4+bet5
						
								# print(text_msg2)
								send_email2(tittle, text_msg, os.getenv('EMAIL_ADDRESS'))
								print("常规邮件发送成功")
						else:
							print("根据用户设定，推送取消")


					# 重置状态信息
					text_msg = ""
					text_msg2 = ""
					nouvelleinformation = False  # 重置状态信息
					del temps_restant_charge     #
					temps_restant_charge = "❔" 
					start0 = 1
					
		except Exception as e:
			print(f"队列消息处理失败：{e}")
			text_msg = ""
			text_msg2 = ""
			nouvelleinformation = False  # 重置状态信息

client = mqtt.Client()
client.enable_logger()
client.on_connect = on_connect
client.on_message = on_message
threading.Thread(target=process_message_queue, daemon=True).start()   
client.connect(os.getenv('MQTT_BROKER_HOST'),int(os.getenv('MQTT_BROKER_PORT', 1883)), 60)
client.loop_start()  # start the loop
try:
	while True:
		time.sleep(1)
except:
        extype, value, tb = sys.exc_info()
        traceback.print_exc()
        # pdb.post_mortem(tb)
client.disconnect()
client.loop_stop()
