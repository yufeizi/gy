import asyncio
import json
import os
import sys
import time
import random
import math
import hashlib
from typing import List, Dict, Any, Optional
from playwright.async_api import async_playwright, Page
from urllib.parse import urlparse, parse_qs

# ====================================================================================================
# 【1】模块导入和依赖检查 - 程序启动第一步
# ====================================================================================================
try:
    # 🔥 修复：确保能找到 jiex 模块
    import sys
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    from jiex import DetailPageExtractor
    print("✅ 成功导入详情页提取器模块")
except ImportError as e:
    print(f"❌ 导入详情页提取器失败: {e}")
    print("⚠️ 将在不集成详情页处理的模式下运行")
    DetailPageExtractor = None

class ProductClicker:
    """智能商品点击器 - 基于JSON数据的人性化商品点击工具"""

    def __init__(self):
        """【2】类初始化方法 - 程序启动第二步"""
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Page = None

        # ====================================================================================================
        # 【3】启动时清理历史数据（在配置加载前执行）
        # ====================================================================================================
        try:
            self._clear_startup_history_data()
        except Exception as e:
            print(f"[警告] 启动清理失败: {e}")

        # ====================================================================================================
        # 【4】配置文件加载
        # ====================================================================================================
        self.config = self._load_config()
        self.debug_port = self.config.get('browser_info', {}).get('debug_port')
        if not self.debug_port:
            raise ValueError("错误：无法从配置文件 config_api.json 中找到 'debug_port'。")
        
        # 🔥 添加browser_id属性
        self.browser_id = self.config.get('browser_info', {}).get('browser_id', 'unknown')
        print(f"[✅] 浏览器ID: {self.browser_id}")

        # ====================================================================================================
        # 【5】点击配置参数初始化
        # ====================================================================================================
        self.search_page_wait = self.config.get('parse_settings', {}).get('search_page_wait', 11)  # 搜索页等待时间
        self.detail_page_wait = self.config.get('click_settings', {}).get('detail_page_wait', 5)  # 详情页等待时间
        self.click_interval_min = self.config.get('click_settings', {}).get('click_interval_min', 2)  # 最小点击间隔
        self.click_interval_max = self.config.get('click_settings', {}).get('click_interval_max', 8)  # 最大点击间隔

        print(f"[✅] 点击配置加载完成:")
        print(f"    - 搜索页等待时间: {self.search_page_wait}秒 (返回搜索页后的等待)")
        print(f"    - 详情页等待时间: {self.detail_page_wait}秒 (详情页浏览停留)")
        print(f"    - 点击间隔: {self.click_interval_min}-{self.click_interval_max}秒 (商品间随机间隔)")

        # 获取目标点击数量
        self.target_count = self.config.get('parse_settings', {}).get('target_count', None)
        print(f"    - 目标点击数量: {self.target_count if self.target_count else '全部商品'}")

        # ====================================================================================================
        # 【6】过滤设置初始化
        # ====================================================================================================
        filter_settings = self.config.get('parse_settings', {}).get('filter_settings', {})
        self.sales_min = filter_settings.get('sales_min', '15')
        self.sales_max = filter_settings.get('sales_max', '')
        self.price_min = filter_settings.get('price_min', '15')
        self.price_max = filter_settings.get('price_max', '')

        # ====================================================================================================
        # 【7】搜索关键词管理初始化
        # ====================================================================================================
        self.search_keywords = self.config.get('parse_settings', {}).get('search_keywords', [])
        self.current_keyword_index = 0  # 默认从第一个关键词开始

        # ====================================================================================================
        # 【7.5】🔥 新增：定时控制初始化
        # ====================================================================================================
        # 🔥 修复：start_time不在__init__中设置，而是在run_clicking_session开始时设置
        self.run_minutes = self.config.get('parse_settings', {}).get('run_minutes', 0)  # 默认运行0分钟(不开启)
        self.pause_minutes = self.config.get('parse_settings', {}).get('pause_minutes', 0)  # 默认暂停0分钟(不开启)
        self.memory_threshold = self.config.get('parse_settings', {}).get('memory_threshold', 200)  # 默认内存阈值200MB
        
        # 🔥 新增：最小时长限制（5分钟）
        # 🔥 修改：移除5分钟限制，支持0值（不开启定时控制）
        if self.run_minutes > 0 and self.run_minutes < 5:
            print(f"[定时] 运行时长 {self.run_minutes} 分钟小于5分钟，自动调整为5分钟")
            self.run_minutes = 5
        if self.pause_minutes > 0 and self.pause_minutes < 5:
            print(f"[定时] 暂停时长 {self.pause_minutes} 分钟小于5分钟，自动调整为5分钟")
            self.pause_minutes = 5
        self.is_paused = False
        self.pause_start_time = None
        self.resume_check_time = None  # 恢复检查时间
        self.last_timed_check = None  # 🔥 修复：将在run_clicking_session开始时设置
        self.total_pause_duration = 0  # 累计暂停时长（秒）
        self.actual_run_duration = 0  # 实际运行时长（秒），排除暂停时间

        print(f"[[OK]] 完整配置加载完成:")
        print(f"    - 搜索页等待时间: {self.search_page_wait}秒")
        print(f"    - 详情页等待时间: {self.detail_page_wait}秒")
        print(f"    - 点击间隔: {self.click_interval_min}-{self.click_interval_max}秒")
        print(f"    - 目标点击数量: {self.target_count}")
        print(f"    - 销量范围: {self.sales_min} - {self.sales_max if self.sales_max else '无上限'}")
        print(f"    - 价格范围: {self.price_min} - {self.price_max if self.price_max else '无上限'}")
        print(f"    - 当前关键词: {self._get_current_keyword()}")
        print(f"    - 关键词进度: {self.current_keyword_index + 1}/{len(self.search_keywords)}")
        print(f"    - 定时控制: {'运行'+str(self.run_minutes)+'分钟, 暂停'+str(self.pause_minutes)+'分钟' if self.run_minutes > 0 else '未开启'}, 内存阈值{self.memory_threshold}MB")

        # ====================================================================================================
        # 【8】初始化日志记录
        # ====================================================================================================
        self.session_logs = []

        # ====================================================================================================
        # 【9】主图哈希值管理
        # ====================================================================================================
        # 修复路径问题 - 确保在正确的目录中创建data文件夹
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"[路径] 当前文件目录: {current_file_dir}")
        
        # 🔥 统一设置所有文件路径
        self._setup_correct_paths()
        
        # 设置哈希文件路径
        self.hash_file = os.path.join(self.data_dir, 'main_image_hashes.json')
        print(f"[路径] 哈希文件完整路径: {self.hash_file}")
        
        self.clicked_hashes = self._load_clicked_hashes()

        print(f"[哈希] 主图哈希管理已启动")
        print(f"   - 数据目录: {self.data_dir}")
        print(f"   - 哈希文件: {self.hash_file}")
        print(f"   - 已点击哈希数量: {len(self.clicked_hashes)}")

        # ====================================================================================================
        # 【10】完整标记系统（页面顺序 + 位置标记）
        # ====================================================================================================
        # 页面顺序文件 - 记录页面所有商品的顺序
        self.page_order_file = os.path.join(self.data_dir, 'page_order.json')

        # 位置标记文件 - 标记最后抓取的商品位置
        self.position_marker_file = os.path.join(self.data_dir, 'position_marker.json')
        self.position_marker = self._load_position_marker()

        # ====================================================================================================
        # 【11】兼容性：保留batch_manager（避免旧方法调用错误）
        # ====================================================================================================
        self.batch_manager = {
            'current_batch': 0,
            'batch_boundaries': [],
            'last_processed_position': 0,
            'batch_markers': {},
            'scroll_position': 0
        }

        print(f"[🔥 标记系统] 完整标记系统已启动")
        print(f"   - 页面顺序文件: {self.page_order_file}")
        print(f"   - 位置标记文件: {self.position_marker_file}")
        print(f"   - 上次标记位置: {self.position_marker.get('last_processed_index', '无')}")
        print(f"   - 上次标记商品: {self.position_marker.get('last_processed_name', '无')[:30] if self.position_marker.get('last_processed_name') else '无'}...")
        print(f"[兼容性] batch_manager已保留（兼容旧方法）")

        # ====================================================================================================
        # 【12】集成详情页提取器
        # ====================================================================================================
        self.detail_extractor = None
        self.detail_integration_enabled = False

        try:
            # 导入jiex模块
            from jiex import get_extractor
            
            # 获取当前浏览器ID
            browser_id = self.config.get('browser_info', {}).get('browser_id', 'default')
            
            # 获取详情页抓取器实例
            self.detail_extractor = get_extractor(browser_id)
            self.detail_integration_enabled = True
            
            print(f"[✅] 详情页提取器集成成功")
            print(f"    - 详情页处理: 已启用")
            print(f"    - 数据上传: 已启用")
            print(f"    - 浏览器ID: {browser_id[-6:]}")
            
        except Exception as e:
            print(f"[❌] 详情页提取器初始化失败: {e}")
            print(f"    - 详情页处理: 已禁用")
            self.detail_integration_enabled = False


    def _get_current_keyword(self) -> str:
        """获取当前关键词"""
        if self.search_keywords and 0 <= self.current_keyword_index < len(self.search_keywords):
            return self.search_keywords[self.current_keyword_index]
        return ""

    def _clear_startup_history_data(self):
        """🔥 启动时清理历史数据文件（保留session.json过滤数据和历史商品数据）"""
        try:
            # 🔥 不再删除product_history.json - 保留历史商品数据，支持zq.py的历史过滤功能
            # history_file = os.path.join(os.path.dirname(__file__), 'logs', 'product_history.json')
            # if os.path.exists(history_file):
            #     os.remove(history_file)
            #     print(f"[清理] 已删除历史商品文件: product_history.json")

            # 🔥 不再删除session.json - 这是zq.py传递的重要过滤数据
            # session_file = os.path.join(os.path.dirname(__file__), 'logs', 'session.json')
            # if os.path.exists(session_file):
            #     os.remove(session_file)
            #     print(f"[清理] 已删除会话文件: session.json")

            # 🔥 不再删除位置标记文件 - 支持断点续传
            # marker_file = os.path.join(os.path.dirname(__file__), 'data', 'position_marker.json')
            # if os.path.exists(marker_file):
            #     os.remove(marker_file)
            #     print(f"[清理] 已删除位置标记文件: position_marker.json")

            print(f"[✅] 启动清理完成，保留session.json、位置标记文件和历史商品数据")

        except Exception as e:
            print(f"[警告] 启动清理失败: {e}")

    def _setup_correct_paths(self):
        """🔥 设置正确的文件路径，使用正确的目录结构"""
        try:
            # 获取当前脚本所在目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 如果在浏览器目录中运行，使用正确的子目录结构
            if "browser_" in current_dir:
                # 使用 data/ 和 logs/ 子目录
                self.data_dir = os.path.join(current_dir, 'data')
                self.logs_dir = os.path.join(current_dir, 'logs')
                print(f"[路径] 检测到浏览器目录，使用 {self.data_dir} 和 {self.logs_dir}")
            else:
                # 在主目录中运行，使用主目录的 data/ 和 logs/
                self.data_dir = os.path.join(current_dir, 'data')
                self.logs_dir = os.path.join(current_dir, 'logs')
                print(f"[路径] 在主目录中运行，使用 {self.data_dir} 和 {self.logs_dir}")
            
            # 确保目录存在
            os.makedirs(self.data_dir, exist_ok=True)
            os.makedirs(self.logs_dir, exist_ok=True)
            
            # 设置正确的文件路径
            self.session_file = os.path.join(self.logs_dir, 'session.json')
            self.product_history_file = os.path.join(self.logs_dir, 'product_history.json')
            self.latest_products_file = os.path.join(self.data_dir, 'latest_20_products.json')
            
            print(f"[路径] 正确路径设置完成:")
            print(f"   - data目录: {self.data_dir}")
            print(f"   - logs目录: {self.logs_dir}")
            print(f"   - session.json: {self.session_file}")
            print(f"   - product_history.json: {self.product_history_file}")
            print(f"   - latest_20_products.json: {self.latest_products_file}")
            
        except Exception as e:
            print(f"[警告] 正确路径设置失败: {e}")

    def _load_config(self):
        """从同目录下的 config_api.json 加载配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'config_api.json')
        print(f"[INFO] 正在从 {config_path} 加载配置...")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[ERROR] 错误: 配置文件 '{config_path}' 未找到。")
            return {}
        except json.JSONDecodeError:
            print(f"[ERROR] 错误: 配置文件 'config_api.json' 格式无效。")
            return {}

    def _load_position_marker(self) -> dict:
        """🔥 只读：加载位置标记数据（不保存，只读取）"""
        try:
            if os.path.exists(self.position_marker_file):
                with open(self.position_marker_file, 'r', encoding='utf-8') as f:
                    marker = json.load(f)
                print(f"[✅] 加载位置标记: {marker.get('last_processed_name', '无')[:30] if marker.get('last_processed_name') else '无'}...")
                return marker
            else:
                print(f"[ℹ️] 位置标记文件不存在，使用默认标记")
                return {
                    'last_processed_index': -1,
                    'last_processed_name': '',
                    'last_processed_hash': '',
                    'last_crawled_position': -1,
                    'last_crawled_hash': '',
                    'total_crawled': 0,
                    'scroll_position': 0
                }
        except Exception as e:
            print(f"[错误] 加载位置标记失败: {e}")
            return {
                'last_processed_index': -1,
                'last_processed_name': '',
                'last_processed_hash': '',
                'last_crawled_position': -1,
                'last_crawled_hash': '',
                'total_crawled': 0,
                'scroll_position': 0
            }

    async def get_current_page_products(self) -> List[Dict[str, Any]]:
        """获取当前页面的商品数据"""
        try:
            
            page_products = await self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('._1unt3Js-');
                    const products = [];

                    cards.forEach(card => {
                        try {
                            const titleElement = card.querySelector('._3ANzdjkc');
                            const title = titleElement ? titleElement.innerText.trim() : '';

                            const imageElement = card.querySelector('img');
                            const imageUrl = imageElement ? imageElement.src : '';

                            const priceElement = card.querySelector('._3gmVc4Lg');
                            const price = priceElement ? priceElement.textContent.trim() : '';

                            const salesElement = card.querySelector('._2u4gEhMf');
                            const sales = salesElement ? salesElement.innerText.trim() : '';

                            if (title) {
                                products.push({
                                    name: title,
                                    image: imageUrl,
                                    price: price,
                                    sales: sales,
                                    element_index: products.length
                                });
                            }
                        } catch (e) {
                            console.warn('处理商品卡片时出错:', e);
                        }
                    });

                    return products;
                }
            """)

            print(f"[✅] 获取当前页面商品: {len(page_products)} 个")
            
            # 🔥 简化：如果扫描到0个商品，直接返回空列表
            if len(page_products) == 0:
                print("⚠️ 扫描到0个商品")
                return []  # 返回空列表，让上层处理
            
            return page_products

        except Exception as e:
            print(f"[错误] 获取页面商品失败: {e}")
            return []



    # ====================================================================================================
    # 【13】主执行逻辑 (高层工作流)
    # ====================================================================================================

    async def run_clicking_session(self):
        """🔥 主函数：运行自动循环点击会话，直到达到目标数量"""
        try:
            # 🔥 修复：在会话开始时设置start_time和last_timed_check，确保时间基准一致
            current_time = time.time()
            self.start_time = current_time
            self.last_timed_check = current_time  # 🔥 修复：同步设置时间基准
            print(f"[定时] 浏览器 {self.browser_id} 会话开始时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.start_time))}")
            print(f"[定时] 时间基准已同步设置 [浏览器:{self.browser_id}]")
            
            # 【13.1】连接浏览器
            if not await self.connect_browser():
                return

            cycle_count = 0
            total_success = 0
            # 🔥 修复：翻页就是点击循环次数，不需要单独的page_count
            
            while True:
                # 🔥 修复：先检查暂停状态，再执行循环逻辑
                if self.is_paused:
                    current_time = time.time()
                    
                    # 检查状态是否正常
                    if self.resume_check_time is None:
                        print(f"[WARNING] 暂停状态异常，resume_check_time为None，30秒后重试... [浏览器:{self.browser_id}]")
                        await asyncio.sleep(30)  # 状态异常时30秒检查一次
                        continue
                    
                    if current_time >= self.resume_check_time:
                        print(f"[RESUME] 暂停时间结束，自动恢复... [浏览器:{self.browser_id}]")
                        await self._resume_from_pause()
                    else:
                        # 还在暂停中，显示剩余时间
                        remaining_seconds = self.resume_check_time - current_time
                        remaining_minutes = remaining_seconds / 60
                        print(f"[PAUSE] 暂停中，还需 {remaining_minutes:.1f} 分钟... [浏览器:{self.browser_id}]")
                        
                        # 如果剩余时间少于30秒，延后检查时间
                        if remaining_seconds < 30:
                            print(f"[PAUSE] 即将恢复，延后检查时间... [浏览器:{self.browser_id}]")
                            await asyncio.sleep(remaining_seconds + 1)  # 延后到恢复时间后1秒
                        else:
                            await asyncio.sleep(30)  # 正常30秒检查一次
                        continue

                # 🔥 修复：只有在非暂停状态下才执行循环逻辑
                cycle_count += 1
                print(f"\n" + "="*80)
                print(f"[CYCLE] 开始第 {cycle_count} 轮点击循环")
                print(f"[PROGRESS] 累计成功: {total_success}/{self.target_count}")
                print(f"[PAGE] 当前轮数: {cycle_count}")
                print("="*80)

                # 🔥 新增：在循环开始时检查定时控制
                await self._check_timed_control()

                # 🔥 新增：内存监控检查（每轮循环检查一次）
                await self._check_memory_usage()

                # 【13.2】加载过滤后的商品数据
                products_to_click = self.load_filtered_products()
                if not products_to_click:
                    print("[警告] 没有从session.json加载到商品，尝试重新抓取...")
                    # 自动调用zq.py重新抓取
                    if await self.trigger_new_scraping():
                        print("[INFO] 等待新数据准备就绪...")
                        await self.wait_for_new_data()
                        # 🔥 修复：不需要增加page_count，因为翻页就是点击循环次数
                        continue
                    else:
                        print("[ERROR] zq.py抓取失败，尝试智能滑动加载...")
                        # 如果zq.py失败，进行智能滑动操作
                        if await self._smart_scroll_for_loading():
                            print("[INFO] 智能滑动完成，再次尝试抓取...")
                            # 滑动后再次尝试抓取
                            if await self.trigger_new_scraping():
                                print("[INFO] 等待新数据准备就绪...")
                                await self.wait_for_new_data()
                                # 🔥 修复：不需要增加page_count，因为翻页就是点击循环次数
                                continue
                            else:
                                print("[ERROR] 滑动后抓取仍然失败，会话结束")
                                break
                        else:
                            print("[ERROR] 智能滑动失败，会话结束")
                            break

                # 【13.3】执行批量点击
                stats = await self.click_products_batch(products_to_click)
                total_success += stats['success']

                # 【13.3.5】🔥 新增：点击任务完成后，必须执行位置标记滚动
                print(f"[POSITION] 点击任务完成，开始执行位置标记滚动...")
                if await self._execute_position_marker_scroll():
                    print(f"[POSITION] 位置标记滚动完成，等待新数据加载...")
                    await asyncio.sleep(2)  # 等待新数据加载
                else:
                    print(f"[WARNING] 位置标记滚动失败，继续执行后续逻辑...")

                # 【13.4】检查是否达到目标点击数量或翻页次数
                print(f"[SUMMARY] 第{cycle_count}轮完成，累计成功: {total_success}/{self.target_count}，页数: {cycle_count}")
                
                # 🔥 修复：翻页就是点击循环几次，用cycle_count来判断
                max_pages = self.config.get('parse_settings', {}).get('page_count', 2)
                if cycle_count >= max_pages:
                    print(f"[PAGE] 🎯 已达到最大翻页次数: {cycle_count}/{max_pages}")
                    print(f"[KEYWORD] 开始切换到下一个关键词...")
                    if await self._start_next_keyword_cycle():
                        print(f"[KEYWORD] ✅ 关键词切换成功")
                        return True  # 退出当前会话，让新关键词流程接管
                    else:
                        print(f"[KEYWORD] ❌ 关键词切换失败，继续当前流程")
                
                # 检查是否达到目标点击数量
                if self.target_count and total_success >= self.target_count:
                    print(f"[TARGET] 🎉 已达到目标点击数量: {total_success}/{self.target_count}")
                    print(f"[KEYWORD] 开始切换到下一个关键词...")
                    if await self._start_next_keyword_cycle():
                        print(f"[KEYWORD] ✅ 关键词切换成功")
                        return True  # 退出当前会话，让新关键词流程接管
                    else:
                        print(f"[KEYWORD] ❌ 关键词切换失败，继续当前流程")
                else:
                    print(f"[CONTINUE] 未达到目标数量，自动开始下一轮...")
                    # 🔥 简化：不再进行复杂的检测重试，直接进入下一轮
                    # 🔥 数据抓取和滑动操作交给zq.py处理
                    print("[INFO] 数据抓取和滑动操作已交给zq.py处理，继续下一轮...")
                    # 等待一下让zq.py有时间处理
                    await asyncio.sleep(3)

        except Exception as e:
            print(f"[CRITICAL] 点击会话期间发生严重错误: {e}")
        finally:
            # 【13.5】最后一步：关闭浏览器
            await self.close_browser()

    async def click_products_batch(self, products: List[Dict[str, Any]]) -> Dict[str, int]:
        """🔥 批量点击商品 - 简化版本"""
        if not products:
            print("[警告] 没有商品需要点击")
            return {'success': 0, 'failed': 0, 'total': 0}

        print(f"\n[🔥 批量点击] 开始处理 {len(products)} 个商品...")
        print("=" * 60)

        # 应用目标数量限制
        if self.target_count and len(products) > self.target_count:
            products = products[:self.target_count]
            print(f"[限制] 应用目标数量限制: {self.target_count}")

        stats = {'success': 0, 'failed': 0, 'total': len(products), 'skipped': 0}
    
        for i, product in enumerate(products):
            product_name = product.get('name', '未知商品')
            
            print(f"\n" + "="*60)
            print(f"[TARGET] [{i + 1}/{len(products)}] 处理商品")
            print(f"[PRODUCT] {product_name[:50]}...")
            print("="*60)

            if i > 0:
                await asyncio.sleep(random.uniform(self.click_interval_min, self.click_interval_max))

            # 直接处理商品
            success = await self.process_single_product(product, i + 1)
            if success:
                stats['success'] += 1
            else:
                stats['failed'] += 1

        # 最终统计
        print(f"\n" + "="*60)
        print(f"[DONE] 批量点击完成！")
        print(f"[SUMMARY] 最终统计:")
        print(f"   - 总商品数: {stats['total']}")
        print(f"   - 成功点击: {stats['success']}")
        print(f"   - 失败点击: {stats['failed']}")
        print(f"   - 成功率: {stats['success']/stats['total']*100:.1f}%" if stats['total'] > 0 else "0.0%")
        print("="*60)

        return stats

    # ====================================================================================================
    # 【15】浏览器管理
    # ====================================================================================================

    async def connect_browser(self):
        """【15.1】连接比特浏览器"""
        try:
            print(f"[CONNECT] 正在连接浏览器，端口: {self.debug_port}")

            self.playwright = await async_playwright().start()

            # 🔥 修复：添加连接超时处理
            try:
                self.browser = await asyncio.wait_for(
                    self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.debug_port}"),
                    timeout=10.0  # 10秒超时
                )
            except asyncio.TimeoutError:
                print(f"[ERROR] 浏览器连接超时（端口: {self.debug_port}）")
                await self.playwright.stop()
                return False

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

            print(f"[OK] 浏览器连接成功")
            print(f"[PAGE] 当前页面: {self.page.url[:100]}...")

            # 🔥 连接成功后立即清除浏览器内存数据
            await self._clear_browser_memory()

            # 🔥 分析页面批次
            await self.analyze_page_batches()

            return True

        except Exception as e:
            print(f"[ERROR] 浏览器连接失败: {e}")
            return False

    async def _clear_browser_memory(self):
        """【15.2】清除浏览器内存数据"""
        try:
            print(f"[清理] 开始清除浏览器内存数据...")

            clear_result = await self.page.evaluate("""
                () => {
                    try {
                        // 清除全局变量
                        if (window.rawData) delete window.rawData;
                        if (window.historyDataForSave) delete window.historyDataForSave;
                        if (window.latest20DataForSave) delete window.latest20DataForSave;
                        if (window.productHistory) delete window.productHistory;
                        if (window.batchMarkers) delete window.batchMarkers;

                        // ⚠️ 重要：不清除localStorage和sessionStorage，保留登录账号信息
                        // 清除localStorage
                        // if (window.localStorage) {
                        //     localStorage.clear();  // 注释掉，避免清除登录信息
                        // }

                        // 清除sessionStorage
                        // if (window.sessionStorage) {
                        //     sessionStorage.clear();  // 注释掉，避免清除登录信息
                        // }

                        // 清除控制台
                        if (console.clear) {
                            console.clear();
                        }

                        console.log('[清理] 浏览器内存数据清除完成');
                        return true;
                    } catch (e) {
                        console.error('[清理] 清除内存数据失败:', e);
                        return false;
                    }
                }
            """)

            if clear_result:
                print(f"[✅] 浏览器内存数据清除成功")
            else:
                print(f"[警告] 浏览器内存数据清除可能不完整")

        except Exception as e:
            print(f"[ERROR] 清除浏览器内存数据失败: {e}")

    async def analyze_page_batches(self) -> List[Dict]:
        """【15.3】分析页面商品批次，建立批次边界"""
        try:
            print(f"[批次] 开始分析页面商品批次...")

            # 获取所有商品的位置信息
            batch_info = await self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('._1unt3Js-');
                    const batches = [];
                    const windowHeight = window.innerHeight;

                    // 按垂直位置分组商品
                    const positions = [];
                    cards.forEach((card, index) => {
                        const rect = card.getBoundingClientRect();
                        positions.push({
                            index: index,
                            top: rect.top,
                            bottom: rect.bottom,
                            height: rect.height,
                            isVisible: rect.top >= 0 && rect.bottom <= windowHeight
                        });
                    });

                    // 根据可见性和位置分批
                    let currentBatch = [];
                    let batchIndex = 0;

                    for (let i = 0; i < positions.length; i++) {
                        const pos = positions[i];

                        // 如果是可见的或部分可见的，加入当前批次
                        if (pos.top < windowHeight && pos.bottom > 0) {
                            currentBatch.push(pos);
                        } else if (currentBatch.length > 0) {
                            // 当前批次结束，开始新批次
                            batches.push({
                                batchIndex: batchIndex,
                                products: currentBatch,
                                startIndex: currentBatch[0].index,
                                endIndex: currentBatch[currentBatch.length - 1].index,
                                boundary: currentBatch[currentBatch.length - 1].bottom
                            });
                            currentBatch = [];
                            batchIndex++;
                        }
                    }

                    // 处理最后一批
                    if (currentBatch.length > 0) {
                        batches.push({
                            batchIndex: batchIndex,
                            products: currentBatch,
                            startIndex: currentBatch[0].index,
                            endIndex: currentBatch[currentBatch.length - 1].index,
                            boundary: currentBatch[currentBatch.length - 1].bottom
                        });
                    }

                    return {
                        totalProducts: positions.length,
                        batches: batches,
                        currentScrollY: window.scrollY
                    };
                }
            """)

            # 更新批次管理器
            self.batch_manager['batch_boundaries'] = batch_info['batches']
            self.batch_manager['scroll_position'] = batch_info['currentScrollY']

            print(f"[批次] 分析完成:")
            print(f"   - 总商品数: {batch_info['totalProducts']}")
            print(f"   - 批次数量: {len(batch_info['batches'])}")
            print(f"   - 当前滚动位置: {batch_info['currentScrollY']}")

            for i, batch in enumerate(batch_info['batches']):
                print(f"   - 批次{i}: 商品{batch['startIndex']}-{batch['endIndex']} (边界: {batch['boundary']})")

            return batch_info['batches']

        except Exception as e:
            print(f"[ERROR] 分析页面批次失败: {e}")
            return []

    async def return_to_search_page(self):
        """【15.4】使用浏览器后退返回搜索页"""
        try:
            print("🔙 准备返回搜索页...")
            return_start_time = time.time()

            # 使用浏览器后退功能
            print("   ⬅️ 执行浏览器后退...")
            await self.page.go_back()

            # 等待搜索页加载
            search_wait_time = self.get_random_wait_time(self.search_page_wait)
            variance_info = f"-2~+3秒" if self.search_page_wait >= 10.0 else "±1秒"
            min_range = max(0.5, self.search_page_wait + (-2.0 if self.search_page_wait >= 10.0 else -1.0))
            max_range = self.search_page_wait + (3.0 if self.search_page_wait >= 10.0 else 1.0)
            print(f"    等待搜索页加载: {search_wait_time}秒 (配置: {self.search_page_wait}秒, 浮动: {variance_info}, 范围: {min_range}~{max_range}秒)")
            await asyncio.sleep(search_wait_time)

            # 验证是否成功返回搜索页
            try:
                current_url = self.page.url
                print(f"   [PAGE] 当前页面: {current_url[:80]}...")

                # 检查是否有商品列表
                product_count = await self.page.evaluate("""
                    () => {
                        const cards = document.querySelectorAll('._1unt3Js-');
                        return cards.length;
                    }
                """)

                if product_count > 0:
                    print(f"   [OK] 成功返回搜索页，发现 {product_count} 个商品")
                else:
                    print(f"   [WARNING] 返回的页面没有商品列表，可能需要额外等待")
                    # 额外等待一下
                    await asyncio.sleep(2)

            except Exception as e:
                print(f"   [WARNING] 验证返回页面时出错: {e}")

            return_end_time = time.time()
            total_return_time = return_end_time - return_start_time
            print(f"   [OK] 返回操作完成，总耗时: {total_return_time:.1f}秒")

        except Exception as e:
            print(f"   [ERROR] 返回搜索页时出错: {e}")



    # ====================================================================================================
    # 【17】主图哈希值管理方法
    # ====================================================================================================
    def _load_clicked_hashes(self) -> set:
        """【17.1】加载已点击商品的主图哈希值"""
        try:
            # 确保data目录存在
            os.makedirs(self.data_dir, exist_ok=True)
            print(f"[哈希] 数据目录: {self.data_dir}")
            print(f"[哈希] 哈希文件: {self.hash_file}")

            if os.path.exists(self.hash_file):
                with open(self.hash_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                hashes = set(data.get('hashes', []))
                print(f"[哈希] 成功加载 {len(hashes)} 个已点击哈希值")
                return hashes
            else:
                print(f"[哈希] 哈希文件不存在，创建新的哈希集合")
                return set()
        except Exception as e:
            print(f"[错误] 加载哈希文件失败: {e}")
            return set()

    def _save_clicked_hashes(self):
        """【17.2】保存已点击商品的主图哈希值"""
        try:
            os.makedirs(self.data_dir, exist_ok=True)

            data = {
                'hashes': list(self.clicked_hashes),
                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
                'total_count': len(self.clicked_hashes)
            }

            with open(self.hash_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            print(f"[保存] 哈希文件已更新，共 {len(self.clicked_hashes)} 个哈希值")
        except Exception as e:
            print(f"[错误] 保存哈希文件失败: {e}")

    def _get_main_image_hash(self, product_data: dict) -> str:
        """【17.3】从商品数据中提取主图URL并计算哈希值 - 统一哈希算法 【重复功能：与 generate_product_hash 功能重复】"""
        try:
            # 优先使用主图URL
            main_image_url = product_data.get('image', '')
            if main_image_url and main_image_url != '未找到图片':
                # 提取数字部分（如果有）
                numbers = ''.join(filter(str.isdigit, main_image_url))
                
                if numbers:
                    # 数字 + 哈希值，总长度16位
                    hash_obj = hashlib.md5(main_image_url.encode('utf-8'))
                    return numbers + hash_obj.hexdigest()[:16-len(numbers)]
                else:
                    # 纯哈希值，16位
                    hash_obj = hashlib.md5(main_image_url.encode('utf-8'))
                    return hash_obj.hexdigest()[:16]
            
            # 如果没有图片，使用商品名称
                name = product_data.get('name', '')
                if name:
                    hash_obj = hashlib.md5(name.encode('utf-8'))
                    return hash_obj.hexdigest()[:16]
            
                    return ""

        except Exception as e:
            print(f"[错误] 生成主图哈希失败: {e}")
            return ""

    def generate_product_hash(self, product_data: dict) -> str:
        """生成商品哈希值 - 基于商品名称"""
        try:
            name = product_data.get('name', '')
            if name:
                hash_obj = hashlib.md5(name.encode('utf-8'))
                return hash_obj.hexdigest()
            return ""
        except Exception as e:
            print(f"[错误] 生成商品哈希失败: {e}")
            return ""

    def _is_already_clicked(self, product_data: dict) -> bool:
        """【17.4】检查商品是否已经被点击过（通过主图哈希值模糊匹配）"""
        try:
            current_hash = self._get_main_image_hash(product_data)
            if not current_hash:
                return False

            # 模糊匹配：检查当前哈希是否包含在已点击的哈希中，或者已点击的哈希包含在当前哈希中
            for clicked_hash in self.clicked_hashes:
                if current_hash in clicked_hash or clicked_hash in current_hash:
                    print(f"[跳过] 商品已点击过，哈希匹配: {current_hash} ≈ {clicked_hash}")
                    return True

            return False

        except Exception as e:
            print(f"[错误] 检查哈希匹配失败: {e}")
            return False

    def _is_manual_extraction_mode(self):
        """检查是否在手动解析模式下"""
        try:
            # 获取当前浏览器ID
            browser_id = self.config.get('browser_info', {}).get('browser_id', 'default')
            
            # 检查是否存在手动解析状态文件
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            
            # 检查当前目录的状态文件
            status_file = os.path.join(current_dir, "manual_extraction_status.json")
            if os.path.exists(status_file):
                import json
                with open(status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                    # 只检查当前浏览器是否在手动解析模式下
                    return status_data.get(browser_id, False)
            
            # 检查主目录的状态文件
            main_status_file = os.path.join(
                os.path.dirname(current_dir), 
                "bite_browser", 
                "manual_extraction_status.json"
            )
            if os.path.exists(main_status_file):
                import json
                with open(main_status_file, 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                    # 只检查当前浏览器是否在手动解析模式下
                    return status_data.get(browser_id, False)
            
            return False
        except Exception as e:
            print(f"[ERROR] 检查手动解析模式失败: {e}")
            return False

    def _add_clicked_hash(self, product_data: dict):
        """【17.5】添加已点击商品的主图哈希值"""
        try:
            main_hash = self._get_main_image_hash(product_data)
            if main_hash:
                self.clicked_hashes.add(main_hash)
                print(f"[记录] 添加主图哈希: {main_hash}")
                # 立即保存到文件
                self._save_clicked_hashes()
        except Exception as e:
            print(f"[错误] 添加哈希失败: {e}")

  
    # 🔥 位置定位方法已删除，标记信息从latest_20_products.json读取
    # ====================================================================================================
    # 【20】滚动到标记位置方法
    # ====================================================================================================
    async def scroll_to_marked_position_and_load_new_data(self) -> bool:
        """【20.1】滚动到最后标记位置并加载新数据"""
        try:
            print(f"[🔄 滚动加载] 开始滚动到标记位置并加载新数据...")

            last_position = self.position_marker.get('last_crawled_position', -1)
            last_hash = self.position_marker.get('last_crawled_hash', '')

            if last_position == -1 or not last_hash:
                print(f"[滚动加载] 没有标记位置，直接滚动一小行")
                await self.gentle_scroll(200)
                return True

            print(f"[滚动加载] 标记位置: {last_position}, 商品哈希: {last_hash[:16]}")

            # 🔥 第一步：滚动到最后标记的商品位置
            scroll_result = await self.page.evaluate("""
                (targetHash) => {
                    const cards = document.querySelectorAll('._1unt3Js-');

                    // 查找标记的商品
                    for (let i = 0; i < cards.length; i++) {
                        const card = cards[i];
                        const imageElement = card.querySelector('img');
                        if (imageElement && imageElement.src) {
                            // 生成哈希值进行匹配
                            const imageUrl = imageElement.src;
                            // 简单的数字提取匹配
                            const numbers = imageUrl.replace(/[^0-9]/g, '');
                            const targetNumbers = targetHash.replace(/[^0-9]/g, '');

                            if (numbers && targetNumbers && (numbers.includes(targetNumbers) || targetNumbers.includes(numbers))) {
                                // 找到标记商品，滚动到此位置
                                // 🔥 修复：使用速率限制滚动，但保持原有调用方式
                                const rect = card.getBoundingClientRect();
                                const currentScrollY = window.pageYOffset;
                                const targetScrollY = currentScrollY + rect.top - window.innerHeight / 2;
                                const scrollDistance = targetScrollY - currentScrollY;
                                
                                // 使用速率限制滚动，而不是scrollIntoView
                                if (Math.abs(scrollDistance) > 100) {
                                    // 分段滚动，每段最多600像素
                                    const maxSegment = 600;
                                    const segments = Math.ceil(Math.abs(scrollDistance) / maxSegment);
                                    const segmentDistance = scrollDistance / segments;
                                    
                                    for (let i = 0; i < segments; i++) {
                                        const currentSegment = i === segments - 1 ? 
                                            scrollDistance - (segmentDistance * i) : segmentDistance;
                                        
                                        window.scrollBy(0, currentSegment);
                                        
                                        // 段间延迟1秒
                                        if (i < segments - 1) {
                                            await new Promise(resolve => setTimeout(resolve, 1000));
                                        }
                                    }
                                }
                                
                                console.log(`[滚动] 找到标记商品，位置: ${i}`);
                                return { success: true, position: i };
                            }
                        }
                    }

                    console.log('[滚动] 未找到标记商品');
                    return { success: false, position: -1 };
                }
            """, last_hash)

            if scroll_result.get('success'):
                print(f"[滚动加载] 成功滚动到标记商品位置: {scroll_result.get('position')}")
                # 等待滚动完成
                await asyncio.sleep(2)
            else:
                print(f"[滚动加载] 未找到标记商品，滚动到页面底部")
                await self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

            # 🔥 第二步：再滚动一小行，触发新数据加载
            print(f"[滚动加载] 再滚动一小行，触发新数据加载...")
            await self.gentle_scroll(300)  # 滚动300px
            await asyncio.sleep(3)  # 等待新数据加载

            print(f"[✅ 滚动加载] 滚动完成，新数据应该已加载")
            return True

        except Exception as e:
            print(f"[错误] 滚动到标记位置失败: {e}")
            return False

    # ====================================================================================================
    # 【21】数据加载方法
    # ====================================================================================================
    def load_filtered_products(self) -> List[Dict[str, Any]]:
        """【21.1】加载过滤好的商品数据（优先内存，备用session.json）"""
        # TODO: 这里需要与抓取器集成，优先获取内存中过滤好的数据
        # 目前先从session.json加载

        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                products = data.get('products', [])
                print(f"[[OK]] 加载过滤好的商品数据: {len(products)} 个")
                return products
            else:
                print(f"[警告] 会话文件不存在: {self.session_file}")
                return []
        except Exception as e:
            print(f"[错误] 加载商品数据失败: {e}")
            return []

    def load_latest_20_products(self) -> List[Dict[str, Any]]:
        """【21.2】加载最新20个抓取的商品数据（用于标记）"""
        try:
            if os.path.exists(self.latest_products_file):
                with open(self.latest_products_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                products = data.get('products', [])
                print(f"[标记] 加载最新20个商品数据: {len(products)} 个")
                return products
            else:
                print(f"[警告] 最新20个商品文件不存在: {self.latest_products_file}")
                return []
        except Exception as e:
            print(f"[错误] 加载最新20个商品数据失败: {e}")
            return []

    # ====================================================================================================
    # 【22】商品匹配算法
    # ====================================================================================================
    def calculate_name_similarity(self, name1: str, name2: str) -> float:
        """【22.1】计算商品名称相似度（连续字符匹配）"""
        if not name1 or not name2:
            return 0.0

        # 找最长连续匹配子串
        max_match_length = 0
        len1, len2 = len(name1), len(name2)

        for i in range(len1):
            for j in range(len2):
                match_length = 0
                while (i + match_length < len1 and
                       j + match_length < len2 and
                       name1[i + match_length] == name2[j + match_length]):
                    match_length += 1
                max_match_length = max(max_match_length, match_length)

        # 计算匹配度（基于较短字符串的长度）
        base_length = min(len1, len2)
        if base_length == 0:
            return 0.0

        similarity = max_match_length / base_length
        return similarity

    def extract_price_number(self, price_str: str) -> str:
        """【22.2】提取价格中的数字部分"""
        if not price_str:
            return ""

        # 移除所有非数字和小数点的字符
        import re
        numbers = re.findall(r'\d+\.?\d*', price_str)
        return ''.join(numbers) if numbers else ""

    def match_product(self, target_product: Dict[str, Any], page_products: List[Dict[str, Any]]) -> Dict[str, Any]:
        """【22.3】匹配商品（只匹配名称和URL哈希值）"""
        target_name = target_product.get('name', '')
        target_image = target_product.get('image', '')

        print(f"[SEARCH] 匹配目标商品: {target_name[:30]}...")

        for page_product in page_products:
            page_name = page_product.get('name', '')
            page_image = page_product.get('image', '')

            # 第一优先级：商品名称80%匹配
            name_similarity = self.calculate_name_similarity(target_name, page_name)
            if name_similarity >= 0.8:
                print(f"[OK] 名称匹配成功 ({name_similarity:.1%}): {page_name[:30]}...")
                return page_product

            # 第二优先级：URL完全匹配（如果都有URL）
            if target_image and page_image and target_image == page_image:
                print(f"[OK] URL匹配成功: {page_name[:30]}...")
                return page_product



        print(f"[ERROR] 未找到匹配商品: {target_name[:30]}...")
        return None

    # ====================================================================================================
    # 【23】人性化行为模拟方法
    # ====================================================================================================
    def generate_random_offset(self, max_offset: int = 10) -> Dict[str, int]:
        """【23.1】生成随机偏移量"""
        return {
            'x': random.randint(-max_offset, max_offset),
            'y': random.randint(-max_offset, max_offset)
        }

    def generate_mouse_path(self, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 20) -> List[Dict[str, int]]:
        """【23.2】生成贝塞尔曲线鼠标轨迹"""
        path = []

        # 生成控制点（添加随机性）
        mid_x = (start_x + end_x) / 2 + random.randint(-50, 50)
        mid_y = (start_y + end_y) / 2 + random.randint(-50, 50)

        for i in range(steps + 1):
            t = i / steps

            # 二次贝塞尔曲线公式
            x = int((1 - t) ** 2 * start_x + 2 * (1 - t) * t * mid_x + t ** 2 * end_x)
            y = int((1 - t) ** 2 * start_y + 2 * (1 - t) * t * mid_y + t ** 2 * end_y)

            path.append({'x': x, 'y': y})

        return path

    def get_random_wait_time(self, base_time: float) -> float:
        """【23.3】获取随机等待时间

        规则:
        - 配置时间 < 10秒: ±1秒浮动
        - 配置时间 >= 10秒: -2秒到+3秒浮动
        - 最小时间不低于0.5秒

        Args:
            base_time: 配置的基础时间

        Returns:
            随机化后的等待时间
        """
        # 根据配置时间确定浮动范围
        if base_time >= 10.0:
            # 10秒以上：-2秒到+3秒
            min_variance = -2.0
            max_variance = 3.0
        else:
            # 10秒以下：±1秒
            min_variance = -1.0
            max_variance = 1.0

        # 计算随机时间范围
        min_time = max(0.5, base_time + min_variance)  # 最小0.5秒
        max_time = base_time + max_variance

        random_time = random.uniform(min_time, max_time)

        return round(random_time, 1)

    # ====================================================================================================
    # 【24】位置标记管理系统（断点续传）
    # ====================================================================================================

    def _save_position_marker(self, index: int, product_name: str):
        """【24.1】保存处理位置标记 - 🔥 已禁用，改由 zq.py 负责"""
        try:
            marker_file = os.path.join(self.data_dir, 'position_marker.json')
            marker = {
                'last_processed_index': index,
                'last_processed_name': product_name,
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
                'session_id': self._get_session_id()
            }

            # 确保data目录存在
            os.makedirs(self.data_dir, exist_ok=True)

            with open(marker_file, 'w', encoding='utf-8') as f:
                json.dump(marker, f, ensure_ascii=False, indent=2)

            print(f"[MARKER] 位置标记已保存: 索引{index}, 商品{product_name[:20]}...")

        except Exception as e:
            print(f"[ERROR] 保存位置标记失败: {e}")

    def _verify_position_marker(self, page_products: List[Dict], index: int, expected_name: str) -> bool:
        """【24.2】验证位置标记是否有效"""
        try:
            if index >= len(page_products):
                print(f"[VERIFY] 标记索引超出范围: {index} >= {len(page_products)}")
                return False

            actual_name = page_products[index].get('name', '').strip()
            if actual_name == expected_name:
                print(f"[VERIFY] 位置标记验证成功: 索引{index}匹配商品名称")
                return True
            else:
                print(f"[VERIFY] 位置标记验证失败:")
                print(f"   期望: {expected_name[:30]}...")
                print(f"   实际: {actual_name[:30]}...")
                return False

        except Exception as e:
            print(f"[ERROR] 验证位置标记失败: {e}")
            return False

    def _get_session_id(self) -> str:
        """【24.3】获取会话ID"""
        try:
            # 基于当前时间和配置生成简单的会话ID
            import hashlib
            session_data = f"{time.time()}_{self.debug_port}"
            return hashlib.md5(session_data.encode()).hexdigest()[:8]
        except:
            return "unknown"

    def _clear_position_marker(self):
        """【24.4】清除位置标记（重新开始时调用）"""
        try:
            marker_file = os.path.join(self.data_dir, 'position_marker.json')
            if os.path.exists(marker_file):
                os.remove(marker_file)
                print(f"[MARKER] 位置标记已清除")
        except Exception as e:
            print(f"[ERROR] 清除位置标记失败: {e}")

    # ====================================================================================================
    # 【25】主图哈希值计算方法
    # ====================================================================================================

    def _calculate_image_hash(self, image_url: str) -> str:
        """【25.1】计算图片URL的哈希值"""
        try:
            import hashlib
            if not image_url:
                return ""

            # 使用MD5计算哈希值
            hash_obj = hashlib.md5(image_url.encode('utf-8'))
            return hash_obj.hexdigest()

        except Exception as e:
            print(f"[ERROR] 计算图片哈希失败: {e}")
            return ""

    # ====================================================================================================
    # 【26】核心点击功能
    # ====================================================================================================


    async def click_product_humanized(self, target_product: Dict[str, Any]) -> bool:
        """【26.1】人性化点击单个商品（基于匹配逻辑）"""
        try:
            product_name = target_product.get('name', '未知商品')
            print(f"[TARGET] 准备点击商品: {product_name[:30]}...")

            # 🔥 0. 检查商品是否已经被点击过（通过主图哈希值）
            if self._is_already_clicked(target_product):
                print(f"⏭️ 商品已点击过，跳过: {product_name[:30]}")
                return False

            # 1. 获取当前页面商品
            page_products = await self.get_current_page_products()
            if not page_products:
                print(f"[ERROR] 当前页面没有商品数据")
                
                # 页面无数据，返回失败让上层处理
                return False
                
                return False

            # 2. 匹配目标商品
            matched_product = self.match_product(target_product, page_products)
            if not matched_product:
                print(f"[ERROR] 未找到匹配的商品，跳过")
                return False

            # 3. 执行人性化点击
            element_index = matched_product.get('element_index', 0)

            # 使用JavaScript在浏览器内执行人性化点击
            click_result = await self.page.evaluate("""
                (elementIndex) => {
                    // ====================================================================================================
                    // JavaScript 人性化点击核心代码
                    // ====================================================================================================

                    // 1. 商品定位函数（基于索引）
                    function getProductElement(elementIndex) {
                        const productCards = document.querySelectorAll('._1unt3Js-');
                        if (elementIndex >= 0 && elementIndex < productCards.length) {
                            return productCards[elementIndex];
                        }
                        return null;
                    }

                    // 2. 生成随机点击位置
                    function getRandomClickPoint(element) {
                        const rect = element.getBoundingClientRect();
                        const padding = 8;

                        return {
                            x: rect.left + padding + Math.random() * (rect.width - 2 * padding),
                            y: rect.top + padding + Math.random() * (rect.height - 2 * padding)
                        };
                    }

                    // 3. 生成鼠标轨迹
                    function generateMousePath(startX, startY, endX, endY, steps = 15) {
                        const path = [];
                        const midX = (startX + endX) / 2 + (Math.random() - 0.5) * 100;
                        const midY = (startY + endY) / 2 + (Math.random() - 0.5) * 100;

                        for (let i = 0; i <= steps; i++) {
                            const t = i / steps;
                            const x = Math.round((1 - t) ** 2 * startX + 2 * (1 - t) * t * midX + t ** 2 * endX);
                            const y = Math.round((1 - t) ** 2 * startY + 2 * (1 - t) * t * midY + t ** 2 * endX);
                            path.push({ x, y });
                        }
                        return path;
                    }

                    // 4. 模拟鼠标移动
                    function simulateMouseMove(path) {
                        return new Promise((resolve) => {
                            let index = 0;

                            function moveNext() {
                                if (index >= path.length) {
                                    resolve();
                                    return;
                                }

                                const point = path[index];

                                // 创建鼠标移动事件
                                const moveEvent = new MouseEvent('mousemove', {
                                    clientX: point.x,
                                    clientY: point.y,
                                    bubbles: true,
                                    cancelable: true
                                });

                                document.dispatchEvent(moveEvent);
                                index++;

                                // 随机延迟 (1-5ms)
                                setTimeout(moveNext, Math.random() * 4 + 1);
                            }

                            moveNext();
                        });
                    }

                    // 5. 人性化点击执行
                    async function executeHumanizedClick(element, clickPoint) {
                        // 先悬停
                        const hoverEvent = new MouseEvent('mouseenter', {
                            clientX: clickPoint.x,
                            clientY: clickPoint.y,
                            bubbles: true,
                            cancelable: true
                        });
                        element.dispatchEvent(hoverEvent);

                        // 短暂延迟
                        await new Promise(resolve => setTimeout(resolve, Math.random() * 200 + 100));

                        // 鼠标按下
                        const mouseDownEvent = new MouseEvent('mousedown', {
                            clientX: clickPoint.x,
                            clientY: clickPoint.y,
                            bubbles: true,
                            cancelable: true,
                            button: 0
                        });
                        element.dispatchEvent(mouseDownEvent);

                        // 短暂延迟 (模拟按下时间)
                        await new Promise(resolve => setTimeout(resolve, Math.random() * 50 + 30));

                        // 鼠标抬起
                        const mouseUpEvent = new MouseEvent('mouseup', {
                            clientX: clickPoint.x,
                            clientY: clickPoint.y,
                            bubbles: true,
                            cancelable: true,
                            button: 0
                        });
                        element.dispatchEvent(mouseUpEvent);

                        // 点击事件
                        const clickEvent = new MouseEvent('click', {
                            clientX: clickPoint.x,
                            clientY: clickPoint.y,
                            bubbles: true,
                            cancelable: true,
                            button: 0
                        });
                        element.dispatchEvent(clickEvent);

                        return true;
                    }

                    // ====================================================================================================
                    // 主执行流程
                    // ====================================================================================================
                    return new Promise(async (resolve) => {
                        try {
                            // 1. 获取商品元素（基于索引）
                            const productElement = getProductElement(elementIndex);
                            if (!productElement) {
                                resolve({ success: false, error: '未找到商品元素' });
                                return;
                            }

                            // 2. 滚动到商品位置 (如果需要)
                            productElement.scrollIntoView({
                                behavior: 'smooth',
                                block: 'center'
                            });

                            // 等待滚动完成 + 额外等待时间确保页面稳定
                            await new Promise(resolve => setTimeout(resolve, Math.random() * 500 + 300));
                            // 🔥 新增：定位移动后的额外等待时间（1.5-2秒）
                            await new Promise(resolve => setTimeout(resolve, Math.random() * 500 + 1500));

                            // 3. 获取当前鼠标位置 (模拟)
                            const currentMouseX = Math.random() * window.innerWidth;
                            const currentMouseY = Math.random() * window.innerHeight;

                            // 4. 获取随机点击位置
                            const clickPoint = getRandomClickPoint(productElement);

                            // 5. 生成鼠标轨迹
                            const mousePath = generateMousePath(
                                currentMouseX, currentMouseY,
                                clickPoint.x, clickPoint.y
                            );

                            // 6. 模拟鼠标移动
                            await simulateMouseMove(mousePath);

                            // 7. 执行人性化点击
                            await executeHumanizedClick(productElement, clickPoint);

                            console.log('[OK] 商品点击完成，索引:', elementIndex);
                            resolve({
                                success: true,
                                clickPoint: clickPoint,
                                elementIndex: elementIndex
                            });

                        } catch (error) {
                            console.error('[ERROR] 点击执行失败:', error);
                            resolve({ success: false, error: error.message });
                        }
                    });
                }
            """, element_index)

            if click_result.get('success'):
                matched_name = matched_product.get('name', '未知商品')
                print(f"[OK] 商品点击成功: {matched_name[:30]}...")

                # 🔥 保存已点击商品的主图哈希值
                self._add_clicked_hash(target_product)

                # 等待页面跳转或加载
                wait_time = self.get_random_wait_time(self.detail_page_wait)
                variance_info = f"-2~+3秒" if self.detail_page_wait >= 10.0 else "±1秒"
                print(f"    页面跳转等待: {wait_time}秒 (配置: {self.detail_page_wait}秒, 浮动: {variance_info})")
                await asyncio.sleep(wait_time)

                return True
            else:
                print(f"[ERROR] 商品点击失败: {click_result.get('error', '未知错误')}")
                return False

        except Exception as e:
            print(f"[ERROR] 点击商品时发生错误: {e}")
            return False

    # ====================================================================================================
    # 【27】智能位置检测
    # ====================================================================================================
    async def check_product_visibility(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """【27.1】检查商品在页面中的可见性和位置"""
        try:
            product_name = product_data.get('name', '')

            # 在页面中查找匹配的商品元素
            visibility_info = await self.page.evaluate(f"""
                () => {{
                    const targetName = "{product_name[:30]}";  // 使用前30个字符匹配
                    const cards = document.querySelectorAll('._1unt3Js-');
                    const windowHeight = window.innerHeight;

                    for (let i = 0; i < cards.length; i++) {{
                        const card = cards[i];
                        const titleElement = card.querySelector('._3ANzdjkc');

                        if (titleElement) {{
                            const cardName = titleElement.innerText.trim();

                            // 简单的名称匹配（包含关系）
                            if (cardName.includes(targetName.substring(0, 20)) ||
                                targetName.includes(cardName.substring(0, 20))) {{

                                const rect = card.getBoundingClientRect();

                                return {{
                                    found: true,
                                    index: i,
                                    top: rect.top,
                                    bottom: rect.bottom,
                                    height: rect.height,
                                    isVisible: rect.top >= 0 && rect.bottom <= windowHeight,
                                    isPartialVisible: (rect.top < windowHeight && rect.bottom > 0),
                                    distanceFromTop: rect.top,
                                    distanceFromBottom: rect.top - windowHeight,
                                    cardName: cardName
                                }};
                            }}
                        }}
                    }}

                    return {{ found: false }};
                }}
            """)

            if visibility_info.get('found'):
                # 分类可见性
                if visibility_info.get('isVisible'):
                    category = 'visible'
                    action = 'click_immediately'
                    scroll_distance = 0
                elif visibility_info.get('isPartialVisible'):
                    category = 'partial'
                    action = 'click_immediately'
                    scroll_distance = 0
                elif visibility_info.get('distanceFromBottom', 0) <= 300:
                    category = 'near'
                    action = 'scroll_then_click'
                    scroll_distance = min(visibility_info.get('distanceFromBottom', 0) + 100, 300)
                else:
                    category = 'far'
                    action = 'defer_to_end'
                    scroll_distance = visibility_info.get('distanceFromBottom', 0)

                return {
                    **visibility_info,
                    'category': category,
                    'action': action,
                    'scroll_distance': scroll_distance,
                    'product_data': product_data
                }
            else:
                return {
                    'found': False,
                    'category': 'not_found',
                    'action': 'skip',
                    'product_data': product_data
                }

        except Exception as e:
            print(f"   [ERROR] 检查商品可见性失败: {e}")
            return {
                'found': False,
                'category': 'error',
                'action': 'skip',
                'product_data': product_data
            }

    # ====================================================================================================
    # 【28】页面批次分析与滚动
    # ====================================================================================================
    async def analyze_page_batches(self) -> List[Dict]:
        """【28.1】分析页面商品批次，建立批次边界"""
        try:
            print(f"[批次] 开始分析页面商品批次...")

            # 获取所有商品的位置信息
            batch_info = await self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('._1unt3Js-');
                    const batches = [];
                    const windowHeight = window.innerHeight;

                    // 按垂直位置分组商品
                    const positions = [];
                    cards.forEach((card, index) => {
                        const rect = card.getBoundingClientRect();
                        positions.push({
                            index: index,
                            top: rect.top,
                            bottom: rect.bottom,
                            height: rect.height,
                            isVisible: rect.top >= 0 && rect.bottom <= windowHeight
                        });
                    });

                    // 根据可见性和位置分批
                    let currentBatch = [];
                    let batchIndex = 0;

                    for (let i = 0; i < positions.length; i++) {
                        const pos = positions[i];

                        // 如果是可见的或部分可见的，加入当前批次
                        if (pos.top < windowHeight && pos.bottom > 0) {
                            currentBatch.push(pos);
                        } else if (currentBatch.length > 0) {
                            // 当前批次结束，开始新批次
                            batches.push({
                                batchIndex: batchIndex,
                                products: currentBatch,
                                startIndex: currentBatch[0].index,
                                endIndex: currentBatch[currentBatch.length - 1].index,
                                boundary: currentBatch[currentBatch.length - 1].bottom
                            });
                            currentBatch = [];
                            batchIndex++;
                        }
                    }

                    // 处理最后一批
                    if (currentBatch.length > 0) {
                        batches.push({
                            batchIndex: batchIndex,
                            products: currentBatch,
                            startIndex: currentBatch[0].index,
                            endIndex: currentBatch[currentBatch.length - 1].index,
                            boundary: currentBatch[currentBatch.length - 1].bottom
                        });
                    }

                    return {
                        totalProducts: positions.length,
                        batches: batches,
                        currentScrollY: window.scrollY
                    };
                }
            """)

            # 更新批次管理器
            self.batch_manager['batch_boundaries'] = batch_info['batches']
            self.batch_manager['scroll_position'] = batch_info['currentScrollY']

            print(f"[批次] 分析完成:")
            print(f"   - 总商品数: {batch_info['totalProducts']}")
            print(f"   - 批次数量: {len(batch_info['batches'])}")
            print(f"   - 当前滚动位置: {batch_info['currentScrollY']}")

            for i, batch in enumerate(batch_info['batches']):
                print(f"   - 批次{i}: 商品{batch['startIndex']}-{batch['endIndex']} (边界: {batch['boundary']})")

            return batch_info['batches']

        except Exception as e:
            print(f"[ERROR] 分析页面批次失败: {e}")
            return []

    async def smart_scroll_to_next_batch(self) -> bool:
        """【28.2】智能滚动到下一批商品（基于商品位置而非批次）"""
        try:
            # 🔥 新增：检查第二批次商品是否加载出来
            print(f"[智能滚动] 检查第二批次商品加载状态...")
            
            # 获取当前页面的商品数量
            current_product_count = await self.page.evaluate("""
                () => {
                    const cards = document.querySelectorAll('._1unt3Js-');
                    return cards.length;
                }
            """)
            
            print(f"[智能滚动] 当前页面商品数量: {current_product_count}")
            
            # 如果商品数量没有增加，说明第二批次没有加载出来
            if current_product_count <= 20:  # 假设每批次20个商品
                print(f"[智能滚动] 第二批次商品未加载，使用位置标记策略...")
                
                # 从position_marker.json获取标记的商品信息
                marked_index = self.position_marker.get('last_processed_index', -1)
                marked_name = self.position_marker.get('last_processed_name', '')
                
                if marked_index >= 0 and marked_name:
                    print(f"[智能滚动] 定位到标记商品: 编号{marked_index}, 名称: {marked_name[:30]}...")
                    
                    # 定位到标记商品的位置（不点击）
                    await self._locate_marked_product(marked_index, marked_name)
                    
                    # 根据编号计算需要滑动的行数
                    rows_to_scroll = self._calculate_rows_to_scroll(marked_index)
                    print(f"[智能滚动] 需要滑动 {rows_to_scroll} 行来加载第二批次")
                    
                    # 执行滑动操作
                    await self._scroll_by_rows(rows_to_scroll)
                    
                    # 等待新商品加载
                    await asyncio.sleep(2)
                    
                    # 检查是否有新商品加载
                    new_product_count = await self.page.evaluate("""
                        () => {
                            const cards = document.querySelectorAll('._1unt3Js-');
                            return cards.length;
                        }
                    """)
                    
                    if new_product_count > current_product_count:
                        print(f"[智能滚动] 第二批次商品加载成功！新商品数量: {new_product_count}")
                    else:
                        print(f"[智能滚动] 第二批次商品仍未加载，可能需要更多滑动")
                    
                    # 更新滚动位置记录
                    new_scroll = await self.page.evaluate("() => window.scrollY")
                    self.batch_manager['scroll_position'] = new_scroll
                    
                    return True
                else:
                    print(f"[智能滚动] 未找到有效的位置标记，使用默认滚动策略")
            
            # 🔥 原有滚动策略：每次滚动固定距离
            scroll_distance = 400  # 固定滚动距离
            current_scroll = await self.page.evaluate("() => window.scrollY")

            print(f"[智能滚动] 使用默认滚动策略，当前位置: {current_scroll}px，滚动距离: {scroll_distance}px")

            await self.page.evaluate(f"""
                () => {{
                    window.scrollBy({{
                        top: {scroll_distance},
                        behavior: 'smooth'
                    }});
                }}
            """)

            # 等待滚动完成
            await asyncio.sleep(1.5)

            # 更新滚动位置记录
            new_scroll = await self.page.evaluate("() => window.scrollY")
            self.batch_manager['scroll_position'] = new_scroll

            print(f"[智能滚动] 滚动完成，新位置: {new_scroll}px")
            return True

        except Exception as e:
            print(f"[ERROR] 智能滚动失败: {e}")
            return False

    async def gentle_scroll(self, distance: int):
        """🔥 温和滚动：只使用鼠标滚轮滚动，更自然，更容易触发加载"""
        try:
            # 🔥 新增：应用速率限制
            await self._rate_limited_scroll(distance)
        except Exception as e:
            print(f"[ERROR] 鼠标滚轮滚动失败: {e}")
            # 如果鼠标滚轮滚动失败，回退到简单滚动
            try:
                await self.page.evaluate(f"window.scrollBy(0, {distance})")
                print(f"[FALLBACK] 使用简单滚动: {distance}像素")
            except Exception as e2:
                print(f"[ERROR] 简单滚动也失败: {e2}")

    async def _rate_limited_scroll(self, distance: int):
        """🔥 速率限制滚动：确保滚动速度不超过600像素/秒"""
        try:
            max_speed = 600  # 最大滚动速度：600像素/秒
            
            if abs(distance) <= max_speed:
                # 距离小于等于限制，直接滚动
                await self._wheel_scroll(distance)
            else:
                # 距离大于限制，分段滚动
                segments = abs(distance) // max_speed + 1
                segment_distance = distance / segments
                
                print(f"[速率限制] 滚动距离 {distance} 像素超过 {max_speed} 像素/秒限制，分为 {segments} 段")
                
                for i in range(segments):
                    current_distance = segment_distance
                    if i == segments - 1:  # 最后一段
                        current_distance = distance - (segment_distance * i)
                    
                    print(f"[速率限制] 第 {i+1}/{segments} 段: {current_distance:.1f} 像素")
                    await self._wheel_scroll(int(current_distance))
                    
                    # 段间延迟1秒
                    if i < segments - 1:
                        await asyncio.sleep(1)
                        print(f"[速率限制] 段间延迟1秒")
                        
        except Exception as e:
            print(f"[ERROR] 速率限制滚动失败: {e}")
            # 回退到直接滚动
            await self._wheel_scroll(distance)

    async def _wheel_scroll(self, distance: int):
        """🔥 内部方法：鼠标滚轮滚动：更自然，更容易触发加载"""
        try:
            scroll_direction = "上" if distance < 0 else "下"
            print(f"[SCROLL] 模拟鼠标滚轮{scroll_direction}滚动，距离: {abs(distance)}像素...")
            
            # 分段滚轮滚动，模拟人工滚轮操作
            steps = 6  # 滚轮滚动步数
            step_distance = distance / steps
            
            for i in range(steps):
                # 计算当前步的滚动距离
                current_step = step_distance + random.uniform(-5, 5)
                
                # 执行滚轮滚动
                await self.page.mouse.wheel(0, current_step)
                
                # 模拟人工滚轮滚动的停顿
                wait_time = random.uniform(0.2, 0.6)
                await asyncio.sleep(wait_time)
                
                print(f"   [滚轮] 第{i+1}/{steps}步: {current_step:.1f}像素, 等待{wait_time:.1f}秒")
            
            # 等待滚动动画完成
            await asyncio.sleep(random.uniform(0.8, 1.5))
            
            print(f"[✅] 鼠标滚轮滚动完成: {scroll_direction} {abs(distance)}像素")

        except Exception as e:
            print(f"[ERROR] 鼠标滚轮滚动失败: {e}")
            # 如果鼠标滚轮滚动失败，回退到简单滚动
            try:
                await self.page.evaluate(f"window.scrollBy(0, {distance})")
                print(f"[FALLBACK] 使用简单滚动: {distance}像素")
            except Exception as e2:
                print(f"[ERROR] 简单滚动也失败: {e2}")

    # 🔥 已注释：上滑3次，下滑3次 - 现在改为只定位到指定位置
    # async def _scroll_up_down_3_times(self) -> bool:
    #     """🔥 上滑3次，下滑3次"""
    #     try:
    #         print(f"[SCROLL] 开始执行上滑3次，下滑3次...")
    #         
    #         # 上滑3次
    #         for i in range(3):
    #             print(f"[SCROLL] 第{i+1}次上滑...")
    #             await self.gentle_scroll(-400)  # 上滑400像素
    #             await asyncio.sleep(random.uniform(0.5, 1.0))  # 0.5-1秒间隔
    #         
    #         # 下滑3次
    #         for i in range(3):
    #             print(f"[SCROLL] 第{i+1}次下滑...")
    #             await self.gentle_scroll(430)  # 下滑430像素
    #             await asyncio.sleep(0.5)  # 固定0.5秒间隔
    #         
    #         print(f"[✅] 上滑3次，下滑3次完成")
    #         return True
    #         
    #     except Exception as e:
    #         print(f"[ERROR] 上滑下滑操作失败: {e}")
    #         return False

    async def _quick_scroll_down_once(self) -> bool:
        """🔥 往下快速滑动1次（触发新数据加载）"""
        try:
            print(f"[SCROLL] 开始执行往下快速滑动1次...")
            
            # 往下快速滑动430像素
            await self.gentle_scroll(430)
            print(f"[SCROLL] 往下快速滑动完成")
            return True
            
        except Exception as e:
            print(f"[ERROR] 往下快速滑动失败: {e}")
            return False

    async def _locate_marked_product(self, marked_index: int, marked_name: str) -> bool:
        """🔥 定位到标记的商品位置（不点击）"""
        try:
            print(f"[定位] 开始定位标记商品: 编号{marked_index}, 名称: {marked_name[:30]}...")
            
            # 计算商品在页面中的位置（假设每行2个商品）
            row_number = (marked_index // 2) + 1  # 从1开始计数
            column_in_row = (marked_index % 2) + 1  # 1表示左列，2表示右列
            
            print(f"[定位] 商品位置: 第{row_number}行，第{column_in_row}列")
            
            # 滚动到该商品附近
            await self._scroll_to_row(row_number)
            
            # 等待页面稳定
            await asyncio.sleep(1)
            
            print(f"[定位] 已定位到标记商品位置")
            return True
            
        except Exception as e:
            print(f"[ERROR] 定位标记商品失败: {e}")
            return False
    
    def _calculate_rows_to_scroll(self, marked_index: int) -> int:
        """🔥 根据商品编号计算需要滑动的行数"""
        try:
            # 每行2个商品，编号从0开始
            # 编号17：滑动1行到编号19（因为19是当前批次的最后一个）
            # 编号15：滑动2行（因为一行是2个品）
            
            # 计算当前批次最后一个商品的编号
            batch_end_index = ((marked_index // 20) + 1) * 20 - 1  # 每批次20个商品
            
            # 计算需要滑动的行数
            if marked_index >= 17:  # 编号17及以上，只需要滑动1行
                rows_to_scroll = 1
            else:  # 编号15及以下，需要滑动2行
                rows_to_scroll = 2
            
            print(f"[计算] 标记商品编号: {marked_index}, 批次结束编号: {batch_end_index}, 需要滑动: {rows_to_scroll} 行")
            return rows_to_scroll
            
        except Exception as e:
            print(f"[ERROR] 计算滑动行数失败: {e}")
            return 2  # 默认滑动2行
    
    async def _scroll_by_rows(self, rows_to_scroll: int) -> bool:
        """🔥 按行数滑动页面"""
        try:
            print(f"[滑动] 开始按行滑动，行数: {rows_to_scroll}")
            
            # 每行大约200像素高度
            row_height = 200
            total_scroll_distance = rows_to_scroll * row_height
            
            print(f"[滑动] 滑动距离: {total_scroll_distance}像素 ({rows_to_scroll}行 × {row_height}像素/行)")
            
            # 使用温和滚动
            await self.gentle_scroll(total_scroll_distance)
            
            print(f"[滑动] 按行滑动完成")
            return True
            
        except Exception as e:
            print(f"[ERROR] 按行滑动失败: {e}")
            return False
    
    async def _scroll_to_row(self, row_number: int) -> bool:
        """🔥 滚动到指定行数"""
        try:
            # 每行大约200像素高度
            row_height = 200
            target_scroll = (row_number - 1) * row_height
            
            print(f"[滚动] 滚动到第{row_number}行，目标位置: {target_scroll}像素")
            
            # 使用温和滚动
            await self.gentle_scroll(target_scroll)
            
            print(f"[滚动] 已滚动到第{row_number}行")
            return True
            
        except Exception as e:
            print(f"[ERROR] 滚动到指定行失败: {e}")
            return False

    async def _is_detail_page(self) -> bool:
        """🔥 检查是否进入详情页"""
        try:
            # 等待页面加载
            await asyncio.sleep(2)
            
            # 检查URL是否包含详情页特征
            current_url = self.page.url
            detail_indicators = ['/g/', '/goods/', '/detail/', '/product/']
            
            for indicator in detail_indicators:
                if indicator in current_url:
                    print(f"[PAGE] 检测到详情页URL: {indicator}")
                    return True
            
            # 检查页面内容是否包含详情页特征
            page_content = await self.page.content()
            detail_content_indicators = [
                '商品详情',
                '商品介绍',
                '规格参数',
                '购买按钮',
                '加入购物车'
            ]
            
            for indicator in detail_content_indicators:
                if indicator in page_content:
                    print(f"[PAGE] 检测到详情页内容: {indicator}")
                    return True
            
            print(f"[PAGE] 未检测到详情页特征")
            return False
            
        except Exception as e:
            print(f"[ERROR] 检查详情页失败: {e}")
            return False

    async def check_security_verification(self) -> bool:
        """🔥 检测安全验证弹窗（滑块验证等）- 所有页面都检测，2秒快速检测"""
        try:
            print(f"[SECURITY] 开始检测安全验证弹窗...")
            
            # 快速检测，总共2秒
            start_time = time.time()
            
            # 检测滑块验证
            slider_selectors = [
                "[class*='slider']",
                "[class*='captcha']",
                "[class*='verify']",
                "[class*='security']",
                "div[class*='slider']",
                "div[class*='captcha']",
                "div[class*='verify']",
                "div[class*='security']",
                # 🔥 新增：拼多多特有的滑块选择器
                "[class*='slide']",
                "[class*='drag']",
                "[class*='puzzle']",
                "div[class*='slide']",
                "div[class*='drag']",
                "div[class*='puzzle']",
                # 拼多多滑块常见类名
                "[class*='slider-container']",
                "[class*='slider-track']",
                "[class*='slider-button']",
                "[class*='slider-text']",
                # 通用滑块元素
                "[role='slider']",
                "[aria-label*='滑块']",
                "[aria-label*='验证']"
            ]
            
            for selector in slider_selectors:
                try:
                    if time.time() - start_time > 2:  # 2秒超时
                        break
                    slider = await self.page.wait_for_selector(selector, timeout=200)  # 每个选择器200ms
                    if slider:
                        print(f"[SECURITY] 检测到滑块验证: {selector}")
                        return True
                except Exception as e:
                    continue
            
            # 检测安全验证弹窗
            security_selectors = [
                "text=安全验证",
                "text=滑块验证",
                "text=人机验证",
                "text=验证码",
                "text=请完成验证",
                # 🔥 新增：拼多多特有的验证文本
                "text=请滑动验证",
                "text=请拖动滑块",
                "text=请完成滑块验证",
                "text=请完成人机验证",
                "text=请完成安全验证",
                "text=请拖动滑块到指定位置",
                "text=请完成拼图验证",
                "text=请完成图形验证",
                # 通用验证文本
                "text=验证",
                "text=验证码",
                "text=安全",
                "text=滑块",
                "text=拖动",
                "text=滑动",
                "[class*='verification']",
                "[class*='security']",
                "[class*='captcha']"
            ]
            
            for selector in security_selectors:
                try:
                    if time.time() - start_time > 2:  # 2秒超时
                        break
                    security_element = await self.page.wait_for_selector(selector, timeout=200)  # 每个选择器200ms
                    if security_element:
                        print(f"[SECURITY] 检测到安全验证: {selector}")
                        return True
                except Exception as e:
                    continue
            
            # 检测弹窗遮罩
            try:
                if time.time() - start_time <= 2:  # 2秒超时
                    overlay = await self.page.wait_for_selector("[class*='overlay'], [class*='modal'], [class*='popup']", timeout=200)
                    if overlay:
                        print(f"[SECURITY] 检测到弹窗遮罩")
                        return True
            except Exception as e:
                pass
            
            print(f"[SECURITY] 未检测到安全验证弹窗")
            return False
            
        except Exception as e:
            print(f"[ERROR] 检测安全验证失败: {e}")
            return False

    async def wait_for_manual_verification(self):
        """🔥 等待人工完成验证 - 增强版，包含UI通知和声音警报"""
        try:
            print(f"\n" + "="*80)
            print(f"[PAUSE] 🚨 检测到安全验证弹窗！")
            print(f"[PAUSE] 程序已暂停，请手动完成验证...")
            print(f"[PAUSE] 验证完成后，程序将自动继续...")
            print(f"[PAUSE] 如需退出，请按 Ctrl+C")
            print("="*80)
            
            # 警报声音由jiex.py统一处理
            
            # 这里不需要额外的通知，jiex.py会处理警报系统
            
            # 持续检测验证是否完成，一直等待直到用户验证完成
            verification_complete = False
            check_interval = 5  # 每5秒检查一次
            total_wait_time = 0
            
            while not verification_complete:
                await asyncio.sleep(check_interval)
                total_wait_time += check_interval
                
                # 检查验证是否完成
                if not await self.check_security_verification():
                    print(f"[PAUSE] ✅ 验证已完成，程序继续运行...")
                    # 验证完成提示声音由jiex.py统一处理
                    verification_complete = True
                else:
                    print(f"[PAUSE] ⏳ 等待验证完成... (已等待{total_wait_time}秒)")
                    
                    # 每30秒提醒一次
                    if total_wait_time % 30 == 0:
                        print(f"[PAUSE] 🔔 提醒：请完成验证，程序正在等待...")
                        # 提醒声音由jiex.py统一处理
            
            print(f"[PAUSE] 程序恢复运行")
            print("="*80)
            
        except KeyboardInterrupt:
            print(f"\n[PAUSE] 🚪 用户中断，程序退出")
            raise
        except Exception as e:
            print(f"[ERROR] 等待验证过程中发生错误: {e}")


    # ====================================================================================================
    # 【29】从jiex.py中提取的详情页抓取方法
    # ====================================================================================================

    async def extract_goods_id_from_current_page(self) -> str:
        """从当前详情页URL提取商品ID"""
        try:
            current_url = self.page.url
            print(f"[SEARCH] 当前页面URL: {current_url[:100]}...")

            # 从URL中提取商品ID
            goods_id = self._extract_goods_id_from_url(current_url)
            if goods_id:
                return goods_id

            # 从页面JavaScript中提取
            goods_id_from_js = await self.page.evaluate("""
                () => {
                    if (window.rawData && window.rawData.store && window.rawData.store.initDataObj && window.rawData.store.initDataObj.goods) {
                        const goods = window.rawData.store.initDataObj.goods;
                        return goods.goodsID || goods.goodsId || goods.goods_id || goods.id;
                    }
                    return null;
                }
            """)

            if goods_id_from_js:
                print(f"🆔 从页面JavaScript提取到商品ID: {goods_id_from_js}")
                return str(goods_id_from_js)

            # 使用时间戳作为备用ID
            timestamp_id = str(int(time.time() * 1000))
            print(f"🆔 使用时间戳ID: {timestamp_id}")
            return timestamp_id

        except Exception as e:
            print(f"[ERROR] 提取商品ID失败: {e}")
            timestamp_id = str(int(time.time() * 1000))
            print(f"🆔 使用备用时间戳ID: {timestamp_id}")
            return timestamp_id

    def _extract_goods_id_from_url(self, url: str) -> Optional[str]:
        """从URL中提取商品ID"""
        try:
            import re
            patterns = [
                r'goods_id[=\/](\d+)',
                r'\/g\/(\d+)',
                r'\/goods\/(\d+)',
                r'\/(\d{10,})'  # 匹配10位以上的数字
            ]

            for pattern in patterns:
                match = re.search(pattern, url)
                if match:
                    goods_id = match.group(1)
                    print(f"🆔 从URL模式 {pattern} 提取到商品ID: {goods_id}")
                    return goods_id

            return None
        except Exception as e:
            print(f"[错误] URL商品ID提取失败: {e}")
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
                return self._extract_goods_id_from_url(url)

            return None
        except Exception as e:
            print(f"[警告] 提取商品ID失败: {e}")
            return None

    async def extract_detail_data_unlimited(self, page, goods_id: str) -> Optional[Dict]:
        """
        🔥 从jiex.py提取的详情页抓取方法
        从详情页抓取完整的window.rawData数据
        """
        try:
            print(f"[抓取] 开始提取详情页数据: {goods_id}")

            # 等待页面基本加载完成
            await page.wait_for_load_state('domcontentloaded')

            # 🔥 修复：1秒等待后抓取，避免误触发警报
            print(f"[WAIT] 等待1秒后开始抓取详情页数据...")
            await asyncio.sleep(1)  # 1秒等待，计入配置时间
            
            # 直接尝试获取window.rawData，不重试
            try:
                raw_data = await page.evaluate('''
                    () => {
                        if (!window.rawData) {
                            console.log("[错误] window.rawData 不存在");
                            return null;
                        }

                        // 🔥 按用户要求：完全按照旧版方法抓取，不管数据多大
                        // 完全复制window.rawData，不做任何限制
                        const clonedData = JSON.parse(JSON.stringify(window.rawData));
                        console.log("[成功] rawData 完整复制完成（无限制版本）");

                        return {
                            url: window.location.href,
                            title: document.title,
                            timestamp: new Date().toISOString(),
                            rawData: clonedData,
                            extractTime: new Date().toISOString().replace('T', ' ').substring(0, 19)
                        };
                    }
                ''')
                
                if raw_data and raw_data.get('rawData'):
                    print("[成功] window.rawData 已获取")
                    # 提取商品ID
                    extracted_goods_id = self._extract_goods_id(raw_data)
                    final_goods_id = extracted_goods_id or goods_id

                    print(f"[成功] 数据抓取完成，商品ID: {final_goods_id}")
                    return {
                        'goods_id': final_goods_id,
                        'data': raw_data,
                        'extract_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                    }
                else:
                    print("[错误] 未获取到有效的rawData")
                    # 🔥 直接通知UI，不等待
                    await self._notify_ui_for_verification()
                    return None
                    
            except Exception as e:
                print(f"[错误] 获取 rawData 失败: {e}")
                # 🔥 直接通知UI，不等待
                await self._notify_ui_for_verification()
                return None

        except Exception as e:
            print(f"[错误] 数据抓取失败: {e}")
            return None

    async def _notify_ui_for_verification(self):
        """🔥 通知UI进行验证处理"""
        try:
            print("🚨 数据抓取失败，启动警报系统")
            
            # 如果启用了详情页集成，使用jiex的警报系统
            if self.detail_integration_enabled and self.detail_extractor:
                print("📢 使用jiex警报系统")
                await self.detail_extractor._start_alert_system()
            else:
                print("📢 使用product_clicker内置警报系统")
                # 简单的警报提示
                print("🚨 数据抓取失败，请检查网络连接或手动验证")
                
        except Exception as e:
            print(f"⚠️ 通知UI失败: {e}")

    async def process_detail_page_integrated(self, goods_id: str) -> bool:
        """集成的详情页处理功能 - 使用无限制抓取"""
        try:
            print(f"[PROCESS] 开始处理详情页数据: {goods_id}")

            # 🔥 立即开始数据抓取，无需等待
            # await asyncio.sleep(2)  # 已移除等待时间

            # 🔥 使用无限制抓取功能
            print(f"[PAGE] 正在抓取详情页数据（无限制模式）...")
            extracted_data = await self.extract_detail_data_unlimited(self.page, goods_id)
            if not extracted_data:
                print("[ERROR] 详情页数据抓取失败")
                return False

            final_goods_id = extracted_data['goods_id']
            raw_data = extracted_data['data']

            # 🔥 如果启用了详情页集成，使用jiex的加密上传功能
            if self.detail_integration_enabled and self.detail_extractor:
                # 复用当前浏览器连接
                self.detail_extractor.page = self.page
                self.detail_extractor.browser = self.browser
                self.detail_extractor.context = self.context

                # 加密压缩数据
                print(f"🔐 正在加密压缩数据...")
                encrypted_result = self.detail_extractor.encrypt_compress_for_cloud(raw_data)
                if encrypted_result and 'final_size' in encrypted_result:
                    print(f"[SUMMARY] 数据压缩统计:")
                    print(f"   - 原始大小: {encrypted_result['original_size']} 字节")
                    print(f"   - 最终大小: {encrypted_result['final_size']} 字节")
                    print(f"   - 压缩率: {encrypted_result['compression_ratio']}")

                    # 上传到服务器
                    print(f"☁️ 正在上传到服务器...")
                    upload_success = await self.detail_extractor.upload_to_server(
                        encrypted_result['encrypted_data'], final_goods_id
                    )

                    if upload_success:
                        # 🔥 检查是否在手动解析模式下，如果是则跳过保存
                        if self._is_manual_extraction_mode():
                            print(f"🔄 手动解析模式下，跳过自动保存功能")
                            download_success = True
                        else:
                            # 🔥 从服务器下载解密后的JSON紧凑化数据到本地TXT文档
                            print(f"📥 正在从服务器下载解密数据到本地...")
                            print(f"CALLING_DOWNLOAD: {final_goods_id}")
                            download_success = await self.detail_extractor.download_and_save_from_server(final_goods_id, raw_data)
                            print(f"DOWNLOAD_RESULT: {download_success}")
                        if download_success:
                            # 🔥 从详情页数据中提取并保存主图哈希值
                            if raw_data and 'rawData' in raw_data:
                                store_data = raw_data['rawData'].get('store', {})
                                init_data = store_data.get('initDataObj', {})
                                goods_data = init_data.get('goods', {})
                                if goods_data:
                                    self._add_clicked_hash(goods_data)

                            print(f"[OK] 详情页数据处理完成: {final_goods_id}")
                            return True
                        else:
                            print(f"[ERROR] 从服务器下载失败: {final_goods_id}")
                            return False
                    else:
                        print(f"[ERROR] 数据上传失败: {final_goods_id}")
                        return False
                else:
                    print(f"[ERROR] 数据加密失败: {final_goods_id}")
                    return False
            else:
                print(f"[WARNING] 详情页集成未启用，跳过数据处理: {final_goods_id}")
                return True

        except Exception as e:
            print(f"[ERROR] 集成详情页处理失败: {e}")
            return False



    async def process_single_product(self, product: Dict[str, Any], index: int) -> bool:
        """处理单个商品的完整流程"""
        try:
            product_start_time = time.time()
            product_name = product.get('name', '未知商品')

            # 执行点击
            click_start_time = time.time()
            success = await self.click_product_humanized(product)
            click_end_time = time.time()

            if success:
                print(f"[OK] 商品点击成功，耗时: {click_end_time - click_start_time:.1f}秒")

                # 🔥 新增：详情页完整处理流程
                detail_start_time = time.time()

                # 1. 获取商品ID
                goods_id = await self.extract_goods_id_from_current_page()

                # 2. 集成详情页数据处理
                detail_processing_success = False
                if self.detail_integration_enabled and goods_id:
                    print(f"[PROCESS] 开始集成详情页处理...")
                    detail_processing_success = await self.process_detail_page_integrated(goods_id)

                # 3. 在详情页检测安全验证弹窗
                if await self.check_security_verification():
                    print("[SECURITY] 在详情页检测到安全验证，暂停程序等待人工处理...")
                    await self.wait_for_manual_verification()
                    # 验证完成后继续处理
                
                # 4. 模拟浏览详情页的行为（保持原有逻辑）
                await self.simulate_detail_page_behavior()
                detail_end_time = time.time()

                # 4. 返回搜索页
                return_start_time = time.time()
                await self.return_to_search_page()
                return_end_time = time.time()

                # 🔥 注释掉位置标记写入功能，改由 zq.py 负责标记
                # product_hash = self.generate_product_hash(product)
                # self._save_position_marker(index, product_name)
                # 🔥 不再覆盖抓取位置标记，保持抓取时的最后一个商品标记
                # self.update_crawled_position_marker(index, product_hash, str(int(time.time())))

                # 记录成功的商品日志
                product_log = {
                    'index': index,
                    'product_name': product_name[:50],
                    'status': 'success',
                    'click_time': round(click_end_time - click_start_time, 1),
                    'detail_time': round(detail_end_time - detail_start_time, 1),
                    'return_time': round(return_end_time - return_start_time, 1),
                    'total_time': round(time.time() - product_start_time, 1),
                    'timestamp': time.strftime("%H:%M:%S", time.localtime()),
                    # 🔥 新增：详情页处理状态
                    'goods_id': goods_id if 'goods_id' in locals() else 'unknown',
                    'detail_processing_enabled': self.detail_integration_enabled,
                    'detail_processing_success': detail_processing_success if 'detail_processing_success' in locals() else False
                }

                print(f"[SUMMARY] 本商品处理时间统计:")
                print(f"   - 点击耗时: {product_log['click_time']}秒")
                print(f"   - 详情页浏览: {product_log['detail_time']}秒")
                print(f"   - 返回搜索页: {product_log['return_time']}秒")
                # 🔥 新增：详情页处理状态显示
                if self.detail_integration_enabled:
                    status_icon = "[OK]" if product_log['detail_processing_success'] else "[ERROR]"
                    print(f"   - 详情页数据处理: {status_icon} {'成功' if product_log['detail_processing_success'] else '失败'}")
                    print(f"   - 商品ID: {product_log['goods_id']}")
                else:
                    print(f"   - 详情页数据处理: [WARNING] 未启用")

                # 添加到会话日志
                self.session_logs.append(product_log)

                return True

            else:
                print(f"[ERROR] 商品点击失败，耗时: {click_end_time - click_start_time:.1f}秒")

                # 记录失败的商品日志
                product_log = {
                    'index': index,
                    'product_name': product_name[:50],
                    'status': 'failed',
                    'click_time': round(click_end_time - click_start_time, 1),
                    'detail_time': 0,
                    'return_time': 0,
                    'total_time': round(time.time() - product_start_time, 1),
                    'timestamp': time.strftime("%H:%M:%S", time.localtime())
                }

                # 添加到会话日志
                self.session_logs.append(product_log)

                return False

        except Exception as e:
            print(f"[ERROR] 处理商品时出错: {e}")
            return False

    # ====================================================================================================
    # 8. 批量点击管理
    # ====================================================================================================
    # 🔥 删除重复方法，保留第276行的简化版本

    def reset_position_marker(self):
        """手动重置位置标记（重新开始处理）"""
        print(f"[RESET] 手动重置位置标记...")
        self._clear_position_marker()
        print(f"[RESET] 位置标记已重置，下次将从头开始处理")

    async def simulate_detail_page_behavior(self):
        """模拟详情页浏览行为"""
        try:
            print("📖 进入详情页，开始模拟浏览行为...")
            detail_start_time = time.time()

            # 等待详情页完全加载
            await asyncio.sleep(1)

            # 随机滚动页面
            scroll_times = random.randint(2, 4)
            print(f"   🖱️ 执行 {scroll_times} 次随机滚动")

            for i in range(scroll_times):
                scroll_amount = random.randint(200, 600)
                await self.page.evaluate(f"""
                    () => {{
                        window.scrollBy(0, {scroll_amount});
                    }}
                """)
                scroll_wait = random.uniform(0.8, 2.0)
                print(f"      滚动 {i+1}/{scroll_times}: {scroll_amount}px, 等待 {scroll_wait:.1f}s")
                await asyncio.sleep(scroll_wait)

            # 🔥 修复：计算已用时间，从配置时间中扣除
            current_elapsed = time.time() - detail_start_time
            remaining_time = max(0.5, self.detail_page_wait - current_elapsed)
            
            # 在详情页停留剩余的配置时间
            stay_time = self.get_random_wait_time(remaining_time)
            variance_info = f"-2~+3秒" if remaining_time >= 10.0 else "±1秒" 
            print(f"    详情页剩余停留时间: {stay_time}秒 (配置: {self.detail_page_wait}秒, 已用: {current_elapsed:.1f}秒, 剩余: {remaining_time:.1f}秒)")
            await asyncio.sleep(stay_time)

            detail_end_time = time.time()
            total_detail_time = detail_end_time - detail_start_time
            print(f"   [OK] 详情页浏览完成，总耗时: {total_detail_time:.1f}秒")

        except Exception as e:
            print(f"   [ERROR] 模拟详情页行为时出错: {e}")



    async def random_human_behavior(self): # 【标记：未使用代码】
        """随机的人性化行为"""
        try:
            behaviors = [
                self.random_scroll,
                self.random_mouse_move,
                self.random_pause
            ]

            # 随机选择1-2个行为执行
            selected_behaviors = random.sample(behaviors, random.randint(1, 2))

            for behavior in selected_behaviors:
                await behavior()

        except Exception as e:
            print(f"[WARNING] 执行随机行为时出错: {e}")

    async def random_scroll(self): # 【标记：未使用代码】
        """随机滚动"""
        await self.page.evaluate("""
            () => {
                const direction = Math.random() > 0.5 ? 1 : -1;
                const amount = Math.random() * 300 + 100;
                window.scrollBy(0, direction * amount);
            }
        """)
        await asyncio.sleep(random.uniform(0.3, 0.8))

    async def random_mouse_move(self): # 【标记：未使用代码】
        """随机鼠标移动"""
        await self.page.evaluate("""
            () => {
                const x = Math.random() * window.innerWidth;
                const y = Math.random() * window.innerHeight;

                const event = new MouseEvent('mousemove', {
                    clientX: x,
                    clientY: y,
                    bubbles: true
                });
                document.dispatchEvent(event);
            }
        """)

    async def random_pause(self): # 【标记：未使用代码】
        """随机暂停"""
        pause_time = random.uniform(0.5, 2.0)
        await asyncio.sleep(pause_time)

    # ====================================================================================================
    # 7. 关键词搜索方法
    # ====================================================================================================
    async def _start_next_keyword_cycle(self):
        """启动下一个关键词的完整循环：搜索→抓取→点击"""
        try:
            current_keyword = self._get_current_keyword()
            if not current_keyword:
                print("[ERROR] 没有可搜索的关键词")
                return False

            print(f"[SEARCH] 开始搜索关键词: {current_keyword}")
            print(f"� 启动pdd_search_simple.py，搜索完成后将自动返回继续点击")

            # 🔥 启动pdd_search_simple.py，并传递回调标记
            import subprocess
            import sys

            # 构建搜索命令，传递关键词和循环标记
            search_script = os.path.join(os.path.dirname(__file__), 'pdd_search_simple.py')
            cmd = [sys.executable, search_script, current_keyword, '--start-cycle']

            print(f"[LOG] 启动搜索流程: {' '.join(cmd)}")
            print(f"   1. pdd_search_simple.py 搜索关键词: {current_keyword}")
            print(f"   2. 自动调用 zq.py 抓取商品数据")
            print(f"   3. 自动调用 product_clicker.py 继续点击")

            # 🔥 关闭当前浏览器连接，让搜索流程接管
            await self.close_browser()
            print(f"[DISCONNECT] 浏览器连接已移交给搜索流程")

            # 执行搜索脚本，开始完整循环
            result = subprocess.run(cmd, text=True, encoding='utf-8')

            if result.returncode == 0:
                print(f"[OK] 关键词循环流程启动成功")
                return True
            else:
                print(f"[ERROR] 关键词循环流程启动失败")
                return False

        except Exception as e:
            print(f"[ERROR] 启动关键词循环时发生错误: {e}")
            return False

    # ====================================================================================================
    # 8. 主程序流程
    # ====================================================================================================
    # 🔥 删除重复方法，保留第291行的自动循环版本






    async def close_browser(self):
        """关闭浏览器连接"""
        try:
            if self.playwright:
                await self.playwright.stop()
            print("[DISCONNECT] 浏览器连接已断开")
        except Exception as e:
            print(f"[ERROR] 关闭浏览器失败: {e}")

    def _update_position_marker_for_page_order(self, page_products: list):
        """🔥 修复：更新位置标记 - 标记page_order.json中实际保存的最后一个商品"""
        if not page_products:
                return

        try:
            # 获取page_order.json中实际保存的最后一个商品（索引19）
            last_product = page_products[-1]
            last_product_name = last_product.get('name', '')
            last_position = len(page_products) - 1  # 应该是19
            
            # 生成商品哈希值
            last_hash = hashlib.md5(last_product_name.encode('utf-8')).hexdigest()

            # 更新位置标记 - 指向page_order.json中的商品
            self.position_marker.update({
                "last_processed_index": last_position,
                "last_processed_name": last_product_name,
                "last_processed_hash": last_hash,
                "last_crawled_position": last_position,
                "last_crawled_hash": last_hash,
                "total_crawled": len(page_products),  # 修复：使用实际保存的商品数量
                "session_id": str(int(time.time()))
            })
            
            # 保存更新后的位置标记
            self._save_position_marker_data(self.position_marker)
            
            print(f"[✅] 位置标记已更新: page_order.json中最后商品 '{last_product_name[:30]}...' (位置: {last_position})")
            
        except Exception as e:
            print(f"[错误] 更新page_order位置标记失败: {e}")

    # 🔥 简化：注释掉复杂的trigger_new_scraping方法
    async def trigger_new_scraping(self) -> bool:
        """🔥 自动触发新的数据抓取（调用zq.py）"""
        try:
            print(f"[SCRAPE] 开始新的数据抓取流程...")
            
            # 调用zq.py抓取新数据
            print(f"[SCRAPE] 调用zq.py抓取新数据...")
            zq_script = os.path.join(os.path.dirname(__file__), 'zq.py')
            
            if not os.path.exists(zq_script):
                print(f"[ERROR] zq.py脚本不存在: {zq_script}")
                return False
            
            try:
                # 使用importlib直接导入zq.py模块
                import importlib.util
                spec = importlib.util.spec_from_file_location("zq_module", zq_script)
                zq_module = importlib.util.module_from_spec(spec)
                
                # 执行模块
                spec.loader.exec_module(zq_module)
                
                # 调用模块的main函数
                if hasattr(zq_module, 'main'):
                    print(f"[INFO] 调用zq.py模块的main函数...")
                    # 传入已连接的页面实例，避免重复连接浏览器
                    try:
                        await zq_module.main(page=self.page, browser_id=self.browser_id)
                        print(f"[✅] zq.py模块执行成功！")
                        
                        # 等待文件保存完成
                        await asyncio.sleep(1)
                        
                        # 检查session.json的修改时间来判断是否有新数据
                        if os.path.exists(self.session_file):
                            file_mtime = os.path.getmtime(self.session_file)
                            current_time = time.time()
                            time_diff = current_time - file_mtime
                            
                            print(f"[SCRAPE] 文件修改时间: {time_diff:.1f}秒前")
                            
                            # 如果文件在10秒内被修改，说明有新数据
                            if time_diff < 10:
                                print(f"[✅] 检测到新数据（文件{time_diff:.1f}秒前被修改）")
                                return True
                            else:
                                print(f"[INFO] 文件修改时间过久（{time_diff:.1f}秒前），无新数据")
                                return False
                        else:
                            print(f"[WARNING] session.json文件不存在，无法判断新数据")
                            return False
                            
                    except Exception as e:
                        print(f"[ERROR] 执行main函数时出错: {e}")
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
            print(f"[ERROR] 调用zq.py时发生错误: {e}")
            return False

    # 🔥 简化：注释掉_get_current_session_data_count方法
    # 🔥 数据数量检测交给zq.py处理
    def _get_current_session_data_count(self) -> int:
        """🔥 已简化：数据数量检测交给zq.py处理"""
        print(f"[INFO] 数据数量检测已交给zq.py处理，此方法已简化")
        return 0  # 直接返回0，简化逻辑

    # 🔥 简化：注释掉复杂的wait_for_new_data方法
    # 🔥 数据等待和检测交给zq.py处理
    async def wait_for_new_data(self, max_wait_time: int = 60):
        """🔥 已简化：数据等待和检测交给zq.py处理"""
        print(f"[WAIT] 数据等待和检测已交给zq.py处理，此方法已简化")
        # 简单等待一下，让zq.py有时间处理
        await asyncio.sleep(3)

    def _check_page_order_updated(self) -> bool:
        """检查page_order.json是否有更新"""
        try:
            page_order_file = os.path.join(self.data_dir, 'page_order.json')
            if not os.path.exists(page_order_file):
                return False
            
            # 检查文件修改时间
            current_mtime = os.path.getmtime(page_order_file)
            
            # 如果文件修改时间比当前时间早5秒以上，说明有更新
            if time.time() - current_mtime < 5:
                return True
                
            return False
            
        except Exception as e:
            print(f"[ERROR] 检查文件更新时发生错误: {e}")
            return False

    # 🔥 简化：注释掉复杂的_check_position_marker_updated方法
    # 🔥 位置标记检测交给zq.py处理
    def _check_position_marker_updated(self) -> bool:
        """🔥 已简化：位置标记检测交给zq.py处理"""
        print(f"[INFO] 位置标记检测已交给zq.py处理，此方法已简化")
        return True  # 直接返回True，让流程继续

    async def scroll_to_next_position(self) -> bool:
        """🔥 模拟人工慢慢滚动到下一个位置"""
        try:
            print(f"[SCROLL] 开始模拟人工滚动...")
            
            # 获取当前位置标记
            current_position = self.position_marker.get('last_processed_index', -1)
            if current_position == -1:
                print(f"[INFO] 没有位置标记，执行默认滚动")
                # 执行默认滚动
                await self.gentle_scroll(800)
                return True
            
            print(f"[SCROLL] 当前位置: {current_position}，准备滚动到下一个位置...")
            
            # 模拟人工滚动：分段滚动，每次滚动距离适中
            scroll_distance = 600  # 每次滚动600像素
            scroll_steps = 3       # 分3步滚动
            step_distance = scroll_distance // scroll_steps
            
            for step in range(scroll_steps):
                current_step = step + 1
                print(f"[SCROLL] 第{current_step}/{scroll_steps}步滚动，距离: {step_distance}像素")
                
                # 执行滚动
                await self.gentle_scroll(step_distance)
                
                # 模拟人工等待（随机时间）
                wait_time = random.uniform(1.5, 3.0)
                print(f"[SCROLL] 等待 {wait_time:.1f} 秒...")
                await asyncio.sleep(wait_time)
            
            print(f"[✅] 滚动完成，总距离: {scroll_distance}像素")
            return True
            
        except Exception as e:
            print(f"[ERROR] 滚动过程中发生错误: {e}")
            return False

    # 🔥 简化：注释掉复杂的_smart_scroll_for_loading方法
    # 🔥 智能滚动策略交给zq.py处理
    async def _smart_scroll_for_loading(self) -> bool:
        """🔥 已简化：智能滚动策略交给zq.py处理"""
        print(f"[SCROLL] 智能滚动策略已交给zq.py处理，此方法已简化")
        return True  # 直接返回True，让流程继续

    async def human_like_scroll(self, distance: int, scroll_type: str = "down"):
        """🔥 模拟人工滚动：使用真实的鼠标拖动轨迹"""
        try:
            # 🔥 新增：应用速率限制
            await self._rate_limited_human_scroll(distance, scroll_type)
        except Exception as e:
            print(f"[ERROR] 人工滚动失败: {e}")
            # 如果人工滚动失败，回退到简单滚动
            try:
                await self.page.evaluate(f"window.scrollBy(0, {distance})")
                print(f"[FALLBACK] 使用简单滚动: {distance}像素")
            except Exception as e2:
                print(f"[ERROR] 简单滚动也失败: {e2}")

    async def _rate_limited_human_scroll(self, distance: int, scroll_type: str = "down"):
        """🔥 速率限制人工滚动：确保滚动速度不超过600像素/秒"""
        try:
            max_speed = 600  # 最大滚动速度：600像素/秒
            if abs(distance) <= max_speed:
                # 距离小于等于600像素，直接滚动
                await self._human_scroll_section(distance, scroll_type)
            else:
                # 距离大于600像素，分段滚动
                segments = abs(distance) // max_speed + 1
                segment_distance = distance / segments
                
                print(f"[速率限制] 人工滚动距离 {distance} 像素超过 {max_speed} 像素/秒限制，分为 {segments} 段")
                
                for i in range(segments):
                    current_distance = segment_distance
                    if i == segments - 1:  # 最后一段
                        current_distance = distance - (segment_distance * i)
                    
                    print(f"[速率限制] 第 {i+1}/{segments} 段: {current_distance:.1f} 像素")
                    await self._human_scroll_section(int(current_distance), scroll_type)
                    
                    # 段间延迟1秒
                    if i < segments - 1:
                        await asyncio.sleep(1)
                        print(f"[速率限制] 段间延迟1秒")
                        
        except Exception as e:
            print(f"[ERROR] 速率限制人工滚动失败: {e}")
            # 回退到直接滚动
            await self._human_scroll_section(distance, scroll_type)

    async def _human_scroll_section(self, distance: int, scroll_type: str = "down"):
        """🔥 内部方法：执行单段人工滚动"""
        try:
            print(f"[SCROLL] 模拟人工{scroll_type}滚动，距离: {abs(distance)}像素...")
            
            # 获取页面尺寸
            viewport = await self.page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")
            center_x = viewport['width'] // 2
            center_y = viewport['height'] // 2
            
            # 计算滚动起点和终点
            if scroll_type == "up":
                start_y = center_y + 100
                end_y = start_y + distance
            else:  # down
                start_y = center_y - 100
                end_y = start_y + distance
            
            # 确保坐标在页面范围内
            start_y = max(100, min(start_y, viewport['height'] - 100))
            end_y = max(100, min(end_y, viewport['height'] - 100))
            
            # 执行真实的鼠标拖动滚动
            await self.page.mouse.move(center_x, start_y)
            await asyncio.sleep(random.uniform(0.1, 0.3))  # 短暂停顿
            
            # 按下鼠标左键
            await self.page.mouse.down()
            await asyncio.sleep(random.uniform(0.05, 0.15))
            
            # 模拟人工拖动的轨迹（分段移动，添加随机偏移）
            steps = 8
            step_distance = distance / steps
            
            for i in range(steps):
                # 添加随机偏移，模拟人工拖动的不规则性
                random_offset_x = random.uniform(-15, 15)
                random_offset_y = random.uniform(-10, 10)
                
                current_y = start_y + (i + 1) * step_distance + random_offset_y
                current_x = center_x + random_offset_x
                
                # 确保坐标在页面范围内
                current_x = max(50, min(current_x, viewport['width'] - 50))
                current_y = max(50, min(current_y, viewport['height'] - 50))
                
                # 移动鼠标
                await self.page.mouse.move(current_x, current_y)
                
                # 随机等待时间，模拟人工拖动的不均匀性
                wait_time = random.uniform(0.05, 0.15)
                await asyncio.sleep(wait_time)
            
            # 释放鼠标左键
            await self.page.mouse.up()
            
            # 等待滚动动画完成
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
            print(f"[✅] 人工滚动完成: {scroll_type} {abs(distance)}像素")
            
        except Exception as e:
            print(f"[ERROR] 人工滚动失败: {e}")
            # 如果人工滚动失败，回退到简单滚动
            try:
                await self.page.evaluate(f"window.scrollBy(0, {distance})")
                print(f"[FALLBACK] 使用简单滚动: {distance}像素")
            except Exception as e2:
                print(f"[ERROR] 简单滚动也失败: {e2}")

    async def _scroll_to_position_marker(self) -> bool:
        """🔥 提取position_marker.json的商品做定位，快速移动到该商品的下2行位置"""
        try:
            print(f"[POSITION] 开始定位到商品位置...")
            
            # 获取position_marker中的商品信息
            if not hasattr(self, 'position_marker') or not self.position_marker:
                print(f"[POSITION] ❌ position_marker数据不存在")
                return False
            
            # 获取上次点击的商品位置信息
            last_product_name = self.position_marker.get('last_processed_name', '')
            last_position = self.position_marker.get('last_processed_index', -1)
            
            if not last_product_name or last_position == -1:
                print(f"[POSITION] ❌ 无法获取上次商品名称或位置")
                return False
            
            print(f"[POSITION] 定位目标: {last_product_name[:30]}... (位置: {last_position})")
            
            # 🔥 修改：快速移动到该商品的下2行位置
            # 计算需要滑动的距离：每个商品大约641像素高度（图片+标题+价格+销量+间距），下2行就是1,282像素
            scroll_distance = 641  # 🔥 减少到641像素，避免分段滚动
            
            print(f"[POSITION] 快速移动到下2行位置，距离: {scroll_distance}像素")
            
            # 使用温和滚动，而不是慢慢滑动
            await self.gentle_scroll(scroll_distance)
            
            print(f"[POSITION] ✅ 已快速定位到商品下2行位置")
            return True
            
        except Exception as e:
            print(f"[ERROR] 定位到商品位置失败: {e}")
            return False

    # 🔥 已注释：上滑3次，下滑4次 - 现在改为只定位到指定位置
    # async def _scroll_up_down_3_4_times(self) -> bool:
    #     """🔥 上滑3次，下滑4次"""
    #     try:
    #         print(f"[SCROLL] 开始执行上滑3次，下滑4次...")
    #         
    #         # 上滑3次
    #         for i in range(3):
    #             print(f"[SCROLL] 第{i+1}次上滑...")
    #             await self.gentle_scroll(-400)  # 上滑400像素
    #             await asyncio.sleep(random.uniform(0.5, 1.0))  # 0.5-1秒间隔
    #         
    #         # 下滑4次
    #         for i in range(4):
    #             print(f"[SCROLL] 第{i+1}次下滑...")
    #             await self.gentle_scroll(430)  # 下滑430像素
    #             await asyncio.sleep(0.5)  # 固定0.5秒间隔
    #         
    #         print(f"[✅] 上滑3次，下滑4次完成")
    #         return True
    #         
    #     except Exception as e:
    #         print(f"[ERROR] 上滑下滑操作失败: {e}")
    #         return False

    async def _execute_position_marker_scroll(self) -> bool:
        """🔥 执行位置标记滚动 - 简化为只定位到商品下2行"""
        try:
            print(f"[POSITION] 开始执行位置标记滚动...")
            
            # 🔥 第一步：提取position_marker.json的商品做定位，快速滑动到该商品下2行
            print(f"[POSITION] 第一步：定位到position_marker.json中的商品，然后快速滑动到下2行...")
            if not await self._scroll_to_position_marker():
                print(f"[POSITION] ❌ 定位到商品位置失败")
                return False
            
            print(f"[POSITION] ✅ 已定位到商品下2行位置（约1200多像素），准备调用zq.py...")
            
            # 🔥 第二步：直接调用zq.py抓取新数据
            print(f"[POSITION] 第二步：调用zq.py抓取新数据...")
            if await self.trigger_new_scraping():
                print(f"[POSITION] ✅ 抓取成功，有新数据")
                return True
            else:
                print(f"[POSITION] ❌ 抓取失败，无新数据")
                return False
            
        except Exception as e:
            print(f"[ERROR] 执行位置标记滚动失败: {e}")
            return False



# ====================================================================================================
# 定时控制方法
# ====================================================================================================

    async def _check_memory_usage(self):
        """🔥 内存使用监控 - 检查浏览器内存是否超过阈值"""
        try:
            if not self.page:
                return
                
            # 获取浏览器内存使用情况
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
            
            if memory_info:
                print(f"[MEMORY] 浏览器内存: {memory_info['used']:.1f}MB / {memory_info['total']:.1f}MB ({memory_info['percentage']:.1f}%) [浏览器:{self.browser_id}]")
                
                # 检查是否超过阈值
                if memory_info['used'] > self.memory_threshold:
                    print(f"🚨 浏览器内存使用超过阈值 {self.memory_threshold}MB，准备重启浏览器... [浏览器:{self.browser_id}]")
                    await self._handle_memory_threshold_exceeded()
                    
        except Exception as e:
            print(f"[WARNING] 内存监控失败: {e} [浏览器:{self.browser_id}]")

    async def _handle_memory_threshold_exceeded(self):
        """🔥 处理内存阈值超限 - 关闭浏览器并重新启动"""
        try:
            print(f"🚨 内存阈值超限 ({self.memory_threshold}MB)，开始处理... [浏览器:{self.browser_id}]")
            
            # 1. 关闭当前浏览器
            await self._close_browser()
            
            # 2. 等待一段时间让系统释放资源
            import time
            await asyncio.sleep(5)
            
            # 3. 重新启动浏览器
            print(f"🔄 重新启动浏览器... [浏览器:{self.browser_id}]")
            await self._start_browser()
            
            # 4. 重新开始点击流程
            print(f"🔄 重新开始点击流程... [浏览器:{self.browser_id}]")
            await self.run_clicking_session()
            
        except Exception as e:
            print(f"❌ 处理内存阈值超限失败: {e} [浏览器:{self.browser_id}]")

    async def _close_browser(self):
        """🔥 关闭浏览器"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            print(f"🔒 浏览器已关闭 [浏览器:{self.browser_id}]")
        except Exception as e:
            print(f"⚠️ 关闭浏览器失败: {e} [浏览器:{self.browser_id}]")

    async def _start_browser(self):
        """🔥 重新启动浏览器"""
        try:
            # 重新连接浏览器
            if await self.connect_browser():
                print(f"✅ 浏览器重新启动成功 [浏览器:{self.browser_id}]")
                return True
            else:
                print(f"❌ 浏览器重新启动失败 [浏览器:{self.browser_id}]")
                return False
        except Exception as e:
            print(f"❌ 重新启动浏览器异常: {e} [浏览器:{self.browser_id}]")
            return False

    async def _check_timed_control(self):
        """🔥 事件驱动的定时控制检查（方案3：百分比间隔检查）"""
        try:
            current_time = time.time()
            
            # 🔥 精确计算实际运行时长（排除暂停时间）
            # 保护机制：确保last_timed_check已初始化
            if self.last_timed_check is None:
                self.last_timed_check = current_time
                print(f"[DEBUG] 时间基准未初始化，设置为当前时间 [浏览器:{self.browser_id}]")
            
            if not self.is_paused:
                # 正在运行状态：累加从上次检查到现在的运行时间
                time_since_last_check = current_time - self.last_timed_check
                self.actual_run_duration += time_since_last_check
                print(f"[DEBUG] 浏览器 {self.browser_id} 本次增加运行时间: {time_since_last_check:.1f} 秒")
                self.last_timed_check = current_time
            else:
                # 暂停状态：不更新运行时长，但更新检查时间
                print(f"[DEBUG] 浏览器 {self.browser_id} 处于暂停状态，不计入运行时间")
                self.last_timed_check = current_time
            
            # 🔥 百分比间隔检查：检查间隔为设定运行时长的10%，最少30秒，最多5分钟
            target_run_seconds = self.run_minutes * 60
            check_interval = max(30, min(300, int(target_run_seconds * 0.1)))
            
            # 添加浏览器ID偏移，避免多个浏览器同时检查造成冲突
            browser_offset = hash(self.browser_id) % 10  # 0-9秒的随机偏移
            check_interval += browser_offset
            
            # 转换为分钟便于显示
            actual_run_minutes = self.actual_run_duration / 60
            total_pause_minutes = self.total_pause_duration / 60
            
            print(f"[DEBUG] ⏰ 浏览器 {self.browser_id} 独立定时控制检查 (方案3：百分比间隔):")
            print(f"[DEBUG]   - 当前时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(current_time))}")
            print(f"[DEBUG]   - 实际运行时长: {actual_run_minutes:.1f} 分钟 ({self.actual_run_duration:.0f} 秒)")
            print(f"[DEBUG]   - 累计暂停时长: {total_pause_minutes:.1f} 分钟 ({self.total_pause_duration:.0f} 秒)")
            print(f"[DEBUG]   - 设置运行时长: {self.run_minutes} 分钟 ({target_run_seconds} 秒)")
            print(f"[DEBUG]   - 暂停状态: {'是' if self.is_paused else '否'}")
            print(f"[DEBUG]   - 检查间隔: {check_interval} 秒 (运行时长{self.run_minutes}分钟的10%)")
            print(f"[DEBUG]   - 浏览器ID: {self.browser_id} (独立计算)")
            
            # 只在非暂停状态下检查运行时长
            if not self.is_paused:
                if self.actual_run_duration >= target_run_seconds:
                    print(f"[DEBUG] ⏸️ 实际运行时长达到 {self.run_minutes} 分钟限制，开始暂停... [浏览器:{self.browser_id}]")
                    await self._pause_for_timed_control()
                else:
                    remaining_seconds = target_run_seconds - self.actual_run_duration
                    remaining_minutes = remaining_seconds / 60
                    print(f"[DEBUG] ▶️ 运行中，还需运行 {remaining_minutes:.1f} 分钟 [浏览器:{self.browser_id}]")
                    
        except Exception as e:
            print(f"[警告] 定时控制检查失败: {e}")

    async def _pause_for_timed_control(self):
        """🔥 因定时控制暂停浏览器（精确检查式）"""
        try:
            print(f"⏸️ 实际运行时长达到 {self.run_minutes} 分钟，开始暂停... [浏览器:{self.browser_id}]")
            print(f"[DEBUG] 暂停时实际运行时长: {self.actual_run_duration/60:.1f} 分钟")
            print(f"[DEBUG] 暂停时累计暂停时长: {self.total_pause_duration/60:.1f} 分钟")
            
            # 1. 设置暂停状态和时间
            self.is_paused = True
            self.pause_start_time = time.time()
            
            # 2. 计算精确的恢复检查时间（用户设定时间 + 5秒）
            self.resume_check_time = self.pause_start_time + (self.pause_minutes * 60) + 5
            
            # 3. 重置实际运行时长，准备下一轮运行
            self.actual_run_duration = 0
            
            print(f"⏸️ 浏览器已暂停，将在 {self.pause_minutes} 分钟后自动恢复 [浏览器:{self.browser_id}]")
            print(f"⏰ 恢复检查时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.resume_check_time))}")
            print(f"🔄 实际运行时长已重置，准备下一轮运行循环")
            
        except Exception as e:
            print(f"❌ 暂停浏览器失败: {e}")

    async def _resume_from_pause(self):
        """🔥 从暂停状态恢复"""
        try:
            print(f"▶️ 暂停时间结束，开始恢复浏览器... [浏览器:{self.browser_id}]")
            
            # 1. 计算这次暂停的实际时长并累加到总暂停时长
            if self.pause_start_time:
                current_time = time.time()
                this_pause_duration = current_time - self.pause_start_time
                self.total_pause_duration += this_pause_duration
                print(f"[DEBUG] 本次暂停时长: {this_pause_duration/60:.1f} 分钟")
                print(f"[DEBUG] 累计暂停时长: {self.total_pause_duration/60:.1f} 分钟")
            
            # 2. 恢复运行状态，重置暂停相关变量
            self.is_paused = False
            self.pause_start_time = None
            self.resume_check_time = None  # 清理恢复检查时间
            self.last_timed_check = time.time()  # 重置检查时间基准
                
            print(f"✅ 浏览器 {self.browser_id} 恢复成功，继续独立计时")
            print(f"[DEBUG] 浏览器 {self.browser_id} 时间基准已重置，准备继续运行")
                
        except Exception as e:
            print(f"❌ 恢复浏览器失败: {e}")

# ====================================================================================================
# 主程序入口
# ====================================================================================================
async def main():
    """主程序入口"""
    clicker = ProductClicker()
    await clicker.run_clicking_session()


async def main_with_callback():
    """主程序入口（用于从搜索脚本回调）"""
    try:
        print("[PROCESS] 从搜索脚本回调，继续点击流程...")

        # 创建ProductClicker实例
        clicker = ProductClicker()

        # 连接到现有浏览器
        if await clicker.connect_browser():
            print("[OK] 重新连接浏览器成功")

            # 继续点击会话
            await clicker.run_clicking_session()
        else:
            print("[ERROR] 重新连接浏览器失败")

    except Exception as e:
        print(f"[ERROR] 回调执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("[TARGET] 智能商品点击器")
    print("基于JSON数据的人性化商品点击工具")
    print("=" * 50)

    try:
        # 检查是否是从搜索脚本回调
        if len(sys.argv) > 1 and sys.argv[1] == '--from-search-callback':
            asyncio.run(main_with_callback())
        else:
            asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[WARNING] 用户中断程序")
    except Exception as e:
        print(f"\n[ERROR] 程序执行失败: {e}")

    print("\n[END] 程序结束")

