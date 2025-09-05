"""
比特浏览器官方API封装
基于官方文档实现的API接口
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any
try:
    from .log_manager import get_logger
    from .proxy_manager import ProxyManager
    from .pdd_account_manager import PDDAccountManager
except ImportError:
    from log_manager import get_logger
    # 🔥 删除代理功能：不再需要代理管理器
# from proxy_manager import ProxyManager



class BitBrowserAPI:
    """比特浏览器API管理器"""
    
    def __init__(self, api_token: str = None, base_url: str = None):
        """
        初始化API管理器

        Args:
            api_token: API Token (比特浏览器本地API不需要Token)
            base_url: 比特浏览器本地服务地址，如果为None则从配置文件获取
        """
        self.api_token = api_token
        
        # 如果没有提供base_url，从配置文件获取
        if base_url is None:
            base_url = self._get_base_url_from_config()
        
        self.base_url = base_url
        self.session = requests.Session()
        self.logger = get_logger()
        # 🔥 删除代理功能：不再需要代理管理器
        # self.proxy_manager = ProxyManager()  # 初始化代理管理器

        # 设置请求头 - 比特浏览器使用x-api-key认证
        self.session.headers.update({
            'Content-Type': 'application/json',
            'x-api-key': api_token if api_token else ''
        })
    
    def _get_base_url_from_config(self) -> str:
        """从配置文件获取base_url"""
        try:
            import os
            import json
            
            # 尝试从当前目录的config_api.json获取
            config_file = os.path.join(os.path.dirname(__file__), "config_api.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    debug_port = config.get('browser_info', {}).get('debug_port')
                    if debug_port:
                        return f"http://127.0.0.1:{debug_port}"
            
            # 如果配置文件不存在或没有端口号，使用默认端口
            return "http://127.0.0.1:54345"
        except Exception as e:
            self.logger.warning(f"无法从配置文件获取端口号: {e}，使用默认端口")
            return "http://127.0.0.1:54345"
    
    def test_connection(self) -> bool:
        """测试连接"""
        try:
            # 使用浏览器列表API来测试连接
            data = {"page": 0, "pageSize": 1}
            response = self.session.post(f"{self.base_url}/browser/list", json=data)
            if response.status_code == 200:
                result = response.json()
                return result.get('success', False)
            return False
        except Exception as e:
            self.logger.error(f"连接测试失败: {e}")
            return False
    
    def create_browser(self, name: str, **kwargs) -> Optional[str]:
        """
        创建浏览器实例
        
        Args:
            name: 浏览器名称
            **kwargs: 其他配置参数
            
        Returns:
            浏览器ID或None
        """
        try:
            # 生成随机硬件配置
            import random

            # 随机硬件并发数 (4-16核)
            random_cores = random.choice([4, 6, 8, 12, 16])

            # 随机设备内存 (4-8GB)
            random_memory = random.choice([4, 6, 8])

            # 基本配置 - 使用自定义平台和随机指纹
            config = {
                'platform': '',  # 自定义平台
                'platformIcon': 'other',  # 自定义平台图标
                'url': 'https://mobile.pinduoduo.com',  # 默认打开拼多多
                'name': name,
                'remark': '',  # 不设置备注
                'userName': '',
                'password': '',
                'cookie': '',
                'syncTabs': True,
                'syncCookies': True,
                'syncIndexedDb': False,
                'syncLocalStorage': False,
                'syncBookmarks': True,
                'credentialsEnableService': False,
                'syncHistory': False,
                'clearCacheFilesBeforeLaunch': False,
                'clearCookiesBeforeLaunch': False,
                'clearHistoriesBeforeLaunch': False,
                'randomFingerprint': False,  # 关闭一键随机指纹，使用自定义指纹
                'workbench': 'disable',  # 不显示工作台
                'disableGpu': False,
                'enableBackgroundMode': False,
                'allowedSignin': False,
                'abortImage': False,
                'abortMedia': False,
                'muteAudio': False,
                'stopWhileNetError': False,
                'browserFingerPrint': {
                    'coreVersion': '104',
                    'ostype': 'PC',
                    'os': 'Win32',
                    'version': '',
                    'userAgent': '',
                    'isIpCreateTimeZone': True,
                    'timeZone': '',
                    'timeZoneOffset': 0,
                    'webRTC': '0',
                    'ignoreHttpsErrors': False,
                    'position': '1',
                    'isIpCreatePosition': True,
                    'lat': '',
                    'lng': '',
                    'precisionData': '',
                    'isIpCreateLanguage': True,
                    'languages': '',
                    'isIpCreateDisplayLanguage': False,
                    'displayLanguages': '',
                    'openWidth': 350,  # 🔥 修改：窗口宽度350
                    'openHeight': 880,  # 🔥 修改：窗口高度880
                    'resolutionType': '0',  # 🔥 修改：跟随电脑分辨率
                    'resolution': '',  # 🔥 修改：跟随电脑分辨率
                    'windowSizeLimit': True,  # 🔥 保持：约束窗口尺寸不超过分辨率
                    'devicePixelRatio': 1,
                    'fontType': '2',
                    'font': '',
                    'canvas': '0',
                    'canvasValue': None,
                    'webGL': '0',
                    'webGLValue': None,
                    'webGLMeta': '0',
                    'webGLManufacturer': '',
                    'webGLRender': '',
                    'audioContext': '0',
                    'audioContextValue': None,
                    'mediaDevice': '0',
                    'mediaDeviceValue': None,
                    'speechVoices': '0',
                    'speechVoicesValue': None,
                    'hardwareConcurrency': str(random_cores),
                    'deviceMemory': str(random_memory),
                    'doNotTrack': '0',
                    'clientRectNoiseEnabled': True,
                    'clientRectNoiseValue': 0,
                    'portScanProtect': '0',
                    'portWhiteList': '',
                    'deviceInfoEnabled': True,
                    'computerName': '',
                    'macAddr': '',
                    'disableSslCipherSuitesFlag': False,
                    'disableSslCipherSuites': None,
                    'enablePlugins': False,
                    'plugins': ''
                }
            }

            # 🔥 删除代理功能：使用固定的"不使用代理"配置
            config.update({
                'proxyMethod': 2,  # 自定义代理
                'proxyType': 'noproxy',
                'host': '',
                'port': 0,
                'proxyUserName': '',
                'proxyPassword': ''
            })

            self.logger.info(f"创建实例 {name} - 不使用代理")

            # 更新配置
            config.update(kwargs)
            
            response = self.session.post(f"{self.base_url}/browser/update", json=config)

            # 🔥 添加调试信息
            self.logger.info(f"API请求状态码: {response.status_code}")
            self.logger.info(f"API响应内容: {response.text[:200]}...")

            result = response.json()
            
            if result.get('success'):
                browser_id = result.get('data', {}).get('id')
                self.logger.info(f"创建浏览器成功: {name}, ID: {browser_id}")
                return browser_id
            else:
                error_msg = result.get('msg', '未知错误')
                self.logger.error(f"创建浏览器失败: {error_msg}")
                # 🔥 添加详细的错误信息用于调试
                self.logger.error(f"完整响应: {result}")
                return None
                
        except Exception as e:
            self.logger.error(f"创建浏览器异常: {e}")
            return None
    
    def open_browser(self, browser_id: str, **kwargs) -> Optional[Dict]:
        """
        打开浏览器实例
        
        Args:
            browser_id: 浏览器ID
            **kwargs: 其他参数
            
        Returns:
            连接信息或None
        """
        try:
            config = {'id': browser_id}
            config.update(kwargs)
            
            response = self.session.post(f"{self.base_url}/browser/open", json=config)
            result = response.json()
            
            if result.get('success'):
                data = result.get('data', {})
                self.logger.info(f"打开浏览器成功: {browser_id}, 调试端口: {data.get('http')}")
                return data
            else:
                error_msg = result.get('msg', '未知错误')
                self.logger.error(f"打开浏览器失败: {error_msg}")
                # 🔥 添加更详细的错误信息用于调试
                self.logger.error(f"完整响应: {result}")
                return None
                
        except Exception as e:
            self.logger.error(f"打开浏览器异常: {e}")
            return None
    
    def close_browser(self, browser_id: str) -> bool:
        """关闭浏览器实例"""
        try:
            config = {'id': browser_id}
            response = self.session.post(f"{self.base_url}/browser/close", json=config)
            result = response.json()
            
            if result.get('success'):
                self.logger.info(f"关闭浏览器成功: {browser_id}")
                return True
            else:
                self.logger.error(f"关闭浏览器失败: {result.get('msg', '未知错误')}")
                return False
                
        except Exception as e:
            self.logger.error(f"关闭浏览器异常: {e}")
            return False
    
    def delete_browser(self, browser_id: str) -> bool:
        """删除浏览器实例"""
        try:
            config = {'id': browser_id}
            response = self.session.post(f"{self.base_url}/browser/delete", json=config)
            result = response.json()
            
            if result.get('success'):
                self.logger.info(f"删除浏览器成功: {browser_id}")
                return True
            else:
                self.logger.error(f"删除浏览器失败: {result.get('msg', '未知错误')}")
                return False
                
        except Exception as e:
            self.logger.error(f"删除浏览器异常: {e}")
            return False
    
    def get_browser_list(self, page: int = 0, page_size: int = 100, **kwargs) -> List[Dict]:
        """
        获取浏览器列表
        
        Args:
            page: 页码，从0开始
            page_size: 每页数量，最大100
            **kwargs: 其他筛选参数
            
        Returns:
            浏览器列表
        """
        try:
            config = {
                'page': page,
                'pageSize': min(page_size, 100)
            }
            config.update(kwargs)
            
            response = self.session.post(f"{self.base_url}/browser/list", json=config)
            result = response.json()
            
            if result.get('success'):
                data = result.get('data', {})
                browsers = data.get('list', [])
                self.logger.info(f"获取浏览器列表成功: {len(browsers)} 个")
                return browsers
            else:
                self.logger.error(f"获取浏览器列表失败: {result.get('msg', '未知错误')}")
                return []
                
        except Exception as e:
            self.logger.error(f"获取浏览器列表异常: {e}")
            return []
    
    def get_browser_detail(self, browser_id: str) -> Optional[Dict]:
        """获取浏览器详情"""
        try:
            # 🔥 添加API调用间隔控制
            import time
            if not hasattr(self, '_last_api_call'):
                self._last_api_call = 0

            current_time = time.time()
            if current_time - self._last_api_call < 0.3:  # 最小间隔300ms
                time.sleep(0.3 - (current_time - self._last_api_call))

            config = {'id': browser_id}
            response = self.session.post(f"{self.base_url}/browser/detail", json=config)
            self._last_api_call = time.time()
            result = response.json()
            
            if result.get('success'):
                return result.get('data')
            else:
                self.logger.error(f"获取浏览器详情失败: {result.get('msg', '未知错误')}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取浏览器详情异常: {e}")
            return None
    
    def get_browser_pids(self, browser_ids: List[str]) -> Dict[str, int]:
        """获取浏览器进程ID"""
        try:
            config = {'ids': browser_ids}
            response = self.session.post(f"{self.base_url}/browser/pids", json=config)
            result = response.json()
            
            if result.get('success'):
                return result.get('data', {})
            else:
                self.logger.error(f"获取浏览器进程ID失败: {result.get('msg', '未知错误')}")
                return {}
                
        except Exception as e:
            self.logger.error(f"获取浏览器进程ID异常: {e}")
            return {}

    def update_browser_name(self, browser_id: str, new_name: str, browser_config: Dict) -> bool:
        """
        更新浏览器名称

        Args:
            browser_id: 浏览器ID
            new_name: 新名称
            browser_config: 完整的浏览器配置

        Returns:
            是否成功
        """
        try:
            # 首先获取浏览器详细信息，包含browserFingerPrint
            detail = self.get_browser_detail(browser_id)
            if not detail:
                self.logger.error("无法获取浏览器详细信息")
                return False

            # 使用详细信息更新名称
            detail['name'] = new_name

            response = self.session.post(f"{self.base_url}/browser/update", json=detail)
            result = response.json()

            if result.get('success'):
                self.logger.info(f"更新浏览器名称成功: {new_name}")
                return True
            else:
                self.logger.error(f"更新浏览器名称失败: {result.get('msg', '未知错误')}")
                return False

        except Exception as e:
            self.logger.error(f"更新浏览器名称异常: {e}")
            return False













    def get_browser_id_by_name(self, browser_name: str) -> Optional[str]:
        """根据浏览器名称获取ID"""
        try:
            browsers = self.get_browser_list()
            for browser in browsers:
                if browser.get('name') == browser_name:
                    return browser.get('id')
            return None
        except Exception as e:
            self.logger.error(f"根据名称获取浏览器ID失败: {e}")
            return None

    def get_all_browsers(self) -> List[Dict]:
        """获取所有浏览器列表（包括屏幕外的）"""
        try:
            # 获取所有浏览器，不分页
            data = {"page": 0, "pageSize": 1000}  # 设置足够大的页面大小
            response = self.session.post(f"{self.base_url}/browser/list", json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    browsers = result.get('data', {}).get('list', [])
                    self.logger.info(f"✅ 获取所有浏览器成功: {len(browsers)} 个")
                    return browsers
                else:
                    self.logger.error(f"❌ 获取浏览器列表失败: {result.get('msg', '未知错误')}")
                    return []
            else:
                self.logger.error(f"❌ 获取浏览器列表API请求失败: {response.status_code}")
                return []
                
        except Exception as e:
            self.logger.error(f"❌ 获取所有浏览器异常: {e}")
            return []

    def open_browser_by_id(self, browser_id: str) -> bool:
        """通过ID直接打开浏览器"""
        try:
            data = {"id": browser_id}
            response = self.session.post(f"{self.base_url}/browser/open", json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✅ 浏览器打开成功: {browser_id}")
                    return True
                else:
                    self.logger.error(f"❌ 打开浏览器失败: {result.get('msg', '未知错误')}")
                    return False
            else:
                self.logger.error(f"❌ 打开浏览器API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 打开浏览器异常: {e}")
            return False

    def close_browser_by_id(self, browser_id: str) -> bool:
        """通过ID直接关闭浏览器"""
        try:
            data = {"id": browser_id}
            response = self.session.post(f"{self.base_url}/browser/close", json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✅ 浏览器关闭成功: {browser_id}")
                    return True
                else:
                    self.logger.error(f"❌ 关闭浏览器失败: {result.get('msg', '未知错误')}")
                    return False
            else:
                self.logger.error(f"❌ 关闭浏览器API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 关闭浏览器异常: {e}")
            return False

    def get_browser_status(self, browser_id: str) -> Optional[str]:
        """获取浏览器状态"""
        try:
            browsers = self.get_all_browsers()
            for browser in browsers:
                if browser.get('id') == browser_id:
                    return browser.get('takeover', 'unknown')
            return None
        except Exception as e:
            self.logger.error(f"❌ 获取浏览器状态异常: {e}")
            return None

    def open_all_browsers(self) -> Dict[str, bool]:
        """批量打开所有浏览器"""
        try:
            browsers = self.get_all_browsers()
            if not browsers:
                self.logger.warning("没有找到浏览器实例")
                return {}

            open_results = {}
            success_count = 0

            for i, browser in enumerate(browsers):
                browser_id = browser.get('id')
                browser_name = browser.get('name', 'Unknown')

                if browser_id:
                    # 添加延时控制API频率
                    if i > 0:
                        time.sleep(0.5)

                    self.logger.info(f"正在打开浏览器: {browser_name}")
                    success = self.open_browser_by_id(browser_id)
                    open_results[browser_name] = success

                    if success:
                        success_count += 1
                        self.logger.info(f"✅ 浏览器打开成功: {browser_name}")
                    else:
                        self.logger.warning(f"❌ 浏览器打开失败: {browser_name}")

            self.logger.info(f"批量打开浏览器完成: 成功 {success_count}/{len(browsers)} 个")
            return open_results

        except Exception as e:
            self.logger.error(f"批量打开浏览器异常: {e}")
            return {}

    def close_all_browsers(self) -> Dict[str, bool]:
        """批量关闭所有浏览器"""
        try:
            browsers = self.get_all_browsers()
            if not browsers:
                self.logger.warning("没有找到浏览器实例")
                return {}

            close_results = {}
            success_count = 0

            for i, browser in enumerate(browsers):
                browser_id = browser.get('id')
                browser_name = browser.get('name', 'Unknown')

                if browser_id:
                    # 添加延时控制API频率
                    if i > 0:
                        time.sleep(0.5)

                    self.logger.info(f"正在关闭浏览器: {browser_name}")
                    success = self.close_browser_by_id(browser_id)
                    close_results[browser_name] = success

                    if success:
                        success_count += 1
                        self.logger.info(f"✅ 浏览器关闭成功: {browser_name}")
                    else:
                        self.logger.warning(f"❌ 浏览器关闭失败: {browser_name}")

            self.logger.info(f"批量关闭浏览器完成: 成功 {success_count}/{len(browsers)} 个")
            return close_results

        except Exception as e:
            self.logger.error(f"批量关闭浏览器异常: {e}")
            return {}

    def hide_browser(self, browser_id: str) -> bool:
        """隐藏浏览器窗口 - 将窗口移到屏幕外"""
        try:
            # 直接移动到屏幕外，简化配置
            hide_config = {
                "startX": -2000,  # 负值，将窗口移到屏幕左侧外（更远）
                "startY": -2000   # 负值，将窗口移到屏幕上方外（更远）
            }
            
            # 设置超时时间，避免无限等待
            response = self.session.post(f"{self.base_url}/windowbounds", json=hide_config, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✅ 浏览器隐藏成功: {browser_id}")
                    return True
                else:
                    error_msg = result.get('msg', '未知错误')
                    self.logger.error(f"❌ 隐藏浏览器失败: {error_msg}")
                    return False
            else:
                self.logger.error(f"❌ 隐藏浏览器API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 隐藏浏览器异常: {e}")
            return False

    def show_browser(self, browser_id: str) -> bool:
        """显示浏览器窗口 - 将窗口移回屏幕内"""
        try:
            # 使用宫格排列方法，将所有浏览器移动到可见区域
            show_config = {
                'type': 'box',          # 宫格排列
                'startX': 50,           # 起始X位置（屏幕左侧可见区域）
                'startY': 50,           # 起始Y位置（屏幕顶部可见区域）
                'width': 350,           # 窗口宽度（与创建实例一致）
                'height': 880,          # 窗口高度（与创建实例一致）
                'col': 10,              # 每行10个浏览器
                'spaceX': 10,           # 横向间距10像素（紧凑排列）
                'spaceY': 20            # 纵向间距20像素
            }
            
            # 设置超时时间，避免无限等待
            response = self.session.post(f"{self.base_url}/windowbounds", json=show_config, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✅ 浏览器显示成功: {browser_id}")
                    return True
                else:
                    error_msg = result.get('msg', '未知错误')
                    self.logger.error(f"❌ 显示浏览器失败: {error_msg}")
                    return False
            else:
                self.logger.error(f"❌ 显示浏览器API请求失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ 显示浏览器异常: {e}")
            return False

    def hide_all_browsers(self) -> Dict[str, bool]:
        """隐藏所有浏览器窗口 - 使用批量操作减少API调用"""
        try:
            browsers = self.get_browser_list()
            if not browsers:
                self.logger.warning("没有找到浏览器实例")
                return {}

            # 🔥 优化：使用批量操作，只调用一次API
            browser_ids = [browser.get('id') for browser in browsers if browser.get('id')]
            if not browser_ids:
                self.logger.warning("没有有效的浏览器ID")
                return {}

            # 使用批量隐藏配置
            hide_config = {
                "startX": -2000,  # 负值，将窗口移到屏幕左侧外（更远）
                "startY": -2000,  # 负值，将窗口移到屏幕上方外（更远）
                "ids": browser_ids  # 批量处理所有浏览器
            }
            
            # 设置超时时间，避免无限等待
            response = self.session.post(f"{self.base_url}/windowbounds", json=hide_config, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✅ 批量隐藏浏览器成功: {len(browser_ids)} 个")
                    # 返回成功结果
                    return {browser.get('name', 'Unknown'): True for browser in browsers if browser.get('id')}
                else:
                    error_msg = result.get('msg', '未知错误')
                    self.logger.error(f"❌ 批量隐藏浏览器失败: {error_msg}")
                    return {browser.get('name', 'Unknown'): False for browser in browsers if browser.get('id')}
            else:
                self.logger.error(f"❌ 批量隐藏浏览器API请求失败: {response.status_code}")
                return {browser.get('name', 'Unknown'): False for browser in browsers if browser.get('id')}

        except Exception as e:
            self.logger.error(f"批量隐藏浏览器异常: {e}")
            return {}

    def show_all_browsers(self) -> Dict[str, bool]:
        """显示所有浏览器窗口 - 使用批量操作减少API调用"""
        try:
            browsers = self.get_browser_list()
            if not browsers:
                self.logger.warning("没有找到浏览器实例")
                return {}

            # 🔥 优化：使用批量操作，只调用一次API
            browser_ids = [browser.get('id') for browser in browsers if browser.get('id')]
            if not browser_ids:
                self.logger.warning("没有有效的浏览器ID")
                return {}

            # 使用批量显示配置
            show_config = {
                'type': 'box',          # 宫格排列
                'startX': 50,           # 起始X位置（屏幕左侧可见区域）
                'startY': 50,           # 起始Y位置（屏幕顶部可见区域）
                'width': 350,           # 窗口宽度（与创建实例一致）
                'height': 880,          # 窗口高度（与创建实例一致）
                'col': 10,              # 每行10个浏览器
                'spaceX': 10,           # 横向间距10像素（紧凑排列）
                'spaceY': 20,           # 纵向间距20像素
                'ids': browser_ids      # 批量处理所有浏览器
            }
            
            # 设置超时时间，避免无限等待
            response = self.session.post(f"{self.base_url}/windowbounds", json=show_config, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    self.logger.info(f"✅ 批量显示浏览器成功: {len(browser_ids)} 个")
                    # 返回成功结果
                    return {browser.get('name', 'Unknown'): True for browser in browsers if browser.get('id')}
                else:
                    error_msg = result.get('msg', '未知错误')
                    self.logger.error(f"❌ 批量显示浏览器失败: {error_msg}")
                    return {browser.get('name', 'Unknown'): False for browser in browsers if browser.get('id')}
            else:
                self.logger.error(f"❌ 批量显示浏览器API请求失败: {response.status_code}")
                return {browser.get('name', 'Unknown'): False for browser in browsers if browser.get('id')}

        except Exception as e:
            self.logger.error(f"批量显示浏览器异常: {e}")
            return {}
