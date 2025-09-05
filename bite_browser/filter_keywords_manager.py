#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
过滤关键词管理器
独立管理几万个过滤关键词，避免卡住界面
"""

import os
import json
import re
from typing import List, Set, Dict
from pathlib import Path


class FilterKeywordsManager:
    """过滤关键词管理器 - 支持每个浏览器独立的过滤关键词文件"""

    def __init__(self, browser_id: str = None, keywords_file: str = None):
        """
        初始化过滤关键词管理器

        Args:
            browser_id: 浏览器ID，用于创建独立的过滤关键词文件
            keywords_file: 过滤关键词文件路径，如果为None则根据browser_id自动生成
        """
        if keywords_file:
            # 如果是相对路径，转换为绝对路径
            if not os.path.isabs(keywords_file):
                self.keywords_file = Path(__file__).parent / keywords_file
            else:
                self.keywords_file = Path(keywords_file)
        elif browser_id:
            # 为每个浏览器创建独立的过滤关键词文件
            pdd_automation_dir = Path(__file__).parent.parent / "pdd_automation"
            self.keywords_file = pdd_automation_dir / f"filter_keywords_{browser_id}.txt"
        else:
            # 🔥 从pdd_automation目录读取全局过滤关键词文件
            pdd_automation_dir = Path(__file__).parent.parent / "pdd_automation"
            self.keywords_file = pdd_automation_dir / "filter_keywords_global.txt"

        self.browser_id = browser_id
        self.keywords_cache: Set[str] = set()
        self.compiled_pattern = None  # 编译后的正则表达式
        self.is_loaded = False

        # 确保config目录存在
        self.keywords_file.parent.mkdir(parents=True, exist_ok=True)

        # 不自动加载文件，等待GUI设置
        print(f"过滤关键词管理器初始化完成 - 文件: {self.keywords_file.name}")
    
    def _ensure_keywords_file_exists(self):
        """确保过滤关键词文件存在"""
        if not self.keywords_file.exists():
            self._create_sample_keywords_file()
    
    def _create_sample_keywords_file(self):
        """创建示例过滤关键词文件"""
        try:
            sample_keywords = [
                "# 过滤关键词文件",
                "# 每行一个关键词，支持中文",
                "# 以#开头的行为注释",
                "",
                "# 质量相关",
                "二手",
                "翻新", 
                "破损",
                "瑕疵",
                "残次品",
                "次品",
                "有瑕疵",
                "",
                "# 状态相关", 
                "预售",
                "定制",
                "现货",
                "",
                "# 其他过滤词",
                "假货",
                "仿品",
                "高仿",
                "A货",
                "",
                "# 在此添加更多过滤关键词..."
            ]
            
            with open(self.keywords_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(sample_keywords))
            
            print(f"✅ 创建示例过滤关键词文件: {self.keywords_file}")
            
        except Exception as e:
            print(f"❌ 创建过滤关键词文件失败: {e}")
    
    def load_keywords(self) -> bool:
        """加载过滤关键词到缓存并编译正则表达式"""
        try:
            if not self.keywords_file.exists():
                print(f"⚠️ 过滤关键词文件不存在: {self.keywords_file}")
                return False

            self.keywords_cache.clear()

            with open(self.keywords_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for line in lines:
                line = line.strip()
                # 跳过空行和注释行
                if line and not line.startswith('#'):
                    self.keywords_cache.add(line.lower())  # 转小写便于匹配

            # 编译正则表达式以提高匹配性能
            self._compile_pattern()

            self.is_loaded = True
            print(f"✅ 加载过滤关键词: {len(self.keywords_cache)} 个，已编译正则表达式")
            return True

        except Exception as e:
            print(f"❌ 加载过滤关键词失败: {e}")
            return False

    def _compile_pattern(self):
        """编译正则表达式模式以提高匹配性能"""
        try:
            if not self.keywords_cache:
                self.compiled_pattern = None
                return

            # 对于大量关键词，分组编译以避免正则表达式过长
            keywords_list = list(self.keywords_cache)

            if len(keywords_list) > 10000:
                # 大量关键词时，使用多个正则表达式
                self.compiled_patterns = []
                chunk_size = 5000  # 每组5000个关键词

                for i in range(0, len(keywords_list), chunk_size):
                    chunk = keywords_list[i:i + chunk_size]
                    escaped_keywords = [re.escape(keyword) for keyword in chunk]
                    pattern = '|'.join(escaped_keywords)
                    compiled_pattern = re.compile(pattern, re.IGNORECASE)
                    self.compiled_patterns.append(compiled_pattern)

                self.compiled_pattern = None  # 使用多模式匹配
                print(f"分组正则表达式编译完成：{len(self.compiled_patterns)} 组")
            else:
                # 少量关键词时，使用单个正则表达式
                escaped_keywords = [re.escape(keyword) for keyword in keywords_list]
                pattern = '|'.join(escaped_keywords)
                self.compiled_pattern = re.compile(pattern, re.IGNORECASE)
                self.compiled_patterns = None
                print(f"单一正则表达式编译完成")

        except Exception as e:
            print(f"⚠️ 编译正则表达式失败，使用普通匹配: {e}")
            self.compiled_pattern = None
            self.compiled_patterns = None
    
    def get_keywords_list(self) -> List[str]:
        """获取过滤关键词列表"""
        if not self.is_loaded:
            self.load_keywords()
        
        return sorted(list(self.keywords_cache))
    
    def get_keywords_count(self) -> int:
        """获取过滤关键词数量"""
        if not self.is_loaded:
            self.load_keywords()
        
        return len(self.keywords_cache)
    
    def contains_keyword(self, text: str) -> bool:
        """检查文本是否包含过滤关键词 - 高性能版本"""
        if not self.is_loaded:
            self.load_keywords()

        if not text:
            return False

        # 使用分组正则表达式进行快速匹配
        if hasattr(self, 'compiled_patterns') and self.compiled_patterns:
            for pattern in self.compiled_patterns:
                if pattern.search(text):
                    return True
            return False

        # 使用单一正则表达式进行快速匹配
        if self.compiled_pattern:
            return bool(self.compiled_pattern.search(text))

        # 备选方案：普通字符串匹配
        text_lower = text.lower()
        for keyword in self.keywords_cache:
            if keyword in text_lower:
                return True

        return False
    
    def find_matched_keywords(self, text: str) -> List[str]:
        """查找文本中匹配的过滤关键词 - 高性能版本"""
        if not self.is_loaded:
            self.load_keywords()

        if not text:
            return []

        matched = []

        # 使用编译后的正则表达式查找所有匹配
        if self.compiled_pattern:
            matches = self.compiled_pattern.findall(text)
            return list(set(matches))  # 去重

        # 备选方案：普通字符串匹配
        text_lower = text.lower()
        for keyword in self.keywords_cache:
            if keyword in text_lower:
                matched.append(keyword)

        return matched

    def batch_filter_titles(self, titles: List[str]) -> Dict[str, bool]:
        """批量过滤标题 - 超高性能批量处理"""
        if not self.is_loaded:
            self.load_keywords()

        results = {}

        if not titles:
            return results

        # 使用字符串包含检查的优化版本
        for title in titles:
            if not title:
                results[title] = False
                continue

            title_lower = title.lower()
            found = False

            # 快速字符串包含检查
            for keyword in self.keywords_cache:
                if keyword in title_lower:
                    found = True
                    break

            results[title] = found

        return results

    def filter_valid_titles(self, titles: List[str]) -> List[str]:
        """过滤出不包含过滤关键词的有效标题"""
        if not self.is_loaded:
            self.load_keywords()

        valid_titles = []

        # 使用编译后的正则表达式进行快速过滤
        if self.compiled_pattern:
            for title in titles:
                if title and not self.compiled_pattern.search(title):
                    valid_titles.append(title)
        else:
            # 备选方案：普通过滤
            for title in titles:
                if title and not self.contains_keyword(title):
                    valid_titles.append(title)

        return valid_titles

    def add_keyword(self, keyword: str) -> bool:
        """添加新的过滤关键词"""
        try:
            if not keyword or not keyword.strip():
                return False

            keyword = keyword.strip()

            # 添加到缓存
            self.keywords_cache.add(keyword.lower())

            # 重新编译正则表达式
            self._compile_pattern()

            # 添加到文件
            with open(self.keywords_file, 'a', encoding='utf-8') as f:
                f.write(f'\n{keyword}')

            print(f"✅ 添加过滤关键词: {keyword}")
            return True

        except Exception as e:
            print(f"❌ 添加过滤关键词失败: {e}")
            return False

    def add_keywords_batch(self, keywords: List[str]) -> bool:
        """批量添加过滤关键词 - 高性能版本"""
        try:
            if not keywords:
                return False

            # 过滤有效关键词
            valid_keywords = [kw.strip() for kw in keywords if kw and kw.strip()]
            if not valid_keywords:
                return False

            # 批量添加到缓存
            for keyword in valid_keywords:
                self.keywords_cache.add(keyword.lower())

            # 只编译一次正则表达式
            self._compile_pattern()

            # 保存到文件
            self._save_keywords_to_file()

            print(f"✅ 批量添加过滤关键词: {len(valid_keywords)} 个")
            return True

        except Exception as e:
            print(f"❌ 批量添加过滤关键词失败: {e}")
            return False
    
    def remove_keyword(self, keyword: str) -> bool:
        """移除过滤关键词"""
        try:
            if not keyword:
                return False

            keyword_lower = keyword.lower()

            if keyword_lower not in self.keywords_cache:
                return False

            # 从缓存移除
            self.keywords_cache.discard(keyword_lower)

            # 重新编译正则表达式
            self._compile_pattern()

            # 重写文件
            self._save_keywords_to_file()

            print(f"✅ 移除过滤关键词: {keyword}")
            return True

        except Exception as e:
            print(f"❌ 移除过滤关键词失败: {e}")
            return False
    
    def _save_keywords_to_file(self):
        """保存关键词到文件"""
        try:
            keywords_list = sorted(list(self.keywords_cache))
            
            content = [
                "# 过滤关键词文件",
                "# 每行一个关键词，支持中文",
                "# 以#开头的行为注释",
                ""
            ]
            
            content.extend(keywords_list)
            
            with open(self.keywords_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
                
        except Exception as e:
            print(f"❌ 保存过滤关键词文件失败: {e}")
            raise
    
    def clear_keywords(self) -> bool:
        """清空所有过滤关键词"""
        try:
            self.keywords_cache.clear()
            self._create_sample_keywords_file()
            print("✅ 过滤关键词已清空")
            return True
            
        except Exception as e:
            print(f"❌ 清空过滤关键词失败: {e}")
            return False
    
    def import_keywords_from_file(self, file_path: str) -> bool:
        """从文件导入过滤关键词"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ 导入文件不存在: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            imported_count = 0
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    self.keywords_cache.add(line.lower())
                    imported_count += 1
            
            # 保存到文件
            self._save_keywords_to_file()
            
            print(f"✅ 导入过滤关键词: {imported_count} 个")
            return True
            
        except Exception as e:
            print(f"❌ 导入过滤关键词失败: {e}")
            return False
    
    def export_keywords_to_file(self, file_path: str) -> bool:
        """导出过滤关键词到文件"""
        try:
            if not self.is_loaded:
                self.load_keywords()
            
            keywords_list = sorted(list(self.keywords_cache))
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(keywords_list))
            
            print(f"✅ 导出过滤关键词: {len(keywords_list)} 个到 {file_path}")
            return True
            
        except Exception as e:
            print(f"❌ 导出过滤关键词失败: {e}")
            return False
    
    def get_file_path(self) -> str:
        """获取过滤关键词文件路径"""
        return str(self.keywords_file.absolute())
    
    def reload_keywords(self) -> bool:
        """重新加载过滤关键词"""
        self.is_loaded = False
        return self.load_keywords()
