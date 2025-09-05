#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拼多多首页搜索工具 - 简化版
功能：连接比特浏览器 + 在拼多多首页搜索关键词
"""

import asyncio
import json
import os
import sys
import time
import random
from playwright.async_api import async_playwright

# 修复Windows控制台编码问题
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())

# 导入简化的比特浏览器API
try:
    from simple_bitbrowser_api import SimpleBitBrowserAPI
    print("成功导入比特浏览器API")
except ImportError as e:
    print(f"导入比特浏览器API失败: {e}")
    exit(1)

# 导入配置管理器
try:
    from config_manager import ConfigManager
    print("成功导入配置管理器")
except ImportError as e:
    print(f"导入配置管理器失败: {e}")
    exit(1)


class PddSearchSimple:
    """拼多多首页搜索工具"""

    def __init__(self):
        """初始化"""
        # 自动检测浏览器ID - 从脚本所在目录检测
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if "browser_" in script_dir:
            self.browser_id = script_dir.split("browser_")[-1]
        else:
            self.browser_id = "default"

        # 🔥 修复：直接加载配置文件，不依赖ConfigManager
        try:
            self.config = self._load_config_api()
            print(f"[OK] 配置加载成功")
        except Exception as e:
            print(f"[ERROR] 配置加载失败: {e}")
            self.config = {}

        # 初始化比特浏览器API
        self.browser_api = SimpleBitBrowserAPI()

        # Playwright相关
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.background_listener_task = None

        # 🔥 新增：运行时长和暂停时长管理（事件驱动）
        # 🔥 内存阈值设置
        self.memory_threshold = self.config.get('parse_settings', {}).get('memory_threshold', 200)  # 默认内存阈值200MB

        print(f"[TARGET] 浏览器ID: {self.browser_id[-6:]}")
        print(f"[定时] 内存阈值: {self.memory_threshold}MB")

    def _load_config_api(self):
        """加载config_api.json配置文件"""
        try:
            config_file = "config_api.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"[配置] 成功加载: {config_file}")
                return config
            else:
                print(f"[警告] 配置文件不存在: {config_file}")
                return {}
        except Exception as e:
            print(f"[错误] 加载配置失败: {e}")
            return {}

    def _load_config(self):
        """加载配置文件"""
        try:
            config_file = f"config_{self.browser_id}.json"
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                print(f"[配置] 成功加载: {config_file}")
                return config
            else:
                print(f"[警告] 配置文件不存在: {config_file}")
                return {}
        except Exception as e:
            print(f"[错误] 加载配置失败: {e}")
            return {}

    def _get_debug_port(self):
        """获取调试端口"""
        # 如果配置中没有browser_info，尝试动态生成
        if 'browser_info' not in self.config:
            self._generate_browser_info()
        
        return self.config.get('browser_info', {}).get('debug_port', 53484)
    
    def _generate_browser_info(self):
        """动态生成浏览器信息配置"""
        try:
            from simple_bitbrowser_api import BitBrowserAPI
            
            # 从当前目录的config_api.json获取浏览器ID
            browser_id = self.config.get('browser_id', 'f075d0d577a14e9eb94e7f14fa70d3d6')
            
            # 创建API实例
            api = BitBrowserAPI()
            
            # 获取浏览器信息
            browser_info = api.open_config_browser()
            
            if browser_info and browser_info.get('success'):
                # 更新配置
                if 'browser_info' not in self.config:
                    self.config['browser_info'] = {}
                
                self.config['browser_info'].update({
                    'browser_id': browser_id,
                    'debug_port': browser_info.get('debug_port'),
                    'folder_name': f'browser_{browser_id}',
                    'filter_keywords_file': f'filter_keywords_{browser_id}.txt'
                })
                
                # 保存配置
                self._save_config()
                print(f"[配置] 动态生成浏览器信息: 端口 {browser_info.get('debug_port')}")
            else:
                print(f"[警告] 无法动态获取浏览器信息: {browser_info.get('error') if browser_info else '未知错误'}")
                
        except Exception as e:
            print(f"[错误] 动态生成浏览器信息失败: {e}")

    def get_search_keywords(self):
        """获取搜索关键词"""
        # 🔥 修复：从parse_settings.search_keywords获取关键词
        keywords = self.config.get('parse_settings', {}).get('search_keywords', [])
        if not keywords:
            print(f"[⚠️ 警告] 未配置搜索关键词，请在配置文件中添加关键词")
            return []
        
        # 统计已搜索和待搜索的关键词
        searched_count = len([kw for kw in keywords if kw.endswith("---已搜索")])
        available_count = len([kw for kw in keywords if not kw.endswith("---已搜索")])
        
        print(f"[📊 关键词统计] 总数量: {len(keywords)} 个")
        print(f"[📊 关键词统计] 已搜索: {searched_count} 个")
        print(f"[📊 关键词统计] 待搜索: {available_count} 个")
        
        if available_count == 0:
            print("[🚨 警告] 所有关键词都已搜索完成，无法继续搜索！")
        
        return keywords

    def mark_keyword_searched(self, keyword):
        """标记关键词为已搜索 - 统一使用_mark_keyword_as_searched方法"""
        try:
            # 调用异步版本的关键词标记方法
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                task = loop.create_task(self._mark_keyword_as_searched(keyword))
                return True
            else:
                # 如果事件循环未运行，直接运行
                loop.run_until_complete(self._mark_keyword_as_searched(keyword))
                return True
        except Exception as e:
            print(f"[错误] 标记关键词失败: {e}")
            return False

    def _save_config(self):
        """保存配置到文件"""
        try:
            # 🔥 统一使用config_api.json，删除多余的配置文件
            config_file = "config_api.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            print(f"[保存] 配置已保存到: {config_file}")
            return True
        except Exception as e:
            print(f"[错误] 保存配置失败: {e}")
            return False

    def filter_search_keywords(self, keywords):
        """
        智能关键词过滤
        - 保留"---已搜索" → 跳过该关键词
        - 删除"---已搜索" → 重新搜索该关键词
        """
        filtered_keywords = []
        skipped_keywords = []

        for keyword in keywords:
            if keyword.endswith("---已搜索"):
                # 跳过已搜索的关键词
                skipped_keywords.append(keyword)
                print(f"[跳过] 已搜索关键词: {keyword}")
            else:
                # 添加到待搜索列表
                filtered_keywords.append(keyword)

        print(f"[过滤] 待搜索: {len(filtered_keywords)} 个，已跳过: {len(skipped_keywords)} 个")
        return filtered_keywords

    async def connect_browser(self):
        """连接比特浏览器"""
        try:
            debug_port = self._get_debug_port()
            print(f"[连接] 正在连接浏览器，端口: {debug_port}")

            # 启动Playwright
            self.playwright = await async_playwright().start()

            # 连接到比特浏览器
            self.browser = await self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")

            # 获取页面
            contexts = self.browser.contexts
            if contexts:
                self.context = contexts[0]
            else:
                self.context = await self.browser.new_context()

            pages = self.context.pages
            if pages:
                self.page = pages[0]
            else:
                self.page = await self.context.new_page()

            print(f"[成功] 浏览器连接成功")
            return True

        except Exception as e:
            print(f"[错误] 浏览器连接失败: {e}")
            return False

    async def goto_homepage(self):
        """导航到拼多多首页"""
        try:
            print("[首页] 正在导航到拼多多首页...")
            await self.page.goto('https://mobile.pinduoduo.com', wait_until='domcontentloaded')  # 优化：更快的加载等待
            await asyncio.sleep(0.5)  # 优化：减少等待时间
            print("[成功] 已到达拼多多首页")

            return True
        except Exception as e:
            print(f"[错误] 导航到首页失败: {e}")
            return False



    async def search_keyword(self, keyword):
        """在首页搜索关键词"""
        try:
            # 开始搜索关键词

            # 等待页面稳定
            await self.wait_random()

            # 查找搜索框
            search_box = await self._find_search_box()
            if not search_box:
                print("[ERROR] 未找到搜索框")
                return False

            # 输入关键词 - 使用更可靠的方法
            # print(f"[调试] 准备输入关键词: {keyword}")

            try:
                # 点击搜索框
                await search_box.click()
                # print(f"[调试] 已点击搜索框")

                # 等待搜索框激活
                await asyncio.sleep(1)

                # 清空搜索框 - 使用多种方法确保清空
                await self.page.keyboard.press('Control+a')  # 全选
                await asyncio.sleep(0.2)
                await self.page.keyboard.press('Delete')     # 删除
                await asyncio.sleep(0.2)
                await self.page.keyboard.press('Backspace')  # 再次删除
                # print(f"[调试] 已清空搜索框")

                # 等待清空完成
                await asyncio.sleep(0.5)

                # 模拟人工逐字输入关键词 - 恢复原始等待时间，防止被检测
                # print(f"[调试] 开始逐字输入关键词: {keyword}")
                for i, char in enumerate(keyword):
                    await self.page.keyboard.type(char)
                    # 恢复原始等待时间，模拟真人输入速度，防止被检测
                    wait_time = random.uniform(0.1, 0.3)
                    await asyncio.sleep(wait_time)
                    # print(f"[调试] 输入第{i+1}个字符: '{char}' (等待{wait_time:.2f}秒)")

                # print(f"[调试] 逐字输入完成: {keyword}")

                # 等待输入完成
                await asyncio.sleep(1)

                # 验证输入内容
                try:
                    current_value = await self.page.evaluate('document.activeElement.value || document.activeElement.textContent || ""')
                    print(f"[验证] 搜索框当前内容: '{current_value}'")

                    if keyword not in str(current_value):
                        print(f"[警告] 搜索框内容不匹配，重新逐字输入")
                        await self.page.keyboard.press('Control+a')
                        # 重新逐字输入
                        for char in keyword:
                            await self.page.keyboard.type(char)
                            await asyncio.sleep(random.uniform(0.1, 0.2))
                        await asyncio.sleep(0.5)
                except Exception as verify_e:
                    print(f"[警告] 验证输入内容失败: {verify_e}")

                print(f"[OK] 已输入关键词: {keyword}")

            except Exception as e:
                print(f"[错误] 搜索框输入失败: {e}")
                print(f"[尝试] 使用备用逐字输入方法")
                try:
                    for char in keyword:
                        await self.page.keyboard.type(char)
                        await asyncio.sleep(random.uniform(0.1, 0.2))
                    print(f"[备用] 通过逐字输入关键词: {keyword}")
                except Exception as backup_e:
                    print(f"[错误] 备用输入方法也失败: {backup_e}")
                    return False

            # 执行搜索
            search_success = await self._execute_search()
            if search_success:
                print(f"[OK] 关键词搜索完成: {keyword}")

                # 标记关键词已搜索
                self.mark_keyword_searched(keyword)

                # � 搜索完成，由workflow_manager.py统一调度后续步骤
                print("[OK] 关键词搜索完成，等待工作流程管理器调度下一步")
                return True
            else:
                print(f"[ERROR] 关键词搜索失败: {keyword}")
                self.mark_keyword_searched(keyword)
                return True

        except Exception as e:
            print(f"[ERROR] 搜索关键词异常: {e}")
            return False

    async def _find_search_box(self):
        """查找搜索框"""
        # 搜索框选择器（按优先级）
        selectors = [
            'div._2fnObgNt._215Ua8G9',         # 首页搜索框(div)
            'div._2bfwu6WT',                   # 搜索页搜索框(div)
            'input[type="search"]',            # 搜索输入框
            'input[placeholder*="搜索"]',       # 包含搜索的placeholder
            '.search-input',                   # 通用搜索输入框
        ]

        for selector in selectors:
            try:
                search_box = await self.page.query_selector(selector)
                if search_box:
                    print(f"[搜索] 找到搜索框: {selector}")
                    return search_box
            except Exception:
                continue

        return None

    async def _execute_search(self):
        """执行搜索"""
        try:
            # 查找搜索按钮
            button_selectors = [
                'div.RuSDrtii',                    # 统一搜索按钮
                'button[type="submit"]',           # 提交按钮
                '.search-button',                  # 搜索按钮
            ]

            search_button = None
            for selector in button_selectors:
                try:
                    search_button = await self.page.query_selector(selector)
                    if search_button:
                        print(f"[搜索] 找到搜索按钮: {selector}")
                        break
                except Exception:
                    continue

            # 执行搜索
            if search_button:
                await search_button.click()
                print("[搜索] 点击搜索按钮")
            else:
                await self.page.keyboard.press('Enter')
                print("[搜索] 按回车键搜索")

            # 等待页面加载 - 优化：使用更快的加载状态
            await self.page.wait_for_load_state('domcontentloaded')  # 从networkidle改为domcontentloaded
            await asyncio.sleep(1)  # 固定等待1秒，替代随机等待

            return True

        except Exception as e:
            print(f"[错误] 执行搜索失败: {e}")
            return False

    async def wait_random(self):
        """随机等待 - 优化：减少等待时间"""
        wait_time = random.uniform(0.5, 1.5)  # 从1-3秒减少到0.5-1.5秒
        print(f"[等待] {wait_time:.1f} 秒...")
        await asyncio.sleep(wait_time)

    async def search_all_keywords(self):
        """搜索所有关键词"""
        try:
            keywords = self.get_search_keywords()
            if not keywords:
                print("[❌ 错误] 没有找到搜索关键词")
                return False

            print(f"[📊 统计] 总关键词数量: {len(keywords)} 个")

            # 过滤掉已搜索的关键词
            available_keywords = [kw for kw in keywords if not kw.endswith("---已搜索")]
            searched_keywords = [kw for kw in keywords if kw.endswith("---已搜索")]

            print(f"[📊 统计] 已搜索关键词: {len(searched_keywords)} 个")
            print(f"[📊 统计] 待搜索关键词: {len(available_keywords)} 个")

            if not available_keywords:
                print("="*60)
                print("🎯 所有关键词都已搜索完成！")
                print("="*60)
                print(f"[📋 详情] 总关键词: {len(keywords)} 个")
                print(f"[📋 详情] 已搜索: {len(searched_keywords)} 个")
                print(f"[📋 详情] 待搜索: 0 个")
                print("="*60)
                print("[💡 建议] 请添加新的搜索关键词到配置文件")
                print("[💡 建议] 或者重置已搜索标记重新开始")
                print("="*60)
                return True

            # 只处理第一个关键词
            keyword = available_keywords[0]
            
            # 🔥 二次检查：确保关键词没有已搜索标记（防止并发问题）
            if keyword.endswith("---已搜索"):
                print(f"[SKIP] ⚠️ 关键词在最后检查时发现已被标记，跳过: {keyword}")
                return await self.search_all_keywords()  # 递归调用，重新选择关键词
            
            print(f"[🔍 搜索] 开始搜索关键词: {keyword}")
            print(f"[📊 剩余] 还有 {len(available_keywords)} 个关键词待搜索")

            # 🔥 修改：事件驱动的内存监控（已包含定时控制检查）
            await self._log_memory_usage("搜索前")

            # 🔥 新增：在搜索前检查定时控制
            # 确保在首页
            if not await self.goto_homepage():
                print(f"[❌ 错误] 无法到达首页")
                return False

            # 搜索关键词
            search_result = await self.search_keyword(keyword)
            
            # 🔥 新增：搜索完成后，应用排序设置
            if search_result:
                # 应用排序设置
                await self._apply_sort_settings()
                
                # 🔥 新增：应用24小时发货设置
                await self._apply_shipping_settings()
                
                # 🔥 新增：搜索完成后，调用zq.py开始抓取数据
                print(f"[✅ 成功] 关键词搜索完成: {keyword}")
                print(f"[🏷️ 标记] 关键词已标记为已搜索: {keyword}")
                
                # 保存配置，标记关键词为已搜索
                await self._mark_keyword_as_searched(keyword)
                
                # 调用zq.py开始抓取数据
                print(f"[🔄 ZQ] 搜索完成，开始调用zq.py抓取商品数据...")
                print(f"[DEBUG] 当前self.page状态: {self.page is not None}")
                print(f"[DEBUG] 当前self.browser_id: {self.browser_id}")
                
                if await self._call_zq_scraper():
                    print(f"[✅ 成功] zq.py调用成功，等待工作流程管理器调度下一步")
                else:
                    print(f"[⚠️ 警告] zq.py调用失败，但搜索任务已完成")
                
                return True
            else:
                print(f"[❌ 失败] 关键词搜索失败: {keyword}")
                return False

        except Exception as e:
            print(f"[❌ 错误] 搜索关键词失败: {e}")
            return False

    async def _apply_sort_settings(self):
        """应用排序设置 - 检查并点击对应的排序按钮"""
        try:
            # 获取排序设置
            sort_method = self.config.get('parse_settings', {}).get('sort_method', '综合排序')
            print(f"[排序] 当前排序设置: {sort_method}")
            
            # 如果是默认的综合排序，不需要操作
            if sort_method == '综合排序':
                print(f"[排序] 使用默认综合排序，无需额外操作")
                return
            
            # 等待页面稳定
            await asyncio.sleep(2)
            
            # 根据排序设置点击对应按钮
            if sort_method == '好评排序':
                await self._click_good_review_sort()
            elif sort_method == '销量排序':
                await self._click_sales_sort()
            else:
                print(f"[排序] 未知的排序方式: {sort_method}")
                
        except Exception as e:
            print(f"[排序] 应用排序设置失败: {e}")

    async def _click_good_review_sort(self):
        """点击好评排序按钮"""
        try:
            print(f"[排序] 开始点击好评排序按钮...")
            
            # 等待页面加载完成
            await asyncio.sleep(2)
            
            # 方法1：通过文本内容查找"综合"按钮并点击
            try:
                # 先点击"综合"按钮展开下拉菜单
                comprehensive_btn = self.page.locator("text=综合")
                if await comprehensive_btn.count() > 0:
                    await comprehensive_btn.first.click()
                    print(f"[排序] 已点击'综合'按钮展开下拉菜单")
                    await asyncio.sleep(1)
                    
                    # 再点击"好评排序"选项
                    good_review_btn = self.page.locator("text=好评排序")
                    if await good_review_btn.count() > 0:
                        await good_review_btn.first.click()
                        print(f"[排序] 已点击'好评排序'选项")
                        await asyncio.sleep(2)
                        return True
                    else:
                        print(f"[排序] 未找到'好评排序'选项")
                else:
                    print(f"[排序] 未找到'综合'按钮")
                    
            except Exception as e:
                print(f"[排序] 通过文本查找失败: {e}")
            
            # 方法2：备用方法 - 通过CSS选择器
            try:
                # 尝试通过CSS选择器查找排序按钮
                sort_buttons = self.page.locator(".sort-button, .filter-item, [data-sort]")
                if await sort_buttons.count() > 0:
                    # 点击第一个排序按钮（通常是综合）
                    await sort_buttons.first.click()
                    await asyncio.sleep(1)
                    
                    # 查找并点击好评排序选项
                    good_review_option = self.page.locator("text=好评排序")
                    if await good_review_option.count() > 0:
                        await good_review_option.first.click()
                        print(f"[排序] 备用方法：已点击'好评排序'选项")
                        await asyncio.sleep(2)
                        return True
                        
            except Exception as e:
                print(f"[排序] 备用方法失败: {e}")
            
            print(f"[排序] 好评排序设置失败")
            return False
            
        except Exception as e:
            print(f"[排序] 点击好评排序按钮异常: {e}")
            return False

    async def _click_sales_sort(self):
        """点击销量排序按钮"""
        try:
            print(f"[排序] 开始点击销量排序按钮...")
            
            # 等待页面加载完成
            await asyncio.sleep(2)
            
            # 直接点击"销量"按钮
            try:
                sales_btn = self.page.locator("text=销量")
                if await sales_btn.count() > 0:
                    await sales_btn.first.click()
                    print(f"[排序] 已点击'销量'按钮")
                    await asyncio.sleep(2)
                    return True
                else:
                    print(f"[排序] 未找到'销量'按钮")
                    
            except Exception as e:
                print(f"[排序] 点击销量按钮失败: {e}")
            
            # 备用方法：通过CSS选择器
            try:
                sort_buttons = self.page.locator(".sort-button, .filter-item, [data-sort]")
                if await sort_buttons.count() > 1:  # 假设销量是第二个按钮
                    await sort_buttons.nth(1).click()
                    print(f"[排序] 备用方法：已点击销量排序按钮")
                    await asyncio.sleep(2)
                    return True
                    
            except Exception as e:
                print(f"[排序] 备用方法失败: {e}")
            
            print(f"[排序] 销量排序设置失败")
            return False
            
        except Exception as e:
            print(f"[排序] 点击销量排序按钮异常: {e}")
            return False

    async def _mark_keyword_as_searched(self, keyword: str):
        """标记关键词为已搜索"""
        try:
            # 🔥 防重复搜索：首先检查关键词是否已经被标记
            if keyword.endswith("---已搜索"):
                print(f"[SKIP] 关键词已经被标记为已搜索: {keyword}")
                return True
            
            # 在配置文件中标记关键词为已搜索
            if 'parse_settings' in self.config and 'search_keywords' in self.config['parse_settings']:
                keywords = self.config['parse_settings']['search_keywords']
                marked = False
                
                for i, kw in enumerate(keywords):
                    # 🔥 精确匹配，避免重复标记
                    if kw == keyword and not kw.endswith("---已搜索"):
                        keywords[i] = f"{keyword}---已搜索"
                        marked = True
                        print(f"[MARK] 标记关键词: {keyword} → {keywords[i]}")
                        break
                    elif kw == keyword and kw.endswith("---已搜索"):
                        print(f"[SKIP] 关键词已被标记: {kw}")
                        return True
                
                if not marked:
                    print(f"[WARNING] 未找到匹配的关键词进行标记: {keyword}")
                    return False
                
                # 🔥 保存前再次确认关键词已被正确标记
                updated_keywords = [kw for kw in keywords if f"{keyword}---已搜索" in kw]
                if not updated_keywords:
                    print(f"[ERROR] 关键词标记验证失败: {keyword}")
                    return False
                
                # 保存更新后的配置
                config_file = "config_api.json"
                with open(config_file, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, ensure_ascii=False, indent=2)
                
                print(f"[保存] 配置已保存到: {config_file}")
                
                # 🔥 验证保存是否成功 - 重新读取配置文件
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        saved_config = json.load(f)
                    saved_keywords = saved_config.get('parse_settings', {}).get('search_keywords', [])
                    if f"{keyword}---已搜索" in saved_keywords:
                        print(f"[验证] ✅ 关键词标记保存成功: {keyword}---已搜索")
                        return True
                    else:
                        print(f"[验证] ❌ 关键词标记保存失败: {keyword}")
                        return False
                except Exception as verify_e:
                    print(f"[验证] 验证保存失败: {verify_e}")
                    return False
                
            else:
                print(f"[WARNING] 配置文件中未找到search_keywords字段")
                return False
                
        except Exception as e:
            print(f"[ERROR] 标记关键词失败: {e}")
            return False

    async def _apply_shipping_settings(self):
        """应用24小时发货设置"""
        try:
            # 获取发货时间设置
            require_24h_shipping = self.config.get('parse_settings', {}).get('filter_settings', {}).get('require_24h_shipping', False)
            print(f"[发货] 当前发货设置: 24小时发货 = {require_24h_shipping}")
            
            # 如果不需要24小时发货，直接返回
            if not require_24h_shipping:
                print(f"[发货] 不需要24小时发货，跳过设置")
                return
            
            # 等待页面稳定
            await asyncio.sleep(2)
            
            # 点击筛选按钮
            await self._click_filter_button()
            
        except Exception as e:
            print(f"[发货] 应用发货设置失败: {e}")

    async def _click_filter_button(self):
        """点击筛选按钮并设置24小时发货"""
        try:
            print(f"[发货] 开始点击筛选按钮...")
            
            # 等待页面加载完成
            await asyncio.sleep(2)
            
            # 方法1：通过文本内容查找"筛选"按钮
            try:
                filter_btn = self.page.locator("text=筛选")
                if await filter_btn.count() > 0:
                    await filter_btn.first.click()
                    print(f"[发货] 已点击'筛选'按钮")
                    await asyncio.sleep(2)
                    
                    # 查找并点击"24小时发货"选项
                    shipping_24h_btn = self.page.locator("text=24小时发货")
                    if await shipping_24h_btn.count() > 0:
                        await shipping_24h_btn.first.click()
                        print(f"[发货] 已点击'24小时发货'选项")
                        await asyncio.sleep(1)
                        
                        # 点击确认按钮
                        await self._click_confirm_button()
                        return True
                    else:
                        print(f"[发货] 未找到'24小时发货'选项，直接点击确认")
                        await self._click_confirm_button()
                        return True
                else:
                    print(f"[发货] 未找到'筛选'按钮")
                    
            except Exception as e:
                print(f"[发货] 通过文本查找筛选按钮失败: {e}")
            
            # 方法2：备用方法 - 通过CSS选择器
            try:
                # 尝试通过CSS选择器查找筛选按钮
                filter_buttons = self.page.locator(".filter-button, .filter-btn, [data-filter]")
                if await filter_buttons.count() > 0:
                    await filter_buttons.first.click()
                    print(f"[发货] 备用方法：已点击筛选按钮")
                    await asyncio.sleep(2)
                    
                    # 查找并点击"24小时发货"选项
                    shipping_24h_btn = self.page.locator("text=24小时发货")
                    if await shipping_24h_btn.count() > 0:
                        await shipping_24h_btn.first.click()
                        print(f"[发货] 备用方法：已点击'24小时发货'选项")
                        await asyncio.sleep(1)
                        
                        # 点击确认按钮
                        await self._click_confirm_button()
                        return True
                    else:
                        print(f"[发货] 备用方法：未找到'24小时发货'选项，直接点击确认")
                        await self._click_confirm_button()
                        return True
                        
            except Exception as e:
                print(f"[发货] 备用方法失败: {e}")
            
            print(f"[发货] 筛选设置失败")
            return False
            
        except Exception as e:
            print(f"[发货] 点击筛选按钮异常: {e}")
            return False

    async def _click_confirm_button(self):
        """点击确认按钮"""
        try:
            print(f"[发货] 开始点击确认按钮...")
            
            # 等待页面稳定
            await asyncio.sleep(1)
            
            # 方法1：通过文本内容查找"确认"按钮
            try:
                confirm_btn = self.page.locator("text=确认")
                if await confirm_btn.count() > 0:
                    await confirm_btn.first.click()
                    print(f"[发货] 已点击'确认'按钮")
                    await asyncio.sleep(2)
                    return True
                else:
                    print(f"[发货] 未找到'确认'按钮")
                    
            except Exception as e:
                print(f"[发货] 通过文本查找确认按钮失败: {e}")
            
            # 方法2：备用方法 - 通过CSS选择器查找红色确认按钮
            try:
                # 查找红色背景的确认按钮
                red_confirm_btn = self.page.locator("button:has-text('确认')")
                if await red_confirm_btn.count() > 0:
                    await red_confirm_btn.first.click()
                    print(f"[发货] 备用方法：已点击红色'确认'按钮")
                    await asyncio.sleep(2)
                    return True
                    
            except Exception as e:
                print(f"[发货] 备用方法失败: {e}")
            
            print(f"[发货] 确认按钮点击失败")
            return False
            
        except Exception as e:
            print(f"[发货] 点击确认按钮异常: {e}")
            return False
                
        except Exception as e:
            print(f"[ERROR] 标记关键词失败: {e}")
            import traceback
            print(f"[ERROR] 详细错误: {traceback.format_exc()}")
            return False

    async def _call_zq_scraper(self) -> bool:
        """调用zq.py开始抓取商品数据，完成后继续调用product_clicker.py"""
        try:
            import importlib.util
            import os
            import time

            # 🔥 调试信息
            print(f"[DEBUG] _call_zq_scraper 开始执行")
            print(f"[DEBUG] self.page: {self.page}")
            print(f"[DEBUG] self.browser_id: {self.browser_id}")
            print(f"[DEBUG] 当前工作目录: {os.getcwd()}")

            # 获取zq.py的路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            zq_script = os.path.join(current_dir, "zq.py")

            if not os.path.exists(zq_script):
                print(f"[ERROR] 找不到zq.py文件: {zq_script}")
                return False

            # 🔥 修复：使用唯一的模块名，避免多个浏览器目录之间的冲突
            # 使用浏览器ID + 时间戳确保唯一性
            unique_module_name = f"zq_module_{self.browser_id}_{int(time.time())}"
            print(f"[ZQ] 导入zq.py模块: {unique_module_name}")

            try:
                # 使用importlib直接导入zq.py模块
                spec = importlib.util.spec_from_file_location(unique_module_name, zq_script)
                zq_module = importlib.util.module_from_spec(spec)
                
                # 🔥 修复：设置模块的__file__属性，确保路径正确
                zq_module.__file__ = zq_script
                
                # 执行模块
                spec.loader.exec_module(zq_module)
                
                # 调用模块的main函数
                if hasattr(zq_module, 'main'):
                    print(f"[ZQ] 调用zq.py模块的main函数...")
                    # 传入已连接的页面实例，避免重复连接浏览器
                    await zq_module.main(page=self.page, browser_id=self.browser_id)
                    print(f"[OK] zq.py模块执行成功！")
                    
                    # 🔥 新增：zq.py完成后，继续调用product_clicker.py
                    print(f"[CHAIN] zq.py抓取完成，继续调用product_clicker.py进行商品点击...")
                    if await self._call_product_clicker():
                        print(f"[OK] 完整调用链执行成功：pdd_search_simple.py -> zq.py -> product_clicker.py")
                        return True
                    else:
                        print(f"[WARNING] product_clicker.py调用失败，但zq.py已完成")
                        return False
                else:
                    print(f"[ERROR] zq.py模块中没有找到main函数")
                    return False
                    
            except Exception as e:
                print(f"[ERROR] 导入或执行zq.py模块失败: {e}")
                print(f"[ERROR] 错误类型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                return False

        except Exception as e:
            print(f"[ERROR] 调用zq.py异常: {e}")
            return False





    async def close_browser(self, force_close=False):
        """🔥 优化：关闭浏览器连接，加强内存释放"""
        try:
            if force_close:
                # 🔥 关闭前先清理内存
                print("[清理] 开始关闭前内存清理...")
                await self._log_memory_usage("关闭前")
                
                # 清理页面资源
                if self.page:
                    try:
                        await self.page.evaluate("""
                            (() => {
                                // 移除所有事件监听器
                                window.removeEventListener('beforeunload', arguments.callee);
                                
                                // 清除所有定时器
                                for (let i = 1; i < 999999; i++) {
                                    clearTimeout(i);
                                    clearInterval(i);
                                }
                                
                                // 清除全局变量
                                Object.keys(window).forEach(key => {
                                    if (typeof window[key] === 'object' && 
                                        key !== 'location' && key !== 'document') {
                                        try { delete window[key]; } catch(e) {}
                                    }
                                });
                                
                                // 强制垃圾回收
                                if (window.gc) window.gc();
                                
                                return true;
                            })()
                        """)
                    except:
                        pass
                
                # 强制关闭浏览器和连接
                if self.page:
                    try:
                        await self.page.close()
                        self.page = None
                    except:
                        pass
                
                if self.browser:
                    try:
                        await self.browser.close()
                        self.browser = None
                    except:
                        pass
                
                if self.playwright:
                    try:
                        await self.playwright.stop()
                        self.playwright = None
                    except:
                        pass
                
                # 🔥 Python垃圾回收
                import gc
                collected = gc.collect()
                print(f"[清理] 浏览器连接已强制关闭，释放了 {collected} 个Python对象")
                
                await self._log_memory_usage("关闭后")
            else:
                # 🔥 正常情况下清理页面但保持连接
                if self.page:
                    await self._optimize_memory_usage()
                print("[保持] 浏览器连接保持开启，内存已优化")
                
        except Exception as e:
            print(f"[错误] 关闭浏览器失败: {e}")
            # 确保资源被清理
            self.page = None
            self.browser = None
            self.playwright = None

    # 🔥 已移除无用的调用方法：_call_zq_scraper() 和 _execute_zq_py()
    # 这些方法会导致重复调用，由 workflow_manager.py 统一管理调用顺序

    async def _call_product_clicker(self) -> bool:
        """调用product_clicker.py进行商品点击"""
        try:
            import importlib.util
            import os

            # 获取product_clicker.py的路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            clicker_script = os.path.join(current_dir, "product_clicker.py")

            if not os.path.exists(clicker_script):
                print(f"[ERROR] 找不到product_clicker.py文件: {clicker_script}")
                return False

            # 直接导入product_clicker.py模块
            print(f"[START] 导入product_clicker.py模块进行商品点击...")
            
            try:
                # 使用importlib直接导入product_clicker.py模块
                spec = importlib.util.spec_from_file_location("clicker_module", clicker_script)
                clicker_module = importlib.util.module_from_spec(spec)
                
                # 执行模块
                spec.loader.exec_module(clicker_module)
                
                # 调用模块的main函数
                if hasattr(clicker_module, 'main'):
                    print(f"[START] 调用product_clicker.py模块的main函数...")
                    # 直接在当前事件循环中运行main函数
                    await clicker_module.main()
                    print(f"[OK] product_clicker.py模块执行成功！")
                    return True
                else:
                    print(f"[ERROR] product_clicker.py模块中没有找到main函数")
                    return False
                    
            except Exception as e:
                print(f"[ERROR] 导入或执行product_clicker.py模块失败: {e}")
                print(f"[ERROR] 错误类型: {type(e).__name__}")
                import traceback
                traceback.print_exc()
                return False

        except Exception as e:
            print(f"[异常] 调用product_clicker.py异常: {e}")
            return False

    async def _clear_memory_data(self):
        """清除浏览器内存数据"""
        try:
            if not self.page:
                print("[WARNING] 页面未连接，跳过内存清理")
                return

            # 🔥 修复JavaScript语法：使用函数包装，保留登录信息
            clear_script = """
            (() => {
                try {
                    // 清除全局变量
                    if (window.rawData) delete window.rawData;
                    if (window.historyDataForSave) delete window.historyDataForSave;
                    if (window.latest20DataForSave) delete window.latest20DataForSave;

                    // ⚠️ 重要：不清除localStorage和sessionStorage，保留登录账号信息
                    // if (window.localStorage) {
                    //     localStorage.clear();  // 注释掉，避免清除登录信息
                    // }
                    // if (window.sessionStorage) {
                    //     sessionStorage.clear();  // 注释掉，避免清除登录信息
                    // }

                    console.log('内存数据清除完成（保留登录信息）');
                    return true;
                } catch (e) {
                    console.error('清除内存数据失败:', e);
                    return false;
                }
            })()
            """

            result = await self.page.evaluate(clear_script)
            if result:
                print("[OK] 内存数据清除成功")
            else:
                print("[WARNING] 内存数据清除可能不完整")

        except Exception as e:
            print(f"[ERROR] 清除内存数据失败: {e}")

    async def _clear_browser_cache_and_console(self):
        """清除浏览器缓存、控制台历史记录等数据（保留登录信息）"""
        try:
            if not self.page:
                print("[WARNING] 页面未连接，跳过缓存清理")
                return

            # ⚠️ 重要：不清除cookies，保留登录账号信息
            # await self.context.clear_cookies()  # 注释掉，避免清除登录信息
            print("[INFO] 跳过cookies清除，保留登录账号信息")

            # 清除控制台历史记录
            clear_console_script = """
            (() => {
                try {
                    // 清除控制台历史记录
                    if (console.clear) {
                        console.clear();
                    }
                    
                    // 清除可能的控制台相关变量
                    if (window.console && window.console.history) {
                        window.console.history = [];
                    }
                    
                    // 清除可能的调试信息
                    if (window.debugInfo) delete window.debugInfo;
                    if (window.logHistory) delete window.logHistory;
                    
                    console.log('控制台历史记录清除完成');
                    return true;
                } catch (e) {
                    console.error('清除控制台历史记录失败:', e);
                    return false;
                }
            })()
            """
            
            result = await self.page.evaluate(clear_console_script)
            if result:
                print("[OK] 控制台历史记录清除成功")
            else:
                print("[WARNING] 控制台历史记录清除可能不完整")

            # 清除页面缓存（保留登录相关数据）
            await self.page.evaluate("""
                (() => {
                    try {
                        // 清除页面缓存相关数据
                        if (window.performance && window.performance.memory) {
                            // 强制垃圾回收（如果支持）
                            if (window.gc) {
                                window.gc();
                            }
                        }
                        
                        // 清除可能的页面缓存变量（但保留登录相关数据）
                        if (window.pageCache) delete window.pageCache;
                        if (window.viewCache) delete window.viewCache;
                        
                        // 保留登录相关的数据
                        // 不清除 localStorage 和 sessionStorage，避免清除登录状态
                        
                        return true;
                    } catch (e) {
                        return false;
                    }
                })()
            """)
            print("[OK] 页面缓存清除完成（保留登录信息）")

        except Exception as e:
            print(f"[ERROR] 清除浏览器缓存和控制台失败: {e}")

    async def _log_memory_usage(self, stage: str):
        """🔥 内存使用监控（事件驱动版）"""
        try:
            import psutil
            import gc
            
            # 获取当前进程的内存使用情况
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
            
            # 获取系统内存情况
            system_memory = psutil.virtual_memory()
            
            print(f"[MEMORY] {stage}:")
            print(f"   进程内存: {memory_info.rss / 1024 / 1024:.1f} MB ({memory_percent:.1f}%)")
            print(f"   系统内存: {system_memory.percent:.1f}% 已使用")
            print(f"   Python对象数: {len(gc.get_objects())}")
            
            # 🔥 修改：检测浏览器内存使用情况
            browser_memory_info = await self._get_browser_memory_usage()
            if browser_memory_info:
                print(f"   浏览器内存: {browser_memory_info['used']:.1f} MB / {browser_memory_info['total']:.1f} MB ({browser_memory_info['percentage']:.1f}%)")
                
                # 🔥 修改：事件驱动的内存阈值检查
                if browser_memory_info['used'] > self.memory_threshold:
                    print(f"⚠️ 浏览器内存使用超过阈值 {self.memory_threshold}MB，准备重启浏览器...")
                    return await self._handle_memory_threshold_exceeded()
            
            # 🔥 修改：同时检查内存使用
            
        except Exception as e:
            print(f"[WARNING] 内存监控失败: {e}")

    async def _get_browser_memory_usage(self):
        """获取浏览器内存使用情况"""
        try:
            if not self.page:
                return None
                
            memory_info = await self.page.evaluate("""
                (() => {
                    try {
                        if (window.performance && window.performance.memory) {
                            const mem = window.performance.memory;
                            return {
                                used: mem.usedJSHeapSize / 1024 / 1024,
                                total: mem.totalJSHeapSize / 1024 / 1024,
                                limit: mem.jsHeapSizeLimit / 1024 / 1024,
                                percentage: (mem.usedJSHeapSize / mem.jsHeapSizeLimit) * 100
                            };
                        }
                        return null;
                    } catch (e) {
                        return null;
                    }
                })()
            """)
            
            return memory_info
            
        except Exception as e:
            print(f"[WARNING] 获取浏览器内存信息失败: {e}")
            return None

    async def _stop_all_scripts(self):
        """🔥 停止所有脚本运行"""
        try:
            # 这里可以添加停止脚本的逻辑
            # 比如发送停止信号给相关进程
            print("🛑 停止所有脚本运行")
        except Exception as e:
            print(f"⚠️ 停止脚本失败: {e}")

    async def _close_browser(self):
        """🔥 关闭浏览器"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            print("🔒 浏览器已关闭")
        except Exception as e:
            print(f"⚠️ 关闭浏览器失败: {e}")

    async def _restart_search_process(self):
        """🔥 重启搜索进程（已废弃，不再使用）"""
        try:
            print("🔄 重启搜索进程...")
            # 重新开始完整的搜索流程
            await self.search_all_keywords()
        except Exception as e:
            print(f"❌ 重启搜索进程失败: {e}")

    def _get_current_keyword(self):
        """获取当前关键词"""
        try:
            keywords = self.config.get('parse_settings', {}).get('search_keywords', [])
            if keywords:
                return keywords[0]  # 返回第一个关键词
            return None
        except Exception as e:
            print(f"❌ 获取当前关键词失败: {e}")
            return None

    async def _handle_memory_threshold_exceeded(self):
        """🔥 处理内存阈值超限 - 关闭浏览器并重新启动"""
        try:
            print(f"🚨 内存阈值超限 ({self.memory_threshold}MB)，开始处理...")
            
            # 1. 关闭当前浏览器
            await self._close_browser()
            
            # 2. 等待一段时间让系统释放资源
            import time
            await asyncio.sleep(5)
            
            # 3. 重新启动浏览器
            print("🔄 重新启动浏览器...")
            await self._start_browser()
            
            # 4. 重新开始搜索流程
            print("🔄 重新开始搜索流程...")
            await self.search_all_keywords()
            
        except Exception as e:
            print(f"❌ 处理内存阈值超限失败: {e}")
            # 如果处理失败，尝试重新启动整个流程
            try:
                await self._restart_search_process()
            except Exception as restart_e:
                print(f"❌ 重启搜索进程也失败: {restart_e}")

    async def _optimize_memory_usage(self):
        """🔥 内存使用优化 - 增强版"""
        try:
            import gc
            
            print("[MEMORY] 开始增强内存优化...")
            
            # 1. 强制垃圾回收
            collected = gc.collect()
            print(f"[MEMORY] 垃圾回收释放了 {collected} 个对象")
            
            # 2. 清理浏览器内存
            if self.page:
                # 🔥 增强的浏览器内存清理
                await self.page.evaluate("""
                    (() => {
                        try {
                            // 强制垃圾回收
                            if (window.gc) window.gc();
                            
                            // 清除所有定时器
                            const highestTimeoutId = setTimeout(";");
                            for (let i = 0; i < highestTimeoutId; i++) {
                                clearTimeout(i);
                                clearInterval(i);
                            }
                            
                            // 清除大型数据结构
                            if (window.pageData) window.pageData = null;
                            if (window.tempData) window.tempData = null;
                            if (window.searchResults) window.searchResults = null;
                            if (window.rawData) window.rawData = null;
                            if (window.historyDataForSave) window.historyDataForSave = null;
                            if (window.latest20DataForSave) window.latest20DataForSave = null;
                            
                            // 清除事件监听器缓存
                            const elements = document.querySelectorAll('*');
                            elements.forEach(el => {
                                if (el._listeners) el._listeners = null;
                                if (el._events) el._events = null;
                                // 移除所有事件监听器
                                const clone = el.cloneNode(true);
                                el.parentNode.replaceChild(clone, el);
                            });
                            
                            // 清除图片缓存
                            const images = document.querySelectorAll('img');
                            images.forEach(img => {
                                if (img.src && !img.src.includes('login') && !img.src.includes('auth') && !img.src.includes('token')) {
                                    img.src = '';
                                    img.removeAttribute('src');
                                }
                            });
                            
                            // 清除视频缓存
                            const videos = document.querySelectorAll('video');
                            videos.forEach(video => {
                                video.src = '';
                                video.load();
                            });
                            
                            // 清除音频缓存
                            const audios = document.querySelectorAll('audio');
                            audios.forEach(audio => {
                                audio.src = '';
                                audio.load();
                            });
                            
                            // 清除可能的缓存对象（保留登录相关）
                            if (window.caches) {
                                caches.keys().then(names => {
                                    names.forEach(name => {
                                        // 不删除包含login、auth、token的缓存
                                        if (!name.includes('login') && !name.includes('auth') && !name.includes('token')) {
                                            caches.delete(name);
                                        }
                                    });
                                });
                            }
                            
                            // 清除Service Worker缓存（保留登录相关）
                            if (navigator.serviceWorker && navigator.serviceWorker.controller) {
                                navigator.serviceWorker.controller.postMessage({
                                    command: 'clearCache',
                                    exclude: ['login', 'auth', 'token']
                                });
                            }
                            
                            // 清除CSS缓存（保留登录相关）
                            const styles = document.querySelectorAll('style');
                            styles.forEach(style => {
                                if (!style.textContent.includes('login') && 
                                    !style.textContent.includes('auth') &&
                                    !style.textContent.includes('token')) {
                                    style.textContent = '';
                                }
                            });
                            
                            // 清除可能的全局变量（保留登录相关）
                            const globalVars = ['pageCache', 'viewCache', 'debugInfo', 'logHistory', 'tempStorage'];
                            globalVars.forEach(varName => {
                                if (window[varName] && !varName.includes('login') && !varName.includes('auth') && !varName.includes('token')) {
                                    delete window[varName];
                                }
                            });
                            
                            // ⚠️ 重要：不清除localStorage和sessionStorage，保留登录账号信息
                            // localStorage和sessionStorage包含登录token，绝对不能清除
                            console.log('内存清理完成（保留登录信息）');
                            
                            return true;
                        } catch (e) {
                            console.error('内存清理失败:', e);
                            return false;
                        }
                    })()
                """)
                
                # 3. 清理Playwright缓存（保留登录cookies）
                try:
                    # 清理页面缓存
                    await self.page.evaluate("window.location.reload()")
                    await asyncio.sleep(1)
                    
                    # ⚠️ 重要：不清除cookies，保留登录信息
                    # await self.context.clear_cookies()  # 注释掉这行，不清除登录cookies
                    
                except Exception as e:
                    print(f"[WARNING] 清理Playwright缓存失败: {e}")
            
            print("[MEMORY] 增强内存优化完成")
            
        except Exception as e:
            print(f"[WARNING] 内存优化失败: {e}")

    async def run(self):
        """主运行函数"""
        try:
            print("[START] 开始拼多多搜索任务")
            
            # 🔥 内存优化：添加初始内存监控
            await self._log_memory_usage("运行开始")

            # 🔥 修复：检查正确的配置文件
            print(f"[DEBUG] 检查配置文件...")
            if not self.config:
                print(f"[ERROR] 配置未加载")
                return
            print(f"[DEBUG] 配置已加载，包含 {len(self.config)} 个配置项")

            # 1. 连接浏览器
            print("[CONNECT] 连接浏览器...")
            print(f"[DEBUG] 准备连接端口: {self._get_debug_port()}")
            if not await self.connect_browser():
                print("[ERROR] 浏览器连接失败")
                return
            print("[OK] 浏览器连接成功")
            print(f"[DEBUG] 当前页面URL: {self.page.url if self.page else 'None'}")

            # 1.5. 🔥 内存优化：强化内存清理
            print("[CLEAR] 强化内存清理和优化...")
            await self._optimize_memory_usage()
            await self._clear_memory_data()
            await self._clear_browser_cache_and_console()
            
            # 内存清理后监控
            await self._log_memory_usage("内存清理后")

            # 2. 搜索关键词
            print("[SEARCH] 开始搜索关键词...")
            result = await self.search_all_keywords()

            if result:
                print("[OK] 搜索任务完成")
            else:
                print("[WARNING] 搜索任务未完成")

            print("[PROCESS] 浏览器保持连接，等待后续操作...")

        except Exception as e:
            print(f"[ERROR] 程序运行异常: {e}")
            await self.close_browser()




