#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jiex.py - 详情页数据抓取模块
功能：
1. 点击进入详情页后立即抓取完整的window.rawData
2. 以商品ID命名保存为压缩JSON的TXT文档
3. 维护已点击商品的JSON文件用于过滤
4. 支持加密上传到服务器（预留接口）
5. 🔥 新增：已搜索关键词传输到主程序（每10分钟）
6. 🔥 新增：UI日志显示（只显示保存成功日志）
"""

import os
import json
import time
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Set, Optional
from pathlib import Path

# 🔥 处理config_manager导入问题
try:
    from config_manager import ConfigManager
    print("config_manager导入成功")
except ImportError as e:
    print(f"[警告] config_manager导入失败: {e}")
    # 创建一个简单的替代类
    class ConfigManager:
        def __init__(self, *args, **kwargs):
            self.config = {}

        def get_config(self):
            return self.config

        def get_browser_id(self):
            return "default"

# 🔥 已删除ui_communication导入，使用简单的日志输出
def log_message(message: str):
    """简单的日志输出函数"""
    print(f"[日志] {message}")

class DetailPageExtractor:
    """详情页数据抓取器"""

    def __init__(self, browser_id: str = None, config_file: str = None):
        """
        初始化详情页抓取器

        Args:
            browser_id: 浏览器ID，如果为None则从配置文件读取
            config_file: 配置文件路径，如果为None则自动检测
        """
        
        # 加载配置管理器
        try:
            # 🔥 修复：如果没有指定配置文件，尝试找到浏览器专用配置
            if not config_file:
                detected_browser_id = self._detect_browser_id()
                if detected_browser_id != "default_browser_id":
                    # 尝试找到浏览器专用配置文件
                    current_file_dir = os.path.dirname(os.path.abspath(__file__))
                    parent_dir = os.path.dirname(current_file_dir)
                    browser_config_path = os.path.join(parent_dir, "generated_scripts", f"browser_{detected_browser_id}", f"config_{detected_browser_id}.json")
                    if os.path.exists(browser_config_path):
                        config_file = browser_config_path
                        print(f"[配置] 找到浏览器专用配置: {config_file}")

            # 🔥 修复：确保传入有效的配置文件路径
            if config_file and os.path.exists(config_file):
                self.config_mgr = ConfigManager(config_file)
            else:
                # 使用默认配置文件
                default_config = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config_api.json")
                self.config_mgr = ConfigManager(default_config)

            self.browser_id = browser_id or self.config_mgr.get_browser_id()
            self.browser_id_short = self.config_mgr.get_browser_id_short()
        except Exception as e:
            print(f"[警告] 配置管理器加载失败，使用备用方案: {e}")
            self.browser_id = browser_id or self._detect_browser_id()
            self.browser_id_short = self.browser_id[-6:] if self.browser_id else "unknown"

        # 设置输出目录 - 彻底修复路径逻辑
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 🔥 修复：简化路径逻辑，避免嵌套目录
        if "browser_" in current_file_dir and self.browser_id in current_file_dir:
            # 已经在浏览器目录中运行
            self.output_dir = Path(current_file_dir)
            # details_dir指向主目录（用于从服务器下载的数据）
            project_root = current_file_dir
            while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                parent = os.path.dirname(project_root)
                if parent == project_root:
                    break
                project_root = parent
            
            # 确保project_root是主目录
            if "generated_scripts" in str(project_root):
                project_root = os.path.dirname(project_root)
            
            # 🔥 修复：设置为实例属性
            self.project_root = Path(project_root)
            self.details_dir = self.project_root / "details"
            self.logs_dir = self.output_dir / "logs"
        elif "generated_scripts" in current_file_dir:
            # 🔥 修复：在generated_scripts目录中运行时，output指向浏览器目录，details指向主目录
            try:
                # 从当前路径中提取浏览器ID
                path_parts = current_file_dir.split(os.sep)
                browser_dir_index = None
                for i, part in enumerate(path_parts):
                    if part.startswith('browser_'):
                        browser_dir_index = i
                        break
                
                if browser_dir_index is not None:
                    # 找到了浏览器目录，使用它作为output_dir
                    browser_dir = os.sep.join(path_parts[:browser_dir_index + 1])
                    self.output_dir = Path(browser_dir)
                    
                    # 找到主目录（包含generated_scripts的目录）
                    project_root = current_file_dir
                    while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                        parent = os.path.dirname(project_root)
                        if parent == project_root:
                            break
                        project_root = parent
                    
                    # 确保project_root是主目录
                    if "generated_scripts" in str(project_root):
                        project_root = os.path.dirname(project_root)
                    
                    # 🔥 修复：设置为实例属性
                    self.project_root = Path(project_root)
                    # details_dir指向主目录（用于从服务器下载的数据）
                    self.details_dir = self.project_root / "details"
                    # logs_dir指向浏览器目录
                    self.logs_dir = self.output_dir / "logs"
                    
                    print(f"[路径修复] 检测到在generated_scripts中运行:")
                    print(f"  - output_dir: {self.output_dir} (浏览器目录)")
                    print(f"  - details_dir: {self.details_dir} (主目录)")
                else:
                    # 没找到浏览器目录，使用主目录
                    project_root = current_file_dir
                    while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                        parent = os.path.dirname(project_root)
                        if parent == project_root:
                            break
                        project_root = parent
                    
                    self.output_dir = Path(project_root)
                    self.details_dir = self.output_dir / "details"
                    self.logs_dir = self.output_dir / "logs"
                
            except Exception as e:
                print(f"[警告] 路径检测失败，使用主目录: {e}")
                # 回退到主目录
                project_root = current_file_dir
                while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                    parent = os.path.dirname(project_root)
                    if parent == project_root:
                        break
                    project_root = parent
                
                self.output_dir = Path(project_root)
                self.details_dir = self.output_dir / "details"
                self.logs_dir = self.output_dir / "logs"
        else:
            # 在主目录中运行，尝试找到浏览器目录
            try:
                project_root = current_file_dir
                while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                    parent = os.path.dirname(project_root)
                    if parent == project_root:
                        break
                    project_root = parent

                browser_dir = os.path.join(project_root, "generated_scripts", f"browser_{self.browser_id}")
                if os.path.exists(browser_dir):
                    # 🔥 修复：设置为实例属性
                    self.project_root = Path(project_root)
                    # output_dir指向浏览器目录（用于CSV等输出文件）
                    self.output_dir = Path(browser_dir)
                    # details_dir指向主目录（用于从服务器下载的数据）
                    self.details_dir = self.project_root / "details"
                    # logs_dir指向浏览器目录
                    self.logs_dir = self.output_dir / "logs"
                    
                    print(f"[路径设置] 在主目录中运行:")
                    print(f"  - output_dir: {self.output_dir} (浏览器目录)")
                    print(f"  - details_dir: {self.details_dir} (主目录)")
                else:
                    # 回退到当前目录
                    self.output_dir = Path(current_file_dir)
                    self.details_dir = self.output_dir / "details"
                    self.logs_dir = self.output_dir / "logs"
            except Exception as e:
                print(f"[警告] 路径检测失败，使用当前目录: {e}")
                self.output_dir = Path(current_file_dir)
                self.details_dir = self.output_dir / "details"
                self.logs_dir = self.output_dir / "logs"

        # 确保目录存在
        self.details_dir.mkdir(exist_ok=True)
        self.logs_dir.mkdir(exist_ok=True)

        # 已点击商品文件
        self.clicked_products_file = self.logs_dir / f"clicked_products_{self.browser_id_short}.json"

        # 任务状态文件
        self.task_status_file = self.logs_dir / "task_status.json"

        # 加载已点击商品列表
        self.clicked_products = self._load_clicked_products()

        print(f"[浏览器] ID: {self.browser_id_short} | 已点击商品: {len(self.clicked_products)}个")

        # 🔥 新增：已搜索关键词传输功能
        self.searched_keywords_file = self.logs_dir / f"searched_keywords_{self.browser_id_short}.json"
        self.main_keywords_file = None
        self.transfer_interval = 600  # 10分钟传输一次
        self.last_transfer_time = 0
        self.transfer_thread = None
        self.is_transfer_running = False
        
        # 初始化已搜索关键词文件
        self._init_searched_keywords_file()
        
        # 启动关键词传输线程
        self._start_keyword_transfer_thread()

        # 🔥 新增：CSV保存和运行时统计功能初始化
        self._init_csv_functionality()
        
        # 🔥 新增：简化警报状态管理
        self._alarm_played = False  # 警报是否已播放
        self._popup_shown = False   # 弹窗是否已显示

    def wait_for_previous_task(self):
        """🔥 等待上一个任务完成 - 排队机制"""
        print("⏳ 检查任务队列状态...")
        while True:
            try:
                if self.task_status_file.exists():
                    with open(self.task_status_file, 'r', encoding='utf-8') as f:
                        status = json.load(f)

                    # 检查是否有其他任务在运行
                    running_tasks = [task for task, running in status.items() if running]
                    if running_tasks:
                        print(f"⏳ 等待任务完成: {', '.join(running_tasks)}")
                        time.sleep(1)
                        continue
                    else:
                        print("[成功] 任务队列空闲，可以开始执行")
                        break
                else:
                    print("[成功] 任务状态文件不存在，可以开始执行")
                    break
            except Exception as e:
                print(f"[警告] 检查任务状态异常: {e}")
                break

    def set_task_status(self, task_name, running):
        """设置任务状态"""
        try:
            status = {}
            if self.task_status_file.exists():
                with open(self.task_status_file, 'r', encoding='utf-8') as f:
                    status = json.load(f)

            status[task_name] = running
            with open(self.task_status_file, 'w', encoding='utf-8') as f:
                json.dump(status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[错误] 设置任务状态失败: {e}")

    def _init_searched_keywords_file(self):
        """初始化已搜索关键词文件"""
        try:
            if not self.searched_keywords_file.exists():
                initial_data = {
                    'searched_keywords': [],
                    'last_update': datetime.now().isoformat()
                }
                with open(self.searched_keywords_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                print(f"[关键词] 初始化已搜索关键词文件: {self.searched_keywords_file}")
        except Exception as e:
            print(f"[错误] 初始化已搜索关键词文件失败: {e}")

    def _start_keyword_transfer_thread(self):
        """启动关键词传输线程"""
        try:
            if not self.is_transfer_running:
                self.is_transfer_running = True
                self.transfer_thread = threading.Thread(target=self._keyword_transfer_worker, daemon=True)
                self.transfer_thread.start()
                print(f"[关键词] 关键词传输线程已启动，传输间隔: {self.transfer_interval}秒")
        except Exception as e:
            print(f"[错误] 启动关键词传输线程失败: {e}")

    def _keyword_transfer_worker(self):
        """关键词传输工作线程"""
        while self.is_transfer_running:
            try:
                current_time = time.time()
                if current_time - self.last_transfer_time >= self.transfer_interval:
                    self._transfer_searched_keywords()
                    self.last_transfer_time = current_time
                time.sleep(60)  # 每分钟检查一次
            except Exception as e:
                print(f"[错误] 关键词传输工作线程异常: {e}")
                time.sleep(60)

    def _transfer_searched_keywords(self):
        """传输已搜索关键词到主程序"""
        try:
            # 查找主程序目录
            main_dir = self._find_main_directory()
            if not main_dir:
                print("[警告] 未找到主程序目录，跳过关键词传输")
                return

            main_keywords_file = main_dir / "已搜索关键词.json"
            
            # 读取浏览器已搜索关键词
            if not self.searched_keywords_file.exists():
                return

            with open(self.searched_keywords_file, 'r', encoding='utf-8') as f:
                browser_data = json.load(f)

            browser_keywords = set(browser_data.get('searched_keywords', []))

            if not browser_keywords:
                return

            # 🔥 使用文件锁避免多浏览器冲突
            import time
            import random
            
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    # 随机延迟避免竞争条件
                    time.sleep(random.uniform(0.1, 0.5))
                    
                    # 读取主程序已搜索关键词
                    main_keywords = set()
                    main_data = {}
                    if main_keywords_file.exists():
                        with open(main_keywords_file, 'r', encoding='utf-8') as f:
                            main_data = json.load(f)
                        main_keywords = set(main_data.get('searched_keywords', []))

                    # 合并关键词
                    combined_keywords = main_keywords.union(browser_keywords)
                    new_keywords = browser_keywords - main_keywords

                    if new_keywords:
                        # 更新主程序文件
                        updated_data = {
                            'searched_keywords': sorted(list(combined_keywords)),
                            'last_update': datetime.now().isoformat(),
                            'browser_updates': {
                                **main_data.get('browser_updates', {}),
                                self.browser_id_short: {
                                    'last_update': datetime.now().isoformat(),
                                    'keywords_count': len(browser_keywords)
                                }
                            }
                        }

                        with open(main_keywords_file, 'w', encoding='utf-8') as f:
                            json.dump(updated_data, f, ensure_ascii=False, indent=2)

                        print(f"[成功] 关键词传输: +{len(new_keywords)}个")
                    else:
                        pass
                    
                    # 成功完成，跳出重试循环
                    break
                    
                except (OSError, IOError, json.JSONDecodeError) as e:
                    print(f"[警告] 文件操作失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    if attempt == max_retries - 1:
                        print("[错误] 达到最大重试次数，跳过本次传输")
                        return
                    time.sleep(random.uniform(1, 2))  # 等待后重试

        except Exception as e:
            print(f"[错误] 传输已搜索关键词失败: {e}")

    def _find_main_directory(self):
        """查找主程序目录"""
        try:
            current_dir = Path(__file__).parent
            while current_dir.parent != current_dir:
                if (current_dir / "generated_scripts").exists():
                    return current_dir
                current_dir = current_dir.parent
            return None
        except Exception as e:
            print(f"[错误] 查找主程序目录失败: {e}")
            return None

    def add_searched_keyword(self, keyword: str):
        """添加已搜索关键词"""
        try:
            if not self.searched_keywords_file.exists():
                self._init_searched_keywords_file()

            with open(self.searched_keywords_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            keywords = set(data.get('searched_keywords', []))
            if keyword not in keywords:
                keywords.add(keyword)
                data['searched_keywords'] = sorted(list(keywords))
                data['last_update'] = datetime.now().isoformat()

                with open(self.searched_keywords_file, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)

                # 不显示具体的关键词，避免日志过多
                # print(f"[关键词] 新增已搜索关键词: {keyword}")
        except Exception as e:
            print(f"[错误] 添加已搜索关键词失败: {e}")

    def _detect_browser_id(self) -> str:
        """自动检测浏览器ID"""
        try:
            # 从当前目录获取浏览器ID
            current_dir = os.getcwd()
            if 'browser_' in current_dir:
                browser_id = current_dir.split('browser_')[-1]
                return browser_id

            # 从配置文件获取
            config_files = [f for f in os.listdir('.') if f.startswith('config_') and f.endswith('.json')]
            if config_files:
                with open(config_files[0], 'r', encoding='utf-8') as f:
                    config = json.load(f)
                browser_id = config.get('browser_info', {}).get('browser_id')
                if browser_id:
                    return browser_id

            # 🔥 新增：从generated_scripts目录检测浏览器ID
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            parent_dir = os.path.dirname(current_file_dir)
            generated_scripts_dir = os.path.join(parent_dir, "generated_scripts")

            if os.path.exists(generated_scripts_dir):
                try:
                    browser_dirs = [d for d in os.listdir(generated_scripts_dir)
                                  if d.startswith('browser_') and os.path.isdir(os.path.join(generated_scripts_dir, d))]
                    if browser_dirs:
                        # 使用第一个找到的浏览器目录
                        browser_dir = browser_dirs[0]
                        browser_id = browser_dir.replace('browser_', '')
                        print(f"[检测] 从generated_scripts检测到浏览器ID: {browser_id}")
                        return browser_id
                except Exception as e:
                    print(f"[警告] 检测浏览器目录失败: {e}")

            # 🔥 修复硬编码：使用通用默认ID
            return "default_browser_id"
        except Exception as e:
            print(f"[警告] 检测浏览器ID失败: {e}")
            return "default_browser_id"

    def _load_clicked_products(self) -> Set[str]:
        """加载已点击商品列表（内存优化版）"""
        try:
            if self.clicked_products_file.exists():
                with open(self.clicked_products_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        # 🔥 内存优化：限制已点击商品数量为最近10000个
                        valid_ids = []
                        for item in data[-10000:]:  # 只保留最近10000个
                            if isinstance(item, str) and item.isdigit() and len(item) > 6:
                                valid_ids.append(item)
                        print(f"[优化] 加载了{len(valid_ids)}个有效商品ID（限制最多10000个）")
                        return set(valid_ids)
                    elif isinstance(data, dict):
                        clicked_products = data.get('clicked_products', [])
                        # 同样过滤和限制数量
                        valid_ids = []
                        for item in clicked_products[-10000:]:  # 只保留最近10000个
                            if isinstance(item, str) and item.isdigit() and len(item) > 6:
                                valid_ids.append(item)
                        return set(valid_ids)
            else:
                print(f"[信息] 已点击商品文件不存在，创建空文件: {self.clicked_products_file}")
                empty_set = set()
                self._save_clicked_products_with_data(empty_set)
            return set()
        except Exception as e:
            print(f"[警告] 加载已点击商品失败: {e}")
            return set()

    # 🔥 已删除本地保存方法 - 数据直接通过suoyin.py加密上传到服务器

    def is_product_clicked(self, product_id: str) -> bool:
        """检查商品是否已被点击过"""
        return str(product_id) in self.clicked_products

    def mark_product_clicked(self, product_id: str):
        """标记商品为已点击（内存优化版）"""
        self.clicked_products.add(str(product_id))
        
        # 🔥 内存优化：如果已点击商品超过10000个，清理老的一半
        if len(self.clicked_products) > 10000:
            # 保留最近5000个（由于set自动去重）
            recent_products = list(self.clicked_products)[-5000:]
            self.clicked_products = set(recent_products)
            print(f"[优化] 已点击商品超限，清理后保留{len(self.clicked_products)}个")
        
        self._save_clicked_products()

    def _save_clicked_products(self):
        """保存已点击商品列表到文件"""
        try:
            self._save_clicked_products_with_data(self.clicked_products)
        except Exception as e:
            pass

    def _save_clicked_products_with_data(self, clicked_products_set):
        """保存已点击商品数据到文件"""
        try:
            # 确保logs目录存在
            self.logs_dir.mkdir(exist_ok=True)

            # 转换为列表并保存
            clicked_list = list(clicked_products_set)

            with open(self.clicked_products_file, 'w', encoding='utf-8') as f:
                json.dump(clicked_list, f, ensure_ascii=False, indent=2)

        except Exception as e:
            pass


    async def extract_detail_data(self, page) -> Optional[Dict]:
        """
        从详情页抓取window.rawData数据
        """
        try:
            # 检查 window.rawData 是否存在且不为 null
            is_ready = await page.evaluate("() => typeof window.rawData !== 'undefined' && window.rawData !== null")
            
            if is_ready:
                print("✅ 找到 window.rawData，正在提取...")
                # 直接返回JS对象，Playwright会自动将其转换为Python字典
                raw_data = await page.evaluate("() => window.rawData")
                
                if raw_data:
                    # 构建返回数据结构
                    full_data = {
                        'rawData': raw_data,
                        'url': await page.evaluate("() => window.location.href"),
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    # 提取商品ID
                    goods_id = self._extract_goods_id(full_data)
                    if goods_id:
                        print(f"🎉 成功抓取到数据，商品ID: {goods_id}")
                        return {
                            'goods_id': goods_id,
                            'data': full_data,
                            'extract_time': datetime.now().isoformat()
                        }
                    else:
                        print("[警告] 未能提取到商品ID")
                        return None
                else:
                    print("🔴 rawData为空")
                    return None
            else:
                print("ℹ️ 当前页面未找到 window.rawData。")
                return None
                
        except Exception as e:
            print(f"❌ 在提取数据时发生错误: {e}")
            return None

    def _extract_goods_id(self, raw_data: Dict) -> Optional[str]:
        """从rawData中提取商品ID"""
        try:
            # 尝试多个可能的路径
            paths = [
                ['rawData', 'store', 'initDataObj', 'goods', 'goodsID'],
                ['rawData', 'store', 'initDataObj', 'goods', 'goodsId'],
                ['rawData', 'store', 'initDataObj', 'queries', 'goods_id'],
                ['rawData', 'goods', 'goodsID'],
                ['rawData', 'goods', 'goodsId']
            ]

            for path in paths:
                try:
                    value = raw_data
                    for key in path:
                        value = value[key]
                    if value:
                        return str(value)
                except (KeyError, TypeError):
                    continue

            # 从URL中提取
            url = raw_data.get('url', '')
            if url:
                import re
                patterns = [
                    r'goods_id[=\/](\d+)',
                    r'\/g\/(\d+)',
                    r'\/goods\/(\d+)',
                    r'\/(\d{10,})'
                ]
                for pattern in patterns:
                    match = re.search(pattern, url)
                    if match:
                        return match.group(1)

            return None
        except Exception as e:
            print(f"[警告] 提取商品ID失败: {e}")
            return None

    async def process_detail_page(self, page, target_goods_id: str = None) -> bool:
        """
        处理详情页：抓取数据并保存

        Args:
            page: Playwright页面对象
            target_goods_id: 目标商品ID（可选，用于验证）

        Returns:
            是否处理成功
        """
        try:
            # 1. 抓取数据
            extracted_data = await self.extract_detail_data(page)
            if not extracted_data:
                print("[失败] 数据抓取失败")
                # 启动警报和弹窗系统
                await self._start_alert_system()
                return False

            goods_id = extracted_data['goods_id']

            # 🔥 新增：如果指定了目标商品ID，进行验证
            if target_goods_id and str(goods_id) != str(target_goods_id):
                print(f"[警告] 商品ID不匹配: 期望={target_goods_id}, 实际={goods_id}")
                # 继续处理，但使用指定的ID
                goods_id = str(target_goods_id)

            # 2. 检查是否已点击过
            if self.is_product_clicked(goods_id):
                print(f"[跳过] 商品 {goods_id} 已被点击过")
                return True

            # 3. 标记为已点击
            self.mark_product_clicked(goods_id)

            # 🔥 已删除本地保存功能 - 现在只使用加密上传到服务器的方式
            # 详情页数据处理已集成到 product_clicker.py 中
            # 使用三重加密压缩上传到服务器，然后从服务器下载到本地

            print(f"[成功] 商品数据抓取成功: ID:{goods_id}")
            print(f"[INFO] 数据处理已移至 product_clicker.py 的集成模式")
            return True

        except Exception as e:
            print(f"[错误] 处理详情页失败: {e}")
            return False

    async def _start_alert_system(self):
        """🔥 简化的警报系统：直接弹窗和5声声音警报 + UI暂停配合"""
        try:
            print("🚨 详情页数据抓取失败，启动警报系统")
            
            # 重置警报状态，允许重新播放
            self.reset_alarm_status()
            
            # 🔥 新增：创建暂停标志文件，让UI显示暂停状态
            await self._create_pause_flag_for_ui()
            
            # 直接播放5声警报
            await self._play_alarm_sound()
            
            # 直接显示弹窗
            await self._show_alert_popup()
            
            print("[成功] 警报系统启动完成：5声警报 + 弹窗 + UI暂停状态")
            
            # 🔥 新增：等待用户通过UI继续程序
            await self._wait_for_ui_resume()
            
        except Exception as e:
            print(f"[错误] 启动警报系统失败: {e}")

    async def _create_pause_flag_for_ui(self):
        """创建暂停标志文件，让UI显示暂停状态"""
        try:
            # 构建暂停标志文件路径
            pause_flag_file = self.output_dir / "pause_flag.txt"
            
            # 确保目录存在
            pause_flag_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建暂停标志文件
            with open(pause_flag_file, 'w', encoding='utf-8') as f:
                f.write(f"paused_at:{time.time()}")
            
            print(f"[成功] 已创建暂停标志文件: {pause_flag_file}")
            print("📱 UI将显示暂停状态，用户可右键点击'继续程序'")
            
        except Exception as e:
            print(f"[警告] 创建暂停标志文件失败: {e}")

    async def _wait_for_ui_resume(self):
        """等待用户通过UI继续程序"""
        try:
            print("⏳ 等待用户通过UI继续程序...")
            
            # 构建暂停标志文件路径
            pause_flag_file = self.output_dir / "pause_flag.txt"
            
            # 等待暂停标志文件被删除（用户点击UI继续程序）
            while pause_flag_file.exists():
                await asyncio.sleep(1)  # 每秒检查一次，但不输出日志
            
            print("[成功] 检测到UI继续程序信号，恢复脚本执行")
            
        except Exception as e:
            print(f"[警告] 等待UI继续程序失败: {e}")

    async def _play_alarm_sound(self):
        """🔥 播放5声警报声音"""
        try:
            # 检查是否已经播放过警报
            if self._alarm_played:
                print("🔊 警报已播放过，跳过重复播放")
                return
            
            # 标记为已播放
            self._alarm_played = True
            print("🔊 开始播放5声警报...")
            
            def play_sound():
                try:
                    import winsound
                    # 🔥 修复：确保在UI环境下也能播放声音
                    for i in range(5):
                        winsound.Beep(1000, 500)  # 1000Hz, 0.5秒
                        time.sleep(0.1)  # 短暂间隔
                    print("🔊 5声警报播放完成")
                except Exception as e:
                    print(f"[警告] 播放声音异常: {e}")
                    # 🔥 新增：备用声音方案
                    try:
                        import os
                        # 使用系统命令播放声音
                        os.system('echo -e "\a\a\a\a\a"')  # 5次蜂鸣
                        print("🔊 使用备用声音方案完成")
                    except Exception as e2:
                        print(f"[警告] 备用声音方案也失败: {e2}")
            
            # 启动声音线程
            sound_thread = threading.Thread(target=play_sound, daemon=True)
            sound_thread.start()
            
        except Exception as e:
            print(f"[警告] 播放声音失败: {e}")

    async def _show_alert_popup(self):
        """🔥 显示警报弹窗"""
        try:
            # 检查是否已经显示过弹窗
            if self._popup_shown:
                print("📢 弹窗已显示过，跳过重复显示")
                return
            
            # 标记为已显示
            self._popup_shown = True
            print("📢 显示警报弹窗...")
            
            def show_popup():
                try:
                    import tkinter as tk
                    from tkinter import messagebox
                    
                    # 🔥 修复：确保在UI环境下也能显示弹窗
                    try:
                        # 创建隐藏的根窗口
                        root = tk.Tk()
                        root.withdraw()  # 隐藏主窗口
                        root.attributes('-topmost', True)  # 置顶显示
                        
                        # 🔥 新增：强制弹窗显示在屏幕中央
                        # 获取屏幕尺寸
                        screen_width = root.winfo_screenwidth()
                        screen_height = root.winfo_screenheight()
                        
                        # 计算弹窗位置（屏幕中央）
                        popup_width = 400
                        popup_height = 300
                        x = (screen_width - popup_width) // 2
                        y = (screen_height - popup_height) // 2
                        
                        # 设置弹窗位置
                        root.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
                        
                        # 显示弹窗
                        messagebox.showwarning(
                            "🚨 系统警报 - 需要人工处理",
                            "详情页数据抓取失败！\n\n可能原因：\n• 遇到滑块验证\n• 网络连接问题\n• 页面加载异常\n\n请人工验证并处理后继续运行脚本。"
                        )
                        
                        # 销毁窗口
                        root.destroy()
                        
                        print("📢 弹窗已显示：请人工验证处理")
                        
                    except Exception as e:
                        print(f"[警告] Tkinter弹窗失败: {e}")
                        # 🔥 新增：备用弹窗方案
                        try:
                            import subprocess
                            # 使用系统命令显示弹窗，强制显示在屏幕中央
                            subprocess.run([
                                'powershell', 
                                '-Command', 
                                'Add-Type -AssemblyName System.Windows.Forms; $form = New-Object System.Windows.Forms.Form; $form.Text = "🚨 系统警报"; $form.Size = New-Object System.Drawing.Size(400,300); $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen; $form.TopMost = $true; $label = New-Object System.Windows.Forms.Label; $label.Text = "详情页数据抓取失败！\n\n请人工验证并处理后继续运行脚本。"; $label.AutoSize = $true; $label.Location = New-Object System.Drawing.Point(20,20); $form.Controls.Add($label); $form.ShowDialog()'
                            ], shell=True)
                            print("📢 使用备用弹窗方案完成")
                        except Exception as e2:
                            print(f"[警告] 备用弹窗方案也失败: {e2}")
                            
                except Exception as e:
                    print(f"[警告] 弹窗显示失败: {e}")
            
            # 启动弹窗线程
            popup_thread = threading.Thread(target=show_popup, daemon=True)
            popup_thread.start()
            
        except Exception as e:
            print(f"[警告] 启动弹窗线程失败: {e}")

    def reset_alarm_status(self):
        """重置警报状态，允许重新播放警报"""
        self._alarm_played = False
        self._popup_shown = False
        print("🔄 警报状态已重置，可以重新播放")


    def _extract_goods_basic_info(self, raw_data: Dict) -> Dict[str, str]:
        """🔥 提取商品基本信息用于日志显示"""
        try:
            info = {
                'name': '未知商品',
                'price': '未知价格',
                'sales': '未知销量'
            }

            # 尝试提取商品名称
            name_paths = [
                ['rawData', 'store', 'initDataObj', 'goods', 'goodsName'],
                ['rawData', 'store', 'initDataObj', 'goods', 'goods_name'],
                ['rawData', 'goods', 'goodsName'],
                ['rawData', 'goods', 'goods_name'],
                ['rawData', 'store', 'initDataObj', 'goods', 'title']
            ]

            for path in name_paths:
                try:
                    value = raw_data
                    for key in path:
                        value = value[key]
                    if value and isinstance(value, str):
                        info['name'] = value[:30] + ('...' if len(value) > 30 else '')  # 限制长度
                        break
                except (KeyError, TypeError):
                    continue

            # 尝试提取价格
            price_paths = [
                ['rawData', 'store', 'initDataObj', 'goods', 'minOnSaleGroupPrice'],
                ['rawData', 'store', 'initDataObj', 'goods', 'price'],
                ['rawData', 'goods', 'price'],
                ['rawData', 'store', 'initDataObj', 'goods', 'marketPrice']
            ]

            for path in price_paths:
                try:
                    value = raw_data
                    for key in path:
                        value = value[key]
                    if value:
                        # 价格可能是数字或字符串，统一处理
                        price_val = float(value) / 100 if isinstance(value, int) and value > 1000 else float(value)
                        info['price'] = f"¥{price_val:.2f}"
                        break
                except (KeyError, TypeError, ValueError):
                    continue

            # 尝试提取销量
            sales_paths = [
                ['rawData', 'store', 'initDataObj', 'goods', 'soldQuantity'],
                ['rawData', 'store', 'initDataObj', 'goods', 'sales'],
                ['rawData', 'goods', 'soldQuantity'],
                ['rawData', 'goods', 'sales']
            ]

            for path in sales_paths:
                try:
                    value = raw_data
                    for key in path:
                        value = value[key]
                    if value is not None:
                        sales_num = int(value)
                        if sales_num >= 10000:
                            info['sales'] = f"{sales_num//10000}万+"
                        else:
                            info['sales'] = str(sales_num)
                        break
                except (KeyError, TypeError, ValueError):
                    continue

            return info

        except Exception as e:
            print(f"[警告] 提取商品基本信息失败: {e}")
            return {
                'name': '未知商品',
                'price': '未知价格',
                'sales': '未知销量'
            }

    async def _upload_to_server(self, goods_id: str, data: Dict) -> bool:
        """
        预留：加密上传数据到服务器

        Args:
            goods_id: 商品ID
            data: 要上传的数据

        Returns:
            是否上传成功
        """
        # TODO: 实现加密上传逻辑
        # 1. 加密数据
        # 2. 上传到服务器
        # 3. 返回结果
        print(f"[预留] 上传商品 {goods_id} 到服务器（功能待实现）")
        return True



    # ==================== 🔥 新增：product_clicker集成所需的方法 ====================

    def encrypt_compress_for_cloud(self, raw_data: Dict) -> Optional[Dict]:
        """
        云端上传的加密压缩方案 - 与服务器端完全一致
        使用与pdd_server.py相同的加密逻辑

        Args:
            raw_data: 原始数据

        Returns:
            包含加密数据和统计信息的字典，失败返回None
        """
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            import lzma
            import base64
            import json

            # 服务器端相同的加密密码
            USER_PASSWORD = "Ylw5555+Yufeizi-Haha23=SM"
            
            # 生成与服务器端完全相同的密钥和IV
            def generate_keys_from_password(password):
                # 生成32字节AES密钥
                key_kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'pdd_aes_key_salt_2025',
                    iterations=100000,
                )
                aes_key = key_kdf.derive(password.encode())
                
                # 生成16字节IV
                iv_kdf = PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=16,
                    salt=b'pdd_aes_iv_salt_2025',
                    iterations=50000,
                )
                aes_iv = iv_kdf.derive(password.encode())
                
                return aes_key, aes_iv
            
            AES_KEY, AES_IV = generate_keys_from_password(USER_PASSWORD)

            # 超紧凑JSON压缩算法 - 与服务器端完全一致
            def ultra_compact_json(data):
                key_mapping = {
                    'goodsName': 'goo', 'originalPrice': 'ori', 'discount': 'dis',
                    'sales': 'sal', 'rating': 'rat', 'reviewCount': 'rev',
                    'shopName': 'sho', 'category': 'cat', 'description': 'des',
                    'imageUrl': 'img', 'detailUrl': 'url', 'brand': 'bra',
                    'specifications': 'spe', 'attributes': 'att', 'tags': 'tag',
                    'promotion': 'pro', 'shipping': 'shi', 'warranty': 'war',
                    'comments': 'com', 'questions': 'que', 'answers': 'ans'
                }
                
                important_keys = ['goods_id', 'goodsId', 'product_id', 'id', 'title', 'price', 'url']
                
                def compress_recursive(obj, depth=0):
                    if depth > 10:
                        return obj
                        
                    if isinstance(obj, dict):
                        compressed = {}
                        for key, value in obj.items():
                            if key in important_keys:
                                new_key = key
                            else:
                                new_key = key_mapping.get(key, key[:3] if len(key) > 3 else key)
                            
                            compressed_value = compress_recursive(value, depth + 1)
                            
                            if compressed_value not in [None, '', [], {}]:
                                compressed[new_key] = compressed_value
                                
                        return compressed
                        
                    elif isinstance(obj, list):
                        if len(obj) > 5:
                            return [compress_recursive(item, depth + 1) for item in obj[:5]]
                        else:
                            return [compress_recursive(item, depth + 1) for item in obj]
                            
                    elif isinstance(obj, str):
                        return obj[:200] if len(obj) > 200 else obj
                        
                    else:
                        return obj
                
                return compress_recursive(data)

            # AES加密函数 - 与服务器端完全一致
            def aes_encrypt(data, key, iv):
                cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
                encryptor = cipher.encryptor()
                
                # PKCS7填充
                block_size = 16
                padding_length = block_size - (len(data) % block_size)
                padded_data = data + bytes([padding_length] * padding_length)
                
                encrypted = encryptor.update(padded_data) + encryptor.finalize()
                return base64.b64encode(encrypted).decode('utf-8')

            # 步骤1：保持原始完整数据（不使用超紧凑压缩）
            json_str = json.dumps(raw_data, ensure_ascii=False, separators=(',', ':'))
            original_size = len(json_str)
            
            # 步骤2：LZMA压缩（最高压缩比）
            compressed = lzma.compress(json_str.encode('utf-8'), preset=9)
            compressed_size = len(compressed)
            
            # 步骤3：AES加密
            encrypted = aes_encrypt(compressed, AES_KEY, AES_IV)
            final_size = len(encrypted)

            # 4. 计算压缩率
            compression_ratio = f"{(1 - final_size / original_size) * 100:.1f}%"

            # 🔥 只显示保存成功的日志，其他不显示
            # print(f"[加密] 完成: {compression_ratio}")

            return {
                'encrypted_data': encrypted,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'final_size': final_size,
                'compression_ratio': compression_ratio,
                'encryption_method': 'AES-256 + LZMA + 完整JSON'
            }

        except Exception as e:
            print(f"[错误] 数据加密压缩失败: {e}")
            return None

    async def upload_to_server(self, encrypted_data: str, goods_id: str) -> bool:
        """
        上传加密数据到真实服务器

        Args:
            encrypted_data: 加密后的数据
            goods_id: 商品ID

        Returns:
            是否上传成功
        """
        try:
            import requests
            import asyncio
            
            # 获取服务器配置
            cloud_config = self.config_mgr.get_config().get('cloud_server', {})
            server_url = cloud_config.get('server_url', 'http://localhost:8888')
            client_id = cloud_config.get('client_id', 'PDD_CLIENT_001')
            
            # 构建上传数据
            upload_data = {
                'goods_id': goods_id,
                'encrypted_data': encrypted_data,
                'browser_id': self.browser_id,
                'client_id': client_id,
                'timestamp': datetime.now().isoformat(),
                'encryption': 'AES-256 + LZMA + 超紧凑JSON'
            }
            
            # 发送POST请求到服务器
            def sync_upload():
                # 🔥 修复：根据server_url自动判断端点路径
                if server_url.endswith('/api'):
                    upload_endpoint = f"{server_url}/upload"
                elif '/api/' in server_url:
                    upload_endpoint = server_url  # server_url已包含完整路径
                else:
                    upload_endpoint = f"{server_url}/upload"
                    
                response = requests.post(
                    upload_endpoint,
                    json=upload_data,
                    timeout=30,
                    headers={'Content-Type': 'application/json'}
                )
                return response
            
            # 在线程池中执行同步请求
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, sync_upload)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'success':
                    return True
                else:
                    print(f"[错误] 服务器返回错误: {result.get('message', '未知错误')}")
                    return False
            else:
                print(f"[错误] 服务器响应错误: HTTP {response.status_code}")
                return False

        except Exception as e:
            print(f"[错误] 上传到服务器失败: {e}")
            return False

    async def download_and_save_from_server(self, goods_id: str, original_data: dict = None) -> bool:
        """从服务器下载数据并保存"""
        try:
            import requests
            import asyncio
            import json

            # 预售检测
            if original_data:
                presale_info = self._extract_presale_info(original_data)
                if presale_info:
                    return True

            # 获取服务器配置
            config = self.config_mgr.get_config()
            cloud_config = config.get('cloud_server', {})
            server_config = config.get('server_config', {})
            
            # 优先使用cloud_server.server_url，其次使用server_config.upload_url
            server_url = cloud_config.get('server_url') or server_config.get('upload_url', 'http://localhost:8888')
            
            # 构建下载地址
            if server_url.endswith('/api'):
                download_endpoint = f"{server_url}/download/{goods_id}"
            elif '/upload' in server_url:
                download_endpoint = server_url.replace('/upload', f'/download/{goods_id}')
            else:
                download_endpoint = f"{server_url}/download/{goods_id}"

            # 下载数据
            import aiohttp
            
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(download_endpoint) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data:
                            # 确保details目录存在
                            import os
                            from pathlib import Path
                            current_file_dir = os.path.dirname(os.path.abspath(__file__))
                            project_root = current_file_dir
                            while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                                parent = os.path.dirname(project_root)
                                if parent == project_root:
                                    break
                                project_root = parent
                            
                            details_dir = Path(project_root) / "details"
                            details_dir.mkdir(exist_ok=True)
                            
                            # 保存数据为TXT文档（以商品ID命名）
                            txt_file = details_dir / f"{goods_id}.txt"
                            with open(txt_file, 'w', encoding='utf-8') as f:
                                json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
                                f.write(json_str)
                            
                            # 验证保存的文件
                            if not (txt_file.exists() and txt_file.stat().st_size > 0):
                                return False
                            
                            # 更新统计
                            self.runtime_parsed_count += 1
                            self._update_runtime_stats()
                            
                            # 保存CSV数据
                            if original_data:
                                csv_data = self._extract_csv_fields(original_data)
                                if csv_data and csv_data.get('商品ID'):
                                    self._save_to_csv_without_count_update(csv_data.copy())
                            
                            return True
                    else:
                        return False

        except Exception as e:
            return False

    # ==================== 云端上传功能（已集成到suoyin.py） ====================
    # 🔥 本地保存功能已删除 - 数据直接通过suoyin.py加密上传到服务器
    # 🔥 Excel导出功能已删除 - 避免重复的Excel导出，使用统一的保存机制

    # ==================== 🔥 新增：CSV保存和运行时统计功能 ====================
    
    def _init_csv_functionality(self):
        """初始化CSV保存和运行时统计功能"""
        try:
            # 运行时统计初始化
            self.runtime_parsed_count = 0
            
            # 🔥 新版路径：保存到主目录的output和cache文件夹
            # 找到主目录（项目根目录）
            current_file_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = current_file_dir
            
            # 向上查找项目根目录（包含generated_scripts的目录）
            while project_root and not os.path.exists(os.path.join(project_root, "generated_scripts")):
                parent = os.path.dirname(project_root)
                if parent == project_root:  # 已经到达根目录
                    break
                project_root = parent
            
            # 创建主目录的output和cache文件夹
            main_output_dir = Path(project_root) / "output"
            main_cache_dir = Path(project_root) / "cache"
            main_output_dir.mkdir(exist_ok=True)
            main_cache_dir.mkdir(exist_ok=True)
            
            # CSV文件路径（保存到主目录output文件夹，文件名加上浏览器ID）
            self.csv_file_path = main_output_dir / f"商品数据_{self.browser_id}.csv"
            
            # 统计JSON文件路径（保存到主目录cache文件夹，文件名加上浏览器ID）
            self.stats_file_path = main_cache_dir / f"统计数量_{self.browser_id}.json"
            
            # 创建CSV文件头（如果文件不存在）
            self._create_csv_header()
            
            # 初始化统计JSON文件
            self._init_stats_file()
            
            print(f"[CSV] CSV功能已初始化（新版路径）")
            print(f"[CSV] 主目录output: {main_output_dir}")
            print(f"[CSV] 主目录cache: {main_cache_dir}")
            print(f"[CSV] CSV文件: {self.csv_file_path}")
            print(f"[CSV] 统计文件: {self.stats_file_path}")
            
        except Exception as e:
            print(f"[错误] CSV功能初始化失败: {e}")
    
    def _create_csv_header(self):
        """创建CSV文件头（如果文件不存在）"""
        try:
            if not self.csv_file_path.exists():
                headers = [
                    "商品ID", "商品名称", "商品链接", "当前价格", "券后价", "商品销量", "店铺销量", 
                    "高清图片", "商家ID", "店铺名称", "发货时间", "发货地", "商品类目", "评价数量", "正在拼", "店铺商品数量", "部分预售", "24小时发货", "新品", "上架时间", "采集时间"
                ]
                
                import csv
                with open(self.csv_file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                print(f"[CSV] CSV文件头已创建")
        except Exception as e:
            print(f"[错误] 创建CSV文件头失败: {e}")
    
    def _init_stats_file(self):
        """初始化统计JSON文件"""
        try:
            stats_data = {
                "解析数量": self.runtime_parsed_count,
                "最后更新": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(self.stats_file_path, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
            print(f"[CSV] 统计文件已初始化: {self.runtime_parsed_count}个")
        except Exception as e:
            print(f"[错误] 初始化统计文件失败: {e}")
    
    def _flexible_get(self, data: Dict, field_names: List[str], default_value=None):
        """灵活获取字段值（忽略大小写和_符号）"""
        try:
            # 首先尝试直接匹配
            for field_name in field_names:
                if field_name in data:
                    return data[field_name]
            
            # 如果直接匹配失败，尝试忽略大小写和_符号的匹配
            data_keys = list(data.keys())
            for field_name in field_names:
                # 标准化字段名（移除_符号，转小写）
                normalized_field = field_name.replace("_", "").lower()
                
                for data_key in data_keys:
                    normalized_data_key = data_key.replace("_", "").lower()
                    if normalized_field == normalized_data_key:
                        return data[data_key]
            
            # 如果还没找到，尝试在嵌套对象中查找
            try:
                goods = data.get("store", {}).get("initDataObj", {}).get("goods", {})
                if goods:
                    for field_name in field_names:
                        if field_name in goods:
                            return goods[field_name]
                    
                    # 在goods中也尝试忽略大小写匹配
                    goods_keys = list(goods.keys())
                    for field_name in field_names:
                        normalized_field = field_name.replace("_", "").lower()
                        for goods_key in goods_keys:
                            normalized_goods_key = goods_key.replace("_", "").lower()
                            if normalized_field == normalized_goods_key:
                                return goods[goods_key]
            except:
                pass
            
            return default_value
        except Exception:
            return default_value

    def _safe_price_convert(self, price_value) -> float:
        """安全转换价格值"""
        try:
            if price_value is None or price_value == "":
                return 0.0
            
            # 如果是字符串，尝试转换为数字
            if isinstance(price_value, str):
                import re
                # 移除非数字字符（除了小数点）
                price_str = re.sub(r"[^0-9.]", "", str(price_value))
                if price_str:
                    price_value = float(price_str)
                else:
                    return 0.0
            
            # 转换为浮点数
            price_float = float(price_value)
            
            # 如果价格大于1000，可能是分为单位，需要转换为元
            if price_float > 1000:
                return round(price_float / 100, 2)
            else:
                return round(price_float, 2)
                
        except Exception:
            return 0.0

    def _safe_int_convert(self, int_value) -> int:
        """安全转换整数值"""
        try:
            if int_value is None or int_value == "":
                return 0
            
            # 如果是字符串，尝试转换为数字
            if isinstance(int_value, str):
                import re
                # 移除非数字字符
                int_str = re.sub(r"[^0-9]", "", str(int_value))
                if int_str:
                    return int(int_str)
                else:
                    return 0
            
            return int(int_value)
        except Exception:
            return 0

    def _extract_csv_fields(self, raw_data: Dict) -> Optional[Dict]:
        """从rawData提取CSV需要的字段"""
        try:
            if not raw_data or 'rawData' not in raw_data:
                return None
            
            data = raw_data['rawData']
            
            # 从rawData中提取goods对象
            goods = data.get('store', {}).get('initDataObj', {}).get('goods', {})
            
            # 提取图标信息
            icon_info = self._extract_icon_info(data)
            
            # 提取上架时间
            upload_time = self._extract_upload_time(data)
            
            # 按照要求的字段结构构建CSV数据
            csv_data = {
                '商品ID': str(self._flexible_get(data, ['goodsID', 'goods_id', 'id'], '') or ''),
                '商品名称': self._flexible_get(data, ['goodsName', 'goods_name', 'title'], '') or '',
                '商品链接': raw_data.get('url', '') or '',
                '当前价格': self._safe_price_convert(self._flexible_get(data, ['minOnSaleGroupPrice', 'price', 'min_price', 'current_price'], 0)),
                '券后价': self._safe_price_convert(self._flexible_get(data, ['minOnSaleGroupPrice', 'coupon_price', 'price'], 0)),
                '商品销量': self._extract_goods_sales(data) or 0,
                '店铺销量': self._extract_store_sales(data) or '',
                '高清图片': self._flexible_get(data, ['hdThumbUrl', 'thumbUrl', 'image_url', 'thumb_url'], '') or '',
                '商家ID': str(self._flexible_get(data, ['mallID', 'mall_id', 'merchant_id'], '') or ''),
                '店铺名称': self._extract_shop_name(data) or '',
                '发货时间': self._extract_delivery_time(data) or '',
                '发货地': self._extract_delivery_location(data) or '',
                '商品类目': self._extract_category_info(data) or '',
                '评价数量': self._extract_review_count(data) or 0,
                '正在拼': self._extract_grouping_info(data) or '',
                '店铺商品数量': self._extract_store_count(data) or '',
                '部分预售': self._extract_presale_info(data) or '',
                '24小时发货': icon_info.get('has_24h_shipping', '否'),
                '新品': icon_info.get('has_new_product', '否'),
                '上架时间': upload_time or '',
                '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return csv_data
            
        except Exception as e:
            print(f"[错误] 提取CSV字段失败: {e}")
            return None
    
    def _extract_icon_info(self, data: Dict) -> Dict:
        """提取图标相关信息"""
        try:
            icon_info = {
                'has_24h_shipping': '否',
                'has_new_product': '否'
            }
            
            # 从商品属性中提取图标信息
            goods_property = data.get('store', {}).get('initDataObj', {}).get('goods', {}).get('goodsProperty', [])
            
            for prop in goods_property:
                if prop.get('key') == '24小时发货':
                    icon_info['has_24h_shipping'] = '是'
                elif prop.get('key') == '新品':
                    icon_info['has_new_product'] = '是'
            
            return icon_info
        except Exception:
            return {
                'has_24h_shipping': '否',
                'has_new_product': '否'
            }
    
    
    
    def _extract_category_info(self, data: Dict) -> str:
        """提取商品分类信息"""
        try:
            # 尝试获取分类链
            cat1 = self._flexible_get(data, ['cat1Name', 'category1', 'catName1'], '')
            cat2 = self._flexible_get(data, ['cat2Name', 'category2', 'catName2'], '')
            cat3 = self._flexible_get(data, ['cat3Name', 'category3', 'catName3'], '')
            
            # 构建分类链
            categories = [cat for cat in [cat1, cat2, cat3] if cat]
            return ' > '.join(categories) if categories else ''
        except:
            return ''
    

    def _extract_upload_time(self, data: Dict) -> str:
        """提取上架时间"""
        try:
            # 从高清图片URL中提取时间
            goods = data.get('store', {}).get('initDataObj', {}).get('goods', {})
            hd_thumb_url = goods.get('hdThumbUrl', '')
            thumb_url = goods.get('thumbUrl', '')
            
            # 优先使用高清图片URL，如果没有则使用普通图片URL
            url = hd_thumb_url if hd_thumb_url else thumb_url
            
            if url:
                import re
                # 从URL中提取日期，格式如：2025-07-12
                match = re.search(r'/(\d{4}-\d{2}-\d{2})/', url)
                if match:
                    return match.group(1)
            
            return ''
        except Exception:
            return ''
    
    def _extract_delivery_time(self, data: Dict) -> str:
        """提取发货时间（deliveryTime字段）"""
        try:
            # 尝试从多个可能的位置获取发货时间
            delivery_time_paths = [
                ['store', 'initDataObj', 'ui', 'deliveryTimeV2Section', 'mainText'],
                ['store', 'initDataObj', 'shipping', 'deliveryTime'],
                ['shipping', 'deliveryTime'],
                ['deliveryTime']
            ]
            
            for path in delivery_time_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return str(value)
                except (KeyError, TypeError):
                    continue
                    
            return ''
        except Exception:
            return ''

    def _extract_shop_name(self, data: Dict) -> str:
        """提取店铺名称（mallName字段）"""
        try:
            # 尝试从多个可能的位置获取店铺名称
            shop_name_paths = [
                ['store', 'initDataObj', 'mall', 'mallName'],
                ['mall', 'mallName'],
                ['mallName']
            ]
            
            for path in shop_name_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return str(value)
                except (KeyError, TypeError):
                    continue
                    
            return ''
        except Exception:
            return ''

    def _extract_presale_info(self, data: Dict) -> str:
        """提取部分预售信息（click_notice字段），只要字段存在就跳过保存"""
        try:
            # 尝试从多个可能的位置获取预售信息
            presale_paths = [
                ['store', 'initDataObj', 'goods', 'click_notice'],
                ['goods', 'click_notice'],
                ['click_notice']
            ]
            
            for path in presale_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        # 只要click_notice字段存在且有内容，就返回该内容（后续会跳过保存）
                        return str(value)
                except (KeyError, TypeError):
                    continue
                    
            return ''  # 字段不存在或为空，返回空字符串（正常保存）
        except Exception:
            return ''

    def _extract_delivery_location(self, data: Dict) -> str:
        """提取发货地（shippingLocation字段）"""
        try:
            # 尝试从多个可能的位置获取发货地
            location_paths = [
                ['store', 'initDataObj', 'ui', 'deliveryTimeV2Section', 'subText'],
                ['store', 'initDataObj', 'shipping', 'shippingLocation'],
                ['store', 'initDataObj', 'shipping', 'originPlace'],
                ['shipping', 'originPlace'],
                ['shipping', 'shippingLocation'],
                ['shippingLocation'],
                ['originPlace']
            ]
            
            for path in location_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return str(value)
                except (KeyError, TypeError):
                    continue
            
            # 备用方案：从UI文本中提取发货地
            try:
                delivery_section = data.get('store', {}).get('initDataObj', {}).get('ui', {}).get('deliveryTimeV2Section', {})
                sub_text = delivery_section.get('subText', '')
                if '发货' in sub_text:
                    import re
                    match = re.search(r'(.+?)发货', sub_text)
                    if match:
                        return match.group(1)
            except:
                pass
                    
            return ''
        except Exception:
            return ''

    def _extract_category_info(self, data: Dict) -> str:
        """提取商品类目"""
        try:
            cat_names = []
            
            # 按顺序提取cat1Name到cat4Name
            for i in range(1, 5):
                cat_name_paths = [
                    ['store', 'initDataObj', 'goods', f'cat{i}Name'],
                    ['goods', f'cat{i}Name'],
                    [f'cat{i}Name']
                ]
                
                for path in cat_name_paths:
                    try:
                        value = data
                        for key in path:
                            value = value[key]
                        if value is not None and value != '':
                            cat_names.append(str(value))
                            break
                    except (KeyError, TypeError):
                        continue
            
            # 按照顺序连接，没有的分类不显示
            return '-'.join(cat_names) if cat_names else ''
        except Exception:
            return ''

    def _extract_review_count(self, data: Dict) -> int:
        """提取评价数量（reviewNum字段）"""
        try:
            # 尝试从多个可能的位置获取评价数量
            review_paths = [
                ['store', 'initDataObj', 'review', 'reviewNum'],
                ['review', 'reviewNum'],
                ['reviewNum']
            ]
            
            for path in review_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return int(value) if value else 0
                except (KeyError, TypeError, ValueError):
                    continue
                    
            return 0
        except Exception:
            return 0

    def _extract_goods_sales(self, data: Dict) -> int:
        """提取商品销量（sideSalesTip）"""
        try:
            # 尝试从多个可能的位置获取商品销量
            sales_paths = [
                ['store', 'initDataObj', 'goods', 'sideSalesTip'],
                ['store', 'initDataObj', 'goods', 'soldQuantity'],
                ['store', 'initDataObj', 'goods', 'sales'],
                ['goods', 'sideSalesTip'],
                ['goods', 'soldQuantity'],
                ['goods', 'sales'],
                ['sideSalesTip'],
                ['soldQuantity']
            ]
            
            for path in sales_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return self._safe_int_convert(value)
                except (KeyError, TypeError):
                    continue
                    
            return 0
        except Exception:
            return 0

    def _extract_store_sales(self, data: Dict) -> str:
        """提取店铺销量（salesTip）"""
        try:
            # 尝试从多个可能的位置获取店铺销量提示
            sales_tip_paths = [
                ['store', 'initDataObj', 'goods', 'salesTip'],
                ['store', 'initDataObj', 'goods', 'sales_tip'],
                ['goods', 'salesTip'],
                ['goods', 'sales_tip'],
                ['salesTip'],
                ['sales_tip']
            ]
            
            for path in sales_tip_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return str(value)
                except (KeyError, TypeError):
                    continue
                    
            return ''
        except Exception:
            return ''

    def _extract_grouping_info(self, data: Dict) -> str:
        """提取正在拼数量（groupsTotal字段）"""
        try:
            # 尝试从多个可能的位置获取正在拼数量
            grouping_paths = [
                ['store', 'initDataObj', 'groupingInfo', 'groupsTotal'],
                ['store', 'initDataObj', 'groupingInfo', 'groupingNum'],
                ['groupingInfo', 'groupsTotal'],
                ['groupingInfo', 'groupingNum'],
                ['groupsTotal'],
                ['groupingNum']
            ]
            
            for path in grouping_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        return str(value)
                except (KeyError, TypeError):
                    continue
                    
            return ''
        except Exception:
            return ''

    def _extract_store_count(self, data: Dict) -> str:
        """提取店铺数量（goodsNumDesc，去掉'商品数量：'只留数字）"""
        try:
            # 尝试从多个可能的位置获取店铺商品数量描述
            store_count_paths = [
                ['store', 'initDataObj', 'goods', 'goodsNumDesc'],
                ['store', 'initDataObj', 'mall', 'goodsNumDesc'],
                ['goods', 'goodsNumDesc'],
                ['goodsNumDesc']
            ]
            
            for path in store_count_paths:
                try:
                    value = data
                    for key in path:
                        value = value[key]
                    if value is not None and value != '':
                        raw_value = str(value)
                        # 去掉"商品数量："前缀，只保留数字
                        import re
                        # 提取数字部分
                        numbers = re.findall(r'\d+', raw_value)
                        if numbers:
                            return numbers[0]  # 返回第一个数字
                        return raw_value  # 如果没有数字，返回原始值
                except (KeyError, TypeError):
                    continue
                    
            return ''
        except Exception:
            return ''

    def _save_to_csv(self, csv_data: Dict) -> bool:
        """保存数据到CSV文件（增量追加）"""

        try:
            import csv
            
            # 按照CSV头的顺序准备数据
            headers = [
                "商品ID", "商品名称", "商品链接", "当前价格", "券后价", "商品销量", "店铺销量", 
                "高清图片", "商家ID", "店铺名称", "发货时间", "发货地", "商品类目", "评价数量", "正在拼", "店铺商品数量", "部分预售", "24小时发货", "新品", "上架时间", "采集时间"
            ]
            
            row_data = [csv_data.get(header, '') for header in headers]
            
            # 追加到CSV文件
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
            
            # 更新运行时统计
            self.runtime_parsed_count += 1
            self._update_runtime_stats()
            
            return True
            
        except Exception as e:
            print(f"[错误] 保存CSV数据失败: {e}")
            return False

    def _save_to_csv_without_count_update(self, csv_data: Dict) -> bool:
        """保存数据到CSV文件（增量追加）- 不更新统计计数"""
        try:
            import csv
            
            # 🔥 修复：确保CSV文件头存在
            self._create_csv_header()
            
            # 按照CSV头的顺序准备数据
            headers = [
                "商品ID", "商品名称", "商品链接", "当前价格", "券后价", "商品销量", "店铺销量", 
                "高清图片", "商家ID", "店铺名称", "发货时间", "发货地", "商品类目", "评价数量", "正在拼", "店铺商品数量", "部分预售", "24小时发货", "新品", "上架时间", "采集时间"
            ]
            
            row_data = [csv_data.get(header, '') for header in headers]
            
            # 追加到CSV文件
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
            
            # 🔥 注意：这里不更新统计计数，避免重复计数
            
            return True
            
        except Exception as e:
            print(f"[错误] 保存CSV数据失败: {e}")
            return False
    
    def _update_runtime_stats(self):
        """更新运行时统计"""
        try:
            stats_data = {
                "解析数量": self.runtime_parsed_count,
                "最后更新": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
            with open(self.stats_file_path, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
            print(f"📊 已解析: {self.runtime_parsed_count}个")
            
        except Exception as e:
            print(f"[错误] 更新运行时统计失败: {e}")

# ==================== 全局接口 ====================

# 🔥 多浏览器实例管理（避免全局单例冲突）
_extractor_instances = {}

def get_extractor(browser_id: str = None) -> DetailPageExtractor:
    """获取抓取器实例（每个浏览器独立实例）"""
    if browser_id is None:
        # 如果没有提供browser_id，尝试从配置文件获取
        try:
            from config_manager import ConfigManager
            config_mgr = ConfigManager()
            browser_id = config_mgr.get_browser_id()
        except:
            browser_id = "default"

    # 为每个浏览器创建独立实例
    if browser_id not in _extractor_instances:
        _extractor_instances[browser_id] = DetailPageExtractor(browser_id)

    return _extractor_instances[browser_id]

async def extract_and_save(page, browser_id: str = None) -> bool:
        """
        便捷函数：抓取并保存详情页数据

        Args:
            page: Playwright页面对象
            browser_id: 浏览器ID

        Returns:
            是否成功
        """
        extractor = get_extractor(browser_id)

        # 设置任务状态为运行中
        extractor.set_task_status("detail_running", True)

        try:
            result = await extractor.process_detail_page(page)
            return result
        finally:
            # 清除任务状态
            extractor.set_task_status("detail_running", False)

def is_product_clicked(product_id: str, browser_id: str = None) -> bool:
    """
    检查商品是否已被点击过（供外部调用）

    Args:
        product_id: 商品ID
        browser_id: 浏览器ID

    Returns:
        是否已被点击过
    """
    extractor = get_extractor(browser_id)
    return extractor.is_product_clicked(product_id)

def get_clicked_products_count(browser_id: str = None) -> int:
    """
    获取已点击商品数量（供外部调用）

    Args:
        browser_id: 浏览器ID

    Returns:
        已点击商品数量
    """
    extractor = get_extractor(browser_id)
    return len(extractor.clicked_products)

async def main():
    """独立运行模式 - 处理已点击的商品详情页数据"""
    print("🔍 详情页数据抓取模块")
    print("=" * 50)

    try:
        # 自动检测浏览器ID
        import os
        current_dir = os.getcwd()
        if "browser_" in current_dir:
            browser_id = current_dir.split("browser_")[-1]
        else:
            browser_id = "default"

        print(f"📋 浏览器ID: {browser_id[-6:]}")

        # 获取提取器实例
        extractor = get_extractor(browser_id)

        # 🔥 排队机制：等待上一个任务完成
        extractor.wait_for_previous_task()

        # 🔥 排队机制：设置当前任务状态为运行中
        extractor.set_task_status("detail_running", True)

        try:
            # 检查是否有已点击的商品需要处理
            clicked_count = len(extractor.clicked_products)
            print(f"📊 已点击商品数量: {clicked_count}")

            # 🔥 调试信息：显示详情数据目录状态
            print(f"📁 详情数据目录: {extractor.details_dir}")
            print(f"📁 目录是否存在: {extractor.details_dir.exists()}")
            if extractor.details_dir.exists():
                existing_files = list(extractor.details_dir.glob("*.txt"))
                print(f"📁 现有详情文件数量: {len(existing_files)}")

            if clicked_count == 0:
                print("ℹ️ 没有已点击的商品，但继续执行详情页抓取（可能有新商品）")
                print("🔄 jiex.py 继续执行 - 检查页面中的商品")
                # 🔥 修复：不跳过，继续执行以处理页面中可能存在的新商品

            # 🔥 修复：无论是否有已点击商品都继续执行
            # 连接到浏览器
            from playwright.async_api import async_playwright
            from config_manager import ConfigManager

            config_mgr = ConfigManager()
            debug_port = config_mgr.get_debug_port()



            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{debug_port}")

            if browser.contexts:
                context = browser.contexts[0]
                if context.pages:
                    page = context.pages[0]

                    print("[成功] 浏览器连接成功")
                    print("🔄 开始处理详情页数据...")

                    # 🔥 修复：传递browser_id参数
                    success = await extract_and_save(page, browser_id)

                    if success:
                        print("[成功] 详情页数据处理完成")
                        # 🔥 调试信息：显示保存结果
                        details_dir = extractor.details_dir
                        if details_dir.exists():
                            saved_files = list(details_dir.glob("*.txt"))
                            print(f"📁 已保存详情文件数量: {len(saved_files)}")
                            if saved_files:
                                latest_file = max(saved_files, key=lambda x: x.stat().st_mtime)
                                print(f"📄 最新保存文件: {latest_file.name}")
                    else:
                        print("[错误] 详情页数据处理失败")
                else:
                    print("[错误] 没有可用的页面")
            else:
                print("[错误] 没有可用的浏览器上下文")

            await playwright.stop()

        except Exception as e:
            print(f"[错误] 详情页数据抓取异常: {e}")
        finally:
            # 🔥 排队机制：无论成功失败都要清除任务状态
            extractor.set_task_status("detail_running", False)

    except Exception as e:
        print(f"[错误] 详情页数据抓取异常: {e}")


if __name__ == "__main__":
    import asyncio
    import sys

    async def parse_single_product(target_goods_id: str):

        try:
            # 创建抓取器实例
            extractor = DetailPageExtractor()

            # 🔥 排队机制：等待上一个任务完成
            extractor.wait_for_previous_task()

            # 🔥 排队机制：设置当前任务状态为运行中
            extractor.set_task_status("detail_running", True)

            try:
                # 连接浏览器并处理详情页
                from playwright.async_api import async_playwright

                async with async_playwright() as playwright:
                    browser = await playwright.chromium.connect_over_cdp(
                        f"http://localhost:{extractor.config_mgr.get_debug_port()}"
                    )

                    if browser.contexts:
                        context = browser.contexts[0]
                        if context.pages:
                            # 🔥 修复：找到正确的详情页面
                            detail_page = None

                            # 遍历所有页面，找到包含商品详情的页面
                            for page in context.pages:
                                try:
                                    url = page.url
                                    # 检查是否是拼多多详情页
                                    if "yangkeduo.com" in url and "goods" in url:
                                        detail_page = page
                                        break
                                except Exception as e:
                                    print(f"[警告] 检查页面失败: {e}")
                                    continue

                            # 如果没找到详情页，使用第一个页面
                            if not detail_page and context.pages:
                                detail_page = context.pages[0]

                            if detail_page:
                                # 处理当前页面的详情数据
                                success = await extractor.process_detail_page(detail_page, target_goods_id)
                            else:
                                print(f"[错误] 没有可用的页面")
                                success = False

                            if success:
                                print(f"[成功] 商品 {target_goods_id} 解析成功")
                            else:
                                print(f"[错误] 商品 {target_goods_id} 解析失败")
                        else:
                            print("[错误] 没有可用的页面")
                    else:
                        print("[错误] 没有可用的浏览器上下文")

                    await playwright.stop()

            finally:
                # 🔥 排队机制：无论成功失败都要清除任务状态
                extractor.set_task_status("detail_running", False)

        except Exception as e:
            print(f"[错误] 单商品解析异常: {e}")

    # 🔥 支持命令行参数：商品ID
    if len(sys.argv) > 1:
        goods_id = sys.argv[1]
        print(f"🎯 解析商品: {goods_id}")
        asyncio.run(parse_single_product(goods_id))
    else:
        print("[错误] 请提供商品ID作为命令行参数")