#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
�手动抓取模块 - 持续监控版本
用于在UI� 集成，实现一直在线自动抓取
"""

import os
import sys
import json
import time
import asyncio
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

class ManualDataExtractor:
    """手动数据抓取器 - 持续监控版本"""
    
    def __init__(self, browser_id: str, ui_log_callback=None):
        self.browser_id = browser_id
        self.is_manual_mode = False
        self.is_monitoring = False
        self.debug_port = None
        self.save_path = None
        self.last_extracted_url = None
        self.monitor_thread = None
        self.ui_log_callback = ui_log_callback  # UI日志回调函数
        
        # 内存监控相关
        self.memory_check_interval = 60  # 每60秒检查一次内存
        self.last_memory_check = time.time()
        self.memory_threshold = 500 * 1024 * 1024  # 500MB内存阈值
        
        # 设置保存路径
        self._setup_save_path()
        
        # 🔥 新增：CSV保存和运行时统计功能初始化
        self._init_csv_functionality()
    
    def _check_memory_usage(self):
        """检查内存使用情况，超过阈值自动清理"""
        current_time = time.time()
        
        # 每60秒检查一次内存
        if current_time - self.last_memory_check < self.memory_check_interval:
            return
        
        try:
            import psutil
            import gc
            
            # 获取当前进程内存使用
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            print(f"[内存监控] 当前内存使用: {memory_mb:.1f}MB")
            
            # 如果超过阈值，执行清理
            if memory_info.rss > self.memory_threshold:
                print(f"[内存监控] ⚠️ 内存使用超过{self.memory_threshold/1024/1024:.0f}MB，开始清理...")
                
                # 强制垃圾回收
                gc.collect()
                
                # 清理可能的缓存数据
                if hasattr(self, 'last_extracted_data'):
                    delattr(self, 'last_extracted_data')
                
                print(f"[内存监控] ✅ 内存清理完成")
            
            self.last_memory_check = current_time
            
        except ImportError:
            # psutil未安装，跳过内存监控
            pass
        except Exception as e:
            print(f"[内存监控] ❌ 内存检查失败: {e}")
    
    def _setup_save_path(self):
        """设置保存路径，优先使用主目录的details文件夹"""
        # 尝试找到主目录的details文件夹
        current_dir = Path(__file__).parent
        main_details = current_dir.parent.parent / "details"
        
        if main_details.exists():
            self.save_path = str(main_details)
            print(f"[路径设置] 使用主目录details: {self.save_path}")
        else:
            # 回退到浏览器特定的details文件夹
            browser_details = current_dir / "details"
            browser_details.mkdir(exist_ok=True)
            self.save_path = str(browser_details)
            print(f"[路径设置] 使用浏览器details: {self.save_path}")
    
    def _get_debug_port(self) -> Optional[int]:
        """获取调试端口"""
        try:
            # 从配置文件获取调试端口
            config_path = Path(__file__).parent / "config_api.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    port = config.get('browser_info', {}).get('debug_port')
                    if port:
                        self.debug_port = port
                        return port
            
            # 如果配置文件不存在，使用默认端口
            return 53484
            
        except Exception as e:
            return None
    
    def start_manual_mode(self):
        """启动手动抓取模式"""
        self.is_manual_mode = True
        print(f"✅ 手动解析功能开启")
        
        # 启动持续监控
        self.start_continuous_monitoring()
    
    def start_continuous_monitoring(self):
        """启动持续监控"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        
        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
    
    def _monitor_loop(self):
        """监控循环 - 一直运行"""
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self.is_monitoring:
                try:
                    # 执行一次抓取检查
                    loop.run_until_complete(self._check_and_extract())
                    
                    # 内存监控检查
                    self._check_memory_usage()
                    
                    # 等待0.5秒后再次检查（提高响应速度）
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"[监控循环] ❌ 抓取检查异常: {e}")
                    # 出错后等待1秒，但继续循环
                    time.sleep(1)

        except Exception as e:
            print(f"[监控循环] ❌ 监控循环严重异常: {e}")
        finally:
            try:
                loop.close()
                print("[监控循环] ✅ 事件循环已关闭")
            except:
                pass
    
    async def _check_and_extract(self):
        """检查当前页面并抓取"""
        try:
            from playwright.async_api import async_playwright
            
            async with async_playwright() as playwright:
                debug_port = self._get_debug_port()
                if not debug_port:
                    return False
                
                browser = await playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
                
                if browser.contexts and browser.contexts[0].pages:
                    page = browser.contexts[0].pages[0]
                    current_url = page.url
                    
                    # 🔥 新增：定期内存清理（每10次检查清理一次）
                    if not hasattr(self, '_check_count'):
                        self._check_count = 0
                    self._check_count += 1
                    
                    if self._check_count % 20 == 0:  # 每20次检查清理一次（每10秒）
                        print(f"[MEMORY] 定期内存清理 (第{self._check_count}次检查)")
                        await self._clean_browser_memory(page)
                    
                    # 检查是否是详情页
                    if self._is_detail_page(current_url):
                        # 检查是否已经抓取过这个页面
                        if current_url != self.last_extracted_url:
                            success = await self.manual_extract_data(page)
                            if success:
                                self.last_extracted_url = current_url
                                return True
                        return False
                    else:
                        return False
                        
                await browser.close()
                return False

        except Exception as e:
            print(f"[检查] 出错: {e}")
            return False

    async def _clean_browser_memory(self, page):
        """清理浏览器内存"""
        try:
            await page.evaluate("""
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
                        if (window.rawData) window.rawData = null;
                        if (window.historyDataForSave) window.historyDataForSave = null;
                        if (window.latest20DataForSave) window.latest20DataForSave = null;
                        
                        // 清除事件监听器缓存
                        const elements = document.querySelectorAll('*');
                        elements.forEach(el => {
                            if (el._listeners) el._listeners = null;
                            if (el._events) el._events = null;
                        });
                        
                        // 清除图片缓存
                        const images = document.querySelectorAll('img');
                        images.forEach(img => {
                            if (img.src && !img.src.includes('login') && !img.src.includes('auth') && !img.src.includes('token')) {
                                img.src = '';
                                img.removeAttribute('src');
                            }
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
            print("[MEMORY] 浏览器内存清理完成")
        except Exception as e:
            print(f"[WARNING] 浏览器内存清理失败: {e}")
    
    def _is_detail_page(self, url):
        """判断是否是详情页"""
        # 只检查URL中是否包含goods_id=，有就是详情页，没有就不是详情页
        return "goods_id=" in url

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

    async def manual_extract_data(self, page) -> bool:
        """手动抓取数据"""
        try:
            # 等待页面基本加载完成
            await page.wait_for_load_state('domcontentloaded')

            # 等待window.rawData可用（减少超时时间，提高速度）
            try:
                await page.wait_for_function('''
                    () => window.rawData &&
                          window.rawData.store &&
                          window.rawData.store.initDataObj
                ''', timeout=2000)  # 减少到2秒
            except Exception as e:
                # 超时后继续尝试获取数据
                pass

            # 抓取完整的rawData
            raw_data = await page.evaluate('''
                () => {
                    if (!window.rawData) {
                        return null;
                    }

                    // 深度复制rawData，避免引用问题
                    function deepClone(obj, maxDepth = 15, currentDepth = 0) {
                        if (currentDepth >= maxDepth) return '[深度限制]';
                        if (obj === null || typeof obj !== 'object') return obj;

                        if (Array.isArray(obj)) {
                            return obj.slice(0, 100).map(item => deepClone(item, maxDepth, currentDepth + 1));
                        }

                        const result = {};
                        let count = 0;
                        for (const key in obj) {
                            if (count >= 200) break; // 限制每层最多200个属性
                            if (obj.hasOwnProperty(key)) {
                                result[key] = deepClone(obj[key], maxDepth, currentDepth + 1);
                                count++;
                            }
                        }
                        return result;
                    }

                    const clonedData = deepClone(window.rawData);

                    return {
                        url: window.location.href,
                        title: document.title,
                        timestamp: new Date().toISOString(),
                        rawData: clonedData,
                        extractTime: new Date().toISOString().replace('T', ' ').substring(0, 19)
                    };
                }
            ''')

            if not raw_data or not raw_data.get('rawData'):
                return False

            # 保存抓取的数据用于后续保存
            self.last_extracted_data = raw_data
            
            # 提取商品ID
            goods_id = self._extract_goods_id(raw_data)
            if goods_id:
                self.last_goods_id = goods_id
            else:
                self.last_goods_id = f"unknown_{int(time.time())}"
            
            # 加密压缩并上传到服务器
            success = await self._process_and_upload_data(raw_data)
            
            return success

        except Exception as e:
            print(f"[抓取] 失败: {e}")
            return False

    async def _process_and_upload_data(self, raw_data) -> bool:
        """处理和上传数据"""
        try:
            # 1. 加密压缩
            encrypted_data = self.encrypt_compress_for_cloud(raw_data)
            if not encrypted_data:
                return False

            # 2. 上传到服务器
            upload_success = await self.upload_to_server(encrypted_data['encrypted_data'], self.last_goods_id)
            if not upload_success:
                return False
            
            # 3. 从服务器下载并保存
            download_success = await self.download_and_save_from_server(self.last_goods_id, raw_data)
            if not download_success:
                return False
            
            return True

        except Exception as e:
            print(f"[处理] 失败: {e}")
            return False

    def encrypt_compress_for_cloud(self, raw_data: Dict) -> Optional[Dict]:
        """
        加密压缩数据用于云端上传

        Args:
            raw_data: 原始数据

        Returns:
            包含加密数据和统计信息的字典，失败返回None
        """
        try:
            import json
            import base64
            import gzip

            # 1. 转换为JSON字符串
            json_str = json.dumps(raw_data, ensure_ascii=False, separators=(',', ':'))
            original_size = len(json_str.encode('utf-8'))

            # 2. 压缩数据
            compressed_data = gzip.compress(json_str.encode('utf-8'))
            compressed_size = len(compressed_data)

            # 3. Base64编码（模拟加密）
            encrypted_data = base64.b64encode(compressed_data).decode('utf-8')
            final_size = len(encrypted_data.encode('utf-8'))

            # 4. 计算压缩率
            compression_ratio = f"{(1 - final_size / original_size) * 100:.1f}%"

            print(f"[加密] 完成: {compression_ratio}")

            return {
                'encrypted_data': encrypted_data,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'final_size': final_size,
                'compression_ratio': compression_ratio
            }

        except Exception as e:
            print(f"[错误] 数据加密压缩失败: {e}")
            return None

    async def upload_to_server(self, encrypted_data: str, goods_id: str) -> bool:
        """
        上传加密数据到服务器

        Args:
            encrypted_data: 加密后的数据
            goods_id: 商品ID

        Returns:
            是否上传成功
        """
        try:
            import asyncio
            # 🔥 模拟上传到服务器
            await asyncio.sleep(0.1)  # 减少延迟，提高速度
            return True

        except Exception as e:
            print(f"[错误] 上传失败: {e}")
            return False

    async def download_and_save_from_server(self, goods_id: str, original_data: dict = None) -> bool:
        """
        从真实Ubuntu服务器下载压缩JSON数据并保存为TXT文档到details目录

        流程：上传到服务器 → 服务器加密压缩保存 → 从服务器下载压缩数据 → 保存为TXT文档到details目录

        Args:
            goods_id: 商品ID
            original_data: 原始数据（用于预售检测、CSV字段提取和商品名称提取，不保存原始数据）

        Returns:
            是否下载保存成功
        """
        try:
            import aiohttp
            import asyncio
            import json
            from pathlib import Path
            
            # 预售检测 - 检测到click_notice字段则跳过保存
            if original_data:
                presale_info = self._extract_presale_info(original_data)
                if presale_info:  # 如果存在click_notice字段内容，则跳过保存
                    print(f"🗑️  检测到部分预售商品({goods_id})，跳过处理")
                    return True

            # 服务器配置（从config_api.json读取或使用默认值）
            server_url = "http://localhost:8888"
            try:
                config_path = Path(__file__).parent / "config_api.json"
                if config_path.exists():
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = json.load(f)
                        cloud_server = config.get('cloud_server', {})
                        server_url = cloud_server.get('server_url', server_url)
            except Exception:
                pass
            
            # 从服务器下载压缩数据
            timeout = aiohttp.ClientTimeout(total=30)  # 30秒超时
            async with aiohttp.ClientSession(timeout=timeout) as session:
                download_data = {'filename': f'{goods_id}.json'}
                async with session.post(f"{server_url}/download", json=download_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('status') == 'success':
                            # 获取解密后的数据（服务器已经解密了）
                            data = result.get('data', {})
                            
                            if not data:
                                return False
                            
                            # 确保details目录存在
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
                            
                            # 提取商品名称用于日志显示
                            goods_name = "未知商品"
                            if original_data and 'rawData' in original_data:
                                try:
                                    raw_data = original_data['rawData']
                                    name_paths = [
                                        ['store', 'initDataObj', 'goods', 'goodsName'],
                                        ['store', 'initDataObj', 'goods', 'goods_name'],
                                        ['goods', 'goodsName'],
                                        ['goods', 'goods_name'],
                                        ['store', 'initDataObj', 'goods', 'title']
                                    ]
                                    
                                    for path in name_paths:
                                        try:
                                            value = raw_data
                                            for key in path:
                                                value = value[key]
                                            if value:
                                                goods_name = str(value)
                                                break
                                        except (KeyError, TypeError):
                                            continue
                                except:
                                    pass
                            
                            # 简化日志：只显示ID、商品名称和保存位置
                            success_msg = f"✅ ID：{goods_id}（{goods_name}）已保存到\\details目录"
                            
                            # 防重复日志
                            if not hasattr(self, '_last_logged_goods'):
                                self._last_logged_goods = set()
                            
                            log_key = f"{goods_id}_{goods_name}"
                            if log_key not in self._last_logged_goods:
                                print(success_msg)
                                
                                # 如果有UI日志回调，发送到UI
                                if hasattr(self, 'ui_log_callback') and self.ui_log_callback:
                                    try:
                                        self.ui_log_callback(success_msg)
                                    except:
                                        pass
                                
                                # 记录已输出的日志，避免重复
                                self._last_logged_goods.add(log_key)
                                
                                # 限制日志记录数量，避免内存泄漏
                                if len(self._last_logged_goods) > 1000:
                                    self._last_logged_goods.clear()
                        else:
                            print(f"❌ 服务器下载失败: {result.get('message', '未知错误')}")
                            return False
                    else:
                        print(f"❌ 服务器响应错误: HTTP {response.status}")
                        return False

            # 从原始数据提取字段并保存到CSV表格（只保存处理后的字段，不保存原始数据）
            try:
                if original_data:  # 用原始数据提取字段
                    csv_data = self._extract_csv_fields(original_data)  # 提取字段：商品ID、商品名称、价格等
                    if csv_data and csv_data.get('商品ID'):
                        self._save_to_csv(csv_data)  # 只保存提取的字段数据到CSV表格
            except Exception as e:
                print(f"⚠️ CSV保存失败: {e}")

            return True

        except asyncio.TimeoutError:
            print(f"❌ 下载超时: {goods_id}")
            return False
        except Exception as e:
            print(f"❌ 从服务器下载失败: {e}")
            return False

    # ==================== 🔥 新增：CSV保存和运行时统计功能 ====================
    
    def _init_csv_functionality(self):
        """初始化CSV保存和运行时统计功能"""
        try:
            # 运行时统计初始化
            self.runtime_parsed_count = 0
            
            # 🔥 修复：根据browser_id确定正确的输出目录
            if self.browser_id:
                # 如果有browser_id，优先使用对应的浏览器目录
                project_root = Path(__file__).parent.parent
                browser_dir = project_root / "generated_scripts" / f"browser_{self.browser_id}"
                if browser_dir.exists():
                    self.csv_output_dir = browser_dir / "output"
                else:
                    # 如果浏览器目录不存在，使用主目录
                    self.csv_output_dir = project_root / "output"
            else:
                # 没有browser_id时，使用当前目录
                # 🔥 新版路径：保存到主目录的output和cache文件夹
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
            
            # CSV文件路径（保存到主目录output文件夹，文件名加上browser_id后缀）
            browser_id = getattr(self, 'browser_id', 'manual')  # 手动抓取使用默认标识
            self.csv_file_path = main_output_dir / f"手动抓取_商品数据_{browser_id}.csv"
            
            # 统计JSON文件路径（保存到主目录cache文件夹，文件名加上browser_id后缀）
            self.stats_file_path = main_cache_dir / f"统计数量_{browser_id}.json"
            
            # 创建CSV文件头（如果文件不存在）
            self._create_csv_header()
            
            # 初始化统计JSON文件
            self._init_stats_file()
            
            print(f"[CSV] CSV功能已初始化")
            print(f"[CSV] 输出目录: {self.csv_output_dir}")
            print(f"[CSV] CSV文件: {self.csv_file_path}")
            print(f"[CSV] 统计文件: {self.stats_file_path}")
            
        except Exception as e:
            print(f"❌ CSV功能初始化失败: {e}")
    
    def _create_csv_header(self):
        """创建CSV文件头（如果文件不存在）"""
        try:
            if not self.csv_file_path.exists():
                headers = [
                    "商品ID", "商品名称", "店铺名称", "商品链接", "当前价格", "券后价", "商品销量", "店铺销量", 
                    "高清图片", "商家ID", "发货时间", "发货地", "商品类目", "评价数量", "正在拼", "店铺商品数量", "24小时发货", "新品", "部分预售", "上架时间", "采集时间"
                ]
                
                import csv
                with open(self.csv_file_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                print(f"[CSV] CSV文件头已创建")
        except Exception as e:
            print(f"❌ 创建CSV文件头失败: {e}")
    
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
            print(f"❌ 初始化统计文件失败: {e}")
    
    def _extract_csv_fields(self, raw_data: Dict) -> Optional[Dict]:
        """从rawData提取CSV需要的字段"""
        try:
            if not raw_data or 'rawData' not in raw_data:
                return None
            
            data = raw_data['rawData']
            
            # 从rawData中提取goods对象（与jiex.py保持一致）
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
                '发货时间': self._extract_delivery_time(data) or '',
                '发货地': self._extract_delivery_location(data) or '',
                '商品类目': self._extract_category_info(data) or '',
                '评价数量': self._extract_review_count(data) or 0,
                '正在拼': self._extract_grouping_info(data) or '',
                '店铺数量': self._extract_store_count(data) or '',
                '24小时发货': icon_info.get('has_24h_shipping', '否'),
                '新品': icon_info.get('has_new_product', '否'),
                '上架时间': upload_time or '',
                '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            return csv_data
            
        except Exception as e:
            print(f"❌ 提取CSV字段失败: {e}")
            return None
    
    def _extract_field_by_paths(self, data: Dict, paths: List[List[str]], default_value):
        """根据多个路径提取字段值"""
        for path in paths:
            try:
                value = data
                for key in path:
                    value = value[key]
                if value is not None:
                    return value
            except (KeyError, TypeError):
                continue
        return default_value
    
    def _format_category_chain(self, data: Dict) -> str:
        """格式化商品分类链：一级-二级-三级-四级"""
        try:
            categories = []
            
            # 分类路径映射
            category_paths = [
                (['store', 'initDataObj', 'goods', 'catId1'], ['store', 'initDataObj', 'goods', 'catName1']),
                (['store', 'initDataObj', 'goods', 'catId2'], ['store', 'initDataObj', 'goods', 'catName2']),
                (['store', 'initDataObj', 'goods', 'catId3'], ['store', 'initDataObj', 'goods', 'catName3']),
                (['store', 'initDataObj', 'goods', 'catId4'], ['store', 'initDataObj', 'goods', 'catName4'])
            ]
            
            for id_path, name_path in category_paths:
                cat_id = self._extract_field_by_paths(data, [id_path], None)
                cat_name = self._extract_field_by_paths(data, [name_path], None)
                
                if cat_id and cat_name and str(cat_id) != '0':
                    categories.append(str(cat_name))
            
            return '-'.join(categories) if categories else ''
            
        except Exception as e:
            print(f"❌ 格式化分类链失败: {e}")
            return ''
    
    def _save_to_csv(self, csv_data: Dict) -> bool:
        """保存数据到CSV文件（增量追加）"""
        try:
            import csv
            
            # 按照CSV头的顺序准备数据
            headers = [
                "商品ID", "商品名称", "商品链接", "当前价格", "券后价", "商品销量", "店铺销量", 
                "高清图片", "商家ID", "发货时间", "发货地", "商品类目", "评价数量", "正在拼", "店铺数量", "24小时发货", "新品", "上架时间", "采集时间"
            ]
            
            row_data = [csv_data.get(header, '') for header in headers]
            
            # 追加到CSV文件
            with open(self.csv_file_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(row_data)
            
            # 更新运行时统计
            self.runtime_parsed_count += 1
            self._update_runtime_stats()
            
            # 🔥 添加详细的保存日志
            goods_id = csv_data.get('商品ID', '未知')
            goods_name = csv_data.get('商品名称', '未知商品')[:30]  # 只显示前30个字符
            print(f"[CSV] ✅ 已保存到表格: {goods_id} - {goods_name}...")
            
            return True
            
        except Exception as e:
            print(f"❌ 保存CSV数据失败: {e}")
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
            
            print(f"[统计] 已解析 {self.runtime_parsed_count} 个商品")
            
        except Exception as e:
            print(f"❌ 更新运行时统计失败: {e}")

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
                ['store', 'initDataObj', 'shipping', 'deliveryTime'],
                ['store', 'initDataObj', 'ui', 'deliveryTimeV2Section', 'mainText'],
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

    def _extract_delivery_location(self, data: Dict) -> str:
        """提取发货地（shippingLocation字段）"""
        try:
            # 尝试从多个可能的位置获取发货地
            location_paths = [
                ['store', 'initDataObj', 'shipping', 'originPlace'],
                ['store', 'initDataObj', 'shipping', 'shippingLocation'],
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
        """提取商品类目（cat1Name,cat2Name,cat3Name,cat4Name）按顺序组合"""
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

    def _get_goods_object(self, data: Dict) -> Dict:
        """获取goods对象（忽略大小写和_符号）"""
        try:
            # 尝试多个可能的路径
            paths = [
                ['store', 'initDataObj', 'goods'],
                ['store', 'initdataobj', 'goods'],
                ['store', 'init_data_obj', 'goods'],
                ['store', 'initDataObj', 'Goods'],
                ['store', 'initdataobj', 'Goods']
            ]
            
            for path in paths:
                try:
                    result = data
                    for key in path:
                        result = result[key]
                    if result:
                        return result
                except (KeyError, TypeError):
                    continue
            
            return {}
        except Exception:
            return {}

    def _get_field_value(self, obj: Dict, field_names: List[str], default_value):
        """获取字段值（忽略大小写和_符号）"""
        try:
            # 首先尝试直接匹配
            for field_name in field_names:
                if field_name in obj:
                    return obj[field_name]
            
            # 如果直接匹配失败，尝试忽略大小写和_符号的匹配
            obj_keys = list(obj.keys())
            for field_name in field_names:
                # 标准化字段名（移除_符号，转小写）
                normalized_field = field_name.replace('_', '').lower()
                
                for obj_key in obj_keys:
                    normalized_obj_key = obj_key.replace('_', '').lower()
                    if normalized_field == normalized_obj_key:
                        return obj[obj_key]
            
            return default_value
        except Exception:
            return default_value

    def _get_price_value(self, goods: Dict, field_names: List[str]) -> float:
        """获取价格值（处理分转元）"""
        try:
            price_raw = self._get_field_value(goods, field_names, 0)
            
            # 如果price_raw是None或空字符串，返回0
            if price_raw is None or price_raw == '':
                return 0.0
            
            # 如果是字符串，尝试转换为数字
            if isinstance(price_raw, str):
                # 移除可能的货币符号和空格
                price_raw = price_raw.replace('¥', '').replace('￥', '').replace('$', '').strip()
                if not price_raw:
                    return 0.0
                try:
                    price_raw = float(price_raw)
                except ValueError:
                    return 0.0
            
            # 如果是数字，进行分转元处理
            if isinstance(price_raw, (int, float)):
                if price_raw > 100:  # 假设大于100的是分
                    return float(price_raw) / 100
                else:
                    return float(price_raw)
            
            return 0.0
        except Exception:
            return 0.0

    def _safe_int_convert(self, value) -> int:
        """安全的整数转换"""
        try:
            if value is None:
                return 0
            
            # 如果是字符串，尝试转换为数字
            if isinstance(value, str):
                # 移除可能的非数字字符
                import re
                value = re.sub(r'[^\d]', '', value)
                if not value:
                    return 0
                return int(value)
            
            # 如果是数字，直接转换
            if isinstance(value, (int, float)):
                return int(value)
            
            return 0
        except Exception:
            return 0

    def _get_image_url(self, goods: Dict) -> str:
        """获取图片URL（优先高清图片）"""
        try:
            hd_url = self._get_field_value(goods, ['hdThumbUrl', 'hd_thumb_url', 'hdThumbUrl'], '')
            if hd_url:
                return hd_url
            
            thumb_url = self._get_field_value(goods, ['thumbUrl', 'thumb_url', 'thumbUrl'], '')
            return thumb_url
        except Exception:
            return ''

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

    def _extract_mall_name(self, data: Dict) -> str:
        """提取店铺名称（mallName字段）"""
        try:
            # 尝试从多个可能的位置获取店铺名称
            mall_name_paths = [
                ['store', 'initDataObj', 'goods', 'mallName'],
                ['store', 'initDataObj', 'mall', 'mallName'],
                ['goods', 'mallName'],
                ['mall', 'mallName'],
                ['mallName']
            ]
            
            for path in mall_name_paths:
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
                ['store', 'initDataObj', 'goods', 'clickNotice'],
                ['goods', 'click_notice'],
                ['goods', 'clickNotice'],
                ['click_notice'],
                ['clickNotice']
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

    def _safe_price_convert(self, value) -> float:
        """安全的价格转换（处理分转元）"""
        try:
            if value is None or value == '':
                return 0.0
            
            # 如果是字符串，尝试转换为数字
            if isinstance(value, str):
                # 移除可能的货币符号和空格
                value = value.replace('¥', '').replace('￥', '').replace('$', '').strip()
                if not value:
                    return 0.0
                try:
                    value = float(value)
                except ValueError:
                    return 0.0
            
            # 如果是数字，进行分转元处理
            if isinstance(value, (int, float)):
                if value > 100:  # 假设大于100的是分
                    return float(value) / 100
                else:
                    return float(value)
            
            return 0.0
        except Exception:
            return 0.0

    def _flexible_get(self, data: Dict, keys: List[str], default):
        """灵活获取字段值（支持多个可能的键名）"""
        for key in keys:
            if isinstance(data, dict) and key in data:
                return data[key]
        return default

    def stop_monitoring(self):
        """停止持续监控"""
        try:
            print(f"[持续监控] 正在停止持续监控...")
            self.is_monitoring = False
            
            if self.monitor_thread and self.monitor_thread.is_alive():
                print(f"[持续监控] 等待监控线程退出...")
                self.monitor_thread.join(timeout=10)
                
                if self.monitor_thread.is_alive():
                    print(f"[持续监控] ⚠️ 监控线程未能在10秒内退出")
                else:
                    print(f"[持续监控] ✅ 监控线程已安全退出")
            
        except Exception as e:
            print(f"[持续监控] ❌ 停止监控时发生异常: {e}")
        finally:
            print(f"[持续监控] 监控已停止")

    async def extract_current_page_ui(self) -> bool:
        """UI集成入口点：抓取当前页面数据并保存到CSV"""
        try:
            print(f"[UI] 开始抓取当前页面数据...")
            
            # 连接到浏览器
            from playwright.async_api import async_playwright
            from config_manager import ConfigManager
            
            config_mgr = ConfigManager()
            debug_port = config_mgr.get_debug_port()
            
            async with async_playwright() as playwright:
                browser = await playwright.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
                
                if browser.contexts:
                    context = browser.contexts[0]
                    if context.pages:
                        page = context.pages[0]
                        
                        print(f"[UI] 成功连接到浏览器，开始抓取数据...")
                        
                        # 使用现有的manual_extract_data方法
                        success = await self.manual_extract_data(page)
                        
                        if success:
                            print(f"[UI] ✅ 数据抓取成功")
                            return True
                        else:
                            print(f"[UI] ❌ 数据抓取失败")
                            return False
                    else:
                        print(f"[UI] ❌ 没有可用的页面")
                        return False
                else:
                    print(f"[UI] ❌ 没有可用的浏览器上下文")
                    return False
                    
        except Exception as e:
            print(f"[UI] ❌ 抓取当前页面数据失败: {e}")
            return False

# 全局实例管理
_manual_extractors: Dict[str, ManualDataExtractor] = {}

# 进程状态管理
_process_status_file = "manual_extraction_status.json"

def get_manual_extractor(browser_id: str, ui_log_callback=None) -> ManualDataExtractor:
    """获取指定浏览器的手动抓取器实例"""
    if browser_id not in _manual_extractors:
        _manual_extractors[browser_id] = ManualDataExtractor(browser_id, ui_log_callback)
    return _manual_extractors[browser_id]

async def extract_current_page_ui(browser_id: str) -> bool:
    """UI集成入口点：抓取指定浏览器的当前页面"""
    extractor = get_manual_extractor(browser_id)
    return await extractor.extract_current_page_ui()

def start_manual_mode(browser_id: str, ui_log_callback=None):
    """启动指定浏览器的手动抓取模式"""
    # 检查是否已有进程在运行
    if _is_process_already_running(browser_id):
        print(f"⚠️ 浏览器 {browser_id} 已有手动抓取进程在运行")
        # 🔥 修复：即使检测到已有进程，也尝试重新启动
        print(f"🔄 尝试重新启动浏览器 {browser_id} 的手动抓取进程...")
        
        # 先停止现有进程
        try:
            if browser_id in _manual_extractors:
                _manual_extractors[browser_id].stop_monitoring()
                print(f"✅ 已停止浏览器 {browser_id} 的现有监控")
        except Exception as e:
            print(f"⚠️ 停止现有监控失败: {e}")
        
        # 清除进程状态
        _clear_process_status(browser_id)
    
    # 启动监控
    extractor = get_manual_extractor(browser_id, ui_log_callback)
    extractor.start_manual_mode()
    
    # 记录进程状态
    _set_process_status(browser_id, True)
    print(f"✅ 浏览器 {browser_id} 手动抓取模式已启动")
    return True

def stop_manual_mode(browser_id: str):
    """停止指定浏览器的手动抓取模式"""
    try:
        if browser_id in _manual_extractors:
            _manual_extractors[browser_id].stop_monitoring()
            # 清理进程状态
            _clear_process_status(browser_id)
            print(f"✅ 浏览器 {browser_id} 手动抓取模式已停止")
        else:
            print(f"⚠️ 浏览器 {browser_id} 没有运行中的抓取器")
    except Exception as e:
        print(f"❌ 停止手动抓取模式失败: {e}")

# 进程状态管理函数
def _is_process_already_running(browser_id: str) -> bool:
    """检查是否已有进程在运行"""
    try:
        import os
        import json
        
        if os.path.exists(_process_status_file):
            with open(_process_status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
                return status_data.get(browser_id, False)
        return False
    except Exception as e:
        print(f"⚠️ 检查进程状态失败: {e}")
        return False

def _set_process_status(browser_id: str, running: bool):
    """设置进程状态"""
    try:
        import os
        import json
        
        status_data = {}
        if os.path.exists(_process_status_file):
            with open(_process_status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
        
        status_data[browser_id] = running
        
        with open(_process_status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        print(f"⚠️ 设置进程状态失败: {e}")

def _clear_process_status(browser_id: str):
    """清除进程状态"""
    try:
        import os
        import json
        
        if os.path.exists(_process_status_file):
            with open(_process_status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
            
            if browser_id in status_data:
                del status_data[browser_id]
                
            with open(_process_status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        print(f"⚠️ 清除进程状态失败: {e}")

# UI集成模式 - 已移除命令行测试代码
if __name__ == "__main__":
    print("sd.py 已集成到UI中，请通过UI界面使用手动抓取功能")