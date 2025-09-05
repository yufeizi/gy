import asyncio
import json
import os
import time
import hashlib
from typing import Set
from playwright.async_api import async_playwright, Page

class HybridHumanizedTester:

    def __init__(self):
        """初始化"""
        self.playwright = None
        self.browser = None
        self.context = None
        self.page: Page = None
        
        # 从配置文件加载端口
        self.config = self._load_config()
        self.debug_port = self.config.get('browser_info', {}).get('debug_port')
        if not self.debug_port:
            raise ValueError("错误：无法从配置文件 config_api.json 中找到 'debug_port'。")
        
        # ====================================================================================================
        # 1. 关键词过滤功能初始化
        # ====================================================================================================
        self.browser_id = self.config.get('browser_info', {}).get('browser_id')
        if not self.browser_id:
            raise ValueError("错误：无法从配置文件 config_api.json 中找到 'browser_id'。")
        
        print(f"🔍 当前浏览器ID: {self.browser_id}")
        self.filter_keywords = self._load_filter_keywords()

        # ====================================================================================================
        # 2. 历史商品管理初始化
        # ====================================================================================================
        self.history_file = os.path.join(os.path.dirname(__file__), 'logs', 'product_history.json')
        self.session_file = os.path.join(os.path.dirname(__file__), 'logs', 'session.json')
        self._ensure_logs_directory()
        self.product_history = self._load_product_history()

        # ====================================================================================================
        # 3. 位置标记功能初始化
        # ====================================================================================================
        self.position_marker_file = os.path.join(os.path.dirname(__file__), 'data', 'position_marker.json')
        self.position_marker = self._load_position_marker()

        # ====================================================================================================
        # 4. 价格过滤功能初始化
        # ====================================================================================================
        filter_settings = self.config.get('parse_settings', {}).get('filter_settings', {})
        self.price_min = filter_settings.get('price_min', '')
        self.price_max = filter_settings.get('price_max', '')
        
        # 转换为数值类型
        self.price_min_float = float(self.price_min) if self.price_min and self.price_min.replace('.', '').isdigit() else 0.0
        self.price_max_float = float(self.price_max) if self.price_max and self.price_max.replace('.', '').isdigit() else float('inf')
        
        print(f"[价格过滤] 价格范围: {self.price_min_float} - {self.price_max_float if self.price_max_float != float('inf') else '无上限'}")

    def _load_config(self):
        """从同目录下的 config_api.json 加载配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'config_api.json')
        print(f"ℹ️ 正在从 {config_path} 加载配置...")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ 错误: 配置文件 '{config_path}' 未找到。")
            return {}
        except json.JSONDecodeError:
            print(f"❌ 错误: 配置文件 'config_api.json' 格式无效。")
            return {}

    # ====================================================================================================
    # 2. 历史商品管理核心方法
    # ====================================================================================================
    def _ensure_logs_directory(self):
        """确保logs目录存在"""
        logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
            print(f"[OK] 创建logs目录: {logs_dir}")

    def _load_product_history(self) -> dict:
        """加载历史商品记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                print(f"[OK] 加载历史商品记录: {len(history)} 条")
                return history
            else:
                print(f"[ℹ️] 历史商品文件不存在，创建新的记录")
                return {}
        except Exception as e:
            print(f"[错误] 加载历史商品记录失败: {e}")
            return {}

    def _save_product_history(self, history: dict):
        """保存历史商品记录"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)
            print(f"[OK] 保存历史商品记录: {len(history)} 条")
        except Exception as e:
            print(f"[错误] 保存历史商品记录失败: {e}")

    def _filter_historical_products(self, products: list) -> list:
        """过滤历史商品，只保留新商品"""
        current_time = time.time()
        new_products = []
        filtered_count = 0

        for product in products:
            product_name = product.get('name', '')
            if product_name in self.product_history:
                filtered_count += 1
            else:
                # 记录新商品到历史
                self.product_history[product_name] = current_time
                new_products.append(product)

        # 保存更新后的历史记录
        self._save_product_history(self.product_history)

        return new_products, filtered_count

    def _save_session_data(self, products: list):
        """保存当前会话数据到session.json（覆盖式保存）"""
        try:
            session_data = {
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "count": len(products),
                "products": products[:20]  # 最多保存20个商品
            }

            with open(self.session_file, 'w', encoding='utf-8') as f:
                json.dump(session_data, f, ensure_ascii=False, indent=2)

            print(f"[OK] 保存会话数据: {len(session_data['products'])} 条商品到 session.json")
        except Exception as e:
            print(f"[错误] 保存会话数据失败: {e}")

    def _load_current_session_data(self) -> list:
        """加载当前session.json中的数据"""
        try:
            if os.path.exists(self.session_file):
                with open(self.session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                return data.get('products', [])
            else:
                return []
        except Exception as e:
            print(f"[错误] 加载当前session数据失败: {e}")
            return []

    def _save_latest_20_products(self, all_products: list):
        """保存当前批次抓取的商品到page_order.json（不过滤，用于标记）"""
        try:
            # 🔥 修复：保存当前批次抓取的商品，而不是总是前20个
            # 如果商品数量超过20个，说明有多个批次，取最后20个（当前批次）
            if len(all_products) > 20:
                current_batch_products = all_products[-20:]  # 取最后20个（当前批次）
                batch_info = f"当前批次（最后20个）"
            else:
                current_batch_products = all_products  # 第一批次，全部保存
                batch_info = f"第一批次（全部{len(all_products)}个）"
            
            latest_data = {
                "timestamp": time.time(),
                "datetime": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "total_count": len(all_products),
                "current_batch_count": len(current_batch_products),
                "batch_info": batch_info,
                "products": current_batch_products  # 保存当前批次的商品
            }

            latest_file = os.path.join(os.path.dirname(__file__), 'data', 'page_order.json')
            os.makedirs(os.path.dirname(latest_file), exist_ok=True)
            
            with open(latest_file, 'w', encoding='utf-8') as f:
                json.dump(latest_data, f, ensure_ascii=False, indent=2)

            print(f"[OK] 保存{latest_data['batch_info']}: {len(latest_data['products'])} 条商品到 page_order.json")
            
            # 🔥 修复：标记page_order.json中实际保存的最后一个商品（索引19）
            if latest_data['products']:
                self._update_position_marker_for_page_order(latest_data['products'])
                
        except Exception as e:
            print(f"[错误] 保存最新20个商品失败: {e}")

    # ====================================================================================================
    # 4. 位置标记核心方法
    # ====================================================================================================
    def _load_position_marker(self) -> dict:
        """加载位置标记数据"""
        try:
            if os.path.exists(self.position_marker_file):
                with open(self.position_marker_file, 'r', encoding='utf-8') as f:
                    marker = json.load(f)
                print(f"[OK] 加载位置标记: {marker.get('last_processed_name', '无')[:30] if marker.get('last_processed_name') else '无'}...")
                return marker
            else:
                print(f"[ℹ️] 位置标记文件不存在，创建新的标记")
                return self._create_default_marker()
        except Exception as e:
            print(f"[错误] 加载位置标记失败: {e}")
            return self._create_default_marker()

    def _create_default_marker(self) -> dict:
        """创建默认位置标记"""
        default_marker = {
            "session_id": str(int(time.time())),
            "last_processed_index": -1,
            "last_processed_name": "",
            "last_processed_hash": "",
            "last_crawled_position": -1,
            "last_crawled_hash": "",
            "total_crawled": 0,
            "scroll_position": 0,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        }
        return default_marker

    def _save_position_marker_data(self, marker_data: dict):
        """保存位置标记数据"""
        try:
            os.makedirs(os.path.dirname(self.position_marker_file), exist_ok=True)
            marker_data['updated_at'] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            
            with open(self.position_marker_file, 'w', encoding='utf-8') as f:
                json.dump(marker_data, f, ensure_ascii=False, indent=2)
            
            print(f"[[OK]] 位置标记已更新: {marker_data.get('last_processed_name', '无')[:30] if marker_data.get('last_processed_name') else '无'}...")
        except Exception as e:
            print(f"[错误] 保存位置标记失败: {e}")

    def _update_position_marker(self, all_products: list):
        """更新位置标记 - 标记最后一个商品"""
        if not all_products:
            return
            
        try:
            # 获取最后一个商品
            last_product = all_products[-1]
            last_product_name = last_product.get('name', '')
            last_position = len(all_products) - 1
            
            # 生成商品哈希值
            last_hash = hashlib.md5(last_product_name.encode('utf-8')).hexdigest()
            
            # 更新位置标记
            self.position_marker.update({
                "last_processed_index": last_position,
                "last_processed_name": last_product_name,
                "last_processed_hash": last_hash,
                "last_crawled_position": last_position,
                "last_crawled_hash": last_hash,
                "total_crawled": self.position_marker.get('total_crawled', 0) + 1,
                "session_id": str(int(time.time()))
            })
            
            # 保存更新后的位置标记
            self._save_position_marker_data(self.position_marker)
            
            print(f"[[OK]] 位置标记已更新: 最后商品 '{last_product_name[:30]}...' (位置: {last_position})")
            
        except Exception as e:
            print(f"[错误] 更新位置标记失败: {e}")

    def _update_position_marker_for_page_order(self, page_products: list):
        """🔥 修复：更新位置标记 - 每次抓取批次重置为0开始"""
        if not page_products:
            return
            
        try:
            # 🔥 修复：每次新的抓取批次，位置标记应该重置为0开始
            # 获取page_order.json中实际保存的最后一个商品（索引19）
            last_product = page_products[-1]
            last_product_name = last_product.get('name', '')
            last_position = len(page_products) - 1  # 当前批次中的最后位置
            
            # 生成商品哈希值
            last_hash = hashlib.md5(last_product_name.encode('utf-8')).hexdigest()
            
            # 🔥 修复：更新位置标记 - 每次抓取批次都从0开始计数
            current_time = time.time()
            self.position_marker.update({
                "last_processed_index": last_position,  # 当前批次中的最后位置
                "last_processed_name": last_product_name,
                "last_processed_hash": last_hash,
                "last_crawled_position": last_position,  # 当前批次中的最后位置
                "last_crawled_hash": last_hash,
                "total_crawled": len(page_products),  # 当前批次抓取的商品数量
                "session_id": str(int(current_time)),  # 新的会话ID
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time)),  # 当前时间
                "updated_at": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(current_time))  # 更新时间
            })
            
            # 保存更新后的位置标记
            self._save_position_marker_data(self.position_marker)
            
            print(f"[[OK]] 位置标记已更新: 当前批次最后商品 '{last_product_name[:30]}...' (位置: {last_position}, 总数: {len(page_products)})")
            
        except Exception as e:
            print(f"[错误] 更新page_order位置标记失败: {e}")

    # ====================================================================================================
    # 3. 关键词过滤核心方法
    # ====================================================================================================
    def _load_filter_keywords(self) -> Set[str]:
        """🔥 优化：高速加载过滤关键词文件（10万关键词优化）"""
        try:
            # 🔥 内置关键词：不可删除的预售过滤词
            builtin_keywords = {"发完", "内发货"}

            filter_file = f"filter_keywords_{self.browser_id}.txt"
            if not os.path.exists(filter_file):
                print(f"[警告] 过滤关键词文件不存在: {filter_file}")
                print(f"[[OK]] 使用内置关键词: {len(builtin_keywords)} 个")
                return builtin_keywords

            with open(filter_file, 'r', encoding='utf-8') as f:
                content = f.read()

            # 🔥 性能优化：保持原始大小写
            file_keywords = {
                line.strip()
                for line in content.splitlines()
                if line.strip() and not line.strip().startswith('#')
            }

            # 🔥 合并内置关键词和文件关键词
            all_keywords = builtin_keywords | file_keywords

            print(f"[[OK]] 加载过滤关键词: {len(all_keywords)} 个 (内置: {len(builtin_keywords)}, 文件: {len(file_keywords)})")
            return all_keywords

        except Exception as e:
            print(f"[错误] 加载过滤关键词失败: {e}")
            # 即使文件加载失败，也返回内置关键词
            builtin_keywords = {"发完", "内发货"}
            print(f"[[OK]] 使用内置关键词: {len(builtin_keywords)} 个")
            return builtin_keywords
    
    def _check_keyword_filter(self, title: str) -> str:
        """🔥 完整关键词匹配：只有完整关键词匹配才过滤（忽略大小写）"""
        if not self.filter_keywords:
            return ""

        if not title:
            return ""

        # 🔥 转小写进行匹配（忽略大小写）
        title_lower = title.lower()

        # 🔥 完整关键词匹配：检查每个关键词是否作为完整词组出现在标题中
        for keyword in self.filter_keywords:
            # 将关键词也转为小写进行比较，但返回原始关键词
            if keyword.lower() in title_lower:
                return keyword

        return ""

    def _check_price_filter(self, price_str: str) -> bool:
        """检查价格是否符合过滤条件"""
        try:
            if not price_str or price_str == '未找到价格':
                return True  # 没有价格信息时默认通过
            
            # 提取价格数字
            import re
            price_match = re.search(r'(\d+\.?\d*)', price_str)
            if not price_match:
                return True  # 无法提取价格时默认通过
            
            price = float(price_match.group(1))
            
            # 检查价格范围
            if self.price_min_float > 0 and price < self.price_min_float:
                print(f"[价格过滤] 价格过低: {price} < {self.price_min_float}")
                return False
            
            if self.price_max_float != float('inf') and price > self.price_max_float:
                print(f"[价格过滤] 价格过高: {price} > {self.price_max_float}")
                return False
            
            return True
            
        except Exception as e:
            print(f"[价格过滤] 价格检查异常: {e}")
            return True  # 异常时默认通过

    async def connect_browser(self):
        """连接比特浏览器"""
        try:
            print(f"🔗 正在连接浏览器，端口: {self.debug_port}")

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{self.debug_port}")

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
            print(f"📄 当前页面: {self.page.url[:100]}...")
            return True

        except Exception as e:
            print(f"❌ 浏览器连接失败: {e}")
            return False

    # ====================================================================================================
    # 核心功能：抓取、排序、过滤
    # ====================================================================================================
    async def scrape_and_process_page(self):
        """执行页面清理、抓取、排序、过滤并输出结果"""
        if not self.page:
            print("❌ 页面未初始化，无法执行抓取")
            return

        print("\n" + "="*80)
        print("🚀 开始执行核心抓取与过滤任务...")
        print("="*80 + "\n")

        # 1. 抓取前清理环境
        step1_start = time.time()
        try:
            await self.page.evaluate("""
                () => {
                    try {
                        console.clear();
                        // ⚠️ 重要：不清除localStorage和sessionStorage，保留登录账号信息
                        // localStorage.clear();  // 注释掉，避免清除登录信息
                        // sessionStorage.clear();  // 注释掉，避免清除登录信息
                        console.log("[OK] (From Python) 环境清理完成（保留登录信息）");
                    } catch (e) {
                        console.error("❌ (From Python) 环境清理失败:", e);
                    }
                }
            """)
            step1_end = time.time()
            print(f"[OK] 步骤1完成: 环境清理")
        except Exception as e:
            step1_end = time.time()
            print(f"❌ 步骤1失败: 环境清理出错: {e}")

        # 2. 配置角标过滤规则（使用哈希值）
        step2_start = time.time()
        

        
        # 原始角标URL列表（包含promotion-1和promotion-2两个域名）
        BADGE_URLS = [
            ('https://promotion-2.pddpic.com/promo/index/4e20a833-ce69-47f7-a9ff-bc1323a442c3.png', '官方旗舰'),
            ('https://promotion-2.pddpic.com/promo/index/962149d1-b03a-47fb-be05-7f289e14ed3b.png', '旗舰店'),
            ('https://funimg-2.pddpic.com/hot_friends/1753bf07-5378-4f13-a373-4b48c2265631.png', '专卖店'),
            ('https://promotion-2.pddpic.com/promo/index/09587d8d-9e2c-4867-9c77-5883e17e88da.png', '黑旗舰店'),
            ('https://promotion-2.pddpic.com/promo/index/6e9dba7f-bef0-4263-a355-e42dc63485c7.png', '官方旗舰'),
            ('https://promotion-2.pddpic.com/promo/gexinghua/0ac91857-db53-4a63-9c25-3fba32284e8f.png', '黑标品牌'),
            ('https://img-1.pddpic.com/aid-image/brand_black_label_combine', '黑标品牌'),
            ('https://promotion-1.pddpic.com/promo/index/4e20a833-ce69-47f7-a9ff-bc1323a442c3.png', '官方旗舰'),
            ('https://promotion-1.pddpic.com/promo/index/962149d1-b03a-47fb-be05-7f289e14ed3b.png', '旗舰店'),
            ('https://funimg-1.pddpic.com/hot_friends/1753bf07-5378-4f13-a373-4b48c2265631.png', '专卖店'),
            ('https://promotion-1.pddpic.com/promo/index/09587d8d-9e2c-4867-9c77-5883e17e88da.png', '黑旗舰店'),
            ('https://promotion-1.pddpic.com/promo/index/6e9dba7f-bef0-4263-a355-e42dc63485c7.png', '官方旗舰'),
            ('https://promotion-1.pddpic.com/promo/gexinghua/0ac91857-db53-4a63-9c25-3fba32284e8f.png', '黑标品牌')
        ]
        
        # 生成URL映射
        BADGE_FILTER_RULES = {}
        for url, description in BADGE_URLS:
            BADGE_FILTER_RULES[url] = f'{description}过滤'
        
        step2_end = time.time()
        print(f"[OK] 步骤2完成: 角标过滤规则配置")
        print(f"[INFO] 角标过滤规则数量: {len(BADGE_FILTER_RULES)}")

        # 3. 选取并排序商品卡片
        step3_start = time.time()
        print("🔄 步骤3: 正在抓取和排序商品卡片...")
        try:
            await self.page.wait_for_selector('._1unt3Js-', timeout=15000)
            product_cards = await self.page.query_selector_all('._1unt3Js-')
            if not product_cards:
                step3_end = time.time()
                print(f"❌ 步骤3失败: 未找到任何商品卡片。⏱️ 耗时: {step3_end - step3_start:.3f} 秒")
                return

            sorted_cards = []
            midpoint = (len(product_cards) + 1) // 2
            for i in range(midpoint):
                if i < len(product_cards): sorted_cards.append(product_cards[i])
                if i + midpoint < len(product_cards): sorted_cards.append(product_cards[i + midpoint])
            
            step3_end = time.time()
            print(f"[OK] 步骤3完成: 抓取并排序了 {len(sorted_cards)} 个商品卡片")
        except Exception as e:
            step3_end = time.time()
            print(f"❌ 步骤3失败: 抓取商品卡片出错: {e}")
            return

        # 4. 遍历卡片，抓取信息（🚀 优化：一次性JavaScript执行）
        step4_start = time.time()
        print("🔄 步骤4: 正在遍历卡片并提取信息...")
        
        # 🚀 使用JavaScript一次性提取所有商品数据（秒级完成）
        all_products_data = await self.page.evaluate("""
            () => {
                const cards = document.querySelectorAll('._1unt3Js-');
                const products = [];
                
                // 排序逻辑：交错排列
                const sortedCards = [];
                const midpoint = Math.ceil(cards.length / 2);
                for (let i = 0; i < midpoint; i++) {
                    if (i < cards.length) sortedCards.push(cards[i]);
                    if (i + midpoint < cards.length) sortedCards.push(cards[i + midpoint]);
                }
                
                // 提取每个商品的信息
                sortedCards.forEach(card => {
                    try {
                        const titleElement = card.querySelector('._3ANzdjkc');
                        let title = titleElement ? titleElement.innerText.trim() : '未找到标题';
                        // 清理特殊字符
                        title = title.replace(/[\uE000-\uF8FF]/g, '').trim();
                        
                        const imageElement = card.querySelector('img');
                        const imageUrl = imageElement ? imageElement.src : '未找到图片';
                        
                        const priceElement = card.querySelector('._3gmVc4Lg');
                        const price = priceElement ? priceElement.textContent.trim() : '未找到价格';
                        
                        const salesElement = card.querySelector('._2u4gEhMf');
                        const sales = salesElement ? salesElement.innerText.trim() : '未找到销量';
                        
                        const badgeElement = card.querySelector('._3fEq-XLr');
                        const badgeUrl = badgeElement ? badgeElement.src : '';
                        
                        products.push({
                            name: title,
                            image: imageUrl,
                            price: price,
                            sales: sales,
                            badgeUrl: badgeUrl
                        });
                    } catch (e) {
                        console.warn('处理单个卡片时跳过，原因:', e);
                    }
                });
                
                return products;
            }
        """)
        
        step4_end = time.time()
        print(f"[OK] 步骤4完成: 提取了 {len(all_products_data)} 条商品数据")

        # 5. 保存原始数据排序最靠后的20个商品（抓取全部数据后）
        step5_start = time.time()
        print("🔄 步骤5: 正在保存原始数据排序最靠后的20个商品...")
        self._save_latest_20_products(all_products_data)
        step5_end = time.time()
        print(f"[OK] 步骤5完成: 原始数据已保存")

        # 6. 历史商品过滤操作
        step6_start = time.time()
        print("🔄 步骤6: 正在过滤历史商品...")
        history_filtered_products, history_filtered_count = self._filter_historical_products(all_products_data)
        step6_end = time.time()
        print(f"[OK] 步骤6完成: 历史商品过滤移除 {history_filtered_count} 条商品，剩余 {len(history_filtered_products)} 条商品")

        # 7. 角标过滤操作
        step7_start = time.time()
        print("🔄 步骤7: 正在根据角标过滤商品...")
        badge_filtered_products = []
        badge_filtered_count = 0

        for product in history_filtered_products:
            badge_url = product.get("badgeUrl", "")
            title = product.get("name", "")
            filtered = False
            filter_reason = ""
            
            # 检查是否匹配任何角标过滤规则（使用ID）
            if badge_url:
                # 检查是否匹配任何过滤规则（页面角标URL包含我们规则中的URL）
                try:
                    matched_rule = None
                    
                    for rule_url, rule_name in BADGE_FILTER_RULES.items():
                        # 包含匹配：页面角标URL包含我们规则中的URL
                        if rule_url in badge_url:
                            matched_rule = rule_name
                            filtered = True
                            filter_reason = rule_name
                            print(f"   ✅ 角标匹配成功: {rule_name}")
                            break
                
                except Exception as e:
                    print(f"   ⚠️ 角标URL匹配失败: {badge_url}, 错误: {e}")
            
            if filtered:
                badge_filtered_count += 1
                print(f"   ❌ 过滤商品: {title[:30]}... ({filter_reason})")
            else:
                badge_filtered_products.append(product)
        
        step7_end = time.time()
        print(f"[OK] 步骤7完成: 角标过滤移除 {badge_filtered_count} 条商品，剩余 {len(badge_filtered_products)} 条商品")

        # ====================================================================================================
        # 8. 关键词过滤操作
        # ====================================================================================================
        print("🔄 步骤8: 正在根据关键词过滤商品...")
        step8_start = time.time()

        final_filtered_products = []
        keyword_filtered_count = 0

        for product in badge_filtered_products:
            title = product.get("name", "")
            matched_keyword = self._check_keyword_filter(title)

            if matched_keyword:
                keyword_filtered_count += 1
                print(f"   ❌ 过滤商品: {title[:30]}... (匹配关键词: {matched_keyword})")
            else:
                final_filtered_products.append(product)

        step8_end = time.time()
        filter_duration = step8_end - step8_start

        print(f"[OK] 步骤8完成: 关键词过滤移除 {keyword_filtered_count} 条商品，最终剩余 {len(final_filtered_products)} 条商品")

        # ====================================================================================================
        # 9. 价格过滤操作
        # ====================================================================================================
        print("🔄 步骤9: 正在根据价格过滤商品...")
        step9_start = time.time()

        price_filtered_products = []
        price_filtered_count = 0

        for product in final_filtered_products:
            title = product.get("name", "")
            price = product.get("price", "")
            
            if self._check_price_filter(price):
                price_filtered_products.append(product)
            else:
                price_filtered_count += 1
                print(f"   ❌ 过滤商品: {title[:30]}... (价格不符合条件)")

        step9_end = time.time()
        price_filter_duration = step9_end - step9_start

        print(f"[OK] 步骤9完成: 价格过滤移除 {price_filtered_count} 条商品，最终剩余 {len(price_filtered_products)} 条商品")

        # ====================================================================================================
        # 10. 检查过滤结果并决定是否保存
        # ====================================================================================================
        step10_start = time.time()
        print("🔄 步骤10: 检查过滤结果...")
        
        # 检查过滤后是否有新数据
        if len(price_filtered_products) > 0:
            print(f"✅ 过滤后有 {len(price_filtered_products)} 个新商品，保存数据...")
            
            # 保存会话数据
            self._save_session_data(price_filtered_products)
            
            step10_end = time.time()
            print(f"[OK] 步骤10完成: 数据已保存")
            
            # 直接进入结果输出
            step11_start = time.time()
            print(f"📊 数据处理摘要: 原始{len(all_products_data)}条 → 历史过滤-{history_filtered_count} → 角标过滤-{badge_filtered_count} → 关键词过滤-{keyword_filtered_count} → 价格过滤-{price_filtered_count} → 最终{len(price_filtered_products)}条")
            step11_end = time.time()
            print(f"🎉 任务完成！总耗时: {step11_end - step1_start:.3f}秒")
            
        else:
            print("⚠️ 过滤后没有新数据，开始第二次抓取尝试...")
            
            # 快速滑动到底部
            if await self._scroll_to_bottom_quickly():
                print("✅ 快速滑动到底部完成，等待新内容加载...")
                await asyncio.sleep(3)  # 等待新内容加载
                
                # 第二次抓取尝试
                second_success = await self._second_scrape_attempt()
                
                if second_success:
                    print("✅ 第二次抓取成功，有数据")
                    # 第二次抓取的数据已经在_second_scrape_attempt中保存了
                else:
                    print("⚠️ 第二次抓取失败，开始第三次抓取尝试...")
                    
                    # 🔥 新增：第三次抓取前的特殊滑动策略
                    if await self._third_scrape_preparation():
                        print("✅ 第三次抓取准备完成，等待新内容加载...")
                        await asyncio.sleep(3)  # 等待新内容加载
                        
                        # 第三次抓取尝试
                        third_success = await self._third_scrape_attempt()
                        
                        if third_success:
                            print("✅ 第三次抓取成功，有数据")
                        else:
                            print("❌ 连续三次抓取都失败，页面可能有问题，停止浏览器全部脚本")
                            await self._stop_all_browser_scripts()
                            return  # 直接退出
                    else:
                        print("❌ 第三次抓取准备失败，停止浏览器全部脚本")
                        await self._stop_all_browser_scripts()
                        return  # 直接退出
            else:
                print("❌ 滑动到底部失败，停止程序")
                return  # 直接退出
            
            step9_end = time.time()
            print(f"[OK] 步骤9完成: 抓取完成。⏱️ 耗时: {step9_end - step9_start:.3f} 秒")

    async def _scroll_to_bottom_quickly(self):
        """快速滑动到页面底部，触发更多内容加载"""
        try:
            print("🔄 开始快速滑动到底部...")
            
            # 获取页面当前高度
            current_height = await self.page.evaluate("() => document.documentElement.scrollHeight")
            print(f"[INFO] 当前页面高度: {current_height}像素")
            
            # 获取视口高度
            viewport_height = await self.page.evaluate("() => window.innerHeight")
            print(f"[INFO] 视口高度: {viewport_height}像素")
            
            # 计算需要滑动的距离（从当前位置到底部）
            current_scroll = await self.page.evaluate("() => window.pageYOffset")
            scroll_distance = current_height - current_scroll - viewport_height
            
            if scroll_distance <= 0:
                print("ℹ️ 已在页面底部，无需滑动")
                return True
            
            print(f"[INFO] 需要滑动距离: {scroll_distance}像素")
            
            # 快速滑动到底部（分段滑动，避免一次性滑动过大）
            segment_size = 1000  # 每次滑动1000像素
            segments = max(1, int(scroll_distance / segment_size))
            
            print(f"[INFO] 分段滑动: {segments}段，每段{segment_size}像素")
            
            for i in range(segments):
                segment_distance = min(segment_size, scroll_distance - i * segment_size)
                if segment_distance <= 0:
                    break
                
                print(f"[INFO] 执行第{i+1}段滑动: {segment_distance}像素")
                
                # 使用JavaScript快速滚动
                await self.page.evaluate(f"window.scrollBy(0, {segment_distance})")
                
                # 短暂等待内容加载
                await asyncio.sleep(0.5)
                
                # 检查是否有新内容加载
                new_height = await self.page.evaluate("() => document.documentElement.scrollHeight")
                if new_height > current_height:
                    print(f"[✅] 检测到新内容加载，页面高度从{current_height}增加到{new_height}")
                    current_height = new_height
                    # 重新计算剩余滑动距离
                    scroll_distance = current_height - await self.page.evaluate("() => window.pageYOffset") - viewport_height
            
            # 最后滑动到真正的底部
            await self.page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
            await asyncio.sleep(1)  # 等待最终内容加载
            
            print("✅ 快速滑动到底部完成")
            return True
            
        except Exception as e:
            print(f"[ERROR] 快速滑动到底部失败: {e}")
            return False

    async def _second_scrape_attempt(self) -> bool:
        """第二次抓取尝试 - 滑动后重新抓取数据，返回是否成功"""
        try:
            print("🔄 开始第二次抓取尝试...")
            
            # 等待页面稳定
            await asyncio.sleep(2)
            
            # 重新抓取商品卡片
            try:
                await self.page.wait_for_selector('._1unt3Js-', timeout=10000)
                product_cards = await self.page.query_selector_all('._1unt3Js-')
                if not product_cards:
                    print("❌ 第二次抓取：未找到任何商品卡片")
                    return False
                
                print(f"[INFO] 第二次抓取：找到 {len(product_cards)} 个商品卡片")
                
                # 使用JavaScript一次性提取所有商品数据
                second_products_data = await self.page.evaluate("""
                    () => {
                        const cards = document.querySelectorAll('._1unt3Js-');
                        const products = [];
                        
                        // 排序逻辑：交错排列
                        const sortedCards = [];
                        const midpoint = Math.ceil(cards.length / 2);
                        for (let i = 0; i < midpoint; i++) {
                            if (i < cards.length) sortedCards.push(cards[i]);
                            if (i + midpoint < cards.length) sortedCards.push(cards[i + midpoint]);
                        }
                        
                        // 提取每个商品的信息
                        sortedCards.forEach(card => {
                            try {
                                const titleElement = card.querySelector('._3ANzdjkc');
                                let title = titleElement ? titleElement.innerText.trim() : '未找到标题';
                                title = title.replace(/[\uE000-\uF8FF]/g, '').trim();
                                
                                const imageElement = card.querySelector('img');
                                const imageUrl = imageElement ? imageElement.src : '未找到图片';
                                
                                const priceElement = card.querySelector('._3gmVc4Lg');
                                const price = priceElement ? priceElement.textContent.trim() : '未找到价格';
                                
                                const salesElement = card.querySelector('._2u4gEhMf');
                                const sales = salesElement ? salesElement.innerText.trim() : '未找到销量';
                                
                                const badgeElement = card.querySelector('._3fEq-XLr');
                                const badgeUrl = badgeElement ? badgeElement.src : '';
                                
                                products.push({
                                    name: title,
                                    image: imageUrl,
                                    price: price,
                                    sales: sales,
                                    badgeUrl: badgeUrl
                                });
                            } catch (e) {
                                console.warn('处理单个卡片时跳过，原因:', e);
                            }
                        });
                        
                        return products;
                    }
                """)
                
                print(f"[INFO] 第二次抓取：成功提取了 {len(second_products_data)} 条商品数据")
                
                # 对第二次抓取的数据进行过滤
                if len(second_products_data) > 0:
                    # 历史商品过滤
                    second_history_filtered, second_history_count = self._filter_historical_products(second_products_data)
                    print(f"[INFO] 第二次抓取：历史过滤移除 {second_history_count} 条，剩余 {len(second_history_filtered)} 条")
                    
                    # 角标过滤
                    second_badge_filtered = []
                    for product in second_history_filtered:
                        badge_url = product.get("badgeUrl", "")
                        if badge_url:
                            filtered = False
                            for rule_url in BADGE_FILTER_RULES.keys():
                                if rule_url in badge_url:
                                    filtered = True
                                    break
                            if not filtered:
                                second_badge_filtered.append(product)
                        else:
                            second_badge_filtered.append(product)
                    
                    print(f"[INFO] 第二次抓取：角标过滤后剩余 {len(second_badge_filtered)} 条")
                    
                    # 关键词过滤
                    second_final_filtered = []
                    for product in second_badge_filtered:
                        title = product.get("name", "")
                        if not self._check_keyword_filter(title):
                            second_final_filtered.append(product)
                    
                    print(f"[INFO] 第二次抓取：关键词过滤后剩余 {len(second_final_filtered)} 条")
                    
                    # 如果第二次抓取有新数据，保存数据
                    if len(second_final_filtered) > 0:
                        print(f"✅ 第二次抓取成功！获得 {len(second_final_filtered)} 个新商品")
                        
                        # 保存第二次抓取的数据
                        self._save_session_data(second_final_filtered)
                        print(f"✅ 已保存第二次抓取的数据，总计 {len(second_final_filtered)} 个商品")
                        return True
                    else:
                        print("⚠️ 第二次抓取后仍然没有新数据")
                        return False
                else:
                    print("❌ 第二次抓取失败：未获取到任何数据")
                    return False
                
            except Exception as e:
                print(f"❌ 第二次抓取过程中发生错误: {e}")
                return False
                
        except Exception as e:
            print(f"[ERROR] 第二次抓取尝试失败: {e}")
            return False
    
    async def _third_scrape_preparation(self) -> bool:
        """第三次抓取准备 - 往上滑动1500像素（分2次），然后快速滑动到底部"""
        try:
            print("🔄 开始第三次抓取准备...")
            
            # 第一步：往上滑动1500像素，分2次滑动
            print("📈 第一步：往上滑动1500像素（分2次）...")
            
            # 第一次往上滑动750像素
            await self.page.evaluate("window.scrollBy(0, -750)")
            await asyncio.sleep(1)
            print("✅ 第一次往上滑动完成：750像素")
            
            # 第二次往上滑动750像素
            await self.page.evaluate("window.scrollBy(0, -750)")
            await asyncio.sleep(1)
            print("✅ 第二次往上滑动完成：750像素")
            
            # 第二步：快速滑动到底部
            print("📉 第二步：快速滑动到底部...")
            if await self._scroll_to_bottom_quickly():
                print("✅ 第三次抓取准备完成")
                return True
            else:
                print("❌ 快速滑动到底部失败")
                return False
                
        except Exception as e:
            print(f"[ERROR] 第三次抓取准备失败: {e}")
            return False
    
    async def _third_scrape_attempt(self) -> bool:
        """第三次抓取尝试 - 特殊滑动后重新抓取数据，返回是否成功"""
        try:
            print("🔄 开始第三次抓取尝试...")
            
            # 等待页面稳定
            await asyncio.sleep(2)
            
            # 查找商品卡片
            product_cards = await self.page.query_selector_all('.goods-card')
            
            if not product_cards:
                print("❌ 第三次抓取：未找到任何商品卡片")
                return False
            
            print(f"[INFO] 第三次抓取：找到 {len(product_cards)} 个商品卡片")
            
            # 提取商品数据
            third_products_data = []
            for i, card in enumerate(product_cards):
                try:
                    # 提取商品信息（与第一次抓取相同的逻辑）
                    product_data = await self._extract_product_data(card)
                    if product_data:
                        third_products_data.append(product_data)
                except Exception as e:
                    print(f"⚠️ 第三次抓取：提取第{i+1}个商品数据失败: {e}")
                    continue
            
            if not third_products_data:
                print("❌ 第三次抓取：未提取到任何商品数据")
                return False
            
            print(f"[INFO] 第三次抓取：成功提取了 {len(third_products_data)} 条商品数据")
            
            # 对第三次抓取的数据进行过滤
            third_history_filtered = self._filter_historical_products(third_products_data)
            third_history_count = len(third_products_data) - len(third_history_filtered)
            
            print(f"[INFO] 第三次抓取：历史过滤移除 {third_history_count} 条，剩余 {len(third_history_filtered)} 条")
            
            if not third_history_filtered:
                print("⚠️ 第三次抓取：历史过滤后没有新数据")
                return False
            
            # 角标过滤
            third_badge_filtered = self._filter_badge_products(third_history_filtered)
            third_badge_count = len(third_history_filtered) - len(third_badge_filtered)
            
            print(f"[INFO] 第三次抓取：角标过滤移除 {third_badge_count} 条，剩余 {len(third_badge_filtered)} 条")
            
            if not third_badge_filtered:
                print("⚠️ 第三次抓取：角标过滤后没有新数据")
                return False
            
            # 关键词过滤
            third_final_filtered = self._filter_keyword_products(third_badge_filtered)
            third_keyword_count = len(third_badge_filtered) - len(third_final_filtered)
            
            print(f"[INFO] 第三次抓取：关键词过滤后剩余 {len(third_final_filtered)} 条")
            
            # 如果第三次抓取有新数据，保存数据
            if third_final_filtered:
                print(f"✅ 第三次抓取成功！获得 {len(third_final_filtered)} 个新商品")
                
                # 保存第三次抓取的数据
                self._save_products_data(third_final_filtered)
                print(f"✅ 已保存第三次抓取的数据，总计 {len(third_final_filtered)} 个商品")
                return True
            else:
                print("⚠️ 第三次抓取后仍然没有新数据")
                return False
                
        except Exception as e:
            print(f"❌ 第三次抓取过程中发生错误: {e}")
            return False
    
    async def _stop_all_browser_scripts(self):
        """停止浏览器全部脚本（不只是zq.py）"""
        try:
            print("🛑 开始停止浏览器全部脚本...")
            
            # 获取当前浏览器ID
            browser_id = self.browser_id
            print(f"🆔 当前浏览器ID: {browser_id}")
            
            # 构建停止标志文件路径
            stop_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "stop_flag.txt"
            )
            
            # 创建停止标志文件
            try:
                os.makedirs(os.path.dirname(stop_flag_file), exist_ok=True)
                with open(stop_flag_file, 'w', encoding='utf-8') as f:
                    f.write(f"stopped_at:{time.time()}")
                print(f"✅ 已创建停止标志文件: {stop_flag_file}")
            except Exception as e:
                print(f"⚠️ 创建停止标志文件失败: {e}")
            
            # 尝试停止当前进程
            try:
                import os
                import signal
                import sys
                
                # 在Windows上使用taskkill，在Linux/Mac上使用kill
                if os.name == 'nt':  # Windows
                    import subprocess
                    # 获取当前进程ID
                    current_pid = os.getpid()
                    print(f"🔄 正在停止当前进程 (PID: {current_pid})...")
                    
                    # 使用taskkill强制停止当前进程
                    subprocess.run(['taskkill', '/F', '/PID', str(current_pid)], 
                                capture_output=True, timeout=5)
                else:  # Linux/Mac
                    print(f"🔄 正在停止当前进程 (PID: {os.getpid()})...")
                    os.kill(os.getpid(), signal.SIGTERM)
                
            except Exception as e:
                print(f"⚠️ 停止当前进程失败: {e}")
                # 如果无法停止当前进程，至少退出程序
                print("🔄 强制退出程序...")
                sys.exit(1)
            
        except Exception as e:
            print(f"❌ 停止浏览器全部脚本失败: {e}")
            # 确保程序退出
            import sys
            sys.exit(1)

    async def close_browser(self):
        """关闭浏览器连接"""
        try:
            if self.playwright:
                await self.playwright.stop()
            print("🔌 浏览器连接已断开")
        except Exception as e:
            print(f"❌ 关闭浏览器失败: {e}")

async def main(page=None, browser_id=None):
    """主执行函数 - 支持传入已连接的页面实例"""
    if page:
        # 使用已连接的页面实例
        print(f"[ZQ] 使用已连接的页面实例，浏览器ID: {browser_id}")
        
        # 🔥 新增：紧急状况检测（已注释掉，改用jiex.py检测）
        # try:
        #     from emergency_monitor import monitor_emergency
        #     emergency_ok = await monitor_emergency(page, browser_id)
        #     if not emergency_ok:
        #         print("🚨 检测到紧急状况，zq.py 已暂停")
        #         return
        # except ImportError:
        #     print("⚠️ emergency_monitor 模块未找到，跳过紧急检测")
        
        tester = HybridHumanizedTester()
        tester.page = page
        tester.browser_id = browser_id
        await tester.scrape_and_process_page()
        # 不关闭浏览器，因为页面是从外部传入的
    else:
        # 创建新实例并连接浏览器
        print(f"[ZQ] 创建新的浏览器连接")
        tester = HybridHumanizedTester()
        if await tester.connect_browser():
            await tester.scrape_and_process_page()
            await tester.close_browser()

if __name__ == "__main__":
    asyncio.run(main())
