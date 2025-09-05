#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
脚本生成器
负责收集UI设置，分配关键词，为每个浏览器生成独立的采集脚本
"""

import os
import json
import shutil
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path


class ScriptGenerator:
    """脚本生成器 - 浏览器模块和脚本模块的桥梁"""
    
    def __init__(self, gui_instance):
        """
        初始化脚本生成器
        
        Args:
            gui_instance: GUI实例，用于获取UI设置
        """
        self.gui = gui_instance

        # 获取当前脚本的绝对路径，确保路径解析正确
        current_dir = Path(__file__).parent.absolute()
        project_root = current_dir.parent

        # 生成的浏览器脚本独立目录 - 与bite模块完全分离
        self.scripts_dir = project_root / "generated_scripts"
        # 🔥 新的模块化模板目录 - 包含多个专业模块
        self.template_dir = project_root / "pdd_automation"

        # 确保生成脚本目录存在
        self.scripts_dir.mkdir(exist_ok=True)
        
        # print("脚本生成器初始化完成")
        # 不显示模板目录和结构信息，避免日志过多

    def _cleanup_old_scripts(self):
        """🔥 修改：每次开始解析时删除全部浏览器文件夹，重新生成"""
        try:
            print("清理所有历史脚本文件夹...")
            print("   清理策略: 删除所有浏览器文件夹，重新生成")

            if not self.scripts_dir.exists():
                return

            # 遍历所有浏览器脚本目录，删除整个文件夹
            cleaned_count = 0
            protected_count = 0

            for browser_folder in self.scripts_dir.iterdir():
                if browser_folder.is_dir() and browser_folder.name.startswith('browser_'):
                    try:
                        print(f"   删除目录: {browser_folder.name}")
                        
                        # 🔥 新策略：删除整个浏览器文件夹
                        import shutil
                        shutil.rmtree(browser_folder)
                        cleaned_count += 1
                        print(f"   ✅ 删除完成: {browser_folder.name}")

                    except Exception as e:
                        if "WinError 32" in str(e) or "另一个程序正在使用" in str(e):
                            print(f"   ⚠️ 跳过正在使用的文件夹: {browser_folder.name} (浏览器运行中)")
                            protected_count += 1
                        else:
                            print(f"   ❌ 删除失败 {browser_folder.name}: {e}")

            print(f"✅ 清理完成，删除了 {cleaned_count} 个目录，保护了 {protected_count} 个运行中目录")

        except Exception as e:
            print(f"❌ 清理历史脚本失败: {e}")

    def _cleanup_files_keep_folders(self, browser_folder: Path):
        """🔥 新方法：只清理根目录文件，保留所有子文件夹结构"""
        try:
            # print(f"     清理策略: 只删除根目录文件，保留所有子文件夹结构")
            
            # 递归清理：删除所有文件，保留所有文件夹
            self._recursive_cleanup_files(browser_folder)
            
            # print(f"     ✅ 清理完成: 保留了所有子文件夹结构")
            
        except Exception as e:
            print(f"     ❌ 清理失败: {e}")

    def _recursive_cleanup_files(self, folder_path: Path):
        """清理根目录文件，保留所有子文件夹结构"""
        try:
            # 遍历文件夹中的所有项目
            for item in folder_path.iterdir():
                if item.is_file():
                    # 删除文件
                    try:
                        item.unlink()
                        # print(f"       删除文件: {item.name}")
                    except Exception as e:
                        print(f"       ⚠️ 删除文件失败 {item.name}: {e}")
                elif item.is_dir():
                    # 🔥 修改：只清理文件，不递归删除子文件夹中的内容
                    # 保留所有文件夹结构，包括data、output等
                    # self._recursive_cleanup_files(item)  # 注释掉这行
                    pass
                    
        except Exception as e:
            print(f"       ❌ 递归清理失败: {e}")

    def _selective_cleanup(self, browser_folder: Path):
        """选择性清理：删除配置文件，保留output目录"""
        try:
            # 🔥 不再删除配置文件，保留配置文件供jiex.py使用
            # config_files = list(browser_folder.glob("config_*.json"))
            # for config_file in config_files:
            #     config_file.unlink()

            # 删除脚本文件
            script_files = list(browser_folder.glob("pdd_script_*.py"))
            for script_file in script_files:
                script_file.unlink()

            # 删除关键词文件
            keyword_files = list(browser_folder.glob("filter_keywords_*.txt"))
            for keyword_file in keyword_files:
                keyword_file.unlink()

            # 删除API文件
            api_files = list(browser_folder.glob("simple_bitbrowser_api.py"))
            for api_file in api_files:
                api_file.unlink()

            # 删除其他临时文件
            temp_files = list(browser_folder.glob("*.log")) + list(browser_folder.glob("*.tmp"))
            for temp_file in temp_files:
                temp_file.unlink()

            # 删除data目录（临时数据）
            data_dir = browser_folder / "data"
            if data_dir.exists():
                import shutil
                shutil.rmtree(data_dir)

            # 删除products_data目录（可重新生成）
            products_data_dir = browser_folder / "products_data"
            if products_data_dir.exists():
                import shutil
                shutil.rmtree(products_data_dir)

            # 保留output目录（重要数据）
            print(f"     已保护: output目录及其数据文件")

        except Exception as e:
            print(f"     ❌ 选择性清理失败: {e}")

    def collect_ui_settings(self) -> Dict[str, Any]:
        """收集UI界面的所有设置"""
        try:
            print("收集UI设置...")

            # 从全局变量收集关键词，避免直接访问可能已销毁的UI控件
            search_keywords = []
            filter_keywords = []

            # 尝试从UI控件获取最新数据，如果失败则使用全局变量
            try:
                if hasattr(self.gui, 'search_keywords_text') and self.gui.search_keywords_text.winfo_exists():
                    search_keywords_text = self.gui.search_keywords_text.get(1.0, "end-1c").strip()
                    search_keywords = [
                        line.replace(' ---已搜索', '').strip()
                        for line in search_keywords_text.split('\n')
                        if line.strip()
                    ]
                else:
                    # 使用全局变量
                    search_keywords = self.gui.global_search_keywords.copy()
            except:
                # 使用全局变量作为备选
                search_keywords = self.gui.global_search_keywords.copy()

            try:
                # 优先从FilterKeywordsManager获取最新的过滤关键词
                if hasattr(self.gui, 'filter_manager'):
                    filter_keywords = self.gui.filter_manager.get_keywords_list()
                    # print(f"从FilterKeywordsManager获取过滤关键词: {len(filter_keywords)} 个")
                elif hasattr(self.gui, 'filter_keywords_text') and self.gui.filter_keywords_text.winfo_exists():
                    filter_keywords_text = self.gui.filter_keywords_text.get(1.0, "end-1c").strip()
                    filter_keywords = [
                        line.strip()
                        for line in filter_keywords_text.split('\n')
                        if line.strip()
                    ]
                else:
                    # 使用全局变量
                    filter_keywords = self.gui.global_filter_keywords.copy()
            except:
                # 使用全局变量作为备选
                filter_keywords = self.gui.global_filter_keywords.copy()

            # 获取API Token
            api_token = ""
            try:
                if hasattr(self.gui, 'api_token_var'):
                    api_token = self.gui.api_token_var.get().strip()
                    # print(f"🔑 获取到API Token: {api_token[:10]}..." if api_token else "⚠️ 未设置API Token")
            except:
                # print("⚠️ 无法获取API Token")
                pass

            # 收集所有UI设置 - 直接使用全局变量，避免访问可能不存在的UI控件
            ui_settings = {
                "search_keywords": search_keywords,
                "filter_keywords": filter_keywords,

                # API配置 - 新增
                "api_token": api_token,

                # 基础设置 - 使用全局变量
                "wait_time": self.gui.global_wait_time,
                "page_count": self.gui.global_page_count,
                "target_count": self.gui.global_target_count,
                "search_page_wait": self.gui.global_search_page_wait,
                "sort_method": self.gui.global_sort_method,
                "require_24h_shipping": self.gui.global_shipping_time == "24小时发货",

                # 🔥 新增：定时运行控制设置
                "run_minutes": self.gui.global_run_minutes,
                "pause_minutes": self.gui.global_pause_minutes,
                "memory_threshold": self.gui.global_memory_threshold,

                # 过滤设置 - 使用全局过滤设置
                "filter_settings": self.gui.global_filter_settings.copy(),

                # 时间设置
                "timing_settings": {
                    "detail_page_wait": self.gui.global_wait_time,  # 详情页等待时间
                    "search_page_wait": self.gui.global_search_page_wait,
                    "random_wait_min": 1,
                    "random_wait_max": 2
                },

                # 目标设置
                "target_settings": {
                    "max_pages": self.gui.global_page_count,
                    "target_count": self.gui.global_target_count
                },
                
                # 生成信息
                "generation_info": {
                    "generated_time": datetime.now().isoformat(),
                    "total_keywords": len(search_keywords),
                    "total_filter_keywords": len(filter_keywords)
                }
            }
            
            # print(f"✅ UI设置收集完成:")
            # print(f"   搜索关键词: {len(search_keywords)} 个")
            # print(f"   🚫 过滤关键词: {len(filter_keywords)} 个")
            # print(f"   目标数量: {ui_settings['target_count']}")
            # print(f"   最大页数: {ui_settings['page_count']}")
            
            return ui_settings
            
        except Exception as e:
            # print(f"❌ 收集UI设置失败: {e}")
            return {}

    def _get_actual_debug_port(self, browser_id: str) -> int:
        """🔥 获取浏览器的实际调试端口 - 改进版"""
        try:
            # 🔥 方法1: 优先从GUI的API实例获取（最准确）
            if hasattr(self.gui, 'api') and self.gui.api:
                try:
                    # print(f"从GUI API获取浏览器列表...")
                    browser_list = self.gui.api.get_browser_list()
                    for browser in browser_list:
                        if browser.get('id') == browser_id:
                            # 检查debug_port字段
                            debug_port = browser.get('debug_port', 0)
                            if debug_port and debug_port != 0:
                                # print(f"从浏览器列表获取端口: {debug_port}")
                                return debug_port
                            break
                    # print(f"⚠️ 浏览器列表中未找到有效端口")
                except Exception as e:
                    # print(f"⚠️ 从GUI API获取端口失败: {e}")
                    pass

            # 🔥 方法2: 通过API直接获取
            try:
                from bitbrowser_api import BitBrowserAPI

                # 获取API Token
                api_token = ""
                if hasattr(self.gui, 'api_token_var'):
                    api_token = self.gui.api_token_var.get().strip()

                if not api_token:
                    from account_manager import AccountManager
                    account_manager = AccountManager()
                    accounts = account_manager.get_accounts()
                    if accounts:
                        api_token = accounts[0].get('api_token', '')

                if api_token:
                    api = BitBrowserAPI(api_token=api_token)

                    # 通过open_browser获取调试端口
                    # print(f"通过API获取调试端口...")
                    result = api.open_browser(browser_id)
                    if result and 'http' in result:
                        debug_info = result['http']
                        if ':' in debug_info:
                            debug_port = int(debug_info.split(':')[-1])
                            # print(f"API获取到端口: {debug_port}")
                            return debug_port

            except Exception as e:
                # print(f"⚠️ API获取端口失败: {e}")
                pass

            # 🔥 方法3: 从现有配置获取
            # print(f"⚠️ 尝试从现有配置获取端口...")
            return self._get_port_from_existing_config(browser_id)

        except Exception as e:
            # print(f"⚠️ 获取调试端口失败: {e}")
            return self._get_port_from_existing_config(browser_id)

    def _get_port_from_existing_config(self, browser_id: str) -> int:
        """从现有配置文件获取端口"""
        try:
            config_file = self.scripts_dir / f"browser_{browser_id}" / f"config_{browser_id}.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    port = config.get('browser_info', {}).get('debug_port')
                    if port and port != 9222:
                        # print(f"从现有配置获取端口: {port}")
                        return port

            # 🔥 修复硬编码：从配置文件读取默认端口
            default_port = self._get_default_port_from_config()
            # print(f"⚠️ 无法获取端口，使用默认端口 {default_port}")
            return default_port

        except Exception as e:
            # print(f"⚠️ 读取现有配置失败: {e}，使用默认端口")
            pass
            return self._get_default_port_from_config()

    def _get_default_port_from_config(self) -> int:
        """从生成的浏览器配置文件获取默认端口"""
        try:
            # 🔥 修复硬编码：使用统一的scripts_dir路径
            # 扫描已生成的浏览器配置文件
            generated_scripts_dir = self.scripts_dir
            if generated_scripts_dir.exists():
                for browser_dir in generated_scripts_dir.iterdir():
                    if browser_dir.is_dir() and browser_dir.name.startswith("browser_"):
                        config_file = browser_dir / "config_api.json"
                        if config_file.exists():
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                                api_url = config.get('api_url', '')
                                if api_url and ':' in api_url:
                                    port = int(api_url.split(':')[-1])
                                    # print(f"   从现有配置获取端口: {port}")
                                    return port

            # 如果没有现有配置，返回比特浏览器API的默认端口
            # print(f"   使用默认端口: 54345")
            # 🔥 修复：不再硬编码端口号，从配置文件获取
            try:
                import os
                import json
                
                # 尝试从主目录的config_api.json获取
                main_config_file = os.path.join(os.path.dirname(__file__), "..", "config_api.json")
                if os.path.exists(main_config_file):
                    with open(main_config_file, 'r', encoding='utf-8') as f:
                        main_config = json.load(f)
                        main_debug_port = main_config.get('browser_info', {}).get('debug_port')
                        if main_debug_port:
                            return main_debug_port
                
                # 如果主配置文件没有，返回None让调用者处理
                return None
            except:
                return None

        except Exception as e:
            # print(f"⚠️ 读取默认端口配置失败: {e}")
            # 🔥 修复：不再硬编码端口号
            return None

    def allocate_keywords(self, total_keywords: List[str], browser_ids: List[str]) -> Dict[str, List[str]]:
        """
        智能分配关键词给各个浏览器（过滤已搜索的关键词）

        Args:
            total_keywords: 所有搜索关键词
            browser_ids: 浏览器ID列表

        Returns:
            关键词分配结果 {browser_id: [keywords]}
        """
        try:
            # print(f"开始分配关键词...")
            # print(f"   总关键词: {len(total_keywords)} 个")
            # print(f"   浏览器数: {len(browser_ids)} 个")

            if not total_keywords or not browser_ids:
                return {}

            # 🔥 过滤掉已搜索的关键词
            filtered_keywords = []
            searched_keywords = []

            for keyword in total_keywords:
                # 检查是否包含"---已搜索"标记
                if "---已搜索" in keyword:
                    searched_keywords.append(keyword)
                    # print(f"   ⏭️ 跳过已搜索关键词: {keyword.split('---已搜索')[0].strip()}")
                else:
                    filtered_keywords.append(keyword.strip())

            # print(f"   过滤结果: {len(filtered_keywords)} 个待搜索, {len(searched_keywords)} 个已搜索")

            # 如果没有待搜索的关键词，返回空分配
            if not filtered_keywords:
                # print("⚠️ 没有待搜索的关键词，所有关键词都已搜索完成")
                return {}

            # 计算分配策略
            base_count = len(filtered_keywords) // len(browser_ids)
            remainder = len(filtered_keywords) % len(browser_ids)

            allocations = {}
            start_idx = 0

            for i, browser_id in enumerate(browser_ids):
                # 前几个浏览器多分配1个关键词（处理余数）
                count = base_count + (1 if i < remainder else 0)
                end_idx = start_idx + count

                # 分配关键词
                allocated_keywords = filtered_keywords[start_idx:end_idx]
                allocations[browser_id] = allocated_keywords

                # print(f"   浏览器 {browser_id[-4:]}: {len(allocated_keywords)} 个关键词")
                # for keyword in allocated_keywords:
                #     print(f"      - {keyword}")

                start_idx = end_idx

            # print("✅ 关键词分配完成")
            return allocations

        except Exception as e:
            # print(f"❌ 关键词分配失败: {e}")
            return {}
    
    def generate_scripts_for_browsers(self, browser_list: List[Dict[str, Any]]) -> bool:
        """
        为所有浏览器生成独立脚本

        Args:
            browser_list: 浏览器信息列表

        Returns:
            是否生成成功
        """
        try:
            # print(f"开始为 {len(browser_list)} 个浏览器生成脚本...")

            # 🔥 0. 清理历史脚本，确保只为当前运行的浏览器生成脚本
            self._cleanup_old_scripts()

            # 1. 收集UI设置
            ui_settings = self.collect_ui_settings()
            if not ui_settings:
                print("❌ UI设置收集失败")
                return False

            # 2. 🔥 提取运行中的浏览器ID列表 - 使用正确的状态字段
            browser_ids = [browser['id'] for browser in browser_list if browser.get('status') == 1]
            # print(f"检测到运行中的浏览器: {len(browser_ids)} 个")
            # for browser_id in browser_ids:
            #     print(f"   - {browser_id}")

            if not browser_ids:
                print("❌ 没有运行中的浏览器")
                return False
            
            # 3. 分配关键词
            keyword_allocations = self.allocate_keywords(ui_settings['search_keywords'], browser_ids)
            if not keyword_allocations:
                print("❌ 关键词分配失败")
                return False
            
            # 4. 为每个浏览器生成脚本
            success_count = 0
            # print(f"开始为运行中的浏览器生成脚本...")

            for browser in browser_list:
                browser_id = browser['id']
                browser_name = browser.get('name', f'Browser_{browser_id}')
                is_running = browser.get('status') == 1  # 🔥 使用正确的状态字段

                # status_text = "运行中" if is_running else "未运行"
                # print(f"   检查浏览器: {browser_name} (ID: {browser_id[-8:]}) - 运行状态: {status_text}")

                if not is_running:
                    # print(f"   ⏸️ 跳过未运行的浏览器: {browser_name}")
                    continue

                if browser_id in keyword_allocations:
                    # print(f"   为浏览器生成脚本: {browser_name}")
                    success = self._generate_single_browser_script(
                        browser,
                        ui_settings,
                        keyword_allocations[browser_id]
                    )
                    if success:
                        success_count += 1
                        # print(f"   ✅ 脚本生成成功: {browser_name}")
                    else:
                        # print(f"   ❌ 脚本生成失败: {browser_name}")
                        pass
                else:
                    # print(f"   ⚠️ 浏览器未分配关键词: {browser_name}")
                    pass
            
            # print(f"脚本生成完成: {success_count}/{len(browser_ids)} 个浏览器")
            return success_count > 0
            
        except Exception as e:
            # print(f"❌ 生成脚本失败: {e}")
            return False
    
    def _generate_single_browser_script(self, browser_info: Dict[str, Any], ui_settings: Dict[str, Any], allocated_keywords: List[str]) -> bool:
        """
        为单个浏览器生成独立脚本
        
        Args:
            browser_info: 浏览器信息
            ui_settings: UI设置
            allocated_keywords: 分配的关键词
            
        Returns:
            是否生成成功
        """
        try:
            browser_id = browser_info['id']
            browser_name = browser_info.get('name', f'Browser_{browser_id}')

            # 获取实际的调试端口
            debug_port = self._get_actual_debug_port(browser_id)

            # print(f"生成脚本: {browser_name} (ID: {browser_id[-4:]}) 端口: {debug_port}")

            # 创建浏览器专用目录 - 使用完整ID
            browser_folder = self.scripts_dir / f"browser_{browser_id}"
            browser_folder.mkdir(exist_ok=True)

            # 检查是否有现有的output目录需要保护
            output_folder = browser_folder / "output"
            has_existing_data = False
            if output_folder.exists():
                excel_files = list(output_folder.glob("*.xlsx"))
                json_files = list(output_folder.glob("*.json"))
                txt_files = list(output_folder.glob("*.txt"))
                data_files = excel_files + json_files + txt_files

                if data_files:
                    has_existing_data = True
                    # print(f"   发现现有数据，将保护现有output目录:")
                    # print(f"     Excel文件: {len(excel_files)} 个")
                    # print(f"     JSON文件: {len(json_files)} 个")
                    # print(f"     TXT文件: {len(txt_files)} 个")
                    pass

            # 🔥 修改：只创建必要的三个文件夹
            # print(f"   创建必要的文件夹结构...")
            
            # 1. logs文件夹 - 存放日志文件
            logs_folder = browser_folder / "logs"
            logs_folder.mkdir(exist_ok=True)
            # print(f"     创建: logs/")
            
            # 2. output文件夹 - 存放输出数据
            output_folder = browser_folder / "output"
            output_folder.mkdir(exist_ok=True)
            # print(f"     创建: output/")
            
            # 3. data文件夹 - 存放临时数据
            data_folder = browser_folder / "data"
            data_folder.mkdir(exist_ok=True)
            # print(f"     创建: data/")
            
            # print(f"   ✅ 文件夹结构创建完成")
            
            # 1. 生成配置文件
            config_success = self._create_browser_config(
                browser_folder, browser_id, ui_settings, allocated_keywords, debug_port
            )
            
            # 2. 复制并修改脚本文件
            script_success = self._create_browser_script(
                browser_folder, browser_id, debug_port, allocated_keywords, ui_settings
            )
            
            if config_success and script_success:
                # print(f"✅ 浏览器 {browser_id[-4:]} 脚本生成成功")
                # print(f"   目录: {browser_folder}")
                # print(f"   关键词: {len(allocated_keywords)} 个")
                return True
            else:
                # print(f"❌ 浏览器 {browser_id[-4:]} 脚本生成失败")
                return False
                
        except Exception as e:
            # print(f"❌ 生成单个浏览器脚本失败: {e}")
            return False


    
    def _create_browser_config(self, browser_folder: Path, browser_id: str, ui_settings: Dict[str, Any], allocated_keywords: List[str], debug_port: int) -> bool:
        """🔥 已删除：不再生成config_{浏览器ID}.json，统一使用config_api.json"""
        try:
            # 为每个浏览器创建独立的过滤关键词文件
            filter_keywords_file = browser_folder / f"filter_keywords_{browser_id}.txt"
            self._create_browser_filter_keywords_file(filter_keywords_file, ui_settings.get("filter_keywords", []))

            print(f"   ✅ 过滤关键词文件: {filter_keywords_file.name}")
            print(f"   ℹ️ 配置文件统一使用: config_api.json")
            return True

        except Exception as e:
            print(f"   ❌ 创建过滤关键词文件失败: {e}")
            return False

    def _create_browser_filter_keywords_file(self, filter_file_path: Path, filter_keywords: List[str]) -> bool:
        """为浏览器创建独立的过滤关键词文件"""
        try:
            content = [
                f"# 浏览器过滤关键词文件",
                f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"# 关键词数量: {len(filter_keywords)}",
                "# 每行一个关键词，支持中文",
                "# 以#开头的行为注释",
                ""
            ]

            # 添加过滤关键词
            content.extend(filter_keywords)

            # 写入文件
            with open(filter_file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))

            print(f"✅ 创建过滤关键词文件: {filter_file_path.name} ({len(filter_keywords)} 个关键词)")
            return True

        except Exception as e:
            print(f"❌ 创建过滤关键词文件失败: {e}")
            return False


    
    def _create_browser_script(self, browser_folder: Path, browser_id: str, debug_port: int, allocated_keywords: List[str], ui_settings: Dict[str, Any]) -> bool:
        """🔥 创建模块化浏览器脚本文件 - 复制整个模板目录"""
        try:
            # 1. 检查模板目录是否存在
            if not self.template_dir.exists():
                print(f"   ❌ 模板目录不存在: {self.template_dir}")
                print(f"   当前工作目录: {os.getcwd()}")
                print(f"   模板目录绝对路径: {self.template_dir.absolute()}")
                return False

            # 2. 🔥 动态扫描所有Python脚本文件（排除特定文件）
            exclude_files = {"__init__.py", "__pycache__"}  # 排除的文件
            template_files = []

            # 扫描模板目录中的所有.py文件
            for py_file in self.template_dir.glob("*.py"):
                if py_file.name not in exclude_files:
                    template_files.append(py_file.name)

            # 🔥 修改：不再硬编码核心文件，完全依赖模板目录扫描
            print(f"   发现模板文件: {len(template_files)} 个")
            for file in sorted(template_files):
                print(f"   {file}")

            # 不显示具体的文件名，避免日志过多
            # print(f"   发现模板文件: {len(template_files)} 个")
            # for file in sorted(template_files):
            #     print(f"   {file}")

            # 🔥 动态扫描配置文件（除了config_api.json，因为它是动态生成的）
            config_files = []
            for config_file in self.template_dir.glob("*.json"):
                if config_file.name != "config_api.json":  # 排除动态生成的配置文件
                    config_files.append(config_file.name)
            
            # 🔥 修改：不复制任何.txt文件，因为关键词文件都是动态生成的
            # 删除这个循环，避免重复复制filter_keywords_global.txt

            # 不显示复制进度，避免日志过多
            # print(f"   复制模块化脚本文件...")
            import time
            current_time = time.strftime("%Y-%m-%d %H:%M:%S")
            print(f"   生成时间: {current_time}")

            for template_file in template_files:
                src_file = self.template_dir / template_file
                dst_file = browser_folder / template_file

                if src_file.exists():
                    # 🔥 强制覆盖，使用当前时间戳
                    shutil.copy(str(src_file), str(dst_file))
                    # 设置当前时间戳
                    import os
                    current_timestamp = time.time()
                    os.utime(str(dst_file), (current_timestamp, current_timestamp))
                    # 不显示具体文件名，避免日志过多
                    # print(f"   ✅ 已复制: {template_file} (时间戳: {current_time})")
                else:
                    print(f"   ⚠️ 模板文件不存在: {template_file}")

            # 2.5. 🔥 生成独立的config_api.json文件
            print(f"   生成独立的config_api.json...")
            self._generate_independent_config_api(browser_folder, browser_id, debug_port, allocated_keywords, ui_settings)

            # 复制所有配置文件
            for config_file in config_files:
                src_file = self.template_dir / config_file
                dst_file = browser_folder / config_file

                if src_file.exists():
                    shutil.copy(str(src_file), str(dst_file))
                    print(f"   ✅ 已复制配置: {config_file}")
                else:
                    print(f"   ⚠️ 配置文件不存在: {config_file}")

            # 3. 🔥 修改：只创建必要的三个文件夹
            # print(f"   检查并创建必要的文件夹...")
            
            # 只创建必要的三个文件夹
            essential_dirs = ["logs", "output", "data"]
            for subdir in essential_dirs:
                subdir_path = browser_folder / subdir
                if not subdir_path.exists():
                    subdir_path.mkdir(exist_ok=True)
                    print(f"     已创建: {subdir}/")
                else:
                    # print(f"     已存在: {subdir}/")
                    pass
            
            # 🔥 新增：复制data目录中的文件
            template_data_dir = self.template_dir / "data"
            browser_data_dir = browser_folder / "data"
            if template_data_dir.exists():
                for data_file in template_data_dir.glob("*"):
                    if data_file.is_file():
                        dst_file = browser_data_dir / data_file.name
                        shutil.copy(str(data_file), str(dst_file))
                        print(f"   ✅ 已复制数据文件: {data_file.name}")
            
            print(f"   ✅ 必要文件夹检查完成")

            # 4. 🔥 保护重要的现有文件（不覆盖）
            important_files = [
                "filter_keywords_*.txt",
                "config_*.json",
                "*.log",
                "clicked_products.json",
                "goods_cache.json",
                "filtered_goods.json",
                "program_status.json"
            ]

            protected_files = []
            for pattern in important_files:
                matching_files = list(browser_folder.glob(pattern))
                for file_path in matching_files:
                    if file_path.exists():
                        protected_files.append(file_path.name)

            if protected_files:
                # print(f"   保护现有重要文件: {len(protected_files)} 个")
                for file_name in protected_files[:5]:  # 只显示前5个
                    # print(f"     {file_name}")
                    pass
                if len(protected_files) > 5:
                    # print(f"     ... 还有 {len(protected_files) - 5} 个文件")
                    pass

            print(f"   模块化脚本创建完成")
            return True

        except Exception as e:
            print(f"   ❌ 创建脚本文件失败: {e}")
            return False

    def _generate_independent_config_api(self, browser_folder: Path, browser_id: str, debug_port: int, allocated_keywords: List[str], ui_settings: Dict[str, Any]):
        """🔥 生成统一的config_api.json配置文件（包含所有必要配置）"""
        try:
            config_api_path = browser_folder / "config_api.json"

            # 🔥 构建完整的统一配置（合并原config_{浏览器ID}.json的内容）
            config_api = {
                "api_token": ui_settings.get("api_token", ""),
                "browser_info": {
                    "browser_id": browser_id,
                    "debug_port": debug_port,
                    "folder_name": f"browser_{browser_id}",
                    "filter_keywords_file": f"filter_keywords_{browser_id}.txt"
                },
                "parse_settings": {
                    "wait_time": ui_settings.get("wait_time", 5),
                    "page_count": ui_settings.get("page_count", 2),
                    "target_count": ui_settings.get("target_count", 33),
                    "search_page_wait": ui_settings.get("search_page_wait", 11),
                    "sort_method": ui_settings.get("sort_method", "综合排序"),
                    "run_minutes": ui_settings.get("run_minutes", 480),  # 🔥 新增：运行时长
                    "pause_minutes": ui_settings.get("pause_minutes", 240),  # 🔥 新增：暂停时长
                    "memory_threshold": ui_settings.get("memory_threshold", 200),  # 🔥 新增：内存阈值
                    "filter_settings": ui_settings.get("filter_settings", {
                        "filter_brand_store": True,
                        "filter_flagship_store": True,
                        "filter_presale": True,
                        "sales_min": "15",
                        "sales_max": "",
                        "price_min": "15",
                        "price_max": "",
                        "require_24h_shipping": ui_settings.get("require_24h_shipping", False)
                    }),
                    "search_keywords": allocated_keywords
                },
                "click_settings": {
                    "search_page_wait": ui_settings.get("search_page_wait", 3),
                    "detail_page_wait": ui_settings.get("wait_time", 1),
                    "click_interval_min": 2,
                    "click_interval_max": 8,
                    "enable_random_behavior": True,
                    "max_click_offset": 10,
                    "mouse_path_steps": 15
                },
                # 🔥 新增：服务器配置（原config_{浏览器ID}.json中的内容）
                "server_config": {
                    "upload_url": ui_settings.get("server_url", "http://127.0.0.1:5000/api/upload"),
                    "encryption_password": ui_settings.get("encryption_password", "请修改为您的实际密码"),
                    "timeout": ui_settings.get("server_timeout", 30),
                    "max_retries": ui_settings.get("server_max_retries", 3)
                },
                # 🔥 新增：生成信息（原config_{浏览器ID}.json中的内容）
                "generation_info": {
                    "generated_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "allocated_keywords_count": len(allocated_keywords),
                    "browser_id": browser_id,
                    "filter_keywords_file": f"filter_keywords_{browser_id}.txt"
                }
            }

            # 保存配置文件
            with open(config_api_path, 'w', encoding='utf-8') as f:
                json.dump(config_api, f, ensure_ascii=False, indent=2)

            print(f"   ✅ 已生成统一配置: config_api.json (浏览器ID: {browser_id})")
            # print(f"   配置包含: API令牌、浏览器信息、解析设置、点击设置、服务器配置、生成信息")

        except Exception as e:
            print(f"   ❌ 生成config_api.json失败: {e}")

    def get_generated_scripts_info(self) -> List[Dict[str, Any]]:
        """获取已生成脚本的信息"""
        try:
            scripts_info = []
            
            if not self.scripts_dir.exists():
                return scripts_info
            
            for browser_folder in self.scripts_dir.iterdir():
                if browser_folder.is_dir() and browser_folder.name.startswith('browser_'):
                    # 🔥 修改：统一使用config_api.json
                    config_file = browser_folder / 'config_api.json'
                    if config_file.exists():
                        try:
                            with open(config_file, 'r', encoding='utf-8') as f:
                                config = json.load(f)
                            
                            scripts_info.append({
                                'folder': browser_folder.name,
                                'folder_path': str(browser_folder),  # 🔥 添加文件夹路径
                                'browser_id': config.get('browser_info', {}).get('browser_id', ''),
                                'debug_port': config.get('browser_info', {}).get('debug_port', None),
                                'keywords_count': len(config.get('parse_settings', {}).get('search_keywords', [])),  # 🔥 修复：从parse_settings中获取
                                'generated_time': config.get('generation_info', {}).get('generated_time', ''),
                                'config_file': str(config_file),
                                'script_file': str(browser_folder / "pdd_search_simple.py"),  # 🔥 使用新的主启动脚本
                                'main_script': str(browser_folder / "pdd_search_simple.py")  # 🔥 明确指定主脚本
                            })
                            
                        except Exception as e:
                            print(f"⚠️ 读取配置失败 {config_file}: {e}")
            
            return scripts_info
            
        except Exception as e:
            print(f"❌ 获取脚本信息失败: {e}")
            return []
    
    def clean_old_scripts(self, keep_browser_ids: List[str] = None) -> bool:
        """清理旧的脚本文件"""
        try:
            if not self.scripts_dir.exists():
                return True
            
            keep_browser_ids = keep_browser_ids or []
            keep_folders = [f"browser_{bid}" for bid in keep_browser_ids]
            
            cleaned_count = 0
            for browser_folder in self.scripts_dir.iterdir():
                if browser_folder.is_dir() and browser_folder.name.startswith('browser_'):
                    if browser_folder.name not in keep_folders:
                        shutil.rmtree(browser_folder)
                        cleaned_count += 1
                        print(f"已清理: {browser_folder.name}")
            
            if cleaned_count > 0:
                print(f"✅ 清理完成: {cleaned_count} 个旧脚本文件夹")
            else:
                print("ℹ️ 没有需要清理的文件")
            
            return True
            
        except Exception as e:
            print(f"❌ 清理脚本失败: {e}")
            return False


