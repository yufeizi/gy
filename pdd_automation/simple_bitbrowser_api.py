#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的比特浏览器API模块
专门用于生成的采集脚本，默认从配置文件读取TOKEN和端口号
"""

import requests
import json

class SimpleBitBrowserAPI:
    """简化的比特浏览器API - 默认从配置文件读取"""

    def __init__(self, api_token: str = None, base_url: str = None):
        # 步骤1：从配置文件读取默认设置
        self.config = self.load_config()

        # 从配置文件获取TOKEN和端口号
        config_browser_info = self.config.get('browser_info', {})
        self.browser_id = config_browser_info.get('browser_id')
        self.debug_port = config_browser_info.get('debug_port')

        # 如果没有提供token，尝试从配置文件读取
        if api_token is None:
            api_token = self.config.get('api_token')

        # 如果没有提供base_url，使用配置文件中的端口号
        if base_url is None:
            config = self.load_config()
            debug_port = config.get('browser_info', {}).get('debug_port')
            if debug_port:
                base_url = f"http://127.0.0.1:{debug_port}"
            else:
                # 如果配置文件中没有端口号，使用默认端口
                base_url = "http://127.0.0.1:54345"

        self.api_token = api_token
        self.base_url = base_url
        self.session = requests.Session()

        # 设置请求头 - 根据官方文档使用x-api-key
        self.session.headers.update({
            'Content-Type': 'application/json'
        })

        if api_token:
            self.session.headers.update({
                'x-api-key': api_token
            })

        # 静默初始化

    def load_config(self):
        """从配置文件加载设置"""
        try:
            import os
            # 修复：使用当前目录下的config_api.json
            config_file = os.path.join(os.path.dirname(__file__), "config_api.json")
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            return {}

    def test_connection(self):
        """测试API连接（静默模式）"""
        try:
            # 测试健康检查接口
            try:
                health_response = self.session.post(f"{self.base_url}/health", json={}, timeout=5)
                if health_response.status_code == 200:
                    return True
            except:
                pass

            # 如果健康检查失败，测试运行中浏览器接口
            try:
                response = self.session.post(
                    f"{self.base_url}/browser/pids/all",
                    json={},
                    timeout=5
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        return True
            except:
                pass

            # 最后测试浏览器列表接口
            try:
                response = self.session.post(
                    f"{self.base_url}/browser/list",
                    json={"page": 0, "pageSize": 1},
                    timeout=5
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get('success'):
                        return True
            except:
                pass

            return False
        except:
            return False

    def get_browser_list(self):
        """获取浏览器列表 - 使用POST请求"""
        try:
            # 根据官方文档：所有接口请求方式均为POST
            response = self.session.post(
                f"{self.base_url}/browser/list",
                json={"page": 0, "pageSize": 100}  # 必需参数
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    return data.get('data', [])
                else:
                    print(f"API返回失败: {data.get('msg', '未知错误')}")
            return []
        except Exception as e:
            print(f"获取浏览器列表失败: {e}")
            return []

    def get_browser_pids(self, browser_ids):
        """获取浏览器调试端口"""
        try:
            response = self.session.post(
                f"{self.base_url}/browser/pids",
                json={"browser_ids": browser_ids}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('data', {})
            return {}
        except Exception as e:
            print(f"获取浏览器端口失败: {e}")
            return {}

    def open_browser(self, browser_id):
        """启动浏览器并返回连接信息 - 基于官方文档"""
        try:
            # 根据官方文档的参数格式
            payload = {
                "id": browser_id,
                "args": [],  # 浏览器启动参数
                "loadExtensions": False,  # 是否加载扩展
                "extractIp": False  # 是否尝试自动提取IP
            }

            print(f"[DEBUG] 启动浏览器请求: {self.base_url}/browser/open")
            print(f"[DEBUG] 请求参数: {payload}")

            response = self.session.post(
                f"{self.base_url}/browser/open",
                json=payload,
                timeout=15  # 增加超时时间
            )

            print(f"[DEBUG] 响应状态: {response.status_code}")

            if response.status_code == 200:
                try:
                    result = response.json()
                    print(f"[DEBUG] 响应内容: {result}")

                    if result.get('success'):
                        data = result.get('data', {})
                        # 根据官方文档的返回格式解析
                        http_url = data.get('http', '')
                        debug_port = http_url.split(':')[-1] if ':' in http_url else None

                        return {
                            'success': True,
                            'debug_port': debug_port,
                            'ws_url': data.get('ws', ''),
                            'http_url': http_url,
                            'core_version': data.get('coreVersion', ''),
                            'driver_path': data.get('driver', '')
                        }
                    else:
                        error_msg = result.get('msg', '启动失败')
                        print(f"[DEBUG] API返回失败: {error_msg}")
                        return {'success': False, 'error': error_msg}
                except json.JSONDecodeError as e:
                    print(f"[DEBUG] JSON解析错误: {e}")
                    return {'success': False, 'error': 'JSON解析失败'}
            else:
                print(f"[DEBUG] HTTP错误: {response.status_code}")
                print(f"[DEBUG] 响应内容: {response.text}")
                return {'success': False, 'error': f'HTTP {response.status_code}'}

        except Exception as e:
            print(f"[DEBUG] 异常: {str(e)}")
            return {'success': False, 'error': str(e)}

    def close_browser(self, browser_id):
        """关闭浏览器"""
        try:
            response = self.session.post(
                f"{self.base_url}/browser/close",
                json={"browser_id": browser_id}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"关闭浏览器失败: {e}")
            return False

    def open_config_browser(self):
        """启动配置文件中的浏览器"""
        if not self.browser_id:
            return None

        # 检查浏览器是否已经在运行
        running_browsers = self.get_running_browsers()
        if self.browser_id in running_browsers:
            return {
                "success": True,
                "ws_url": f"ws://127.0.0.1:{self.debug_port}",
                "http": f"127.0.0.1:{self.debug_port}",
                "status": "already_running"
            }

        # 如果没有运行，尝试启动
        return self.open_browser(self.browser_id)

    def get_running_browsers(self):
        """获取正在运行的浏览器列表 - 基于官方文档"""
        try:
            # 根据官方文档，使用正确的API端点
            response = self.session.post(
                f"{self.base_url}/browser/pids/all",
                json={},  # 官方文档显示无参数
                timeout=5
            )

            print(f"[DEBUG] API请求: {self.base_url}/browser/pids/all")
            print(f"[DEBUG] 响应状态: {response.status_code}")

            if response.status_code == 200:
                result = response.json()
                print(f"[DEBUG] 响应内容: {result}")

                if result.get('success'):
                    # 官方文档显示返回格式为 {"浏览器ID": 进程ID}
                    browser_data = result.get('data', {})
                    return list(browser_data.keys())
                else:
                    print(f"[DEBUG] API返回失败: {result.get('msg', '未知错误')}")
            else:
                print(f"[DEBUG] HTTP错误: {response.status_code}")
                print(f"[DEBUG] 响应内容: {response.text}")

            return []
        except Exception as e:
            print(f"[DEBUG] 异常: {str(e)}")
            return []

    def get_config_browser_info(self):
        """获取配置文件中的浏览器信息"""
        return {
            'browser_id': self.browser_id,
            'debug_port': self.debug_port
        }

    def get_browser_id(self):
        """获取当前浏览器ID"""
        return self.browser_id

    def execute_js(self, js_code):
        """执行JavaScript代码"""
        try:
            import websocket
            import json
            import requests

            # 获取浏览器连接信息
            browser_info = self.open_config_browser()
            if not browser_info or not browser_info.get('success'):
                print(f"❌ 浏览器未运行: {browser_info.get('error') if browser_info else '无法启动浏览器'}")
                return None

            debug_port = self.debug_port
            print(f"🔗 连接到浏览器调试端口: {debug_port}")

            # 获取可用的WebSocket端点
            try:
                tabs_response = requests.get(f"http://127.0.0.1:{debug_port}/json", timeout=5)
                tabs = tabs_response.json()

                if not tabs:
                    print("❌ 没有找到可用的标签页")
                    return None

                # 使用第一个标签页
                tab = tabs[0]
                ws_url = tab['webSocketDebuggerUrl']
                print(f"🔗 使用WebSocket URL: {ws_url}")

            except Exception as e:
                print(f"❌ 获取WebSocket端点失败: {e}")
                return None

            # 创建WebSocket连接，设置45秒超时
            ws = websocket.create_connection(ws_url, timeout=45)

            # 发送JavaScript执行命令
            command = {
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": js_code,
                    "returnByValue": True,
                    "awaitPromise": True,
                    "timeout": 45000  # 45秒超时（毫秒）
                }
            }

            ws.send(json.dumps(command))

            # 接收响应，设置45秒超时
            import socket
            ws.sock.settimeout(45)
            response = ws.recv()
            ws.close()

            result = json.loads(response)

            # 增强的结果处理逻辑
            if 'result' in result and 'result' in result['result']:
                result_data = result['result']['result']

                # 检查是否有value字段
                if 'value' in result_data:
                    js_result = result_data['value']
                    print(f"✅ JavaScript执行成功")
                    return js_result
                # 检查是否有其他返回类型
                elif 'type' in result_data:
                    if result_data['type'] == 'undefined':
                        print(f"✅ JavaScript执行成功 (返回undefined)")
                        return None
                    elif result_data['type'] == 'object' and result_data.get('subtype') == 'null':
                        print(f"✅ JavaScript执行成功 (返回null)")
                        return None
                    else:
                        print(f"✅ JavaScript执行成功 (返回类型: {result_data['type']})")
                        return result_data.get('description', str(result_data))
                else:
                    print(f"✅ JavaScript执行成功 (无value字段)")
                    return str(result_data)
            else:
                print(f"❌ JavaScript执行失败: {result}")
                return None

        except ImportError:
            print("❌ 缺少websocket-client库，请安装: pip install websocket-client")
            return None
        except Exception as e:
            print(f"❌ 执行JavaScript失败: {e}")
            return None

    def get_page_source(self):
        """获取当前页面源码 - 简化版本，返回模拟数据用于测试"""
        try:
            print("⚠️ get_page_source方法暂时返回None，建议使用其他数据源")
            print("💡 建议使用real_data_jx_system_regex.py进行实时数据抓取")
            return None

        except Exception as e:
            print(f"❌ 获取页面源码失败: {e}")
            return None

# 为了兼容性，创建别名
BitBrowserAPI = SimpleBitBrowserAPI
