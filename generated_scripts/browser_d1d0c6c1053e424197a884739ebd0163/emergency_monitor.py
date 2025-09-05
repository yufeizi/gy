#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emergency_monitor.py - 紧急监控模块
功能：
1. 检测滑块验证（页面标题为"安全验证"时）
2. 与主UI通信（弹窗警告：请人工处理）
3. 暂停该浏览器所有脚本运行
4. 等待人工处理后恢复
"""

import asyncio
import json
import time
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import Page
from typing import Dict, List, Optional, Tuple


class EmergencyMonitor:
    """紧急监控器"""
    
    def __init__(self, page: Page, browser_id: str):
        """
        初始化紧急监控器
        
        Args:
            page: Playwright页面对象
            browser_id: 浏览器ID
        """
        self.page = page
        self.browser_id = browser_id
        
        # 设置路径
        self._setup_paths()
        
        # 紧急状态
        self.current_emergency = None
        self.page_state = "unknown"
        
        print(f"🚨 紧急监控器已初始化 (浏览器: {browser_id})")
    
    def _setup_paths(self):
        """设置文件路径"""
        try:
            # 获取当前文件所在目录
            current_file_dir = Path(__file__).parent
            
            # 如果在浏览器目录中运行，向上找到项目根目录
            if "browser_" in str(current_file_dir):
                project_root = current_file_dir
                while project_root.name != "ccccc" and project_root.parent != project_root:
                    project_root = project_root.parent
                
                self.logs_dir = project_root / "logs"
                self.config_dir = project_root / "config"
            else:
                # 在主目录中运行
                self.logs_dir = current_file_dir.parent / "logs"
                self.config_dir = current_file_dir.parent / "config"
            
            # 确保目录存在
            self.logs_dir.mkdir(exist_ok=True)
            self.config_dir.mkdir(exist_ok=True)
            
            # 紧急相关文件
            self.emergency_alerts_file = self.logs_dir / "emergency_alerts.json"
            self.emergency_status_file = self.logs_dir / "emergency_status.json"
            self.sound_alerts_file = self.logs_dir / "sound_alerts.json"
            self.ui_commands_file = self.config_dir / "ui_commands.json"
            
        except Exception as e:
            print(f"❌ 设置路径失败: {e}")
            # 使用当前目录作为备用
            self.logs_dir = Path("logs")
            self.config_dir = Path("config")
            self.emergency_alerts_file = self.logs_dir / "emergency_alerts.json"
            self.emergency_status_file = self.logs_dir / "emergency_status.json"
            self.sound_alerts_file = self.logs_dir / "sound_alerts.json"
            self.ui_commands_file = self.config_dir / "ui_commands.json"
    
    async def monitor_and_handle(self) -> bool:
        """
        监控并处理紧急状况
        
        Returns:
            bool: True表示可以继续，False表示需要暂停
        """
        try:
            # 1. 检测页面状态
            page_state = await self._detect_page_state()
            self.page_state = page_state
            
            # 2. 检测异常情况
            emergency = await self._detect_emergency()
            
            # 3. 处理异常
            if emergency:
                await self._handle_emergency(emergency, page_state)
                return False  # 需要暂停
            
            return True  # 可以继续
            
        except Exception as e:
            print(f"❌ 紧急监控失败: {e}")
            return True  # 出错时允许继续
    
    async def _detect_page_state(self) -> str:
        """🔥 优化：使用URL精准检测页面状态"""
        try:
            # 1. 🔥 优先使用URL判断页面类型（更准确、更快速）
            current_url = self.page.url
            
            # 检测详情页URL模式
            detail_url_patterns = [
                '/goods.html',           # 拼多多商品详情页
                '/detail/',             # 详情页路径
                '/goods/',              # 商品页路径
                '/item/',               # 商品条目页
                'goods_id=',            # URL参数包含商品ID
                'item_id=',             # URL参数包含商品ID
                '/product/',            # 产品详情页
            ]
            
            for pattern in detail_url_patterns:
                if pattern in current_url.lower():
                    print(f"🔍 URL检测: 详情页 - {pattern} in {current_url}")
                    return "detail_page"
            
            # 检测搜索页URL模式
            search_url_patterns = [
                '/search_result.html',  # 拼多多搜索结果页
                '/search/',             # 搜索页路径
                'search.html',          # 搜索页面
                'q=',                   # 搜索查询参数
                'keyword=',             # 关键词参数
                'query=',               # 查询参数
                '/list/',               # 列表页面
            ]
            
            for pattern in search_url_patterns:
                if pattern in current_url.lower():
                    print(f"🔍 URL检测: 搜索页 - {pattern} in {current_url}")
                    return "search_page"
            
            # 2. 🔥 备选方案：如果URL无法判断，使用优化后的元素检测
            print(f"🔍 URL无法判断页面类型，使用备选检测方案: {current_url}")
            
            # 检测是否在白屏或错误页（优先级最高）
            if await self._detect_white_screen():
                return "white_screen"
            
            # 快速检测详情页（只检查最关键的元素）
            detail_selectors = [
                'text=商品详情',
                'text=立即购买',
                '[class*="goods-detail"]',
                '[class*="product-info"]'
            ]
            
            for selector in detail_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        return "detail_page"
                except:
                    continue
            
            # 快速检测搜索页（只检查最关键的元素）
            search_selectors = [
                'input[placeholder*="搜索"]',
                '[class*="search-result"]',
                'text=筛选',
                '[class*="goods-list"]'
            ]
            
            for selector in search_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        return "search_page"
                except:
                    continue
            
            print(f"⚠️ 无法识别页面类型: {current_url}")
            return "unknown"
            
        except Exception as e:
            print(f"❌ 检测页面状态失败: {e}")
            return "unknown"
    
    async def _detect_emergency(self) -> Optional[Dict]:
        """🔥 简化：只检测滑块验证"""
        try:
            # 只检测滑块验证，使用页面标题检测
            slider_detected = await self._detect_slider_verification_by_title()
            if slider_detected:
                return {
                    'type': 'slider_verification', 
                    'message': '请人工处理',
                    'severity': 'high',
                    'browser_id': self.browser_id
                }
            
            return None  # 没有检测到滑块验证
            
        except Exception as e:
            print(f"❌ 检测滑块验证失败: {e}")
            return None
    
    async def _detect_slider_verification_by_title(self) -> bool:
        """🔥 通过页面标题检测滑块验证"""
        try:
            # 获取页面标题
            title = await self.page.title()
            
            # 检测滑块验证的标题
            if title and "安全验证" in title:
                print(f"🚨 检测到滑块验证页面: {title}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ 检测滑块验证标题失败: {e}")
            return False
    
    async def _detect_slider_verification(self) -> bool:
        """检测滑块验证"""
        try:
            slider_selectors = [
                'text=安全验证',
                'text=滑动验证',
                'text=点击下方',
                'text=拖动滑块',
                'text=验证码',
                '[class*="slider"]',
                '[class*="captcha"]',
                '[class*="verify"]',
                '.slider-verify',
                '#slider-verify',
                '.captcha',
                '#captcha'
            ]
            
            for selector in slider_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f"🚨 检测到滑块验证: {selector}")
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"❌ 检测滑块验证失败: {e}")
            return False
    
    async def _detect_white_screen(self) -> bool:
        """检测白屏"""
        try:
            # 检查页面是否基本为空
            body_content = await self.page.evaluate("""
                () => {
                    const body = document.body;
                    if (!body) return { isEmpty: true, reason: 'no_body' };
                    
                    const textContent = body.textContent || '';
                    const innerHTML = body.innerHTML || '';
                    
                    // 检查是否几乎没有内容
                    if (textContent.trim().length < 50 && innerHTML.length < 200) {
                        return { isEmpty: true, reason: 'minimal_content' };
                    }
                    
                    // 检查是否有主要的拼多多元素
                    const hasLogo = document.querySelector('[alt*="拼多多"]') || 
                                   document.querySelector('[class*="logo"]') ||
                                   document.querySelector('img[src*="logo"]');
                    
                    const hasSearch = document.querySelector('input[placeholder*="搜索"]') ||
                                     document.querySelector('[class*="search"]');
                    
                    if (!hasLogo && !hasSearch) {
                        return { isEmpty: true, reason: 'missing_key_elements' };
                    }
                    
                    return { isEmpty: false, reason: 'normal' };
                }
            """)
            
            if body_content.get('isEmpty', False):
                reason = body_content.get('reason', 'unknown')
                print(f"🚨 检测到白屏: {reason}")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ 检测白屏失败: {e}")
            return False
    
    async def _detect_network_error(self) -> Optional[str]:
        """检测网络错误"""
        try:
            error_selectors = [
                'text=网络错误',
                'text=页面不存在',
                'text=服务器错误',
                'text=访问被拒绝',
                'text=网络繁忙',
                'text=连接超时',
                '[class*="error"]',
                '[class*="404"]',
                '[class*="500"]',
                '[class*="timeout"]'
            ]
            
            for selector in error_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        text = await element.text_content()
                        return f"页面错误: {text[:50]}"
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"❌ 检测网络错误失败: {e}")
            return None
    
    async def _detect_other_errors(self) -> Optional[str]:
        """检测其他错误"""
        try:
            # 检测页面加载状态
            page_state = await self.page.evaluate("""
                () => {
                    if (document.readyState !== 'complete') {
                        return `页面未完全加载: ${document.readyState}`;
                    }
                    
                    // 检查是否有错误提示
                    const errorElements = document.querySelectorAll('[class*="error"], [class*="fail"], [class*="warning"]');
                    for (const elem of errorElements) {
                        if (elem.offsetWidth > 0 && elem.offsetHeight > 0) {
                            const text = elem.textContent || '';
                            if (text.trim()) {
                                return `页面错误: ${text.trim()[:50]}`;
                            }
                        }
                    }
                    
                    return null;
                }
            """)
            
            return page_state
            
        except Exception as e:
            print(f"❌ 检测其他错误失败: {e}")
            return None
    
    async def _handle_emergency(self, emergency: Dict, page_state: str):
        """处理紧急状况"""
        try:
            print(f"🚨 处理紧急状况: {emergency['message']}")
            
            # 1. 保存紧急状态
            self._save_emergency_status(emergency)
            
            # 2. 发送弹窗和声音警报
            self._send_ui_alerts(emergency)
            
            # 3. 根据页面状态处理
            if page_state == "detail_page":
                print("📱 当前在详情页，尝试返回搜索页...")
                if await self._return_to_search_page():
                    print("✅ 已返回搜索页")
                else:
                    print("❌ 返回搜索页失败")
            
            # 4. 暂停程序等待恢复
            print("⏸️ 程序已暂停，等待人工处理...")
            await self._wait_for_recovery()
            
        except Exception as e:
            print(f"❌ 处理紧急状况失败: {e}")
    
    def _save_emergency_status(self, emergency: Dict):
        """保存紧急状态"""
        try:
            status_data = {
                'browser_id': self.browser_id,
                'emergency_type': emergency['type'],
                'message': emergency['message'],
                'severity': emergency['severity'],
                'page_state': self.page_state,
                'detected_time': datetime.now().isoformat(),
                'timestamp': time.time()
            }
            
            # 保存到紧急状态文件
            with open(self.emergency_status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
            
            # 添加到紧急警报列表
            alerts = []
            if self.emergency_alerts_file.exists():
                with open(self.emergency_alerts_file, 'r', encoding='utf-8') as f:
                    alerts = json.load(f)
            
            alerts.append(status_data)
            
            # 只保留最近10条警报
            if len(alerts) > 10:
                alerts = alerts[-10:]
            
            with open(self.emergency_alerts_file, 'w', encoding='utf-8') as f:
                json.dump(alerts, f, ensure_ascii=False, indent=2)
            
            print(f"💾 紧急状态已保存: {emergency['type']}")
            
        except Exception as e:
            print(f"❌ 保存紧急状态失败: {e}")
    
    def _send_ui_alerts(self, emergency: Dict):
        """发送UI警报（弹窗和声音）"""
        try:
            # 1. 弹窗消息
            popup_data = {
                'type': 'emergency',
                'title': '🚨 紧急状况警报',
                'message': emergency['message'],
                'details': f"浏览器: {self.browser_id}\n页面状态: {self.page_state}\n严重程度: {emergency['severity']}",
                'timestamp': datetime.now().isoformat(),
                'browser_id': self.browser_id
            }
            
            # 写入弹窗文件（主UI会读取并显示）
            popup_file = self.logs_dir / "popup_messages.json"
            popups = []
            if popup_file.exists():
                with open(popup_file, 'r', encoding='utf-8') as f:
                    popups = json.load(f)
            
            popups.append(popup_data)
            
            # 只保留最近5条弹窗
            if len(popups) > 5:
                popups = popups[-5:]
            
            with open(popup_file, 'w', encoding='utf-8') as f:
                json.dump(popups, f, ensure_ascii=False, indent=2)
            
            # 2. 声音警报
            sound_data = {
                'type': 'emergency',
                'sound': 'alert.wav',  # 主UI会播放这个声音文件
                'message': emergency['message'],
                'timestamp': datetime.now().isoformat(),
                'browser_id': self.browser_id
            }
            
            with open(self.sound_alerts_file, 'w', encoding='utf-8') as f:
                json.dump(sound_data, f, ensure_ascii=False, indent=2)
            
            print("📢 UI警报已发送（弹窗+声音）")
            
        except Exception as e:
            print(f"❌ 发送UI警报失败: {e}")
    
    async def _return_to_search_page(self) -> bool:
        """从详情页返回搜索页"""
        try:
            # 尝试点击返回按钮
            back_selectors = [
                'text=返回',
                'text=←',
                'text=后退',
                '[class*="back"]',
                '[class*="return"]',
                '.back-button',
                '#back-button'
            ]
            
            for selector in back_selectors:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        print(f"✅ 点击返回按钮: {selector}")
                        
                        # 等待页面加载
                        await asyncio.sleep(2)
                        
                        # 验证是否返回搜索页
                        if await self._detect_page_state() == "search_page":
                            return True
                        else:
                            print("⚠️ 点击返回后未到达搜索页")
                            break
                except:
                    continue
            
            # 如果点击返回失败，尝试浏览器后退
            try:
                await self.page.go_back()
                print("✅ 使用浏览器后退")
                await asyncio.sleep(2)
                
                if await self._detect_page_state() == "search_page":
                    return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"❌ 返回搜索页失败: {e}")
            return False
    
    async def _wait_for_recovery(self):
        """简化：不再循环等待，直接退出"""
        try:
            print("🚨 滑块验证检测到，脚本即将停止")
            print("⏸️ 程序已暂停，请人工处理滑块验证")
            # 不再循环检测，直接退出让脚本停止
            
        except Exception as e:
            print(f"❌ 处理停止失败: {e}")
    
    async def _check_resume_signal(self) -> bool:
        """检查是否收到继续信号"""
        try:
            if not self.ui_commands_file.exists():
                return False
            
            with open(self.ui_commands_file, 'r', encoding='utf-8') as f:
                command = json.load(f)
            
            if command.get('action') == 'continue' and command.get('browser_id') == self.browser_id:
                # 清除命令
                self.ui_commands_file.unlink()
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ 检查恢复信号失败: {e}")
            return False
    
    def _clear_emergency_status(self):
        """清除紧急状态"""
        try:
            if self.emergency_status_file.exists():
                self.emergency_status_file.unlink()
            
            if self.sound_alerts_file.exists():
                self.sound_alerts_file.unlink()
            
            print("✅ 紧急状态已清除")
            
        except Exception as e:
            print(f"❌ 清除紧急状态失败: {e}")


# 全局监控器实例
_emergency_monitors = {}


def get_emergency_monitor(page: Page, browser_id: str) -> EmergencyMonitor:
    """获取紧急监控器实例"""
    global _emergency_monitors
    
    key = f"{browser_id}_{id(page)}"
    if key not in _emergency_monitors:
        _emergency_monitors[key] = EmergencyMonitor(page, browser_id)
    
    return _emergency_monitors[key]


async def monitor_emergency(page: Page, browser_id: str) -> bool:
    """监控紧急状况（全局接口）"""
    monitor = get_emergency_monitor(page, browser_id)
    return await monitor.monitor_and_handle()


if __name__ == "__main__":
    print("🧪 测试紧急监控模块")
    print("✅ 模块加载成功") 