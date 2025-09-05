#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
搜索结果汇总管理器
负责收集各个浏览器的搜索结果并汇总显示
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path


class SearchSummaryManager:
    """搜索结果汇总管理器"""
    
    def __init__(self):
        """初始化汇总管理器"""
        self.scripts_dir = Path("scripts")
        self.summary_file = Path("search_summary.json")
        
        print("搜索结果汇总管理器初始化完成")
    
    def collect_all_search_results(self) -> Optional[Dict[str, Any]]:
        """收集所有浏览器的搜索结果"""
        try:
            print("开始汇总搜索结果...")
            
            all_results = {
                'summary_time': datetime.now().isoformat(),
                'total_browsers': 0,
                'total_keywords_searched': 0,
                'total_products_collected': 0,
                'browser_results': {},
                'keyword_summary': {},
                'detailed_results': []
            }
            
            # 扫描所有浏览器文件夹
            if not self.scripts_dir.exists():
                print("⚠️ scripts目录不存在")
                return all_results
            
            for browser_folder in self.scripts_dir.iterdir():
                if browser_folder.is_dir() and browser_folder.name.startswith('browser_'):
                    browser_result = self._collect_browser_result(browser_folder)
                    
                    if browser_result:
                        browser_id = browser_result['browser_id']
                        all_results['browser_results'][browser_id] = browser_result
                        all_results['total_browsers'] += 1
                        
                        # 汇总关键词信息
                        self._merge_keyword_results(all_results, browser_result)
                        
                        # 添加详细结果
                        all_results['detailed_results'].append(browser_result)
            
            # 计算总计
            all_results['total_keywords_searched'] = len(all_results['keyword_summary'])
            
            # 保存汇总结果
            with open(self.summary_file, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            
            print(f"✅ 汇总完成:")
            print(f"   浏览器数量: {all_results['total_browsers']}")
            print(f"   搜索关键词: {all_results['total_keywords_searched']}")
            print(f"   采集商品: {all_results['total_products_collected']}")
            
            return all_results
            
        except Exception as e:
            print(f"❌ 汇总搜索结果失败: {e}")
            return None
    
    def _collect_browser_result(self, browser_folder: Path) -> Optional[Dict[str, Any]]:
        """收集单个浏览器的结果"""
        try:
            browser_id_suffix = browser_folder.name[-4:]  # 获取后4位
            
            # 查找搜索状态文件
            status_files = list(browser_folder.glob(f'searched_keywords_{browser_id_suffix}.json'))
            
            if not status_files:
                print(f"⚠️ 未找到搜索状态文件: {browser_folder.name}")
                return None
            
            status_file = status_files[0]
            
            with open(status_file, 'r', encoding='utf-8') as f:
                browser_data = json.load(f)
            
            # 标准化数据格式
            result = {
                'browser_id': browser_data.get('browser_id', ''),
                'browser_folder': browser_folder.name,
                'last_updated': browser_data.get('last_updated', ''),
                'searched_keywords': browser_data.get('searched_keywords', []),
                'keyword_details': browser_data.get('keyword_details', []),
                'total_keywords': len(browser_data.get('searched_keywords', [])),
                'total_collected': 0
            }
            
            # 计算总采集数量
            for detail in result['keyword_details']:
                result['total_collected'] += detail.get('collected_count', 0)
            
            print(f"   {browser_folder.name}: {result['total_keywords']}个关键词, {result['total_collected']}个商品")
            
            return result
            
        except Exception as e:
            print(f"⚠️ 读取浏览器结果失败 {browser_folder.name}: {e}")
            return None
    
    def _merge_keyword_results(self, all_results: Dict[str, Any], browser_result: Dict[str, Any]):
        """合并关键词结果到总汇总中"""
        try:
            for keyword_detail in browser_result.get('keyword_details', []):
                keyword = keyword_detail['keyword']
                collected_count = keyword_detail.get('collected_count', 0)
                completed_time = keyword_detail.get('completed_time', '')
                browser_id = browser_result['browser_id']
                
                if keyword not in all_results['keyword_summary']:
                    all_results['keyword_summary'][keyword] = {
                        'total_collected': 0,
                        'browsers': [],
                        'browser_details': {},
                        'first_completed': completed_time,
                        'last_completed': completed_time
                    }
                
                keyword_info = all_results['keyword_summary'][keyword]
                keyword_info['total_collected'] += collected_count
                keyword_info['browsers'].append(browser_id[-4:])
                keyword_info['browser_details'][browser_id[-4:]] = {
                    'collected_count': collected_count,
                    'completed_time': completed_time
                }
                
                # 更新时间范围
                if completed_time < keyword_info['first_completed']:
                    keyword_info['first_completed'] = completed_time
                if completed_time > keyword_info['last_completed']:
                    keyword_info['last_completed'] = completed_time
                
                # 累加到总数
                all_results['total_products_collected'] += collected_count
                
        except Exception as e:
            print(f"⚠️ 合并关键词结果失败: {e}")
    
    def get_summary_for_ui(self) -> Optional[Dict[str, Any]]:
        """获取用于UI显示的汇总数据"""
        try:
            if not self.summary_file.exists():
                return None
            
            with open(self.summary_file, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except Exception as e:
            print(f"❌ 读取汇总数据失败: {e}")
            return None
    
    def format_keyword_display_text(self, original_keywords: List[str]) -> str:
        """格式化关键词显示文本，添加已搜索标记"""
        try:
            summary_data = self.get_summary_for_ui()
            if not summary_data:
                return '\n'.join(original_keywords)
            
            keyword_summary = summary_data.get('keyword_summary', {})
            formatted_lines = []
            
            for keyword in original_keywords:
                clean_keyword = keyword.replace(' ---已搜索', '').strip()
                
                if clean_keyword in keyword_summary:
                    keyword_info = keyword_summary[clean_keyword]
                    total_collected = keyword_info['total_collected']
                    browsers = ', '.join(keyword_info['browsers'])
                    formatted_lines.append(f"{clean_keyword} ---已搜索 ({total_collected}个商品, 浏览器:{browsers})")
                else:
                    formatted_lines.append(clean_keyword)
            
            return '\n'.join(formatted_lines)
            
        except Exception as e:
            print(f"❌ 格式化关键词显示失败: {e}")
            return '\n'.join(original_keywords)
    
    def generate_summary_report(self) -> str:
        """生成汇总报告文本"""
        try:
            summary_data = self.get_summary_for_ui()
            if not summary_data:
                return "没有找到汇总数据"
            
            report_lines = [
                "📊 拼多多采集结果汇总报告",
                "=" * 50,
                f"汇总时间: {summary_data['summary_time']}",
                f"浏览器数量: {summary_data['total_browsers']}",
                f"搜索关键词数: {summary_data['total_keywords_searched']}",
                f"采集商品总数: {summary_data['total_products_collected']}",
                "",
                "🔍 关键词详情:",
                "-" * 30
            ]
            
            # 按采集数量排序
            keyword_items = list(summary_data['keyword_summary'].items())
            keyword_items.sort(key=lambda x: x[1]['total_collected'], reverse=True)
            
            for keyword, info in keyword_items:
                browsers_info = []
                for browser_id, details in info['browser_details'].items():
                    browsers_info.append(f"{browser_id}({details['collected_count']}个)")
                
                browsers_text = ', '.join(browsers_info)
                report_lines.append(f"• {keyword}: {info['total_collected']}个商品 [{browsers_text}]")
            
            # 浏览器详情
            if summary_data['detailed_results']:
                report_lines.extend([
                    "",
                    "📱 浏览器详情:",
                    "-" * 30
                ])
                
                for browser_result in summary_data['detailed_results']:
                    browser_id = browser_result['browser_id'][-4:]
                    total_keywords = browser_result['total_keywords']
                    total_collected = browser_result['total_collected']
                    last_updated = browser_result.get('last_updated', '未知')
                    
                    report_lines.append(f"• 浏览器 {browser_id}: {total_keywords}个关键词, {total_collected}个商品")
                    report_lines.append(f"  最后更新: {last_updated}")
            
            return '\n'.join(report_lines)
            
        except Exception as e:
            print(f"❌ 生成汇总报告失败: {e}")
            return f"生成报告失败: {e}"
    
    def export_summary_to_file(self, export_path: str = None) -> bool:
        """导出汇总报告到文件"""
        try:
            if not export_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_path = f"搜索汇总报告_{timestamp}.txt"
            
            report_content = self.generate_summary_report()
            
            with open(export_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            
            print(f"✅ 汇总报告已导出: {export_path}")
            return True
            
        except Exception as e:
            print(f"❌ 导出汇总报告失败: {e}")
            return False
    
    def clear_search_records(self, browser_ids: List[str] = None) -> bool:
        """清理搜索记录"""
        try:
            print("开始清理搜索记录...")
            
            cleared_count = 0
            
            if not self.scripts_dir.exists():
                print("⚠️ scripts目录不存在")
                return True
            
            for browser_folder in self.scripts_dir.iterdir():
                if browser_folder.is_dir() and browser_folder.name.startswith('browser_'):
                    # 如果指定了browser_ids，只清理指定的
                    if browser_ids:
                        browser_id_suffix = browser_folder.name[-4:]
                        if not any(bid.endswith(browser_id_suffix) for bid in browser_ids):
                            continue
                    
                    # 清理搜索状态文件
                    status_files = list(browser_folder.glob('searched_keywords_*.json'))
                    for status_file in status_files:
                        status_file.unlink()
                        cleared_count += 1
                        print(f"   已清理: {status_file.name}")
            
            # 清理汇总文件
            if self.summary_file.exists():
                self.summary_file.unlink()
                print(f"   已清理: {self.summary_file.name}")
            
            print(f"✅ 清理完成: {cleared_count} 个搜索记录文件")
            return True
            
        except Exception as e:
            print(f"❌ 清理搜索记录失败: {e}")
            return False
    
    def get_browser_search_progress(self, browser_id: str) -> Dict[str, Any]:
        """获取单个浏览器的搜索进度"""
        try:
            browser_folder = self.scripts_dir / f"browser_{browser_id[-4:]}"
            if not browser_folder.exists():
                return {'total': 0, 'completed': 0, 'progress': 0}
            
            # 读取配置文件获取总关键词数
            config_files = list(browser_folder.glob('config_*.json'))
            total_keywords = 0
            if config_files:
                with open(config_files[0], 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    total_keywords = len(config.get('search_keywords', []))
            
            # 读取搜索状态文件获取已完成数
            status_files = list(browser_folder.glob('searched_keywords_*.json'))
            completed_keywords = 0
            if status_files:
                with open(status_files[0], 'r', encoding='utf-8') as f:
                    status_data = json.load(f)
                    completed_keywords = len(status_data.get('searched_keywords', []))
            
            progress = (completed_keywords / total_keywords * 100) if total_keywords > 0 else 0
            
            return {
                'total': total_keywords,
                'completed': completed_keywords,
                'remaining': total_keywords - completed_keywords,
                'progress': progress
            }
            
        except Exception as e:
            print(f"❌ 获取浏览器搜索进度失败: {e}")
            return {'total': 0, 'completed': 0, 'progress': 0}
