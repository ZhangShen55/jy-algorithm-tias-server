# app/services/ias_client.py
# 用于智能app向IAS服务注册，注销和保活
import json
import os
import requests
import logging
import threading
from datetime import datetime
from ..core.settings import settings

logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.DEBUG)

# logging.
class IASClient:
    """IAS服务客户端"""
    def __init__(self, ias_base_url=None):
        """
        初始化IAS客户端
        """
        self.ias_base_url = ias_base_url or os.environ.get("SERVER")
        self.aem_config = settings.AEM.dict() if hasattr(settings, 'AEM') else {}
        self.keepalive_thread = None
        self.stop_keepalive = threading.Event()


    def register(self):
        """向IAS服务注册"""
        if not self.aem_config:
            logger.error("AEM配置为空，无法注册服务")
            return False

        if not self.ias_base_url:
            logger.error("IAS服务URL未设置，无法注册服务")
            return False

        register_data = {
            "Register": {
                "AppName": self.aem_config.get("AppName"),
                "InstanceId": self.aem_config.get("InstanceId"),
                "IpAddr": self.aem_config.get("IpAddr"),
                "Port": self.aem_config.get("Port"),
                "MetaData": self.aem_config.get("MetaData", {})
            }
        }

        try:
            url = f"{self.ias_base_url}/AEM/Register"
            logger.info(f"发送注册请求到: {url}")
            logger.debug(f"注册数据: {json.dumps(register_data)}")

            response = requests.post(url, json=register_data, timeout=10)
            if response.status_code == 200:
                resp_data = response.json()
                status_code = resp_data.get("ResponseStatusObject", {}).get("StatusCode")
                print("注册状态码:",status_code)
                if status_code == 2000:
                    logger.info("服务注册成功")
                    # 记录注册时间
                    from ..services.capacity_service import set_register_time
                    set_register_time()
                    return True
                else:
                    status_string = resp_data.get("ResponseStatusObject", {}).get("StatusString", "未知错误")
                    logger.error(f"服务注册失败: {status_string}")
            else:
                logger.error(f"服务注册请求失败，状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"发送注册请求时发生错误: {str(e)}")

        return False

    def unregister(self):
        """向IAS服务注销"""
        if not self.aem_config:
            logger.error("AEM配置为空，无法注销服务")
            return False

        if not self.ias_base_url:
            logger.error("IAS服务URL未设置，无法注销服务")
            return False

        unregister_data = {
            "UnRegister": {
                "AppName": self.aem_config.get("AppName"),
                "InstanceId": self.aem_config.get("InstanceId")
            }
        }

        try:
            url = f"{self.ias_base_url}/AEM/UnRegister"
            logger.info(f"发送注销请求到: {url}")
            logger.debug(f"注销数据: {json.dumps(unregister_data)}")

            response = requests.post(url, json=unregister_data, timeout=10)
            if response.status_code == 200:
                resp_data = response.json()
                status_code = resp_data.get("ResponseStatusObject", {}).get("StatusCode")
                print("注销状态码:",status_code)
                if status_code == 1000:
                    logger.info("服务注销成功")
                    return True
                else:
                    status_string = resp_data.get("ResponseStatusObject", {}).get("StatusString", "未知错误")
                    logger.error(f"服务注销失败: {status_string}")
            else:
                logger.error(f"服务注销请求失败，状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"发送注销请求时发生错误: {str(e)}")

        return False

    def keepalive(self):
        """向IAS服务发送保活请求"""
        if not self.aem_config:
            logger.error("AEM配置为空，无法发送保活请求")
            return False

        if not self.ias_base_url:
            logger.error("IAS服务URL未设置，无法发送保活请求")
            return False

        keepalive_data = {
            "Keepalive": {
                "AppName": self.aem_config.get("AppName"),
                "InstanceId": self.aem_config.get("InstanceId")
            }
        }

        try:
            url = f"{self.ias_base_url}/AEM/Keepalive"
            # logger.debug(f"发送保活请求到: {url}")
            # logger.debug(f"保活数据: {json.dumps(keepalive_data)}")

            response = requests.post(url, json=keepalive_data, timeout=10)
            if response.status_code == 200:
                resp_data = response.json()
                status_code = resp_data.get("ResponseStatusObject", {}).get("StatusCode")
                # print("保活状态码:",status_code)
                if status_code == 1000:
                    # logger.debug(f"保活请求成功，时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    return True
                else:
                    status_string = resp_data.get("ResponseStatusObject", {}).get("StatusString", "未知错误")
                    logger.error(f"保活请求失败: {status_string}")
            else:
                logger.error(f"保活请求失败，状态码: {response.status_code}")
        except Exception as e:
            logger.error(f"发送保活请求时发生错误: {str(e)}")

        return False
    
    def _keepalive_thread_func(self):
        """保活线程函数"""
        interval = self.aem_config.get("KeepaliveInterval", 40)  # 默认60秒
        logger.info(f"启动保活线程，间隔: {interval}秒一次")

        while not self.stop_keepalive.is_set():
            self.keepalive()
            self.stop_keepalive.wait(timeout=interval)

    def start_keepalive_thread(self):
        """启动保活线程"""
        if self.keepalive_thread and self.keepalive_thread.is_alive():
            logger.warning("保活线程已经在运行")
            return

        self.stop_keepalive.clear()
        self.keepalive_thread = threading.Thread(
            target=self._keepalive_thread_func,
            daemon=True,
            name="IAS-Keepalive"
        )
        self.keepalive_thread.start()
        logger.info("保活线程已启动")
    
    def stop_keepalive_thread(self):
        """停止保活线程"""
        if not self.keepalive_thread or not self.keepalive_thread.is_alive():
            logger.warning("保活线程未运行")
            return
        
        logger.info("正在停止保活线程...")
        self.stop_keepalive.set()
        self.keepalive_thread.join(timeout=5)
        if self.keepalive_thread.is_alive():
            logger.warning("保活线程未能在5秒内停止")
        else:
            logger.info("保活线程已停止")

# 创建一个全局的IAS客户端实例
ias_client = None

def init_ias_client(ias_base_url=None):
    """初始化IAS客户端"""
    global ias_client
    ias_client = IASClient(ias_base_url)
    return ias_client

def get_ias_client():
    """获取IAS客户端实例"""
    global ias_client
    if ias_client is None:
        ias_client = init_ias_client()
    return ias_client