async def main():
    """程序入口"""
    try:
        print("[DEBUG] 创建PddSearchSimple实例...")
        searcher = PddSearchSimple()
        print("[DEBUG] 实例创建成功，开始运行...")
        
        # 🔥 新增：在搜索前进行紧急状况检测（已注释掉，改用jiex.py检测）
        # if hasattr(searcher, 'page') and searcher.page and hasattr(searcher, 'browser_id') and searcher.browser_id:
        #     try:
        #         from emergency_monitor import monitor_emergency
        #         emergency_ok = await monitor_emergency(searcher.page, searcher.browser_id)
        #         if not emergency_ok:
        #             print("🚨 检测到紧急状况，搜索程序已暂停")
        #             return
        #     except ImportError:
        #         print("⚠️ emergency_monitor 模块未找到，跳过紧急检测")
        
        await searcher.run()
        print("[DEBUG] 程序运行完成")
    except Exception as e:
        print(f"[ERROR] main()函数异常: {e}")
        import traceback
        traceback.print_exc()
        raise


def test_single_keyword():
    """测试单个关键词搜索"""
    async def test():
        searcher = PddSearchSimple()
        try:
            # 连接浏览器
            if await searcher.connect_browser():
                # 导航到首页
                if await searcher.goto_homepage():
                    # 获取配置文件中的第一个未搜索关键词进行测试
                    keywords = searcher.get_search_keywords()
                    if keywords:
                        # 过滤掉已搜索的关键词
                        available_keywords = [kw for kw in keywords if not kw.endswith("---已搜索")]
                        if available_keywords:
                            test_keyword = available_keywords[0]
                            print(f"[TEST] 使用配置文件中的关键词进行测试: {test_keyword}")
                            await searcher.search_keyword(test_keyword)
                        else:
                            print("[ERROR] 所有关键词都已搜索完成")
                    else:
                        print("[ERROR] 配置文件中没有找到关键词")
        finally:
            await searcher.close_browser()

    asyncio.run(test())


def show_usage():
    """显示使用说明"""
    print("=" * 50)
    print("[LOG] 拼多多首页搜索工具")
    print("=" * 50)
    print()
    print("使用方法:")
    print("  python pdd_search_simple.py           # 搜索配置文件中的所有关键词")
    print("  python pdd_search_simple.py test      # 测试单个关键词搜索")
    print("  python pdd_search_simple.py help      # 显示帮助信息")
    print()
    print("功能说明:")
    print("  1. 自动连接比特浏览器")
    print("  2. 导航到拼多多首页")
    print("  3. 搜索配置文件中的关键词")
    print("  4. 智能查找搜索框和搜索按钮")
    print()
    print("配置文件:")
    print("  config_{browser_id}.json")
    print("  - search_keywords: 搜索关键词列表")
    print("  - browser_info.debug_port: 浏览器调试端口")
    print()
    print("注意事项:")
    print("  - 确保比特浏览器正在运行")
    print("  - 确保配置文件存在且正确")
    print("  - 确保网络连接正常")


def run_main():
    """运行主程序的包装函数"""
    try:
        print("[DEBUG] 开始执行主程序")

        # 🔥 修复事件循环问题：使用新的事件循环
        import asyncio
        import sys

        # Windows平台特殊处理
        if sys.platform == 'win32':
            # 设置事件循环策略
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # 运行主程序
            loop.run_until_complete(main())
            print("[DEBUG] 主程序执行完成")
        finally:
            # 确保事件循环正确关闭
            try:
                # 取消所有未完成的任务
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                # 等待所有任务完成
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception as e:
                print(f"[DEBUG] 清理任务时出错: {e}")
            finally:
                loop.close()
                print("[DEBUG] 事件循环已关闭")

    except KeyboardInterrupt:
        print("\n程序已停止")
    except Exception as e:
        print(f"\n程序异常: {e}")
        import traceback
        print(f"异常详情: {traceback.format_exc()}")

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        keyword = sys.argv[1]

        # 检查特殊参数
        if keyword in ["help", "-h", "--help"]:
            print("[PAGE] 拼多多首页搜索工具")
            print("用法: python pdd_search_simple.py [关键词]")
            print("示例: python pdd_search_simple.py 牛仔裤")
            sys.exit(0)
        elif keyword == "test":
            print("[TEST] 测试模式暂不支持")
            sys.exit(0)
        else:
            print(f"[SEARCH] 搜索关键词: {keyword}")
            run_main()
    else:
        # 正常运行模式
        print("[DEBUG] 进入正常运行模式")
        run_main()

print("[PAGE] 文件: pdd_search_simple.py - 拼多多首页搜索工具")
