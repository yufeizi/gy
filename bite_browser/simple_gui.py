"""
简化的比特浏览器管理界面
基于官方API实现
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog, scrolledtext
import threading
import time
import json
import os
import asyncio
import sys
import psutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path
from bitbrowser_api import BitBrowserAPI
from log_manager import get_logger
from account_manager import AccountManager
from script_generator import ScriptGenerator
from search_summary_manager import SearchSummaryManager
from security_manager import security_manager


class SingleInstanceChecker:
    """单实例检查器"""

    def __init__(self, app_name="BitBrowserGUI"):
        self.app_name = app_name
        self.lock_file = f"{app_name}.lock"
        self.pid_file = f"{app_name}.pid"

    def is_already_running(self):
        """检查是否已经有实例在运行"""
        try:
            # 检查PID文件是否存在
            if os.path.exists(self.pid_file):
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())

                # 检查进程是否还在运行
                if psutil.pid_exists(pid):
                    try:
                        process = psutil.Process(pid)
                        # 检查进程名是否匹配
                        if 'python' in process.name().lower():
                            return True
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                # 如果进程不存在，删除旧的PID文件
                os.remove(self.pid_file)

            return False

        except Exception:
            return False

    def create_lock(self):
        """创建锁文件"""
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(os.getpid()))
            return True
        except Exception:
            return False

    def remove_lock(self):
        """移除锁文件"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception:
            pass


class SimpleBitBrowserGUI:
    """简化的比特浏览器管理界面"""
    
    def __init__(self):
        """初始化界面"""
        # 单实例检查
        self.instance_checker = SingleInstanceChecker("BitBrowserGUI")
        if self.instance_checker.is_already_running():
            messagebox.showerror("错误", "程序已经在运行中！\n请不要重复打开程序。")
            sys.exit(1)

        # 创建锁文件
        if not self.instance_checker.create_lock():
            messagebox.showerror("错误", "无法创建程序锁文件！")
            sys.exit(1)

        self.logger = get_logger()
        self.api = None
        self.bitbrowser_api = None  # [HOT] 添加bitbrowser_api属性，与api指向同一实例
        self.browsers: Dict[str, Dict] = {}  # 存储浏览器信息
        # [HOT] 动态获取配置文件路径，支持独立部署
        self.config_file = str(Path(__file__).parent.parent / "pdd_automation" / "config_api.json")
        self.account_manager = AccountManager()  # 多账号管理器

        # 脚本生成和汇总管理器
        self.script_generator = ScriptGenerator(self)
        self.summary_manager = SearchSummaryManager()

        # 过滤关键词管理器 - 动态获取过滤关键词文件路径
        from filter_keywords_manager import FilterKeywordsManager
        # [HOT] 修复硬编码：使用全局过滤关键词文件
        filter_keywords_file = str(Path(__file__).parent.parent / "pdd_automation" / "filter_keywords_global.txt")
        self.filter_manager = FilterKeywordsManager(keywords_file=filter_keywords_file)

        # 全局配置
        self.global_search_keywords = []
        self.global_filter_keywords = []
        self.global_wait_time = 3
        self.global_page_count = 5
        self.global_target_count = 100
        self.global_search_page_wait = 2  # 搜索页面等待时间

        # 过滤设置
        self.global_filter_settings = {
            "filter_brand_store": False,
            "filter_flagship_store": False,
            "filter_presale": False,
            "sales_min": "",
            "sales_max": "",
            "price_min": "",
            "price_max": ""
        }
        # 排序设置 
        self.global_sort_method = "综合排序"  # 默认综合排序

        # 发货时间设置
        self.global_shipping_time = "48小时发货"  # 默认48小时发货

        # 定时运行控制设置
        self.global_run_minutes = 0  # 默认运行0分钟(不开启)
        self.global_pause_minutes = 0  # 默认暂停0分钟(不开启)
        self.global_memory_threshold = 200  # 默认内存阈值200MB

        # 已搜索关键词记录
        self.searched_keywords = set()

        # [HOT] 数据传输管理器
        self.data_transfer_manager = None

        # [HOT] 手动抓取进程管理器
        self.manual_extraction_processes = {}

        # [HOT] 记录软件启动时间（用于计算当次运行时长）
        from datetime import datetime
        self.software_start_time = datetime.now()

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("鱼非子DD解析V2.5 - 比特浏览器多实例管理")
        self.root.geometry("898x709")
        self.root.resizable(False, False)  # 禁止调整窗口大小
        
        # [HOT] 窗口居中显示
        self.center_window()
        
        self.create_widgets()
        self.logger.info("比特浏览器管理界面初始化完成")

        # 设置窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 在界面创建完成后加载配置
        self.root.after(100, self.load_config)
        # 加载过滤关键词到界面
        self.root.after(200, self.load_filter_keywords_to_gui)
        # 启动实时同步机制
        self.root.after(300, self.setup_real_time_sync)
        # [HOT] 初始化数据传输管理器
        self.root.after(400, self.init_data_transfer_manager)
        # 🚨 启动紧急警报监听器 (已停用 - 改用jiex.py直接通知)
        # self.root.after(450, self.start_emergency_alert_monitor)
        # [HOT] 启动简化的弹窗检查 (已停用 - 改用回调函数直接通知)
        # self.root.after(500, self.check_simple_popup_alerts)
        # 同步配置到UI界面（最后执行，确保所有UI控件都已创建）
        self.root.after(500, self.sync_config_to_ui)
        # [HOT] 新增：启动轻量级定时刷新（解析数量和状态）
        self.root.after(1000, self.start_auto_refresh)
        
        # [HOT] 新增：JSON文件缓存，减少重复读取
        self._json_cache = {}  # {file_path: {'mtime': timestamp, 'data': content}}

    def load_config(self):
        """加载保存的配置"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                    # 加载API Token
                    saved_token = config.get('api_token', '')
                    if saved_token and hasattr(self, 'api_token_var'):
                        self.api_token_var.set(saved_token)
                        self.logger.info("已加载保存的API Token")

                    # 加载解析设置
                    if 'parse_settings' in config:
                        settings = config['parse_settings']
                        self.global_wait_time = settings.get('wait_time', 3)
                        self.global_page_count = settings.get('page_count', 5)
                        self.global_target_count = settings.get('target_count', 100)
                        self.global_search_page_wait = settings.get('search_page_wait', 2)

                        # 加载过滤设置
                        if 'filter_settings' in settings:
                            self.global_filter_settings.update(settings['filter_settings'])

                        # 加载排序设置
                        self.global_sort_method = settings.get('sort_method', '综合排序')
                        
                        # 加载发货时间设置
                        require_24h = settings.get('filter_settings', {}).get('require_24h_shipping', False)
                        self.global_shipping_time = "24小时发货" if require_24h else "48小时发货"
                        
                        # 加载定时运行控制设置
                        self.global_run_minutes = settings.get('run_minutes', 0)
                        self.global_pause_minutes = settings.get('pause_minutes', 0)
                        self.global_memory_threshold = settings.get('memory_threshold', 200)

                        # 加载关键词 - 兼容新旧配置文件格式
                        # 优先从parse_settings中加载，如果没有则从根级别加载
                        self.global_search_keywords = settings.get('search_keywords', [])
                        if not self.global_search_keywords:
                            self.global_search_keywords = config.get('search_keywords', [])

                        self.global_filter_keywords = settings.get('filter_keywords', [])

                        # 从过滤关键词文件加载过滤关键词
                        self._load_filter_keywords_from_file()

                        # 同步过滤关键词到管理器 (无论是否为空都要同步)
                        self._sync_filter_keywords_to_manager()

                        self.logger.info("已加载保存的解析设置")

        except Exception as e:
            self.logger.error(f"加载配置失败: {e}")

    def sync_config_to_ui(self):
        """同步配置数据到UI界面"""
        try:
            # 同步搜索关键词到UI
            if hasattr(self, 'search_keywords_text') and self.global_search_keywords:
                keywords_text = '\n'.join(self.global_search_keywords)
                self.search_keywords_text.delete(1.0, tk.END)
                self.search_keywords_text.insert(1.0, keywords_text)
                self.logger.info(f"已同步 {len(self.global_search_keywords)} 个搜索关键词到UI")

            # 同步解析设置到UI
            if hasattr(self, 'wait_time_var'):
                self.wait_time_var.set(str(self.global_wait_time))
            if hasattr(self, 'page_count_var'):
                self.page_count_var.set(str(self.global_page_count))
            if hasattr(self, 'target_count_var'):
                self.target_count_var.set(str(self.global_target_count))
            if hasattr(self, 'search_page_wait_var'):
                self.search_page_wait_var.set(str(self.global_search_page_wait))

            # 同步排序设置到UI
            if hasattr(self, 'sort_method_var'):
                self.sort_method_var.set(self.global_sort_method)
                
            # 同步发货时间设置到UI
            if hasattr(self, 'shipping_time_var'):
                self.shipping_time_var.set(self.global_shipping_time)
                
            # 同步定时运行控制设置到UI
            if hasattr(self, 'run_minutes_var'):
                self.run_minutes_var.set(str(self.global_run_minutes))
            if hasattr(self, 'pause_minutes_var'):
                self.pause_minutes_var.set(str(self.global_pause_minutes))
            if hasattr(self, 'memory_threshold_var'):
                self.memory_threshold_var.set(str(self.global_memory_threshold))

            # 同步过滤设置到UI
            for key, value in self.global_filter_settings.items():
                var_name = f"{key}_var"
                if hasattr(self, var_name):
                    var = getattr(self, var_name)
                    if isinstance(value, bool):
                        var.set(value)
                    else:
                        var.set(str(value))

            self.logger.info("配置数据已同步到UI界面")

        except Exception as e:
            self.logger.error(f"同步配置到UI失败: {e}")

    def _load_filter_keywords_from_file(self):
        """从过滤关键词文件加载关键词到全局变量"""
        try:
            # [HOT] 修复硬编码：使用相对路径，不使用绝对路径
            filter_keywords_file = str(Path(__file__).parent.parent / "pdd_automation" / "filter_keywords_global.txt")

            if os.path.exists(filter_keywords_file):
                with open(filter_keywords_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 过滤掉注释行和空行
                keywords = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        keywords.append(line)

                # 更新全局变量
                self.global_filter_keywords = keywords
                self.logger.info(f"✅ 从文件加载过滤关键词: {len(keywords)} 个")
            else:
                self.logger.warning(f"⚠️ 过滤关键词文件不存在: {filter_keywords_file}")

        except Exception as e:
            self.logger.error(f"[ERROR] 加载过滤关键词失败: {e}")

    def center_window(self):
        """[HOT] 窗口居中显示"""
        try:
            # 获取屏幕尺寸
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # 获取窗口尺寸
            window_width = 898
            window_height = 709
            
            # 计算居中位置
            x = (screen_width - window_width) // 2
            y = (screen_height - window_height) // 2
            
            # 设置窗口位置
            self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
            
            self.logger.info(f"窗口已居中显示: 屏幕({screen_width}x{screen_height}) -> 窗口({window_width}x{window_height}) -> 位置({x},{y})")
            
        except Exception as e:
            self.logger.error(f"窗口居中失败: {e}")

    def save_config(self):
        """保存配置"""
        try:
            # 收集所有设置（不包含过滤关键词，过滤关键词由FilterKeywordsManager独立管理）
            config = {
                'api_token': self.api_token_var.get().strip() if hasattr(self, 'api_token_var') else '',
                'parse_settings': {
                    'wait_time': self.global_wait_time,
                    'page_count': self.global_page_count,
                    'target_count': self.global_target_count,
                    'search_page_wait': self.global_search_page_wait,
                    'sort_method': self.global_sort_method,  # 新增排序设置
                    'run_minutes': self.global_run_minutes,  # 定时运行控制
                    'pause_minutes': self.global_pause_minutes,  # 定时暂停控制
                    'memory_threshold': self.global_memory_threshold,  # 内存阈值
                    'filter_settings': self.global_filter_settings.copy(),
                    'search_keywords': self.global_search_keywords.copy()
                    # 注意：filter_keywords 不再保存到配置文件，由FilterKeywordsManager独立管理
                }
            }

            # [HOT] 使用绝对路径确保配置文件保存到正确位置
            from pathlib import Path
            config_path = Path(__file__).parent.parent / "pdd_automation" / "config_api.json"
            config_path.parent.mkdir(exist_ok=True)  # 确保目录存在

            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            self.logger.info(f"配置已保存到: {config_path}")

            # 🔄 镜像保存一份到 bite_browser/api_config.json，保持口径一致
            try:
                mirror_path = Path(__file__).parent / "api_config.json"
                with open(mirror_path, 'w', encoding='utf-8') as mf:
                    json.dump(config, mf, ensure_ascii=False, indent=2)
                self.logger.info(f"配置已镜像保存到: {mirror_path}")
            except Exception as mirror_e:
                self.logger.warning(f"⚠️ 镜像保存到 bite_browser/api_config.json 失败: {mirror_e}")
        except Exception as e:
            self.logger.error(f"保存配置失败: {e}")

    def show_account_manager(self):
        """显示账号管理窗口"""
        account_window = tk.Toplevel(self.root)
        account_window.title("多账号管理")
        account_window.geometry("800x600")
        account_window.transient(self.root)
        account_window.grab_set()

        # 创建主框架
        main_frame = ttk.Frame(account_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 账号列表框架
        list_frame = ttk.LabelFrame(main_frame, text="账号列表")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 创建账号列表
        columns = ('name', 'usage', 'status', 'last_used')
        account_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        account_tree.heading('name', text='账号名称')
        account_tree.heading('usage', text='使用情况')
        account_tree.heading('status', text='状态')
        account_tree.heading('last_used', text='最后使用')

        account_tree.column('name', width=150)
        account_tree.column('usage', width=100)
        account_tree.column('status', width=100)
        account_tree.column('last_used', width=150)

        account_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="➕ 添加账号", command=lambda: self.add_account_dialog(account_tree)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="🔄 刷新状态", command=lambda: self.refresh_account_list(account_tree)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="💾 备份管理", command=self.show_backup_manager).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="[ERROR] 关闭", command=account_window.destroy).pack(side=tk.RIGHT)

        # 初始加载账号列表
        self.refresh_account_list(account_tree)

    def add_account_dialog(self, account_tree):
        """添加账号对话框"""
        dialog = tk.Toplevel(self.root)
        dialog.title("添加账号")
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        # 账号名称
        ttk.Label(dialog, text="账号名称:").pack(pady=5)
        name_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=name_var, width=40).pack(pady=5)

        # API Token
        ttk.Label(dialog, text="API Token:").pack(pady=5)
        token_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=token_var, width=40, show="*").pack(pady=5)

        # 最大浏览器数
        ttk.Label(dialog, text="最大浏览器数:").pack(pady=5)
        max_var = tk.StringVar(value="10")
        ttk.Entry(dialog, textvariable=max_var, width=40).pack(pady=5)

        # 按钮
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        def save_account():
            name = name_var.get().strip()
            token = token_var.get().strip()
            try:
                max_browsers = int(max_var.get().strip())
            except ValueError:
                max_browsers = 10

            if name and token:
                self.account_manager.add_account(name, token, max_browsers)
                self.refresh_account_list(account_tree)
                dialog.destroy()
                messagebox.showinfo("成功", f"账号 '{name}' 添加成功！")
            else:
                messagebox.showerror("错误", "请填写完整信息！")

        ttk.Button(btn_frame, text="保存", command=save_account).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def refresh_account_list(self, account_tree):
        """刷新账号列表"""
        # 清空现有项目
        for item in account_tree.get_children():
            account_tree.delete(item)

        # 获取账号状态
        status_list = self.account_manager.get_account_status()

        for status in status_list:
            account_tree.insert('', 'end', values=(
                status['name'],
                status['usage_rate'],
                status['status'],
                status['last_used']
            ))

    def show_backup_manager(self):
        """显示备份管理窗口"""
        backup_window = tk.Toplevel(self.root)
        backup_window.title("配置备份管理")
        backup_window.geometry("700x500")
        backup_window.transient(self.root)
        backup_window.grab_set()

        # 创建主框架
        main_frame = ttk.Frame(backup_window)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 备份列表框架
        list_frame = ttk.LabelFrame(main_frame, text="备份列表")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 创建备份列表
        columns = ('browser_name', 'backup_time', 'account')
        backup_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=15)

        backup_tree.heading('browser_name', text='浏览器名称')
        backup_tree.heading('backup_time', text='备份时间')
        backup_tree.heading('account', text='来源账号')

        backup_tree.column('browser_name', width=200)
        backup_tree.column('backup_time', width=150)
        backup_tree.column('account', width=150)

        backup_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 按钮框架
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X)

        def restore_selected():
            selection = backup_tree.selection()
            if not selection:
                messagebox.showwarning("警告", "请选择要恢复的备份！")
                return

            if not self.api:
                messagebox.showerror("错误", "请先连接API！")
                return

            # 获取选中的备份
            item = backup_tree.item(selection[0])
            browser_name = item['values'][0]

            # 找到对应的备份文件
            backups = self.account_manager.get_backup_list()
            backup_file = None
            for backup in backups:
                if backup['browser_name'] == browser_name:
                    backup_file = backup['filepath']
                    break

            if backup_file:
                new_id = self.account_manager.restore_browser_from_backup(self.api, backup_file)
                if new_id:
                    messagebox.showinfo("成功", f"浏览器恢复成功！新ID: {new_id}")
                    self.refresh_browsers()
                else:
                    messagebox.showerror("失败", "浏览器恢复失败！")
            else:
                messagebox.showerror("错误", "找不到备份文件！")

        ttk.Button(btn_frame, text="🔄 刷新列表", command=lambda: self.refresh_backup_list(backup_tree)).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="📥 恢复选中", command=restore_selected).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btn_frame, text="[ERROR] 关闭", command=backup_window.destroy).pack(side=tk.RIGHT)

        # 初始加载备份列表
        self.refresh_backup_list(backup_tree)

    def refresh_backup_list(self, backup_tree):
        """刷新备份列表"""
        # 清空现有项目
        for item in backup_tree.get_children():
            backup_tree.delete(item)

        # 获取备份列表
        backups = self.account_manager.get_backup_list()

        for backup in backups:
            backup_tree.insert('', 'end', values=(
                backup['browser_name'],
                backup['backup_time'],
                backup['account']
            ))

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # API Token 配置区域
        self.create_api_section(main_frame)
        
        # 控制按钮区域
        self.create_control_section(main_frame)
        
        # 浏览器列表区域
        self.create_browser_list(main_frame)
        
        # 日志区域
        self.create_log_section(main_frame)
    
    def create_api_section(self, parent):
        """创建API配置区域"""
        api_frame = ttk.LabelFrame(parent, text="API配置", padding="10")
        api_frame.pack(fill=tk.X, pady=(0, 10))
        
        # API Token输入
        token_frame = ttk.Frame(api_frame)
        token_frame.pack(fill=tk.X)

        ttk.Label(token_frame, text="API Token (必填):").pack(side=tk.LEFT)

        self.api_token_var = tk.StringVar(value="")
        self.api_token_entry = ttk.Entry(token_frame, textvariable=self.api_token_var, width=40, show="*")
        self.api_token_entry.pack(side=tk.LEFT, padx=(10, 10), fill=tk.X, expand=True)

        # 保存按钮
        self.save_btn = tk.Button(token_frame, text="💾保存", command=self.save_config,
                                 bg="#4A90E2", fg="white", font=("宋体", 10),
                                 relief="flat", bd=0, anchor="center", width=10, height=2)
        self.save_btn.pack(side=tk.LEFT, padx=(0, 15))

        # 连接按钮
        self.connect_btn = tk.Button(token_frame, text="🔗连接API", command=self.connect_api,
                                    bg="#4A90E2", fg="white", font=("宋体", 10),
                                    relief="flat", bd=0, anchor="center", width=12, height=2)
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 15))



        # 连接状态
        self.connection_status = ttk.Label(token_frame, text="未连接", foreground="red")
        self.connection_status.pack(side=tk.LEFT, padx=(15, 0))

        # 添加提示信息
        tip_frame = ttk.Frame(api_frame)
        tip_frame.pack(fill=tk.X, pady=(5, 0))

        tip_text = "💡 请在比特浏览器软件中获取API Token，填入后点击保存，下次启动会自动加载"
        ttk.Label(tip_frame, text=tip_text, foreground="blue", font=('Arial', 8)).pack(side=tk.LEFT)
    
    def create_control_section(self, parent):
        """创建控制区域"""
        # 创建主控制框架
        main_control_frame = ttk.Frame(parent)
        main_control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # 左边：实例控制板块
        instance_frame = ttk.LabelFrame(main_control_frame, text="实例控制", padding="10")
        instance_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # 实例控制按钮 - 使用grid布局实现均匀分布，应用橙红色背景
        instance_frame.columnconfigure(0, weight=1)
        instance_frame.columnconfigure(1, weight=1)
        instance_frame.columnconfigure(2, weight=1)
        instance_frame.columnconfigure(3, weight=1)
        instance_frame.columnconfigure(4, weight=1)
        
        tk.Button(instance_frame, text="➕创建实例", command=self.create_instance, 
                 bg="#2E8B57", fg="white", font=("宋体", 10), 
                 relief="flat", bd=0, anchor="center", width=12, height=2).grid(row=0, column=0, padx=3, pady=5, sticky="")
        
        tk.Button(instance_frame, text="🔄刷新列表", command=self.refresh_browsers, 
                 bg="#2E8B57", fg="white", font=("宋体", 10), 
                 relief="flat", bd=0, anchor="center", width=12, height=2).grid(row=0, column=1, padx=3, pady=5, sticky="")
        
        # 开启/关闭所有按钮（动态切换）
        self.open_close_button = tk.Button(instance_frame, text="🚀开启所有", command=self.toggle_open_close, 
                                          bg="#2E8B57", fg="white", font=("宋体", 10), 
                                          relief="flat", bd=0, anchor="center", width=12, height=2)
        self.open_close_button.grid(row=0, column=2, padx=3, pady=5, sticky="")
        self.browsers_open = False  # 跟踪浏览器开启状态
        
        # 隐藏/显示浏览器按钮（动态切换）
        self.hide_show_button = tk.Button(instance_frame, text="👻隐藏实例", command=self.toggle_browser_visibility, 
                                         bg="#2E8B57", fg="white", font=("宋体", 10), 
                                         relief="flat", bd=0, anchor="center", width=12, height=2)
        self.hide_show_button.grid(row=0, column=3, padx=3, pady=5, sticky="")
        self.browsers_hidden = False  # 跟踪浏览器隐藏状态
        
        # 右边：解析控制板块
        parse_frame = ttk.LabelFrame(main_control_frame, text="解析控制", padding="10")
        parse_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # 解析控制按钮 - 使用grid布局实现均匀分布，应用墨绿色背景
        parse_frame.columnconfigure(0, weight=1)
        parse_frame.columnconfigure(1, weight=1)
        parse_frame.columnconfigure(2, weight=1)
        parse_frame.columnconfigure(3, weight=1)
        parse_frame.columnconfigure(4, weight=1)
        
        tk.Button(parse_frame, text="🔍解析设置", command=self.show_filter_config, 
                 bg="#2E8B57", fg="white", font=("宋体", 10), 
                 relief="flat", bd=0, anchor="center", width=12, height=2).grid(row=0, column=0, padx=3, pady=5, sticky="")
        
        # 开始/停止解析按钮（动态切换）
        self.start_stop_button = tk.Button(parse_frame, text="▶️开始解析", command=self.toggle_start_stop, 
                                          bg="#2E8B57", fg="white", font=("宋体", 10), 
                                          relief="flat", bd=0, anchor="center", width=12, height=2)
        self.start_stop_button.grid(row=0, column=1, padx=3, pady=5, sticky="")
        self.parsing_active = False  # 跟踪解析状态
        
        # 暂停/继续运行按钮（动态切换）
        self.pause_continue_button = tk.Button(parse_frame, text="⏸️暂停程序", command=self.toggle_pause_continue, 
                                              bg="#FF0000", fg="white", font=("宋体", 10), 
                                              relief="flat", bd=0, anchor="center", width=12, height=2)
        self.pause_continue_button.grid(row=0, column=2, padx=3, pady=5, sticky="")
        self.program_paused = False  # 跟踪程序暂停状态
    
    def create_browser_list(self, parent):
        """创建浏览器列表"""
        list_frame = ttk.LabelFrame(parent, text="浏览器实例", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # 创建Treeview - 删除重复的运行状态列，添加运行时长
        columns = ('seq', 'name', 'id', 'debug_port', 'parse_count', 'runtime', 'takeover')
        self.browser_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=10)

        # 设置列标题和宽度
        self.browser_tree.heading('seq', text='序号')
        self.browser_tree.heading('name', text='实例名称')
        self.browser_tree.heading('id', text='实例ID')
        self.browser_tree.heading('debug_port', text='调试端口')
        self.browser_tree.heading('parse_count', text='解析数量')
        self.browser_tree.heading('runtime', text='运行时长')  # [HOT] 修改：解析状态改为运行时长
        self.browser_tree.heading('takeover', text='运行状态')

        self.browser_tree.column('seq', width=40)
        self.browser_tree.column('name', width=120)
        self.browser_tree.column('id', width=100)
        self.browser_tree.column('debug_port', width=80)
        self.browser_tree.column('parse_count', width=80)
        self.browser_tree.column('runtime', width=100)  # [HOT] 修改：运行时长列
        self.browser_tree.column('takeover', width=100)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.browser_tree.yview)
        self.browser_tree.configure(yscrollcommand=scrollbar.set)
        
        self.browser_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 绑定双击事件和右键菜单
        self.browser_tree.bind('<Double-1>', self.on_browser_double_click)
        self.browser_tree.bind('<Button-3>', self.on_browser_right_click)  # 右键菜单
    
    def create_log_section(self, parent):
        """创建日志区域"""
        log_frame = ttk.LabelFrame(parent, text="操作日志", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建文本框
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=8)
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)
        
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 清空日志按钮
        clear_frame = ttk.Frame(log_frame)
        clear_frame.pack(fill=tk.X, pady=(5, 0))
        ttk.Button(clear_frame, text="清空日志", command=self.clear_log).pack()
    
    def connect_api(self):
        """连接API"""
        def run():
            try:
                api_token = self.api_token_var.get().strip()
                if not api_token:
                    self.connection_status.config(text="Token为空", foreground="red")
                    self.log_message("[ERROR] 错误：请输入API Token")
                    messagebox.showerror("错误", "请先输入API Token！\n\n获取方法：\n1. 打开比特浏览器软件\n2. 点击右上角设置\n3. 找到Local API选项\n4. 复制API Token")
                    return
                
                # [HOT] 安全措施：验证Token基本格式
                cleaned_token = security_manager.sanitize_input(api_token)
                if len(cleaned_token) < 16:
                    self.connection_status.config(text="Token无效", foreground="red")
                    self.log_message("[ERROR] 错误：API Token格式无效")
                    security_manager.log_security_event(
                        "INVALID_API_TOKEN", 
                        {"reason": "token_too_short", "length": len(cleaned_token)},
                        "WARNING"
                    )
                    messagebox.showerror("错误", "API Token格式无效，长度过短")
                    return

                self.log_message("正在连接比特浏览器API...")
                self.connection_status.config(text="连接中...", foreground="orange")

                # 创建API实例
                self.api = BitBrowserAPI(api_token)
                self.bitbrowser_api = self.api  # [HOT] 让bitbrowser_api指向同一个实例

                # 测试连接
                if self.api.test_connection():
                    # 进一步测试Token是否有效
                    browsers = self.api.get_browser_list(page=0, page_size=1)
                    if browsers is not None:
                        self.connection_status.config(text="✅ 已连接", foreground="green")
                        self.log_message("✅ API连接成功，Token验证通过")
                        
                        # [HOT] 安全措施：记录成功连接
                        security_manager.log_security_event(
                            "API_CONNECTION_SUCCESS", 
                            {"token_length": len(cleaned_token), "timestamp": datetime.now().isoformat()},
                            "INFO"
                        )

                        # 自动刷新浏览器列表
                        self.refresh_browsers()
                    else:
                        self.connection_status.config(text="[ERROR] Token无效", foreground="red")
                        self.log_message("[ERROR] API Token无效，请检查Token是否正确")
                        messagebox.showerror("Token错误", "API Token无效！\n\n请检查：\n1. Token是否正确复制\n2. 比特浏览器是否开启API功能\n3. Token是否已过期")
                else:
                    self.connection_status.config(text="[ERROR] 服务异常", foreground="red")
                    self.log_message("[ERROR] 比特浏览器本地服务连接失败")
                    messagebox.showerror("连接失败", "无法连接到比特浏览器本地服务！\n\n请检查：\n1. 比特浏览器软件是否正在运行\n2. 本地服务端口是否正常（从配置文件获取）\n3. 防火墙是否阻止连接")

            except Exception as e:
                self.connection_status.config(text="[ERROR] 连接错误", foreground="red")
                self.log_message(f"连接API出错: {e}")
                messagebox.showerror("连接错误", f"连接API时发生错误：\n{e}")

        threading.Thread(target=run, daemon=True).start()
    
    def create_instance(self):
        """创建实例"""
        if not self.api:
            messagebox.showerror("错误", "请先连接API")
            return

        # 弹出对话框输入实例名称，并检查重复
        while True:
            name = simpledialog.askstring("创建实例", "请输入实例名称:")
            if not name:
                return

            # 检查是否有重复名称
            name_exists = False
            for browser in self.browsers.values():
                if browser.get('name') == name:
                    name_exists = True
                    break

            if name_exists:
                messagebox.showerror("名称重复", f"实例名称 '{name}' 已存在，请使用不同的名称！")
                continue
            else:
                break  # 名称有效，退出循环
        
        def run():
            try:
                self.log_message(f"正在创建实例: {name}")
                
                browser_id = self.api.create_browser(name)
                if browser_id:
                    self.log_message(f"✅ 实例创建成功: {name}")
                    self.refresh_browsers()
                else:
                    self.log_message(f"[ERROR] 实例创建失败: {name}")
                
            except Exception as e:
                self.log_message(f"创建实例失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def refresh_browsers(self):
        """刷新浏览器列表 - 优化API调用频率"""
        if not self.api:
            return
        
        def run():
            try:
                self.log_message("正在刷新浏览器列表...")
                
                # [HOT] 优化1：获取浏览器列表
                browsers = self.api.get_browser_list()
                
                # 更新浏览器字典
                old_browsers = self.browsers.copy()  # 保存旧状态
                self.browsers.clear()
                for browser in browsers:
                    browser_id = browser['id']
                    browser_info = browser.copy()
                    
                    # 保持已有的启动时间记录
                    if browser_id in old_browsers and 'start_time' in old_browsers[browser_id]:
                        browser_info['start_time'] = old_browsers[browser_id]['start_time']
                    elif browser.get('status') == 1:  # 如果是运行中状态且没有记录启动时间
                        from datetime import datetime
                        browser_info['start_time'] = datetime.now()
                        
                    self.browsers[browser_id] = browser_info
                
                # [HOT] 优化2：批量获取运行状态，减少API调用
                if browsers:
                    browser_ids = [b['id'] for b in browsers]
                    
                    # 只调用一次API获取所有浏览器的运行状态
                    pids = self.api.get_browser_pids(browser_ids)
                    
                    # 更新运行状态
                    for browser in browsers:
                        browser_id = browser['id']
                        browser['is_running'] = browser_id in pids
                        browser['pid'] = pids.get(browser_id)

                        # [HOT] 优化3：优先使用缓存，减少API调用
                        cached_port = getattr(self, '_debug_port_cache', {}).get(browser_id)
                        if cached_port:
                            browser['debug_port'] = cached_port
                        else:
                            browser['debug_port'] = '-'  # 暂时设为默认值
                    
                    # [HOT] 优化4：延迟获取调试端口，避免阻塞刷新
                    # 将调试端口获取放到后台，不影响主要刷新流程
                    self.root.after(100, lambda: self._update_debug_ports_async(browser_ids))
                
                # [HOT] 优化5：检查脚本错误状态（本地文件操作，不涉及API）
                for browser in browsers:
                    browser_id = browser['id']
                    browser['has_error'] = self._check_script_error_status(browser_id)
                
                # 更新界面显示
                self.update_browser_display()
                
                self.log_message(f"✅ 刷新完成，共 {len(browsers)} 个实例")
                
            except Exception as e:
                self.log_message(f"刷新浏览器列表失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def _update_debug_ports_async(self, browser_ids):
        """异步更新调试端口 - 避免阻塞主要刷新流程"""
        try:
            for browser_id in browser_ids:
                # 检查浏览器是否还在运行
                browser = self.browsers.get(browser_id)
                if not browser or not browser.get('is_running'):
                    continue
                
                # 检查缓存
                cached_port = getattr(self, '_debug_port_cache', {}).get(browser_id)
                if cached_port:
                    browser['debug_port'] = cached_port
                    continue
                
                try:
                    # [HOT] 优化：添加延迟，避免API频率限制
                    time.sleep(0.2)  # 200ms延迟，确保不超过5次/秒
                    
                    result = self.api.open_browser(browser_id)
                    if result and 'http' in result:
                        debug_info = result['http']
                        if ':' in debug_info:
                            debug_port = debug_info.split(':')[-1]
                            browser['debug_port'] = debug_port
                            
                            # 缓存调试端口
                            if not hasattr(self, '_debug_port_cache'):
                                self._debug_port_cache = {}
                            self._debug_port_cache[browser_id] = debug_port
                            
                            # 异步更新界面
                            self.root.after(0, lambda: self._update_single_browser_display(browser_id))
                            
                except Exception as e:
                    browser['debug_port'] = '-'
                    # 不记录错误日志，避免刷屏
                
        except Exception as e:
            self.log_message(f"异步更新调试端口失败: {e}")
    
    def _update_single_browser_display(self, browser_id):
        """更新单个浏览器的显示"""
        try:
            # 找到对应的树形项目
            for item in self.browser_tree.get_children():
                values = self.browser_tree.item(item)['values']
                if len(values) > 2 and values[2] == browser_id:  # ID在第三列
                    # 更新调试端口列
                    browser = self.browsers.get(browser_id)
                    if browser:
                        values = list(values)
                        values[3] = str(browser.get('debug_port', '-'))  # 调试端口在第四列
                        self.browser_tree.item(item, values=values)
                    break
        except Exception:
            pass  # 忽略更新失败

    def _check_script_error_status(self, browser_id: str) -> bool:
        """检查脚本是否处于错误状态"""
        try:
            # 检查生成的脚本目录中是否有错误标记文件
            scripts_dir = os.path.join(os.path.dirname(__file__), '..', 'generated_scripts')
            browser_folder = os.path.join(scripts_dir, f'browser_{browser_id}')
            error_file = os.path.join(browser_folder, 'error_status.json')

            if os.path.exists(error_file):
                with open(error_file, 'r', encoding='utf-8') as f:
                    error_data = json.load(f)
                    return error_data.get('has_critical_error', False)

            return False
        except Exception:
            return False

    def _calculate_runtime(self, browser_id: str) -> str:
        """[HOT] 计算当次运行软件的时长 - 只对运行中的浏览器计时"""
        try:
            # [HOT] 首先检查浏览器是否在运行中
            browser_info = None
            for browser in self.browsers.values():
                if browser.get('id') == browser_id:
                    browser_info = browser
                    break

            # [HOT] 如果浏览器不在运行中，返回"未运行" - 使用正确的状态字段
            if not browser_info or browser_info.get('status') != 1:
                return "未运行"

            from datetime import datetime

            # [HOT] 获取浏览器的启动时间
            start_time = browser_info.get('start_time')
            if not start_time:
                return "启动中..."

            # [HOT] 计算该浏览器的独立运行时长
            now_dt = datetime.now()
            duration = now_dt - start_time

            # 格式化时长显示：按小时和分钟显示
            total_seconds = int(duration.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            # [HOT] 按要求格式化：少于1小时按分钟计算，否则按小时计算
            if hours > 0:
                return f"{hours}小时"
            elif minutes > 0:
                return f"{minutes}分钟"
            else:
                return "1分钟"  # 不足1分钟显示为1分钟

        except Exception:
            return "未知"

    def _get_current_parse_count(self, browser_id: str) -> str:
        """🔥 新版：从主目录cache文件夹获取解析数量（整个软件执行期间的统计）"""
        try:
            # 构建主目录cache文件夹中的统计文件路径
            cache_file_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # 回到主目录
                "cache",
                f"统计数量_{browser_id}.json"
            )
            
            # 检查文件是否存在
            if not os.path.exists(cache_file_path):
                return "0"
            
            # 直接读取JSON文件中的解析数量
            try:
                with open(cache_file_path, 'r', encoding='utf-8') as f:
                    stats_data = json.load(f)
                    parse_count = stats_data.get("解析数量", 0)
                    return str(parse_count)
            except:
                return "0"
                        
        except Exception as e:
            return "0"


    def start_auto_refresh(self):
        """[HOT] 启动轻量级定时刷新 - 每分钟更新解析数量和状态"""
        try:
            # 执行轻量级刷新
            self._refresh_parse_counts_and_status()
            
            # 设置下次刷新（60秒后）
            self.root.after(60000, self.start_auto_refresh)
            
        except Exception as e:
            print(f"⚠️ 自动刷新异常: {e}")
            # 即使出错也要继续刷新
            self.root.after(60000, self.start_auto_refresh)

    def _refresh_parse_counts_and_status(self):
        """[HOT] 轻量级刷新：只更新解析数量和状态，不重新获取浏览器列表"""
        try:
            # 检查是否有浏览器列表
            if not self.browsers:
                return
            
            # 获取当前显示的项目
            current_items = []
            for item in self.browser_tree.get_children():
                values = list(self.browser_tree.item(item)['values'])
                current_items.append((item, values))
            
            # 更新每个浏览器的解析数量和状态
            updated_count = 0
            for item, values in current_items:
                try:
                    if len(values) >= 6:  # 确保有足够的列
                        # 从值中提取浏览器ID（第3列，去掉"..."）
                        browser_id_display = values[2]  # "browser_id[:20]..."
                        
                        # 找到完整的浏览器ID
                        browser_id = None
                        for bid in self.browsers:
                            if bid.startswith(browser_id_display.replace("...", "")):
                                browser_id = bid
                                break
                        
                        if browser_id:
                            # 获取最新的解析数量
                            new_parse_count = self._get_current_parse_count(browser_id)
                            
                            # 获取最新状态
                            browser = self.browsers[browser_id]
                            is_running = browser.get('status') == 1
                            has_error = browser.get('has_error', False)
                            is_paused = self._is_browser_paused(browser_id)
                            is_stopped = self._is_browser_stopped(browser_id)
                            
                            # 确定状态文字
                            if has_error:
                                new_status = "[ERROR] 错误"
                            elif is_paused:
                                new_status = "⏸️️ 已暂停"
                            elif is_stopped:
                                new_status = "⏹️ 已停止"
                            elif is_running and browser.get('debug_port', '-') != '-':
                                new_status = "✅ 运行中"
                            elif is_running:
                                new_status = "✅ 运行中"
                            else:
                                new_status = "未运行"
                            
                            # 检查是否需要更新
                            old_parse_count = values[4]  # 解析数量列
                            old_status = values[6]       # 状态列
                            
                            if new_parse_count != old_parse_count or new_status != old_status:
                                # 更新值
                                values[4] = new_parse_count  # 解析数量
                                values[6] = new_status       # 状态
                                
                                # 更新显示
                                self.browser_tree.item(item, values=values)
                                updated_count += 1
                                
                except Exception as e:
                    print(f"⚠️ 更新浏览器项目失败: {e}")
                    continue
            
            # 只在有更新时输出日志
            if updated_count > 0:
                print(f"🔄 轻量级刷新完成: 更新了 {updated_count} 个浏览器的状态")
            
            # [HOT] 定期清理缓存，防止内存泄漏
            if len(self._json_cache) > 50:  # 限制缓存文件数量
                # 清理一半最老的缓存
                cache_items = list(self._json_cache.items())
                keep_count = 25
                self._json_cache = dict(cache_items[-keep_count:])
                print("🧹 已清理JSON文件缓存")
                
        except Exception as e:
            print(f"[ERROR] 轻量级刷新失败: {e}")

    def update_browser_display(self):
        """更新浏览器显示"""
        # 清空现有项目
        for item in self.browser_tree.get_children():
            self.browser_tree.delete(item)

        # 按序号排序浏览器
        sorted_browsers = sorted(self.browsers.items(), key=lambda x: x[1].get('seq', 0))

        # 添加浏览器信息
        for index, (browser_id, browser) in enumerate(sorted_browsers, 1):
            name = str(browser.get('name', 'Unknown'))  # 确保名称是字符串

            # [HOT] 修复：显示真实的调试端口而不是PID
            debug_port = str(browser.get('debug_port', '-'))

            # 获取解析数量（当次运行的TXT文件数量）
            parse_count = self._get_current_parse_count(browser_id)

            # [HOT] 计算运行时长
            runtime = self._calculate_runtime(browser_id)

            # [HOT] 优化：运行状态显示 - 检查暂停、停止和运行状态
            is_running = browser.get('status') == 1 or browser.get('is_running', False)  # status=1表示运行中
            has_error = browser.get('has_error', False)  # 检查是否有错误状态
            
            # [HOT] 新增：检查暂停和停止状态
            is_paused = self._is_browser_paused(browser_id)
            is_stopped = self._is_browser_stopped(browser_id)

            if has_error:
                takeover_status = "[ERROR] 错误"  # 红色X表示错误
            elif is_paused:
                takeover_status = "⏸️️ 已暂停"  # 显示暂停状态
            elif is_stopped:
                takeover_status = "⏹️ 已停止"  # 显示停止状态
            elif is_running and browser.get('debug_port', '-') != '-':
                takeover_status = "✅ 运行中"  # 绿色勾表示正常运行
            elif is_running:
                takeover_status = "✅ 运行中"  # 绿色勾表示运行中
            else:
                takeover_status = "未运行"  # 普通文字表示未运行

            # 插入浏览器信息到列表 - 使用运行时长替代解析状态
            self.browser_tree.insert('', 'end', values=(
                str(index),  # 序号
                name,
                browser_id[:20] + "...",  # 截断ID显示
                debug_port,
                parse_count,
                runtime,  # [HOT] 修改：显示运行时长
                takeover_status
            ))
    
    def open_all_browsers(self):
        """一键开启所有浏览器"""
        if not self.api:
            messagebox.showerror("错误", "请先连接API")
            return
        
        def run():
            try:
                self.log_message("🚀 开始一键开启所有浏览器...")
                
                opened_count = 0
                results = {}
                for browser_id, browser in self.browsers.items():
                    if not browser.get('is_running', False):
                        result = self.api.open_browser(browser_id)
                        results[browser_id] = result
                        if result:
                            opened_count += 1
                            self.log_message(f"✅ 开启浏览器: {browser.get('name')}")
                            # [HOT] 记录浏览器启动时间
                            from datetime import datetime
                            if browser_id in self.browsers:
                                self.browsers[browser_id]['start_time'] = datetime.now()
                        else:
                            self.log_message(f"[ERROR] 开启失败: {browser.get('name')}")
                
                self.log_message(f"🎊 一键开启完成！成功开启 {opened_count} 个浏览器")
                # [HOT] 移除刷新调用，避免闪烁
                
                # 调用回调函数更新按钮状态
                self.root.after(0, lambda: self._on_open_browsers_complete(results))
                
            except Exception as e:
                self.log_message(f"一键开启失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def close_all_browsers(self):
        """一键关闭所有浏览器"""
        if not self.api:
            messagebox.showerror("错误", "请先连接API")
            return
        
        # [HOT] 安全措施：记录批量关闭操作
        security_manager.log_security_event(
            "BATCH_CLOSE_BROWSERS", 
            {"operation": "close_all_browsers", "timestamp": datetime.now().isoformat()},
            "INFO"
        )
        
        # 直接关闭，不需要确认弹窗
        
        def run():
            try:
                self.log_message("[ERROR] 开始一键关闭所有浏览器...")
                
                # [HOT] 第一步：停止所有浏览器的手动解析模式
                self.log_message("🛑 第一步：停止所有浏览器的手动解析模式...")
                self.stop_all_manual_extraction()
                # 等待一下确保手动解析完全停止
                import time
                time.sleep(2)
                
                closed_count = 0
                results = {}
                for browser_id, browser in self.browsers.items():
                    if browser.get('is_running', False):
                        result = self.api.close_browser(browser_id)
                        results[browser_id] = result
                        if result:
                            closed_count += 1
                            self.log_message(f"✅ 关闭浏览器: {browser.get('name')}")
                            
                            # [HOT] 清除启动时间记录
                            if browser_id in self.browsers and 'start_time' in self.browsers[browser_id]:
                                del self.browsers[browser_id]['start_time']
                                self.log_message(f"🧹 清除浏览器启动时间记录: {browser.get('name')}")
                        else:
                            self.log_message(f"[ERROR] 关闭失败: {browser.get('name')}")
                
                self.log_message(f"🎊 一键关闭完成！成功关闭 {closed_count} 个浏览器")
                # [HOT] 移除刷新调用，避免闪烁
                
                # 调用回调函数更新按钮状态
                self.root.after(0, lambda: self._on_close_browsers_complete(results))
                
            except Exception as e:
                self.log_message(f"一键关闭失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def on_browser_double_click(self, event):
        """双击浏览器直接打开"""
        selection = self.browser_tree.selection()
        if not selection:
            return

        # 获取浏览器名称
        item = self.browser_tree.item(selection[0])
        browser_name = str(item['values'][1])  # 名称在第二列，确保是字符串

        # 通过浏览器名称查找浏览器数据
        browser = None
        for b in self.browsers.values():
            if str(b.get('name', '')) == browser_name:
                browser = b
                break

        if browser:
            # 双击直接打开浏览器
            if not browser.get('is_running', False):
                self.open_single_browser(browser)
            else:
                self.log_message(f"浏览器 {browser.get('name')} 已经在运行中")

    def on_browser_right_click(self, event):
        """右键点击浏览器显示菜单"""
        try:
            self.log_message("🖱️ 右键点击事件触发")

            # 选中右键点击的项目
            item_id = self.browser_tree.identify_row(event.y)
            self.log_message(f"识别到项目ID: {item_id}")

            if item_id:
                self.browser_tree.selection_set(item_id)

                # 获取浏览器名称
                item = self.browser_tree.item(item_id)
                browser_name = str(item['values'][1])  # 名称在第二列，确保是字符串
                self.log_message(f"界面显示名称: '{browser_name}'")

                # 通过浏览器名称查找浏览器数据
                browser = None
                for b in self.browsers.values():
                    stored_name = str(b.get('name', ''))
                    if stored_name == browser_name:
                        browser = b
                        break

                if browser:
                    self.log_message(f"找到浏览器数据，准备显示菜单")
                    self.show_context_menu(event, browser)
                else:
                    self.log_message(f"[ERROR] 未找到浏览器数据: {browser_name}")
                    self.log_message(f"可用的浏览器: {[b.get('name') for b in self.browsers.values()]}")
            else:
                self.log_message("[ERROR] 未识别到有效的项目")

        except Exception as e:
            self.log_message(f"[ERROR] 右键菜单错误: {e}")
            import traceback
            self.log_message(f"详细错误: {traceback.format_exc()}")

    def show_context_menu(self, event, browser):
        """显示右键上下文菜单"""
        try:
            self.log_message("📋 开始创建右键菜单")
            context_menu = tk.Menu(self.root, tearoff=0)

            # 第一个选项：打开实例（如果浏览器未运行）
            is_browser_running = browser.get('status') == 1 or browser.get('is_running', False)
            if not is_browser_running:
                context_menu.add_command(label="🟢 打开实例", command=lambda: self.open_single_browser(browser))
                context_menu.add_separator()

            # [HOT] 调整顺序：手动解析、程序控制按钮（动态显示）
            is_browser_running = browser.get('status') == 1 or browser.get('is_running', False)
            if is_browser_running:
                # 检查是否已经在手动解析模式
                browser_id = browser['id']
                is_manual_mode = hasattr(self, 'manual_extraction_processes') and browser_id in self.manual_extraction_processes
                
                if is_manual_mode:
                    # 手动解析模式：显示自动解析按钮
                    context_menu.add_command(label="🤖 自动解析", command=lambda: self.start_auto_extraction(browser))
                else:
                    # 自动解析模式：显示手动解析按钮
                    context_menu.add_command(label="🔍 手动解析", command=lambda: self.start_manual_extraction(browser))

                context_menu.add_separator()
                
                # [HOT] 动态程序控制按钮
                browser_id = browser['id']
                
                # 检查程序状态 - 优先使用内存中的状态
                is_paused = browser.get('is_paused', False) or self._is_browser_paused(browser_id)
                is_stopped = browser.get('is_stopped', False) or self._is_browser_stopped(browser_id)
                
                if is_paused:
                    # 暂停状态：显示继续运行
                    context_menu.add_command(label="▶️ 继续运行", command=lambda: self.continue_program(browser))
                elif is_stopped:
                    # 停止状态：显示开始程序
                    context_menu.add_command(label="🚀 开始程序", command=lambda: self.start_program(browser))
                else:
                    # 运行状态：显示暂停程序和停止程序
                    context_menu.add_command(label="⏸️ 暂停程序", command=lambda: self.pause_program(browser))
                    context_menu.add_command(label="⏹️ 停止程序", command=lambda: self.stop_program(browser))

                context_menu.add_separator()

            # 修改名称选项
            context_menu.add_command(label="📝 修改名称", command=lambda: self.edit_browser_name(browser))

            context_menu.add_separator()
            context_menu.add_command(label="📄 查看详情", command=lambda: self.show_browser_details(browser))

            context_menu.add_separator()
            
            # 关闭实例（如果浏览器正在运行）
            if is_browser_running:
                context_menu.add_command(label="🔴 关闭实例", command=lambda: self.close_single_browser(browser))
                context_menu.add_separator()
            
            context_menu.add_command(label="🗑 删除实例", command=lambda: self.delete_single_browser(browser))

            self.log_message(f"📋 菜单创建完成，准备显示在位置: ({event.x_root}, {event.y_root})")

            context_menu.tk_popup(event.x_root, event.y_root)
            self.log_message("📋 右键菜单显示成功")

        except Exception as e:
            self.log_message(f"[ERROR] 显示右键菜单错误: {e}")
            import traceback
            self.log_message(f"详细错误: {traceback.format_exc()}")
        finally:
            try:
                context_menu.grab_release()
            except:
                pass

    def edit_browser_name(self, browser):
        """修改浏览器名称"""
        current_name = browser.get('name', '')

        while True:
            new_name = simpledialog.askstring("修改名称", f"请输入新的实例名称:", initialvalue=current_name)

            if not new_name:  # 用户取消
                return

            if new_name == current_name:  # 名称没有改变
                return

            # 检查是否有重复名称
            name_exists = False
            for other_browser in self.browsers.values():
                if other_browser['id'] != browser['id'] and other_browser.get('name') == new_name:
                    name_exists = True
                    break

            if name_exists:
                messagebox.showerror("名称重复", f"实例名称 '{new_name}' 已存在，请使用不同的名称！")
                current_name = new_name  # 保持用户输入的内容
                continue
            else:
                break  # 名称有效，退出循环

        if new_name and new_name != browser.get('name', ''):
            def run():
                try:
                    self.log_message(f"正在修改浏览器名称: {current_name} -> {new_name}")

                    # 使用专门的更新名称方法
                    if self.api.update_browser_name(browser['id'], new_name, browser):
                        self.log_message(f"✅ 浏览器名称修改成功: {new_name}")
                        # 刷新列表
                        self.refresh_browsers()
                    else:
                        self.log_message(f"[ERROR] 浏览器名称修改失败")

                except Exception as e:
                    self.log_message(f"修改浏览器名称失败: {e}")

            threading.Thread(target=run, daemon=True).start()

    def backup_browser_config(self, browser):
        """备份浏览器配置"""
        def run():
            try:
                self.log_message(f"正在备份浏览器配置: {browser.get('name')}")

                if self.account_manager.backup_browser_config(self.api, browser['id'], browser.get('name')):
                    self.log_message(f"✅ 浏览器配置备份成功: {browser.get('name')}")
                else:
                    self.log_message(f"[ERROR] 浏览器配置备份失败: {browser.get('name')}")

            except Exception as e:
                self.log_message(f"备份浏览器配置失败: {e}")

        threading.Thread(target=run, daemon=True).start()



















        # 滚动条
        account_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=account_tree.yview)
        account_tree.configure(yscrollcommand=account_scrollbar.set)

        account_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        account_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 填充账号列表
        for browser_name, account_data in all_accounts.items():
            cookie_count = len(account_data.get('cookies', {}))
            token_count = len(account_data.get('tokens', {}))
            user_info_count = len(account_data.get('user_info', {}))
            save_time = account_data.get('save_time', '未知')

            account_tree.insert('', 'end', values=(
                browser_name,
                cookie_count,
                token_count,
                user_info_count,
                save_time
            ))

        # 详情显示框架
        detail_frame = ttk.LabelFrame(main_frame, text="账号详情", padding="10")
        detail_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # 详情文本框
        detail_text = tk.Text(detail_frame, height=8, wrap=tk.WORD)
        detail_scrollbar = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=detail_text.yview)
        detail_text.configure(yscrollcommand=detail_scrollbar.set)

        detail_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def on_account_select(event):
            """选择账号时显示详情"""
            selection = account_tree.selection()
            if selection:
                item = account_tree.item(selection[0])
                browser_name = item['values'][0]

                if browser_name in all_accounts:
                    account_data = all_accounts[browser_name]

                    detail_text.delete(1.0, tk.END)
                    detail_text.insert(tk.END, f"浏览器实例: {browser_name}\n")
                    detail_text.insert(tk.END, f"保存时间: {account_data.get('save_time', '未知')}\n\n")

                    # 显示Cookies
                    cookies = account_data.get('cookies', {})
                    if cookies:
                        detail_text.insert(tk.END, f"🍪 Cookies ({len(cookies)}个):\n")
                        for key, value in cookies.items():
                            detail_text.insert(tk.END, f"  {key}: {value[:50]}{'...' if len(value) > 50 else ''}\n")
                        detail_text.insert(tk.END, "\n")

                    # 显示Tokens
                    tokens = account_data.get('tokens', {})
                    if tokens:
                        detail_text.insert(tk.END, f"🔑 Tokens ({len(tokens)}个):\n")
                        for key, value in tokens.items():
                            detail_text.insert(tk.END, f"  {key}: {value[:50]}{'...' if len(value) > 50 else ''}\n")
                        detail_text.insert(tk.END, "\n")

                    # 显示用户信息
                    user_info = account_data.get('user_info', {})
                    if user_info:
                        detail_text.insert(tk.END, f"👤 用户信息 ({len(user_info)}个):\n")
                        for key, value in user_info.items():
                            detail_text.insert(tk.END, f"  {key}: {value}\n")
                        detail_text.insert(tk.END, "\n")

                    # 显示会话信息
                    session_info = account_data.get('session_info', {})
                    if session_info:
                        detail_text.insert(tk.END, f"🔐 会话信息 ({len(session_info)}个):\n")
                        for key, value in session_info.items():
                            detail_text.insert(tk.END, f"  {key}: {value[:50]}{'...' if len(value) > 50 else ''}\n")

        account_tree.bind('<<TreeviewSelect>>', on_account_select)

        # 操作按钮框架
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)

        # 按钮
        ttk.Button(button_frame, text="🔄 立即保存所有账号",
                  command=lambda: self.save_all_pdd_accounts(pdd_window)).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="📁 打开账号目录",
                  command=self.open_pdd_accounts_dir).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="🔄 刷新列表",
                  command=lambda: self.refresh_pdd_window(pdd_window)).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(button_frame, text="关闭", command=pdd_window.destroy).pack(side=tk.RIGHT)

    def save_all_pdd_accounts(self, parent_window):
        """立即保存所有拼多多账号"""
        def run():
            try:
                if self.api and hasattr(self.api, 'auto_save_pdd_accounts'):
                    self.log_message("🛒 开始保存所有拼多多账号信息...")
                    results = self.api.auto_save_pdd_accounts()

                    success_count = sum(1 for success in results.values() if success)
                    total_count = len(results)

                    self.log_message(f"✅ 拼多多账号保存完成: 成功 {success_count}/{total_count} 个")

                    messagebox.showinfo("保存完成",
                        f"拼多多账号信息保存完成！\n"
                        f"成功保存: {success_count} 个\n"
                        f"总浏览器: {total_count} 个")

                    # 刷新窗口
                    parent_window.destroy()
                    self.show_pdd_account_manager()
                else:
                    messagebox.showerror("错误", "拼多多账号管理器未初始化！")
            except Exception as e:
                self.log_message(f"保存拼多多账号失败: {e}")
                messagebox.showerror("错误", f"保存拼多多账号失败: {e}")

        threading.Thread(target=run, daemon=True).start()

    def open_pdd_accounts_dir(self):
        """打开拼多多账号目录"""
        try:
            accounts_dir = os.path.join(os.getcwd(), 'pdd_accounts')
            if not os.path.exists(accounts_dir):
                os.makedirs(accounts_dir)
            os.startfile(accounts_dir)
        except Exception as e:
            messagebox.showerror("错误", f"打开账号目录失败: {e}")

    def refresh_pdd_window(self, parent_window):
        """刷新拼多多账号窗口"""
        parent_window.destroy()
        self.show_pdd_account_manager()

    def show_cookie_window(self, browser, cookie_data):
        """显示Cookie查看窗口"""
        cookie_window = tk.Toplevel(self.root)
        cookie_window.title(f"Cookie查看 - {browser.get('name')}")
        cookie_window.geometry("800x600")
        cookie_window.resizable(True, True)

        # 创建滚动文本框
        text_frame = ttk.Frame(cookie_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)

        cookie_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 9))
        cookie_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=cookie_text.yview)
        cookie_text.configure(yscrollcommand=cookie_scrollbar.set)

        # 格式化Cookie显示
        formatted_cookie = f"""🍪 浏览器Cookie信息
{'='*80}

📋 实例名称: {browser.get('name', 'Unknown')}
🆔 实例ID: {browser.get('id', 'Unknown')}
⏰ 获取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

{'='*80}
Cookie数据:
{'='*80}

{cookie_data}

{'='*80}
"""

        cookie_text.insert(tk.END, formatted_cookie)
        cookie_text.config(state=tk.DISABLED)

        cookie_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cookie_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮框架
        button_frame = ttk.Frame(cookie_window)
        button_frame.pack(fill=tk.X, pady=10)

        # 复制Cookie按钮
        ttk.Button(button_frame, text="📋 复制Cookie",
                  command=lambda: self.copy_cookie_data(cookie_data)).pack(side=tk.LEFT, padx=(0, 10))

        # 保存Cookie按钮
        ttk.Button(button_frame, text="💾 保存到文件",
                  command=lambda: self.save_cookie_to_file(browser, cookie_data)).pack(side=tk.LEFT, padx=(0, 10))

        # 关闭按钮
        ttk.Button(button_frame, text="关闭", command=cookie_window.destroy).pack(side=tk.RIGHT)

    def copy_cookie_data(self, cookie_data):
        """复制Cookie数据到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(cookie_data)
        self.log_message("📋 Cookie数据已复制到剪贴板")
        messagebox.showinfo("成功", "Cookie数据已复制到剪贴板！")

    def save_cookie_to_file(self, browser, cookie_data):
        """保存Cookie到文件"""
        from tkinter import filedialog
        import time

        default_filename = f"{browser.get('name', 'unknown')}_cookies_{int(time.time())}.txt"

        file_path = filedialog.asksaveasfilename(
            title="保存Cookie到文件",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfilename=default_filename
        )

        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cookie_data)
                self.log_message(f"✅ Cookie已保存到: {file_path}")
                messagebox.showinfo("成功", f"Cookie已保存到:\n{file_path}")
            except Exception as e:
                self.log_message(f"[ERROR] 保存Cookie失败: {e}")
                messagebox.showerror("错误", f"保存Cookie失败: {e}")

    def get_proxy_method_text(self, method):
        """获取代理方法文本"""
        proxy_methods = {
            1: "提取IP",
            2: "自定义代理",
            3: "无代理"
        }
        return proxy_methods.get(method, f"未知({method})")

    def get_workbench_text(self, workbench):
        """获取工作台文本"""
        workbench_types = {
            'localserver': '本地服务器',
            'disable': '禁用',
            'enable': '启用'
        }
        return workbench_types.get(workbench, workbench)

    def get_dnt_text(self, dnt):
        """获取Do Not Track文本"""
        dnt_values = {
            '0': '未设置',
            '1': '启用',
            'null': '未设置'
        }
        return dnt_values.get(str(dnt), str(dnt))

    def get_resolution_type_text(self, res_type):
        """获取分辨率类型文本"""
        types = {
            '0': '自动',
            '1': '自定义'
        }
        return types.get(str(res_type), str(res_type))

    def get_position_text(self, position):
        """获取地理位置文本"""
        positions = {
            '0': '询问',
            '1': '允许',
            '2': '阻止'
        }
        return positions.get(str(position), str(position))

    def get_webrtc_text(self, webrtc):
        """获取WebRTC文本"""
        webrtc_values = {
            '0': '真实',
            '1': '替换',
            '2': '禁用'
        }
        return webrtc_values.get(str(webrtc), str(webrtc))

    def get_canvas_text(self, canvas):
        """获取Canvas文本"""
        canvas_values = {
            '0': '真实',
            '1': '噪声',
            '2': '阻止'
        }
        return canvas_values.get(str(canvas), str(canvas))

    def get_webgl_text(self, webgl):
        """获取WebGL文本"""
        webgl_values = {
            '0': '真实',
            '1': '噪声',
            '2': '阻止'
        }
        return webgl_values.get(str(webgl), str(webgl))

    def get_webgl_meta_text(self, meta):
        """获取WebGL元数据文本"""
        meta_values = {
            '0': '真实',
            '1': '掩码'
        }
        return meta_values.get(str(meta), str(meta))

    def get_audio_context_text(self, audio):
        """获取AudioContext文本"""
        audio_values = {
            '0': '真实',
            '1': '噪声'
        }
        return audio_values.get(str(audio), str(audio))

    def get_media_device_text(self, media):
        """获取媒体设备文本"""
        media_values = {
            '0': '真实',
            '1': '掩码'
        }
        return media_values.get(str(media), str(media))

    def get_speech_voices_text(self, speech):
        """获取语音合成文本"""
        speech_values = {
            '0': '真实',
            '1': '掩码'
        }
        return speech_values.get(str(speech), str(speech))

    def get_font_type_text(self, font_type):
        """获取字体类型文本"""
        font_types = {
            '0': '真实',
            '1': '自定义',
            '2': '自动'
        }
        return font_types.get(str(font_type), str(font_type))

    def get_port_scan_protect_text(self, protect):
        """获取端口扫描保护文本"""
        protect_values = {
            '0': '禁用',
            '1': '启用'
        }
        return protect_values.get(str(protect), str(protect))

    def copy_browser_id(self, browser):
        """复制浏览器ID到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(browser['id'])
        self.log_message(f"📋 已复制浏览器ID: {browser['id']}")

    def show_browser_details(self, browser):
        """显示浏览器详细信息"""
        def run():
            try:
                # 获取完整的浏览器详情
                self.log_message(f"正在获取详细信息: {browser.get('name')}")
                full_details = self.api.get_browser_detail(browser['id'])

                if full_details:
                    self.display_detailed_info(full_details)
                else:
                    # 如果API获取失败，使用现有数据
                    self.display_detailed_info(browser)

            except Exception as e:
                self.log_message(f"获取详细信息失败: {e}")
                # 使用现有数据作为备选
                self.display_detailed_info(browser)

        threading.Thread(target=run, daemon=True).start()

    def display_detailed_info(self, browser):
        """显示详细信息窗口"""
        # 先计算居中位置
        window_width = 1000
        window_height = 800
        x = (self.root.winfo_screenwidth() // 2) - (window_width // 2)
        y = (self.root.winfo_screenheight() // 2) - (window_height // 2)
        
        details_window = tk.Toplevel(self.root)
        details_window.title(f"浏览器详情 - {browser.get('name')}")
        details_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        details_window.resizable(True, True)

        # 创建滚动文本框
        text_frame = ttk.Frame(details_window, padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True)

        details_text = tk.Text(text_frame, wrap=tk.WORD, font=('Consolas', 9))
        details_scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=details_text.yview)
        details_text.configure(yscrollcommand=details_scrollbar.set)

        # 获取浏览器指纹信息
        fingerprint = browser.get('browserFingerPrint', {})

        # 格式化浏览器完整信息
        info = f"""🌐 浏览器实例详细配置信息
{'='*84}

📋 基本信息
{'─'*84}
实例名称: {browser.get('name', 'Unknown')}
实例ID: {browser.get('id', 'Unknown')}
序号: {browser.get('seq', 'Unknown')}
代码: {browser.get('code', 'Unknown')}
平台: {browser.get('platform', '自定义平台') or '自定义平台'}
平台图标: {browser.get('platformIcon', 'other')}
URL: {browser.get('url', '无')}
备注: {browser.get('remark', '无')}
运行状态: {'🟢 运行中' if browser.get('is_running', False) else '⚪ 已停止'}
进程ID: {browser.get('pid', '无')}

📅 时间信息
{'─'*84}
创建时间: {browser.get('createdTime', 'Unknown')}
更新时间: {browser.get('updateTime', '无')}
操作时间: {browser.get('operTime', '无')}
关闭时间: {browser.get('closeTime', '无')}

🌍 网络与代理
{'─'*84}
代理方法: {self.get_proxy_method_text(browser.get('proxyMethod', 2))}
代理类型: {browser.get('proxyType', 'noproxy')}
代理主机: {browser.get('host', '无')}
代理端口: {browser.get('port', '无') if browser.get('port') else '无'}
代理用户名: {browser.get('proxyUserName', '无')}
代理密码: {'已设置' if browser.get('proxyPassword') else '无'}
最后IP: {browser.get('lastIp', '无')}
最后国家: {browser.get('lastCountry', '无')}
IP检查服务: {browser.get('ipCheckService', 'IP2Location')}
IPv6: {'是' if browser.get('isIpv6', False) else '否'}

👤 账号信息
{'─'*84}
用户名: {browser.get('userName', '无')}
密码: {'已设置' if browser.get('password') else '无'}
Cookie: {'已设置' if browser.get('cookie') else '无'}
其他Cookie: {'已设置' if browser.get('otherCookie') else '无'}

🔧 浏览器配置
{'─'*84}
浏览器核心: {browser.get('coreProduct', 'chrome')}
核心版本: {browser.get('coreVersion', '134')}
操作系统: {browser.get('os', 'Win32')}
系统类型: {browser.get('ostype', 'PC')}
工作台: {self.get_workbench_text(browser.get('workbench', 'localserver'))}
随机指纹: {'是' if browser.get('randomFingerprint', False) else '否'}

🔄 同步设置
{'─'*84}
同步标签页: {'是' if browser.get('syncTabs', False) else '否'}
同步Cookie: {'是' if browser.get('syncCookies', False) else '否'}
同步书签: {'是' if browser.get('syncBookmarks', False) else '否'}
同步历史: {'是' if browser.get('syncHistory', False) else '否'}
同步扩展: {'是' if browser.get('syncExtensions', False) else '否'}
同步本地存储: {'是' if browser.get('syncLocalStorage', False) else '否'}
同步IndexedDB: {'是' if browser.get('syncIndexedDb', False) else '否'}
同步Google账号: {'是' if browser.get('syncGoogleAccount', False) else '否'}

🛡️ 安全与隐私
{'─'*84}
允许登录: {'是' if browser.get('allowedSignin', False) else '否'}
禁用GPU: {'是' if browser.get('disableGpu', False) else '否'}
静音音频: {'是' if browser.get('muteAudio', False) else '否'}
阻止图片: {'是' if browser.get('abortImage', False) else '否'}
阻止媒体: {'是' if browser.get('abortMedia', False) else '否'}
禁用通知: {'是' if browser.get('disableNotifications', False) else '否'}
禁用剪贴板: {'是' if browser.get('disableClipboard', False) else '否'}
Do Not Track: {self.get_dnt_text(browser.get('doNotTrack', '0'))}

🧹 清理设置
{'─'*84}
启动前清理缓存: {'是' if browser.get('clearCacheFilesBeforeLaunch', False) else '否'}
启动前清理Cookie: {'是' if browser.get('clearCookiesBeforeLaunch', False) else '否'}
启动前清理历史: {'是' if browser.get('clearHistoriesBeforeLaunch', False) else '否'}

🌍 网络与代理
{'─'*40}
代理方法: {browser.get('proxyMethod', 'Unknown')}
代理类型: {browser.get('proxyType', 'Unknown')}
代理主机: {browser.get('host', '无')}
代理端口: {browser.get('port', '无')}
代理用户名: {browser.get('proxyUserName', '无')}
最后IP: {browser.get('lastIp', '无')}
最后国家: {browser.get('lastCountry', '无')}
IP检查服务: {browser.get('ipCheckService', 'Unknown')}
IPv6: {'是' if browser.get('isIpv6', False) else '否'}

👤 账号信息
{'─'*40}
用户名: {browser.get('userName', '无')}
密码: {'已设置' if browser.get('password') else '无'}
Cookie: {'已设置' if browser.get('cookie') else '无'}
其他Cookie: {'已设置' if browser.get('otherCookie') else '无'}

🔧 浏览器配置
{'─'*40}
浏览器核心: {browser.get('coreProduct', 'Unknown')}
核心版本: {browser.get('coreVersion', 'Unknown')}
操作系统: {browser.get('os', 'Unknown')}
系统类型: {browser.get('ostype', 'Unknown')}
工作台: {browser.get('workbench', 'Unknown')}
随机指纹: {'是' if browser.get('randomFingerprint', False) else '否'}

🔄 同步设置
{'─'*40}
同步标签页: {'是' if browser.get('syncTabs', False) else '否'}
同步Cookie: {'是' if browser.get('syncCookies', False) else '否'}
同步书签: {'是' if browser.get('syncBookmarks', False) else '否'}
同步历史: {'是' if browser.get('syncHistory', False) else '否'}
同步扩展: {'是' if browser.get('syncExtensions', False) else '否'}
同步本地存储: {'是' if browser.get('syncLocalStorage', False) else '否'}
同步IndexedDB: {'是' if browser.get('syncIndexedDb', False) else '否'}
同步Google账号: {'是' if browser.get('syncGoogleAccount', False) else '否'}

🛡️ 安全与隐私
{'─'*40}
允许登录: {'是' if browser.get('allowedSignin', False) else '否'}
禁用GPU: {'是' if browser.get('disableGpu', False) else '否'}
静音音频: {'是' if browser.get('muteAudio', False) else '否'}
阻止图片: {'是' if browser.get('abortImage', False) else '否'}
阻止媒体: {'是' if browser.get('abortMedia', False) else '否'}
禁用通知: {'是' if browser.get('disableNotifications', False) else '否'}
禁用剪贴板: {'是' if browser.get('disableClipboard', False) else '否'}
Do Not Track: {browser.get('doNotTrack', '0')}

🧹 清理设置
{'─'*40}
启动前清理缓存: {'是' if browser.get('clearCacheFilesBeforeLaunch', False) else '否'}
启动前清理Cookie: {'是' if browser.get('clearCookiesBeforeLaunch', False) else '否'}
启动前清理历史: {'是' if browser.get('clearHistoriesBeforeLaunch', False) else '否'}

👆 指纹配置
{'─'*84}"""

        # 如果有指纹信息，添加详细指纹配置
        if fingerprint:
            info += f"""
User-Agent: {fingerprint.get('userAgent', '自动生成')}
操作系统版本: {fingerprint.get('version', '自动')}
屏幕分辨率: {fingerprint.get('resolution', '1920 x 1080')}
窗口大小: {fingerprint.get('openWidth', 1280)} x {fingerprint.get('openHeight', 720)}
设备像素比: {fingerprint.get('devicePixelRatio', 1)}
分辨率类型: {self.get_resolution_type_text(fingerprint.get('resolutionType', '0'))}
窗口大小限制: {'是' if fingerprint.get('windowSizeLimit', True) else '否'}

🌍 地理位置与时区
{'─'*84}
时区: {fingerprint.get('timeZone', '自动') or 'Asia/Shanghai'}
时区偏移: {fingerprint.get('timeZoneOffset', -480)}
IP创建时区: {'是' if fingerprint.get('isIpCreateTimeZone', True) else '否'}
地理位置: {self.get_position_text(fingerprint.get('position', '1'))}
IP创建位置: {'是' if fingerprint.get('isIpCreatePosition', True) else '否'}
纬度: {fingerprint.get('lat', '自动')}
经度: {fingerprint.get('lng', '自动')}
精度数据: {fingerprint.get('precisionData', '自动')}

🗣️ 语言设置
{'─'*84}
语言: {fingerprint.get('languages', '自动') or 'zh-CN'}
IP创建语言: {'是' if fingerprint.get('isIpCreateLanguage', True) else '否'}
显示语言: {fingerprint.get('displayLanguages', '自动') or 'zh-CN'}
IP创建显示语言: {'是' if fingerprint.get('isIpCreateDisplayLanguage', False) else '否'}

🖥️ 硬件信息
{'─'*84}
硬件并发: {fingerprint.get('hardwareConcurrency', 4)}
设备内存: {fingerprint.get('deviceMemory', 8)}GB
Do Not Track: {self.get_dnt_text(fingerprint.get('doNotTrack', '0'))}

🎨 图形与渲染
{'─'*84}
WebRTC: {self.get_webrtc_text(fingerprint.get('webRTC', '0'))}
Canvas: {self.get_canvas_text(fingerprint.get('canvas', '0'))}
Canvas值: {fingerprint.get('canvasValue', '自动')}
WebGL: {self.get_webgl_text(fingerprint.get('webGL', '0'))}
WebGL值: {fingerprint.get('webGLValue', '自动')}
WebGL元数据: {self.get_webgl_meta_text(fingerprint.get('webGLMeta', '0'))}
WebGL厂商: {fingerprint.get('webGLManufacturer', '自动')}
WebGL渲染器: {fingerprint.get('webGLRender', '自动')}

🔊 音频系统
{'─'*84}
AudioContext: {self.get_audio_context_text(fingerprint.get('audioContext', '0'))}
AudioContext值: {fingerprint.get('audioContextValue', '自动')}
媒体设备: {self.get_media_device_text(fingerprint.get('mediaDevice', '0'))}
媒体设备值: {fingerprint.get('mediaDeviceValue', '自动')}
语音合成: {self.get_speech_voices_text(fingerprint.get('speechVoices', '0'))}
语音合成值: {fingerprint.get('speechVoicesValue', '自动')}

🔤 字体设置
{'─'*84}
字体类型: {self.get_font_type_text(fingerprint.get('fontType', '2'))}
字体: {fingerprint.get('font', '自动')}

🛡️ 隐私保护
{'─'*84}
客户端矩形噪声: {'启用' if fingerprint.get('clientRectNoiseEnabled', True) else '禁用'}
客户端矩形噪声值: {fingerprint.get('clientRectNoiseValue', 0)}
端口扫描保护: {self.get_port_scan_protect_text(fingerprint.get('portScanProtect', '0'))}
端口白名单: {fingerprint.get('portWhiteList', '无')}
设备信息启用: {'是' if fingerprint.get('deviceInfoEnabled', True) else '否'}
忽略HTTPS错误: {'是' if fingerprint.get('ignoreHttpsErrors', False) else '否'}

💻 系统信息
{'─'*84}
计算机名: {fingerprint.get('computerName', '自动')}
MAC地址: {fingerprint.get('macAddr', '自动')}
禁用SSL密码套件: {'是' if fingerprint.get('disableSslCipherSuitesFlag', False) else '否'}
SSL密码套件: {fingerprint.get('disableSslCipherSuites', '无')}

🔌 插件设置
{'─'*84}
启用插件: {'是' if fingerprint.get('enablePlugins', False) else '否'}
插件列表: {fingerprint.get('plugins', '无')}
"""
        else:
            info += """
未找到指纹配置信息
"""

        info += f"""

👥 用户信息
{'─'*40}
创建者: {browser.get('createdName', 'Unknown')}
创建者ID: {browser.get('createdBy', 'Unknown')}
用户ID: {browser.get('userId', 'Unknown')}
主用户ID: {browser.get('mainUserId', 'Unknown')}
更新者: {browser.get('updateName', '无')}
操作者: {browser.get('operUserName', '无')}

🏷️ 其他信息
{'─'*40}
是否删除: {'是' if browser.get('isDelete', 0) == 1 else '否'}
删除原因: {browser.get('delReason', '无')}
是否共享: {'是' if browser.get('isShare', 0) == 1 else '否'}
排序: {browser.get('sort', 0)}
备注类型: {browser.get('remarkType', 'Unknown')}
是否属于我: {'是' if browser.get('belongToMe', False) else '否'}
有效用户名: {'是' if browser.get('isValidUsername', False) else '否'}
创建数量: {browser.get('createNum', 0)}
是否随机指纹: {'是' if browser.get('isRandomFinger', False) else '否'}

{'='*80}
"""

        details_text.insert(tk.END, info)
        details_text.config(state=tk.DISABLED)

        details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        details_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮框架
        button_frame = ttk.Frame(details_window)
        button_frame.pack(fill=tk.X, pady=10)

        # 复制信息按钮
        ttk.Button(button_frame, text="📋 复制信息",
                  command=lambda: self.copy_browser_details(info)).pack(side=tk.LEFT, padx=(0, 10))

        # 关闭按钮
        ttk.Button(button_frame, text="关闭", command=details_window.destroy).pack(side=tk.RIGHT)

    def copy_browser_details(self, info):
        """复制浏览器详细信息到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(info)
        self.log_message("📋 浏览器详细信息已复制到剪贴板")
    
    def show_browser_menu(self, browser):
        """显示浏览器操作菜单"""
        menu = tk.Toplevel(self.root)
        menu.title(f"浏览器操作 - {browser.get('name')}")
        menu.geometry("300x200")
        menu.resizable(False, False)
        
        # 居中显示
        menu.transient(self.root)
        menu.grab_set()
        
        ttk.Label(menu, text=f"浏览器: {browser.get('name')}", font=('Arial', 12, 'bold')).pack(pady=10)
        
        if browser.get('is_running', False):
            ttk.Button(menu, text="关闭浏览器", command=lambda: [self.close_single_browser(browser), menu.destroy()]).pack(pady=5)
        else:
            ttk.Button(menu, text="打开浏览器", command=lambda: [self.open_single_browser(browser), menu.destroy()]).pack(pady=5)

        ttk.Button(menu, text="删除浏览器", command=lambda: [self.delete_single_browser(browser), menu.destroy()]).pack(pady=5)
        ttk.Button(menu, text="取消", command=menu.destroy).pack(pady=10)
    
    def open_single_browser(self, browser):
        """打开单个浏览器"""
        def run():
            try:
                self.log_message(f"正在打开浏览器: {browser.get('name')}")

                # [HOT] 添加重试机制处理"浏览器正在打开中"错误
                max_retries = 3
                retry_delay = 5  # 秒

                for attempt in range(max_retries):
                    result = self.api.open_browser(browser['id'])
                    if result:
                        self.log_message(f"✅ 浏览器打开成功: {browser.get('name')}")
                        # [HOT] 记录浏览器启动时间
                        from datetime import datetime
                        browser_id = browser['id']
                        if browser_id in self.browsers:
                            self.browsers[browser_id]['start_time'] = datetime.now()
                        break
                    else:
                        if attempt < max_retries - 1:
                            self.log_message(f"⏳ 浏览器正在启动中，{retry_delay}秒后重试... ({attempt + 1}/{max_retries})")
                            time.sleep(retry_delay)
                        else:
                            self.log_message(f"[ERROR] 浏览器打开失败: {browser.get('name')} (已重试{max_retries}次)")

                self.refresh_browsers()

            except Exception as e:
                self.log_message(f"打开浏览器失败: {e}")

        threading.Thread(target=run, daemon=True).start()
    
    def close_single_browser(self, browser):
        """关闭单个浏览器"""
        def run():
            try:
                self.log_message(f"正在关闭浏览器: {browser.get('name')}")
                
                # [HOT] 第一步：停止该浏览器的手动解析模式
                browser_id = browser['id']
                self.log_message(f"🛑 停止浏览器 {browser.get('name')} 的手动解析模式...")
                
                try:
                    # 尝试通过sd.py停止手动解析
                    import sys
                    import os
                    
                    # 构建sd.py的路径
                    sd_path = os.path.join(
                        os.path.dirname(__file__), 
                        "..", 
                        "generated_scripts", 
                        f"browser_{browser_id}", 
                        "sd.py"
                    )
                    
                    if os.path.exists(sd_path):
                        # 将sd.py所在目录添加到Python路径
                        sd_dir = os.path.dirname(sd_path)
                        if sd_dir not in sys.path:
                            sys.path.insert(0, sd_dir)
                        
                        try:
                            # 使用统一的方法停止手动解析
                            self._stop_manual_extraction_for_browser(browser_id)
                            
                        except Exception as e:
                            self.log_message(f"⚠️ 停止浏览器 {browser.get('name')} 手动解析失败: {e}")
                    
                    # 从手动抓取进程字典中移除
                    if hasattr(self, 'manual_extraction_processes') and browser_id in self.manual_extraction_processes:
                        del self.manual_extraction_processes[browser_id]
                        
                except Exception as e:
                    self.log_message(f"⚠️ 停止手动解析时出错: {e}")

                # 第二步：关闭浏览器
                if self.api.close_browser(browser['id']):
                    self.log_message(f"✅ 浏览器关闭成功: {browser.get('name')}")
                    
                    # [HOT] 第三步：清除启动时间记录
                    browser_id = browser['id']
                    if browser_id in self.browsers and 'start_time' in self.browsers[browser_id]:
                        del self.browsers[browser_id]['start_time']
                        self.log_message(f"🧹 清除浏览器启动时间记录: {browser.get('name')}")
                else:
                    self.log_message(f"[ERROR] 浏览器关闭失败: {browser.get('name')}")

                self.refresh_browsers()

            except Exception as e:
                self.log_message(f"关闭浏览器失败: {e}")

        threading.Thread(target=run, daemon=True).start()
    
    def pause_single_browser(self, browser):
        """暂停单个浏览器的自动化任务"""
        def run():
            try:
                self.log_message(f"正在暂停浏览器自动化任务: {browser.get('name')}")
                
                # 获取浏览器ID
                browser_id = browser['id']
                
                # 检查是否有脚本在运行
                script_processes = self._find_browser_script_processes(browser_id)
                
                if script_processes:
                    # 暂停脚本进程
                    for process in script_processes:
                        try:
                            process.suspend()  # 暂停进程
                            self.log_message(f"✅ 已暂停脚本进程: PID {process.pid}")
                        except Exception as e:
                            self.log_message(f"⚠️ 暂停进程失败 PID {process.pid}: {e}")
                    
                    self.log_message(f"✅ 浏览器自动化任务已暂停: {browser.get('name')}")
                else:
                    self.log_message(f"[INFO] 未找到运行中的脚本进程: {browser.get('name')}")
                
                # 刷新浏览器状态
                self.refresh_browsers()
                
            except Exception as e:
                self.log_message(f"暂停浏览器自动化任务失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def _find_browser_script_processes(self, browser_id):
        """查找浏览器相关的脚本进程"""
        try:
            script_processes = []
            
            # [HOT] 改进进程查找逻辑，增加调试信息
            self.log_message(f"🔍 正在搜索浏览器 {browser_id[-6:]} 相关的脚本进程...")
            found_processes = 0
            
            for process in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if process.info['name'] and 'python' in process.info['name'].lower():
                        cmdline = process.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(str(arg) for arg in cmdline)
                            
                            # [HOT] 扩展脚本名称列表，包含可能的脚本文件
                            browser_scripts = [
                                'pdd_search_simple.py', 'product_clicker.py', 'zq.py',
                                'jiex.py', 'sd.py', 'workflow_manager.py', 'shib.py',
                                'suoyin.py', 'pdd_goods_scraper_final.py', 
                                'real_data_jx_system_regex.py'
                            ]
                            
                            # 方法1: 检查命令行是否包含完整浏览器ID
                            if browser_id in cmdline_str:
                                script_processes.append(process)
                                found_processes += 1
                                self.log_message(f"   ✅ 发现进程 PID {process.pid}: {process.info['name']} (匹配浏览器ID)")
                                continue
                            
                            # 方法2: 检查是否包含浏览器相关脚本
                            for script_name in browser_scripts:
                                if script_name in cmdline_str:
                                    # 进一步检查是否在浏览器目录下运行
                                    if f'browser_{browser_id}' in cmdline_str or browser_id[-6:] in cmdline_str:
                                        script_processes.append(process)
                                        found_processes += 1
                                        self.log_message(f"   ✅ 发现进程 PID {process.pid}: {script_name} (匹配浏览器目录)")
                                        break
                            
                            # 方法3: 检查工作目录是否在浏览器文件夹中
                            try:
                                if hasattr(process, 'cwd'):
                                    cwd = process.cwd()
                                    if f'browser_{browser_id}' in cwd and any(script in cmdline_str for script in browser_scripts):
                                        if process not in script_processes:  # 避免重复添加
                                            script_processes.append(process)
                                            found_processes += 1
                                            self.log_message(f"   ✅ 发现进程 PID {process.pid}: 工作目录匹配")
                            except:
                                pass
                            
                            # [HOT] 方法4: 检查进程是否在generated_scripts目录下运行
                            try:
                                if hasattr(process, 'cwd'):
                                    cwd = process.cwd()
                                    if 'generated_scripts' in cwd and any(script in cmdline_str for script in browser_scripts):
                                        # 检查是否在对应浏览器目录下
                                        if f'browser_{browser_id}' in cwd:
                                            if process not in script_processes:  # 避免重复添加
                                                script_processes.append(process)
                                                found_processes += 1
                                                self.log_message(f"   ✅ 发现进程 PID {process.pid}: generated_scripts目录匹配")
                            except:
                                pass
                            
                            # [HOT] 方法5: 检查进程是否在主目录下运行但包含浏览器ID参数
                            try:
                                if hasattr(process, 'cwd'):
                                    cwd = process.cwd()
                                    # 如果进程在主目录下运行，检查命令行是否包含浏览器ID
                                    if cwd == os.path.dirname(__file__) and any(script in cmdline_str for script in browser_scripts):
                                        if browser_id[-6:] in cmdline_str:  # 使用短ID匹配
                                            if process not in script_processes:  # 避免重复添加
                                                script_processes.append(process)
                                                found_processes += 1
                                                self.log_message(f"   ✅ 发现进程 PID {process.pid}: 主目录+浏览器ID匹配")
                            except:
                                pass
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            self.log_message(f"🔍 搜索完成，找到 {found_processes} 个相关进程")
            return script_processes
        except Exception as e:
            self.log_message(f"[ERROR] 查找脚本进程失败: {e}")
            return []
    
    def start_manual_extraction(self, browser):
        """[HOT] 统一的手动解析模式启动方法"""
        def run():
            try:
                # 获取浏览器ID
                browser_id = browser['id']
                browser_id_short = browser_id[-6:] if len(browser_id) > 6 else browser_id
                
                # [HOT] 第一步：暂停自动化任务
                self.log_message(f"🔄 正在暂停浏览器 {browser_id_short} 的自动化任务...")
                script_processes = self._find_browser_script_processes(browser_id)
                paused_count = 0
                
                if script_processes:
                    for process in script_processes:
                        try:
                            process.suspend()
                            paused_count += 1
                            self.log_message(f"✅ 已暂停脚本进程: PID {process.pid}")
                            # [HOT] 更新浏览器暂停状态和创建暂停标志文件
                            self._update_browser_pause_status(browser_id, True)
                            self._create_pause_flag_file(browser_id)
                        except Exception as e:
                            self.log_message(f"⚠️ 暂停进程失败 PID {process.pid}: {e}")
                    
                    if paused_count > 0:
                        self.log_message(f"✅ 已暂停 {paused_count} 个脚本进程")
                    else:
                        self.log_message(f"[INFO] 没有找到需要暂停的脚本进程")
                else:
                    self.log_message(f"[INFO] 未找到运行中的脚本进程，继续启动手动解析")
                
                # [HOT] 第二步：启动统一的手动解析功能
                try:
                    success = self._start_unified_manual_extraction(browser_id)
                    if success:
                        self.log_message(f"✅ 浏览器 {browser_id_short} 的手动解析功能已启动")
                    else:
                        self.log_message(f"[ERROR] 浏览器 {browser_id_short} 的手动解析启动失败")
                except Exception as e:
                    self.log_message(f"启动手动解析模式失败: {e}")
                
            except Exception as e:
                self.log_message(f"启动手动解析模式失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def _start_unified_manual_extraction(self, browser_id: str) -> bool:
        """[HOT] 统一的手动解析功能启动方法"""
        try:
            # [HOT] 第一步：检查并关闭其他浏览器的手动解析
            if hasattr(self, 'manual_extraction_processes') and self.manual_extraction_processes:
                other_browsers = [bid for bid in self.manual_extraction_processes.keys() if bid != browser_id]
                if other_browsers:
                    self.log_message(f"🔄 检测到其他浏览器正在运行手动解析，正在关闭...")
                    for other_browser_id in other_browsers:
                        try:
                            self._stop_manual_extraction_for_browser(other_browser_id)
                            del self.manual_extraction_processes[other_browser_id]
                        except Exception as e:
                            self.log_message(f"⚠️ 关闭浏览器 {other_browser_id[-6:]} 手动解析失败: {e}")
                    self.log_message(f"✅ 其他浏览器的手动解析已全部关闭")
            
            # [HOT] 第二步：清理状态文件，确保可以启动
            self._clear_manual_extraction_status(browser_id)
            
            # [HOT] 第三步：启动当前浏览器的手动解析
            success = self._start_manual_extraction_for_browser(browser_id)
            if success:
                # 保存到手动抓取进程字典（用于状态管理）
                if not hasattr(self, 'manual_extraction_processes'):
                    self.manual_extraction_processes = {}
                self.manual_extraction_processes[browser_id] = {
                    'type': 'unified',
                    'browser_id': browser_id,
                    'status': 'running',
                    'start_time': time.time()
                }
                return True
            else:
                return False
                
        except Exception as e:
            self.log_message(f"[ERROR] 统一手动解析启动失败: {e}")
            return False

    def _start_manual_extraction_for_browser(self, browser_id: str) -> bool:
        """[HOT] 为指定浏览器启动手动解析功能"""
        try:
                            # 构建sd.py的路径
            sd_path = os.path.join(
                                os.path.dirname(__file__), 
                                "..", 
                                "generated_scripts", 
                f"browser_{browser_id}", 
                                "sd.py"
                            )
                            
            if not os.path.exists(sd_path):
                self.log_message(f"[ERROR] 找不到sd.py文件: {sd_path}")
                return False
            
                                # 将sd.py所在目录添加到Python路径
            sd_dir = os.path.dirname(sd_path)
            if sd_dir not in sys.path:
                sys.path.insert(0, sd_dir)
            
                                    # 导入sd.py模块
            import sd
                                    
            # 启动手动抓取模式，传递UI日志回调
            success = sd.start_manual_mode(browser_id, self.log_message)
            
            if success:
                self.log_message(f"✅ 浏览器 {browser_id[-6:]} 的手动解析已启动")
                return True
            else:
                self.log_message(f"[ERROR] 浏览器 {browser_id[-6:]} 的手动解析启动失败")
                return False
                            
        except Exception as e:
            self.log_message(f"[ERROR] 启动浏览器 {browser_id[-6:]} 手动解析失败: {e}")
            return False

    def _clear_manual_extraction_status(self, browser_id: str):
        """[HOT] 清理手动解析状态文件"""
        try:
            # 清理状态文件
            status_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "manual_extraction_status.json"
            )
            
            if os.path.exists(status_file):
                os.remove(status_file)
                self.log_message(f"✅ 已清理浏览器 {browser_id[-6:]} 的手动解析状态文件")
                
            # 清理主目录的状态文件
            main_status_file = os.path.join(
                os.path.dirname(__file__), 
                "manual_extraction_status.json"
            )
            
            if os.path.exists(main_status_file):
                try:
                    import json
                    with open(main_status_file, 'r', encoding='utf-8') as f:
                        status_data = json.load(f)
                    
                    if browser_id in status_data:
                        del status_data[browser_id]
                        
                    with open(main_status_file, 'w', encoding='utf-8') as f:
                        json.dump(status_data, f, ensure_ascii=False, indent=2)
                        
                    self.log_message(f"✅ 已清理主目录中浏览器 {browser_id[-6:]} 的状态记录")
                except Exception as e:
                    self.log_message(f"⚠️ 清理主目录状态文件失败: {e}")
                
        except Exception as e:
            self.log_message(f"⚠️ 清理状态文件失败: {e}")
    
    def _stop_manual_extraction_for_browser(self, browser_id: str) -> bool:
        """[HOT] 为指定浏览器停止手动解析功能"""
        try:
                    # 构建sd.py的路径
                    sd_path = os.path.join(
                        os.path.dirname(__file__), 
                        "..", 
                        "generated_scripts", 
                        f"browser_{browser_id}", 
                        "sd.py"
                    )
                    
                    if not os.path.exists(sd_path):
                        return False
            
                    # 将sd.py所在目录添加到Python路径
                    sd_dir = os.path.dirname(sd_path)
                    if sd_dir not in sys.path:
                        sys.path.insert(0, sd_dir)
                    
                    # 导入sd.py模块
                    import sd
                    
                    # 停止手动抓取模式
                    sd.stop_manual_mode(browser_id)
                    
                    self.log_message(f"✅ 浏览器 {browser_id[-6:]} 的手动解析已停止")
                    return True
            
        except Exception as e:
            self.log_message(f"[ERROR] 停止浏览器 {browser_id[-6:]} 手动解析失败: {e}")
            return False
            

    
    def start_auto_extraction(self, browser):
        """启动自动解析模式"""
        def run():
            try:
                self.log_message(f"正在启动自动解析模式: {browser.get('name')}")
                
                # 获取浏览器ID
                browser_id = browser['id']
                browser_id_short = browser_id[-6:] if len(browser_id) > 6 else browser_id
                
                # 恢复暂停的自动化任务
                self.log_message(f"▶️️ 恢复浏览器自动化任务: {browser.get('name')}")
                script_processes = self._find_browser_script_processes(browser_id)
                
                if script_processes:
                    for process in script_processes:
                        try:
                            # 添加超时处理，避免卡死
                            import threading
                            import time
                            
                            def resume_with_timeout(proc, timeout=5):
                                try:
                                    proc.resume()
                                    return True
                                except Exception as e:
                                    return False
                            
                            # 在后台线程中恢复进程，避免卡死
                            resume_thread = threading.Thread(
                                target=resume_with_timeout, 
                                args=(process, 5), 
                                daemon=True
                            )
                            resume_thread.start()
                            resume_thread.join(timeout=5)  # 最多等待5秒
                            
                            if resume_thread.is_alive():
                                self.log_message(f"⚠️ 恢复进程超时 PID {process.pid}，强制终止")
                                try:
                                    process.terminate()
                                    process.wait(timeout=3)
                                except:
                                    pass
                            else:
                                self.log_message(f"✅ 已恢复脚本进程: PID {process.pid}")
                                
                        except Exception as e:
                            self.log_message(f"⚠️ 恢复进程失败 PID {process.pid}: {e}")
                else:
                    # 如果没有找到暂停的进程，重新启动自动化脚本
                    self.log_message(f"🔄 重新启动自动化脚本: {browser_id_short}")
                    self._restart_automation_script(browser)
                
                # 停止手动解析模式
                self.log_message(f"🛑 正在停止手动解析模式...")
                try:
                    # 导入sd.py模块来停止手动解析
                    import sys
                    import os
                    
                    # 构建sd.py的路径
                    sd_path = os.path.join(
                        os.path.dirname(__file__), 
                        "..", 
                        "generated_scripts", 
                        f"browser_{browser_id}", 
                        "sd.py"
                    )
                    
                    if os.path.exists(sd_path):
                        # 使用统一的方法停止手动解析
                        self._stop_manual_extraction_for_browser(browser_id)
                    else:
                        self.log_message(f"⚠️ 找不到sd.py文件，无法停止手动解析")
                        
                except Exception as e:
                    self.log_message(f"⚠️ 停止手动解析模式时出错: {e}")
                
                # 从手动抓取进程字典中移除
                if hasattr(self, 'manual_extraction_processes') and browser_id in self.manual_extraction_processes:
                    del self.manual_extraction_processes[browser_id]
                
                self.log_message(f"✅ 自动解析模式已启动: {browser.get('name')}")
                
                # 刷新浏览器状态
                self.refresh_browsers()
                
            except Exception as e:
                self.log_message(f"启动自动解析模式失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def _restart_automation_script(self, browser):
        """重新启动自动化脚本"""
        try:
            browser_id = browser['id']
            browser_id_short = browser_id[-6:] if len(browser_id) > 6 else browser_id
            
            # 构建自动化脚本路径
            script_path = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "pdd_search_simple.py"
            )
            
            if os.path.exists(script_path):
                import subprocess
                import sys
                # 启动自动化脚本
                cmd = [sys.executable, script_path]
                process = subprocess.Popen(
                    cmd,
                    cwd=os.path.dirname(script_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                # 验证进程是否成功启动
                try:
                    # 等待一小段时间检查进程状态
                    import time
                    time.sleep(0.5)
                    
                    if process.poll() is None:  # 进程还在运行
                        self.log_message(f"✅ 自动化脚本重新启动成功: PID {process.pid}")
                        self.log_message(f"📁 脚本路径: {script_path}")
                    else:
                        # 进程异常退出
                        return_code = process.poll()
                        self.log_message(f"[ERROR] 自动化脚本启动失败，返回码: {return_code}")
                        # 尝试读取错误信息
                        try:
                            stderr_output = process.stderr.read().decode('utf-8', errors='ignore')
                            if stderr_output:
                                self.log_message(f"错误信息: {stderr_output[:200]}...")
                        except:
                            pass
                except Exception as e:
                    self.log_message(f"⚠️ 验证进程状态失败: {e}")
                
            else:
                self.log_message(f"[ERROR] 自动化脚本不存在: {script_path}")
                
        except Exception as e:
            self.log_message(f"重新启动自动化脚本失败: {e}")
    
    def stop_manual_extraction(self, browser):
        """停止手动解析模式"""
        def run():
            try:
                self.log_message(f"正在停止手动解析模式: {browser.get('name')}")
                
                # 获取浏览器ID
                browser_id = browser['id']
                
                # 停止手动抓取进程
                if hasattr(self, 'manual_extraction_processes') and browser_id in self.manual_extraction_processes:
                    process = self.manual_extraction_processes[browser_id]
                    try:
                        if process.poll() is None:  # 进程还在运行
                            process.terminate()  # 终止进程
                            self.log_message(f"✅ 手动抓取进程已终止: PID {process.pid}")
                        else:
                            self.log_message(f"[INFO] 手动抓取进程已结束: PID {process.pid}")
                        
                        # 从字典中移除
                        del self.manual_extraction_processes[browser_id]
                        
                    except Exception as e:
                        self.log_message(f"⚠️ 终止手动抓取进程失败: {e}")
                else:
                    self.log_message(f"[INFO] 未找到手动抓取进程: {browser.get('name')}")
                
                # 刷新浏览器状态
                self.refresh_browsers()
                
            except Exception as e:
                self.log_message(f"停止手动解析模式失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()

    def stop_all_manual_extraction(self):
        """停止所有浏览器的手动解析模式"""
        def run():
            try:
                self.log_message("🛑 正在停止所有浏览器的手动解析模式...")
                
                if not hasattr(self, 'manual_extraction_processes'):
                    self.log_message("[INFO] 没有运行中的手动解析进程")
                    return
                
                stopped_count = 0
                for browser_id, process_info in list(self.manual_extraction_processes.items()):
                    try:
                        # 尝试通过sd.py停止手动解析
                        import sys
                        import os
                        
                        # 构建sd.py的路径
                        sd_path = os.path.join(
                            os.path.dirname(__file__), 
                            "..", 
                            "generated_scripts", 
                            f"browser_{browser_id}", 
                            "sd.py"
                        )
                        
                        if os.path.exists(sd_path):
                            # 将sd.py所在目录添加到Python路径
                            sd_dir = os.path.dirname(sd_path)
                            if sd_dir not in sys.path:
                                sys.path.insert(0, sd_dir)
                            
                            try:
                                # 使用统一的方法停止手动解析
                                self._stop_manual_extraction_for_browser(browser_id)
                                stopped_count += 1
                                
                            except Exception as e:
                                self.log_message(f"⚠️ 停止浏览器 {browser_id[-6:]} 手动解析失败: {e}")
                        
                        # 从字典中移除
                        del self.manual_extraction_processes[browser_id]
                        
                    except Exception as e:
                        self.log_message(f"⚠️ 处理浏览器 {browser_id[-6:]} 时出错: {e}")
                
                if stopped_count > 0:
                    self.log_message(f"🎉 成功停止 {stopped_count} 个浏览器的手动解析")
                # [HOT] 简化：没有手动解析进程时不显示日志，避免干扰
                    
            except Exception as e:
                self.log_message(f"[ERROR] 停止所有手动解析失败: {e}")
        
        threading.Thread(target=run, daemon=True).start()
    
    def delete_single_browser(self, browser):
        """删除单个浏览器"""
        # [HOT] 添加确认弹窗
        try:
            import tkinter.messagebox as messagebox
            
            # 显示确认弹窗
            browser_name = browser.get('name', '未知浏览器')
            result = messagebox.askyesno(
                "确认删除", 
                f"确定要删除浏览器 '{browser_name}' 吗？\n\n此操作不可撤销！"
            )
            
            # 如果用户点击"否"，则不执行删除
            if not result:
                self.log_message(f"用户取消删除浏览器: {browser_name}")
                return
                
        except Exception as e:
            self.log_message(f"确认弹窗显示失败: {e}")
            # 如果弹窗失败，继续执行删除（保持原有行为）

        def run():
            try:
                self.log_message(f"正在删除浏览器: {browser.get('name')}")

                if self.api.delete_browser(browser['id']):
                    self.log_message(f"✅ 浏览器删除成功: {browser.get('name')}")
                else:
                    self.log_message(f"[ERROR] 浏览器删除失败: {browser.get('name')}")

                self.refresh_browsers()

            except Exception as e:
                self.log_message(f"删除浏览器失败: {e}")

        threading.Thread(target=run, daemon=True).start()
    
    def log_message(self, message):
        """添加日志消息 - [HOT] 优化版：只显示关键信息"""
        # [HOT] 日志过滤：只显示关键操作信息
        if not self._should_display_log(message):
            # 仍然记录到日志文件，但不显示在UI
            self.logger.info(message)
            return

        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        # 在主线程中更新UI
        self.root.after(0, lambda: self._append_log(log_entry))

        # 同时记录到日志文件
        self.logger.info(message)

    def _should_display_log(self, message):
        """[HOT] 判断是否应该在UI显示日志"""
        # [HOT] 只显示关键操作信息
        key_patterns = [
            # 浏览器操作
            "打开浏览器", "关闭浏览器", "✅ 浏览器打开成功", "✅ 浏览器关闭成功",
            "[ERROR] 浏览器打开失败", "[ERROR] 浏览器关闭失败",

            # 脚本操作
            "开始解析", "停止解析", "✅ 启动浏览器", "✅ 已停止脚本进程",
            "[HOT] 强制终止脚本进程", "🎉 所有脚本启动完成", "🎉 成功停止",

            # 过滤相关
            "关键词过滤", "旗舰店过滤", "品牌店过滤", "预售过滤", "销量过滤", "价格过滤",
            "过滤条件", "过滤结果", "商品过滤",

            # 商品解析成功
            "商品解析成功", "详情页数据抓取成功", "商品ID", "商品名称", "商品价格", "销量",
            "✅ 商品", "🔍 开始抓取商品",

            # 重要错误和成功信息
            "[ERROR] 错误", "[ERROR] 失败", "✅ 成功", "⚠️ 警告",

            # 脚本生成和启动
            "🚀 开始生成", "✅ 脚本生成完成", "📋 为", "个浏览器生成脚本"
        ]

        # [HOT] 过滤掉的无关信息
        ignore_patterns = [
            "正在刷新浏览器列表", "🔍 获取调试端口", "📋 开始创建右键菜单",
            "📋 菜单创建完成", "📋 右键菜单显示成功", "🖱️ 右键点击事件触发",
            "识别到项目ID", "界面显示名称", "找到浏览器数据", "准备显示菜单",
            "正在获取详细信息", "正在连接比特浏览器API", "API连接成功",
            "📊 API返回浏览器数量", "运行状态检测结果", "status=1", "检测到",
            "步骤1:", "步骤2:", "📊 待搜索关键词", "📋 启动策略", "⏰ 等待6秒"
        ]

        # 检查是否包含要显示的关键词
        for pattern in key_patterns:
            if pattern in message:
                return True

        # 检查是否包含要忽略的词
        for pattern in ignore_patterns:
            if pattern in message:
                return False

        # 默认显示（保险起见）
        return True

    def _append_log(self, log_entry):
        """[HOT] 在主线程中添加日志 - 限制显示5条避免卡顿"""
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

        # [HOT] 限制UI显示最多5条日志，避免卡顿
        lines = self.log_text.get("1.0", tk.END).split('\n')
        # 过滤空行
        non_empty_lines = [line for line in lines if line.strip()]

        if len(non_empty_lines) > 5:
            # 保留最新的5条日志
            self.log_text.delete("1.0", tk.END)
            recent_lines = non_empty_lines[-5:]
            for line in recent_lines:
                self.log_text.insert(tk.END, line + '\n')
            self.log_text.see(tk.END)
    
    def clear_log(self):
        """清空日志"""
        self.log_text.delete("1.0", tk.END)

    def on_closing(self):
        """程序关闭时的处理"""
        try:
            self.log_message("👋 程序关闭")
            
            # [HOT] 新增：关闭时停止所有运行的脚本
            self.log_message("🛑 正在停止所有运行的脚本...")
            self._stop_all_scripts_on_exit()
            
            # [HOT] 清除UI界面的日志信息
            self.log_message("🧹 正在清除日志信息...")
            self.clear_log()
            self.log_message("✅ 日志信息已清除")
            
            # [HOT] 清空browser_control.log文件
            try:
                log_file_path = os.path.join(os.path.dirname(__file__), "browser_control.log")
                if os.path.exists(log_file_path):
                    # 清空文件内容
                    with open(log_file_path, 'w', encoding='utf-8') as f:
                        f.write("")
                    self.log_message("✅ browser_control.log文件已清空")
                else:
                    self.log_message("[INFO] browser_control.log文件不存在")
            except Exception as e:
                self.log_message(f"⚠️ 清空browser_control.log失败: {e}")
            
            # 🔥 新增：清理主目录cache文件夹
            try:
                import shutil
                cache_dir = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),  # 回到主目录
                    "cache"
                )
                if os.path.exists(cache_dir):
                    shutil.rmtree(cache_dir)
                    self.log_message("🗑️ 主目录cache文件夹已清理")
                else:
                    self.log_message("[INFO] cache文件夹不存在")
            except Exception as e:
                self.log_message(f"⚠️ 清理cache文件夹失败: {e}")

        except Exception as e:
            self.log_message(f"关闭时处理失败: {e}")
        finally:
            # 清理单实例锁文件
            if hasattr(self, 'instance_checker'):
                self.instance_checker.remove_lock()
            self.root.destroy()

    def _stop_all_scripts_on_exit(self):
        """程序退出时停止所有运行的脚本"""
        try:
            # [HOT] 修复：直接调用stop_parsing_scripts来真正终止进程
            self.log_message("🛑 正在终止所有脚本进程...")
            self.stop_parsing_scripts()
            
            # 等待一下确保进程被终止
            import time
            time.sleep(2)
            
            # [HOT] 额外检查：强制终止所有相关进程
            self._force_terminate_all_scripts()
                
        except Exception as e:
            self.log_message(f"[ERROR] 停止所有脚本失败: {e}")

    def _force_terminate_all_scripts(self):
        """强制终止所有脚本进程 - [HOT] 方案2：进程结束时自动清理暂停标志"""
        try:
            import psutil
            import subprocess
            
            terminated_count = 0
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(str(arg) for arg in cmdline)
                            
                            # 查找脚本进程
                            script_names = ['pdd_search_simple.py', 'product_clicker.py', 'zq.py', 'jiex.py', 'sd.py']
                            if any(script_name in cmdline_str for script_name in script_names):
                                # 排除主程序
                                if 'main.py' not in cmdline_str and 'simple_gui.py' not in cmdline_str:
                                    # [HOT] 方案2：在终止进程前，清理对应的暂停标志文件
                                    self._cleanup_pause_flags_for_process(cmdline_str)
                                    
                                    try:
                                        proc.terminate()
                                        proc.wait(timeout=3)
                                        terminated_count += 1
                                        self.log_message(f"✅ 已终止进程 PID: {proc.pid}")
                                    except:
                                        try:
                                            proc.kill()
                                            terminated_count += 1
                                            self.log_message(f"[HOT] 强制终止进程 PID: {proc.pid}")
                                        except:
                                            # 最后使用taskkill
                                            try:
                                                subprocess.run(['taskkill', '/F', '/PID', str(proc.pid)], 
                                                             capture_output=True, timeout=3)
                                                terminated_count += 1
                                                self.log_message(f"🔨 taskkill终止进程 PID: {proc.pid}")
                                            except:
                                                pass
                except:
                    continue
            
            if terminated_count > 0:
                self.log_message(f"🎯 强制终止了 {terminated_count} 个脚本进程")
            else:
                self.log_message("[INFO] 没有找到需要终止的脚本进程")
                    
        except Exception as e:
            self.log_message(f"[ERROR] 强制终止脚本失败: {e}")

    def _cleanup_pause_flags_for_process(self, cmdline_str: str):
        """[HOT] 方案2：为终止的进程清理暂停标志文件"""
        try:
            # 从命令行中提取浏览器ID
            browser_id = None
            for part in cmdline_str.split():
                if 'browser_' in part:
                    # 提取浏览器ID
                    if 'browser_' in part:
                        browser_id = part.split('browser_')[-1].split('/')[0].split('\\')[0]
                        break
            
            if browser_id:
                # 清理对应的暂停标志文件
                pause_flag_file = os.path.join(
                    os.path.dirname(__file__), 
                    "..", 
                    "generated_scripts", 
                    f"browser_{browser_id}", 
                    "pause_flag.txt"
                )
                
                if os.path.exists(pause_flag_file):
                    try:
                        os.remove(pause_flag_file)
                        self.log_message(f"🧹 清理暂停标志：浏览器 {browser_id[-6:]} 进程终止")
                    except Exception as e:
                        self.log_message(f"⚠️ 清理暂停标志失败: {e}")
        except Exception as e:
            self.log_message(f"⚠️ 清理进程暂停标志失败: {e}")

    # ==================== 识别过滤功能 ====================

    def show_filter_config(self):
        """显示解析设置窗口"""
        # 先计算居中位置
        window_width = 800
        window_height = 700
        x = (self.root.winfo_screenwidth() // 2) - (window_width // 2)
        y = (self.root.winfo_screenheight() // 2) - (window_height // 2)
        
        config_window = tk.Toplevel(self.root)
        config_window.title("解析设置")
        config_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        config_window.resizable(False, False)  # 禁止调整窗口大小
        
        # 设置窗口属性，确保它依附于主窗口且不会被意外关闭
        config_window.transient(self.root)
        config_window.grab_set()

        # 创建笔记本控件
        notebook = ttk.Notebook(config_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 基本设置标签页（包含过滤设置、定时功能和关键词管理）
        self.create_basic_config_tab(notebook)

        # 添加保存按钮
        self.create_save_buttons(config_window)

    def create_basic_config_tab(self, parent):
        """创建基本设置标签页 - 🎨 重新设计的UI布局"""
        config_frame = ttk.Frame(parent, padding="15")
        parent.add(config_frame, text="基本设置")

        # 🎯 第一行：核心配置区域（左右两列布局）
        top_frame = ttk.Frame(config_frame)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        # 左边：基本设置
        basic_group = ttk.LabelFrame(top_frame, text="⚙️ 基本设置", padding="12")
        basic_group.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # 使用网格布局，让标签和输入框对齐
        basic_group.columnconfigure(1, weight=1)
        basic_group.columnconfigure(2, weight=1)

        # 左边：基本设置（4个）
        # 详情页等待时间
        ttk.Label(basic_group, text="详情页等待时间(秒):", font=("Microsoft YaHei", 9)).grid(row=0, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.wait_time_var = tk.IntVar(value=self.global_wait_time)
        wait_time_spinbox = ttk.Spinbox(basic_group, from_=1, to=60, textvariable=self.wait_time_var, width=12, command=self.auto_save_config)
        wait_time_spinbox.grid(row=0, column=1, sticky=tk.W, pady=6)
        wait_time_spinbox.bind('<KeyRelease>', lambda e: self.auto_save_config())

        # 搜索页等待时间
        ttk.Label(basic_group, text="搜索页等待时间(秒):", font=("Microsoft YaHei", 9)).grid(row=1, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.search_page_wait_var = tk.IntVar(value=self.global_search_page_wait)
        search_page_wait_spinbox = ttk.Spinbox(basic_group, from_=0, to=30, textvariable=self.search_page_wait_var, width=12, command=self.auto_save_config)
        search_page_wait_spinbox.grid(row=1, column=1, sticky=tk.W, pady=6)
        search_page_wait_spinbox.bind('<KeyRelease>', lambda e: self.auto_save_config())

        # 翻页数量
        ttk.Label(basic_group, text="每个关键词翻页数:", font=("Microsoft YaHei", 9)).grid(row=2, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.page_count_var = tk.IntVar(value=self.global_page_count)
        page_count_spinbox = ttk.Spinbox(basic_group, from_=1, to=50, textvariable=self.page_count_var, width=12, command=self.auto_save_config)
        page_count_spinbox.grid(row=2, column=1, sticky=tk.W, pady=6)
        page_count_spinbox.bind('<KeyRelease>', lambda e: self.auto_save_config())

        # 每个关键词点击量
        ttk.Label(basic_group, text="每个关键词点击量:", font=("Microsoft YaHei", 9)).grid(row=3, column=0, sticky=tk.W, padx=(0, 12), pady=6)
        self.target_count_var = tk.IntVar(value=self.global_target_count)
        target_count_spinbox = ttk.Spinbox(basic_group, from_=1, to=10000, textvariable=self.target_count_var, width=12, command=self.auto_save_config)
        target_count_spinbox.grid(row=3, column=1, sticky=tk.W, pady=6)
        target_count_spinbox.bind('<KeyRelease>', lambda e: self.auto_save_config())

        # 右边：排序方式和其他设置
        # 排序方式
        ttk.Label(basic_group, text="排序方式:", font=("Microsoft YaHei", 9)).grid(row=0, column=2, sticky=tk.W, padx=(12, 12), pady=6)
        self.sort_method_var = tk.StringVar(value=self.global_sort_method)
        sort_method_combo = ttk.Combobox(basic_group, textvariable=self.sort_method_var, 
                                        values=["综合排序", "好评排序", "销量排序"], 
                                        state="readonly", width=12)
        sort_method_combo.grid(row=0, column=3, sticky=tk.W, pady=6)
        sort_method_combo.bind('<<ComboboxSelected>>', lambda e: self.auto_save_sort_method())

        # 发货时间设置
        ttk.Label(basic_group, text="发货时间:", font=("Microsoft YaHei", 9)).grid(row=1, column=2, sticky=tk.W, padx=(12, 12), pady=6)
        self.shipping_time_var = tk.StringVar(value=self.global_shipping_time)
        shipping_time_combo = ttk.Combobox(basic_group, textvariable=self.shipping_time_var, 
                                          values=["48小时发货", "24小时发货"], 
                                          state="readonly", width=12)
        shipping_time_combo.grid(row=1, column=3, sticky=tk.W, pady=6)
        shipping_time_combo.bind('<<ComboboxSelected>>', lambda e: self.auto_save_shipping_time())

        # 运行时长设置
        ttk.Label(basic_group, text="运行时长(分钟):", font=("Microsoft YaHei", 9)).grid(row=2, column=2, sticky=tk.W, padx=(12, 12), pady=6)
        self.run_minutes_var = tk.IntVar(value=self.global_run_minutes)
        run_minutes_spinbox = ttk.Spinbox(basic_group, from_=0, to=1440, textvariable=self.run_minutes_var, width=12, command=self.auto_save_config)
        run_minutes_spinbox.grid(row=2, column=3, sticky=tk.W, pady=6)
        run_minutes_spinbox.bind('<KeyRelease>', lambda e: self.delayed_auto_save_config())

        # 暂停时长设置
        ttk.Label(basic_group, text="暂停时长(分钟):", font=("Microsoft YaHei", 9)).grid(row=3, column=2, sticky=tk.W, padx=(12, 12), pady=6)
        self.pause_minutes_var = tk.IntVar(value=self.global_pause_minutes)
        pause_minutes_spinbox = ttk.Spinbox(basic_group, from_=0, to=1440, textvariable=self.pause_minutes_var, width=12, command=self.auto_save_config)
        pause_minutes_spinbox.grid(row=3, column=3, sticky=tk.W, pady=6)
        pause_minutes_spinbox.bind('<KeyRelease>', lambda e: self.delayed_auto_save_config())

        # 右边：过滤设置（2排布局）
        shop_group = ttk.LabelFrame(top_frame, text="🔧 过滤设置", padding="12")
        shop_group.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        # 使用网格布局，让过滤设置也做成2排
        shop_group.columnconfigure(1, weight=1)

        self.filter_brand_store_var = tk.BooleanVar(value=self.global_filter_settings.get("filter_brand_store", False))
        self.filter_flagship_store_var = tk.BooleanVar(value=self.global_filter_settings.get("filter_flagship_store", False))
        self.filter_presale_var = tk.BooleanVar(value=self.global_filter_settings.get("filter_presale", False))

        # 左边：过滤选项
        ttk.Checkbutton(shop_group, text="过滤品牌店", variable=self.filter_brand_store_var,
                       command=self.auto_save_filter_settings).grid(row=0, column=0, sticky=tk.W, pady=4, padx=(0, 12))
        ttk.Checkbutton(shop_group, text="过滤旗舰店", variable=self.filter_flagship_store_var,
                       command=self.auto_save_filter_settings).grid(row=1, column=0, sticky=tk.W, pady=4, padx=(0, 12))
        ttk.Checkbutton(shop_group, text="过滤预售", variable=self.filter_presale_var,
                       command=self.auto_save_filter_settings).grid(row=2, column=0, sticky=tk.W, pady=4, padx=(0, 12))

        # 过滤已解析商品（默认打勾，不能去掉）
        self.filter_parsed_products_var = tk.BooleanVar(value=True)  # 默认True
        filter_parsed_checkbutton = ttk.Checkbutton(shop_group, text="过滤已解析商品", variable=self.filter_parsed_products_var,
                                                   command=self.auto_save_filter_settings)
        filter_parsed_checkbutton.grid(row=3, column=0, sticky=tk.W, pady=4, padx=(0, 12))
        # 设置为禁用状态，用户不能取消勾选
        filter_parsed_checkbutton.state(['disabled'])

        # 🎯 第二行：范围过滤区域（左右两列布局）
        middle_frame = ttk.Frame(config_frame)
        middle_frame.pack(fill=tk.X, pady=(0, 15))

        # 强制配置网格布局，让两个框完全均匀分布
        middle_frame.columnconfigure(0, weight=1, uniform="equal")
        middle_frame.columnconfigure(1, weight=1, uniform="equal")

        # 左边：销量范围过滤
        sales_group = ttk.LabelFrame(middle_frame, text="📊 销量范围过滤", padding="12")
        sales_group.grid(row=0, column=0, sticky="nsew", padx=(0, 2))

        sales_frame = ttk.Frame(sales_group)
        sales_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(sales_frame, text="销量范围:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        self.sales_min_var = tk.StringVar(value=self.global_filter_settings.get("sales_min", ""))
        sales_min_entry = ttk.Entry(sales_frame, textvariable=self.sales_min_var, width=15)
        sales_min_entry.pack(side=tk.LEFT, padx=(12, 6))
        sales_min_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        ttk.Label(sales_frame, text="至", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        self.sales_max_var = tk.StringVar(value=self.global_filter_settings.get("sales_max", ""))
        sales_max_entry = ttk.Entry(sales_frame, textvariable=self.sales_max_var, width=15)
        sales_max_entry.pack(side=tk.LEFT, padx=(6, 12))
        sales_max_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        # 右边：价格范围过滤
        price_group = ttk.LabelFrame(middle_frame, text="💰 价格范围过滤", padding="12")
        price_group.grid(row=0, column=1, sticky="nsew", padx=(2, 0))

        price_frame = ttk.Frame(price_group)
        price_frame.pack(fill=tk.X, pady=(8, 0))

        ttk.Label(price_frame, text="价格范围:", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        self.price_min_var = tk.StringVar(value=self.global_filter_settings.get("price_min", ""))
        price_min_entry = ttk.Entry(price_frame, textvariable=self.price_min_var, width=15)
        price_min_entry.pack(side=tk.LEFT, padx=(12, 6))
        price_min_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        ttk.Label(price_frame, text="至", font=("Microsoft YaHei", 9)).pack(side=tk.LEFT)

        self.price_max_var = tk.StringVar(value=self.global_filter_settings.get("price_max", ""))
        price_max_entry = ttk.Entry(price_frame, textvariable=self.price_max_var, width=15)
        price_max_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())
        price_max_entry.pack(side=tk.LEFT, padx=(6, 12))

        # 🎯 第三行：关键词管理区域（最重要的功能放在底部，占用更多空间）
        keywords_group = ttk.LabelFrame(config_frame, text="🔍 关键词管理", padding="12")
        keywords_group.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        # 创建左右两列的关键词管理布局 - 使用网格布局确保平均分配
        keywords_frame = ttk.Frame(keywords_group)
        keywords_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
        
        # 配置网格列权重，让两列平均分配空间
        keywords_frame.columnconfigure(0, weight=1)
        keywords_frame.columnconfigure(1, weight=1)

        # 左边：搜索关键词
        search_group = ttk.LabelFrame(keywords_frame, text="🔎 搜索关键词", padding="10")
        search_group.grid(row=0, column=0, sticky="nsew", padx=(0, 4))

        # 搜索关键词文本框
        self.search_keywords_text = scrolledtext.ScrolledText(search_group, height=6, wrap=tk.WORD, font=("Consolas", 9))
        self.search_keywords_text.pack(fill=tk.BOTH, expand=True)
        self.search_keywords_text.insert(tk.END, '\n'.join(self.global_search_keywords))

        # [HOT] 搜索关键词实时同步绑定
        self.search_keywords_text.bind('<KeyRelease>', lambda e: self.real_time_sync_search_keywords())
        self.search_keywords_text.bind('<Button-1>', lambda e: self.root.after(100, self.real_time_sync_search_keywords))
        self.search_keywords_text.bind('<Control-v>', lambda e: self.root.after(100, self.real_time_sync_search_keywords))
        self.search_keywords_text.bind('<Control-x>', lambda e: self.root.after(100, self.real_time_sync_search_keywords))

        # 搜索关键词按钮
        search_btn_frame = ttk.Frame(search_group)
        search_btn_frame.pack(fill=tk.X, pady=(8, 0))

        # [HOT] 修复：将按钮居中
        ttk.Button(search_btn_frame, text="清除标记", command=self.clear_search_keyword_marks).pack(expand=True)

        # 右边：过滤关键词
        filter_group = ttk.LabelFrame(keywords_frame, text="🚫 过滤关键词", padding="10")
        filter_group.grid(row=0, column=1, sticky="nsew", padx=(4, 0))

        # 过滤关键词文本框
        self.filter_keywords_text = scrolledtext.ScrolledText(filter_group, height=6, wrap=tk.WORD, font=("Consolas", 9))
        self.filter_keywords_text.pack(fill=tk.BOTH, expand=True)
        self.filter_keywords_text.insert(tk.END, '\n'.join(self.global_filter_keywords))

        # [HOT] 实时同步绑定 - 多种事件触发
        self.filter_keywords_text.bind('<KeyRelease>', lambda e: self.real_time_sync_filter_keywords())
        self.filter_keywords_text.bind('<Button-1>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<Control-v>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<Control-x>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<Delete>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<BackSpace>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))

        # [HOT] 新增：过滤关键词按钮区域
        filter_btn_frame = ttk.Frame(filter_group)
        filter_btn_frame.pack(fill=tk.X, pady=(8, 0))

        # [HOT] 新增：全部清除按钮
        ttk.Button(filter_btn_frame, text="全部清除", command=self.clear_all_filter_keywords).pack(expand=True)

    def create_filter_settings_tab(self, parent):
        """创建过滤设置标签页"""
        filter_frame = ttk.Frame(parent, padding="10")
        parent.add(filter_frame, text="过滤设置")

        # 过滤设置
        shop_group = ttk.LabelFrame(filter_frame, text="过滤设置", padding="10")
        shop_group.pack(fill=tk.X, pady=(0, 10))

        self.filter_brand_store_var = tk.BooleanVar(value=self.global_filter_settings.get("filter_brand_store", False))
        self.filter_flagship_store_var = tk.BooleanVar(value=self.global_filter_settings.get("filter_flagship_store", False))
        self.filter_presale_var = tk.BooleanVar(value=self.global_filter_settings.get("filter_presale", False))

        # 使用更美观的复选框布局
        ttk.Checkbutton(shop_group, text="过滤品牌店", variable=self.filter_brand_store_var,
                       command=self.auto_save_filter_settings).pack(anchor=tk.W, pady=4)
        ttk.Checkbutton(shop_group, text="过滤旗舰店", variable=self.filter_flagship_store_var,
                       command=self.auto_save_filter_settings).pack(anchor=tk.W, pady=4)
        ttk.Checkbutton(shop_group, text="过滤预售", variable=self.filter_presale_var,
                       command=self.auto_save_filter_settings).pack(anchor=tk.W, pady=4)

        # 24小时发货筛选
        self.require_24h_shipping_var = tk.BooleanVar(value=self.global_filter_settings.get("require_24h_shipping", False))
        ttk.Checkbutton(shop_group, text="只要24小时发货", variable=self.require_24h_shipping_var,
                       command=self.auto_save_filter_settings).pack(anchor=tk.W, pady=4)

        # 过滤已解析商品（默认打勾，不能去掉）
        self.filter_parsed_products_var = tk.BooleanVar(value=True)  # 默认True
        filter_parsed_checkbutton = ttk.Checkbutton(shop_group, text="过滤已解析商品", variable=self.filter_parsed_products_var,
                                                   command=self.auto_save_filter_settings)
        filter_parsed_checkbutton.pack(anchor=tk.W, pady=4)
        # 设置为禁用状态，用户不能取消勾选
        filter_parsed_checkbutton.state(['disabled'])

        # 销量范围过滤
        sales_group = ttk.LabelFrame(filter_frame, text="销量范围过滤", padding="10")
        sales_group.pack(fill=tk.X, pady=(0, 10))

        sales_frame = ttk.Frame(sales_group)
        sales_frame.pack(fill=tk.X)

        ttk.Label(sales_frame, text="销量范围:").pack(side=tk.LEFT)

        self.sales_min_var = tk.StringVar(value=self.global_filter_settings.get("sales_min", ""))
        sales_min_entry = ttk.Entry(sales_frame, textvariable=self.sales_min_var, width=8)
        sales_min_entry.pack(side=tk.LEFT, padx=(10, 5))
        sales_min_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        ttk.Label(sales_frame, text=" - ").pack(side=tk.LEFT)

        self.sales_max_var = tk.StringVar(value=self.global_filter_settings.get("sales_max", ""))
        sales_max_entry = ttk.Entry(sales_frame, textvariable=self.sales_max_var, width=8)
        sales_max_entry.pack(side=tk.LEFT, padx=(5, 10))
        sales_max_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        ttk.Label(sales_frame, text="留空表示不限制").pack(side=tk.LEFT)

        # 价格范围过滤
        price_group = ttk.LabelFrame(filter_frame, text="价格范围过滤", padding="10")
        price_group.pack(fill=tk.X, pady=(0, 10))

        price_frame = ttk.Frame(price_group)
        price_frame.pack(fill=tk.X)

        ttk.Label(price_frame, text="价格范围:").pack(side=tk.LEFT)

        self.price_min_var = tk.StringVar(value=self.global_filter_settings.get("price_min", ""))
        price_min_entry = ttk.Entry(price_frame, textvariable=self.price_min_var, width=8)
        price_min_entry.pack(side=tk.LEFT, padx=(10, 5))
        price_min_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        ttk.Label(price_frame, text=" - ").pack(side=tk.LEFT)

        self.price_max_var = tk.StringVar(value=self.global_filter_settings.get("price_max", ""))
        price_max_entry = ttk.Entry(price_frame, textvariable=self.price_max_var, width=8)
        price_max_entry.pack(side=tk.LEFT, padx=(5, 10))
        price_max_entry.bind('<KeyRelease>', lambda e: self.auto_save_filter_settings())

        ttk.Label(price_frame, text="元 留空表示不限制").pack(side=tk.LEFT)





        # 说明文本
        info_group = ttk.LabelFrame(filter_frame, text="说明", padding="10")
        info_group.pack(fill=tk.BOTH, expand=True)

        info_text = tk.Text(info_group, height=6, wrap=tk.WORD, state=tk.DISABLED)
        info_text.pack(fill=tk.BOTH, expand=True)

        info_content = """过滤设置说明：

1. 过滤设置：勾选后将跳过对应类型的店铺商品
2. 销量范围：设置销量范围，超出范围的商品将被过滤
3. 价格范围：设置价格范围，超出范围的商品将被过滤
4. 过滤已解析商品：默认启用，自动跳过已经解析过的商品
5. 范围设置：可以只设置最小值或最大值，留空表示不限制
6. 示例：100-1000 表示只处理价格在100到1000元之间的商品"""

        info_text.config(state=tk.NORMAL)
        info_text.insert(tk.END, info_content)
        info_text.config(state=tk.DISABLED)

    def create_keywords_tab(self, parent):
        """创建关键词管理标签页"""
        keywords_frame = ttk.Frame(parent, padding="10")
        parent.add(keywords_frame, text="关键词管理")

        # 搜索关键词
        search_group = ttk.LabelFrame(keywords_frame, text="搜索关键词", padding="10")
        search_group.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 搜索关键词文本框
        if not hasattr(self, 'search_keywords_text'):
            self.search_keywords_text = scrolledtext.ScrolledText(search_group, height=6, wrap=tk.WORD)
            self.search_keywords_text.pack(fill=tk.BOTH, expand=True)
            self.search_keywords_text.insert(tk.END, '\n'.join(self.global_search_keywords))

            # [HOT] 搜索关键词实时同步绑定
            self.search_keywords_text.bind('<KeyRelease>', lambda e: self.real_time_sync_search_keywords())
            self.search_keywords_text.bind('<Button-1>', lambda e: self.root.after(100, self.real_time_sync_search_keywords))
            self.search_keywords_text.bind('<Control-v>', lambda e: self.root.after(100, self.real_time_sync_search_keywords))
            self.search_keywords_text.bind('<Control-x>', lambda e: self.root.after(100, self.real_time_sync_search_keywords))
        else:
            # 如果已存在，重新配置现有实例
            self.search_keywords_text.pack_forget()  # 移除旧的包装
            self.search_keywords_text.pack(fill=tk.BOTH, expand=True)
            self.search_keywords_text.delete(1.0, tk.END)
            self.search_keywords_text.insert(tk.END, '\n'.join(self.global_search_keywords))

        # 搜索关键词按钮
        search_btn_frame = ttk.Frame(search_group)
        search_btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(search_btn_frame, text="清除标记", command=self.clear_search_keyword_marks).pack(side=tk.LEFT, padx=(0, 5))

        # 过滤关键词
        filter_group = ttk.LabelFrame(keywords_frame, text="过滤关键词", padding="10")
        filter_group.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        # 过滤关键词文本框
        self.filter_keywords_text = scrolledtext.ScrolledText(filter_group, height=6, wrap=tk.WORD)
        self.filter_keywords_text.pack(fill=tk.BOTH, expand=True)
        self.filter_keywords_text.insert(tk.END, '\n'.join(self.global_filter_keywords))

        # [HOT] 实时同步绑定 - 多种事件触发
        self.filter_keywords_text.bind('<KeyRelease>', lambda e: self.real_time_sync_filter_keywords())
        self.filter_keywords_text.bind('<Button-1>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<Control-v>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<Control-x>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<Delete>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))
        self.filter_keywords_text.bind('<BackSpace>', lambda e: self.root.after(100, self.real_time_sync_filter_keywords))

        # 过滤关键词按钮区域（保留但去掉按钮）
        filter_btn_frame = ttk.Frame(filter_group)
        filter_btn_frame.pack(fill=tk.X, pady=(10, 0))



    def create_save_buttons(self, parent_window):
        """创建保存按钮区域"""
        save_frame = ttk.Frame(parent_window)
        save_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 配置网格列权重，实现真正的居中
        save_frame.columnconfigure(0, weight=1)  # 左侧状态标签
        save_frame.columnconfigure(1, weight=1)  # 中间按钮
        save_frame.columnconfigure(2, weight=1)  # 右侧按钮组

        # 状态标签 - 左对齐
        self.save_status_label = ttk.Label(save_frame, text="✅ 设置已自动保存", foreground="green")
        self.save_status_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        # 中间：打开保存目录按钮 - 真正居中
        ttk.Button(save_frame, text="打开保存目录", command=self.open_details_folder).grid(row=0, column=1)

        # 右侧按钮组
        right_frame = ttk.Frame(save_frame)
        right_frame.grid(row=0, column=2, sticky="e")
        
        ttk.Button(right_frame, text="重置为默认", command=self.reset_to_default).pack(side=tk.RIGHT, padx=(5, 0))

    def reset_to_default(self):
        """重置为默认设置"""
        if messagebox.askyesno("确认重置", "确定要重置所有设置为默认值吗？\n这将清除当前的所有配置。"):
            try:
                # 重置基本设置
                if hasattr(self, 'wait_time_var'):
                    self.wait_time_var.set(5)
                if hasattr(self, 'search_page_wait_var'):
                    self.search_page_wait_var.set(2)
                if hasattr(self, 'page_count_var'):
                    self.page_count_var.set(5)
                if hasattr(self, 'target_count_var'):
                    self.target_count_var.set(100)

                # 重置过滤设置
                if hasattr(self, 'filter_brand_store_var'):
                    self.filter_brand_store_var.set(False)
                if hasattr(self, 'filter_flagship_store_var'):
                    self.filter_flagship_store_var.set(False)
                if hasattr(self, 'filter_presale_var'):
                    self.filter_presale_var.set(False)
                if hasattr(self, 'sales_min_var'):
                    self.sales_min_var.set("")
                if hasattr(self, 'sales_max_var'):
                    self.sales_max_var.set("")
                if hasattr(self, 'price_min_var'):
                    self.price_min_var.set("")
                if hasattr(self, 'price_max_var'):
                    self.price_max_var.set("")

                # 重置关键词
                if hasattr(self, 'search_keywords_text'):
                    self.search_keywords_text.delete('1.0', tk.END)
                    self.search_keywords_text.insert('1.0', "手机壳\n数据线\n充电器\n蓝牙耳机\n手机支架")
                if hasattr(self, 'filter_keywords_text'):
                    self.filter_keywords_text.delete('1.0', tk.END)
                    self.filter_keywords_text.insert('1.0', "二手\n翻新\n破损\n瑕疵")

                # 保存重置后的设置（不显示弹窗）
                try:
                    # 保存基本配置
                    self.auto_save_config()
                    # 保存过滤设置
                    self.auto_save_filter_settings()
                    # 保存关键词设置
                    self.save_keywords_to_config()
                except Exception as e:
                    print(f"保存重置设置时出错: {e}")

                self.save_status_label.config(text="✅ 已重置为默认设置", foreground="blue")

            except Exception as e:
                messagebox.showerror("重置失败", f"重置设置时出错：{e}")

    def save_keywords_to_config(self):
        """保存关键词到配置"""
        try:
            if hasattr(self, 'search_keywords_text'):
                search_keywords = [kw.strip() for kw in self.search_keywords_text.get('1.0', tk.END).strip().split('\n') if kw.strip()]
                self.global_search_keywords = search_keywords

            if hasattr(self, 'filter_keywords_text'):
                filter_keywords = [kw.strip() for kw in self.filter_keywords_text.get('1.0', tk.END).strip().split('\n') if kw.strip()]
                self.global_filter_keywords = filter_keywords

        except Exception as e:
            print(f"保存关键词失败: {e}")

    def _get_python_executable(self):
        """获取正确的Python可执行文件路径"""
        try:
            # [HOT] 优先使用虚拟环境的Python - 动态路径
            # 从bite_browser目录向上一级找到项目根目录
            project_root = Path(__file__).parent.parent
            venv_python = project_root / "pdd_env" / "Scripts" / "python.exe"

            if venv_python.exists():
                # 不显示Python路径，避免日志过多
                return str(venv_python.absolute())
            else:
                # 如果虚拟环境不存在，使用当前Python
                # 不显示Python路径，避免日志过多
                return sys.executable
        except Exception as e:
            self.log_message(f"⚠️ 获取Python路径失败: {e}")
            return sys.executable

    def delayed_auto_save_config(self):
        """延迟2秒自动保存配置"""
        try:
            # 取消之前的延迟任务
            if hasattr(self, '_delayed_save_task'):
                self.root.after_cancel(self._delayed_save_task)
            
            # 设置新的延迟任务
            self._delayed_save_task = self.root.after(2000, self.auto_save_config)
        except Exception as e:
            print(f"设置延迟保存失败: {e}")

    def auto_save_config(self):
        """自动保存全局配置"""
        try:
            # 更新全局变量
            if hasattr(self, 'wait_time_var'):
                self.global_wait_time = self.wait_time_var.get()
            if hasattr(self, 'page_count_var'):
                self.global_page_count = self.page_count_var.get()
            if hasattr(self, 'target_count_var'):
                self.global_target_count = self.target_count_var.get()
            if hasattr(self, 'search_page_wait_var'):
                self.global_search_page_wait = self.search_page_wait_var.get()
            if hasattr(self, 'memory_threshold_var'):
                self.global_memory_threshold = self.memory_threshold_var.get()
            if hasattr(self, 'run_minutes_var'):
                self.global_run_minutes = self.run_minutes_var.get()
            if hasattr(self, 'pause_minutes_var'):
                self.global_pause_minutes = self.pause_minutes_var.get()

            # 保存到文件
            self.save_config()

            # 更新状态显示
            if hasattr(self, 'save_status_label'):
                try:
                    if self.save_status_label.winfo_exists():
                        self.save_status_label.config(text="✅ 设置已自动保存", foreground="green")
                except tk.TclError:
                    pass  # 控件已被销毁，忽略错误
        except tk.TclError:
            # 控件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"自动保存配置失败: {e}")

    def auto_save_filter_settings(self):
        """自动保存过滤设置"""
        try:
            # 更新全局过滤设置
            if hasattr(self, 'filter_brand_store_var'):
                self.global_filter_settings["filter_brand_store"] = self.filter_brand_store_var.get()
            if hasattr(self, 'filter_flagship_store_var'):
                self.global_filter_settings["filter_flagship_store"] = self.filter_flagship_store_var.get()
            if hasattr(self, 'filter_presale_var'):
                self.global_filter_settings["filter_presale"] = self.filter_presale_var.get()
            if hasattr(self, 'sales_min_var'):
                self.global_filter_settings["sales_min"] = self.sales_min_var.get()
            if hasattr(self, 'sales_max_var'):
                self.global_filter_settings["sales_max"] = self.sales_max_var.get()
            if hasattr(self, 'price_min_var'):
                self.global_filter_settings["price_min"] = self.price_min_var.get()
            if hasattr(self, 'price_max_var'):
                self.global_filter_settings["price_max"] = self.price_max_var.get()
            if hasattr(self, 'require_24h_shipping_var'):
                self.global_filter_settings["require_24h_shipping"] = self.require_24h_shipping_var.get()

            # 保存到文件
            self.save_config()

            # 更新状态显示
            if hasattr(self, 'save_status_label'):
                try:
                    if self.save_status_label.winfo_exists():
                        self.save_status_label.config(text="✅ 设置已自动保存", foreground="green")
                except tk.TclError:
                    pass  # 控件已被销毁，忽略错误
        except tk.TclError:
            # 控件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"自动保存过滤设置失败: {e}")
    def auto_save_sort_method(self):
        """自动保存排序设置"""
        try:
            # 更新全局变量
            if hasattr(self, 'sort_method_var'):
                self.global_sort_method = self.sort_method_var.get()
            
            # 保存到文件
            self.save_config()

            # 更新状态显示
            if hasattr(self, 'save_status_label'):
                try:
                    if self.save_status_label.winfo_exists():
                        self.save_status_label.config(text="✅ 排序设置已保存", foreground="green")
                except tk.TclError:
                    pass  # 控件已被销毁，忽略错误
        except tk.TclError:
            # 控件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"自动保存排序设置失败: {e}")

    def auto_save_shipping_time(self):
        """自动保存发货时间设置"""
        try:
            # 更新全局变量
            if hasattr(self, 'shipping_time_var'):
                shipping_time = self.shipping_time_var.get()
                # 根据选择设置24小时发货标志
                self.global_filter_settings["require_24h_shipping"] = (shipping_time == "24小时发货")
            
            # 保存到文件
            self.save_config()

            # 更新状态显示
            if hasattr(self, 'save_status_label'):
                try:
                    if self.save_status_label.winfo_exists():
                        self.save_status_label.config(text="✅ 发货时间设置已保存", foreground="green")
                except tk.TclError:
                    pass  # 控件已被销毁，忽略错误
        except tk.TclError:
            # 控件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"自动保存发货时间设置失败: {e}")



    def auto_save_search_keywords(self):
        """自动保存搜索关键词"""
        try:
            if hasattr(self, 'search_keywords_text') and self.search_keywords_text.winfo_exists():
                text = self.search_keywords_text.get(1.0, tk.END).strip()
                self.global_search_keywords = [line.strip() for line in text.split('\n') if line.strip()]
                # 保存到文件
                self.save_config()
        except tk.TclError:
            # 控件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"自动保存搜索关键词失败: {e}")

    def real_time_sync_filter_keywords(self):
        """实时同步过滤关键词 - 用户编辑时立即同步到所有位置"""
        try:
            if hasattr(self, 'filter_keywords_text') and self.filter_keywords_text.winfo_exists():
                text = self.filter_keywords_text.get(1.0, tk.END).strip()
                new_keywords = [line.strip() for line in text.split('\n') if line.strip()]

                # 检查是否有变化，避免无意义的同步
                if new_keywords != self.global_filter_keywords:
                    self.global_filter_keywords = new_keywords

                    # [HOT] 实时同步到所有位置
                    self._sync_filter_keywords_to_manager()
                    self._sync_filter_keywords_to_global_file()
                    self._sync_filter_keywords_to_scripts()

                    # 更新状态显示
                    if hasattr(self, 'save_status_label'):
                        self.save_status_label.config(
                            text=f"🔄 实时同步: {len(new_keywords)} 个关键词",
                            foreground="blue"
                        )

                    print(f"实时同步过滤关键词: {len(new_keywords)} 个")

        except tk.TclError:
            # 控件已被销毁，忽略错误
            pass
        except Exception as e:
            print(f"[ERROR] 实时同步过滤关键词失败: {e}")

    def auto_save_filter_keywords(self):
        """自动保存过滤关键词 - 保持向后兼容"""
        self.real_time_sync_filter_keywords()

    def _sync_filter_keywords_to_manager(self):
        """同步过滤关键词到FilterKeywordsManager - 简化版本"""
        try:
            if not hasattr(self, 'filter_manager'):
                return

            # 获取要同步的关键词
            keywords_to_sync = [kw.strip() for kw in self.global_filter_keywords if kw.strip()]

            # 直接设置关键词缓存
            self.filter_manager.keywords_cache = set(kw.lower() for kw in keywords_to_sync)
            self.filter_manager.is_loaded = True

            if keywords_to_sync:
                print(f"✅ 设置过滤关键词: {len(keywords_to_sync)} 个")
            else:
                print("✅ 未设置过滤关键词，将不进行过滤")

        except Exception as e:
            print(f"[ERROR] 同步过滤关键词失败: {e}")

    def _sync_filter_keywords_to_global_file(self):
        """同步过滤关键词到全局配置文件"""
        try:
            import os
            from datetime import datetime

            # [HOT] 修复：使用统一的路径，避免重复创建
            global_file = str(Path(__file__).parent.parent / "pdd_automation" / "filter_keywords_global.txt")

            # 确保目录存在
            os.makedirs(os.path.dirname(global_file), exist_ok=True)

            # 创建文件内容
            content = [
                "# 全局过滤关键词文件",
                f"# 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"# 关键词数量: {len(self.global_filter_keywords)}",
                "# 每行一个关键词，支持中文",
                "# 以#开头的行为注释",
                ""
            ]

            # 添加过滤关键词
            content.extend(self.global_filter_keywords)

            # 写入文件
            with open(global_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))

            print(f"   ✅ 已更新全局配置文件: {len(self.global_filter_keywords)} 个关键词")

        except Exception as e:
            print(f"[ERROR] 同步过滤关键词到全局文件失败: {e}")

    def _sync_filter_keywords_to_scripts(self):
        """同步过滤关键词到所有已生成的脚本目录"""
        try:
            import os
            from pathlib import Path
            from datetime import datetime

            scripts_dir = Path("../generated_scripts")
            if not scripts_dir.exists():
                return

            updated_count = 0

            # 遍历所有浏览器脚本目录
            for browser_folder in scripts_dir.iterdir():
                if browser_folder.is_dir() and browser_folder.name.startswith('browser_'):
                    # 查找过滤关键词文件
                    filter_files = list(browser_folder.glob('filter_keywords_*.txt'))

                    for filter_file in filter_files:
                        try:
                            # 创建新的过滤关键词内容
                            content = [
                                "# 浏览器过滤关键词文件",
                                f"# 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                                f"# 关键词数量: {len(self.global_filter_keywords)}",
                                "# 每行一个关键词，支持中文",
                                "# 以#开头的行为注释",
                                ""
                            ]

                            # 添加过滤关键词
                            content.extend(self.global_filter_keywords)

                            # 写入文件
                            with open(filter_file, 'w', encoding='utf-8') as f:
                                f.write('\n'.join(content))

                            updated_count += 1
                            print(f"   ✅ 已更新: {filter_file.name}")

                        except Exception as e:
                            print(f"   [ERROR] 更新失败 {filter_file.name}: {e}")

            if updated_count > 0:
                print(f"已同步过滤关键词到 {updated_count} 个脚本目录")
            else:
                print("📝 没有找到需要更新的脚本目录")

        except Exception as e:
            print(f"[ERROR] 同步过滤关键词到脚本目录失败: {e}")

    def load_filter_keywords_to_gui(self):
        """从filter_keywords_global.txt文件加载过滤关键词到GUI界面"""
        try:
            # [HOT] 修复：使用统一的路径
            filter_keywords_file = str(Path(__file__).parent.parent / "pdd_automation" / "filter_keywords_global.txt")

            if os.path.exists(filter_keywords_file):
                with open(filter_keywords_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                # 过滤掉注释行和空行
                keywords = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        keywords.append(line)

                # 更新全局变量
                self.global_filter_keywords = keywords

                # 更新GUI界面显示
                if hasattr(self, 'filter_keywords_text') and self.filter_keywords_text.winfo_exists():
                    self.filter_keywords_text.delete(1.0, tk.END)
                    self.filter_keywords_text.insert(1.0, '\n'.join(keywords))

                # 同步到FilterKeywordsManager
                self._sync_filter_keywords_to_manager()

                print(f"✅ 已从文件加载过滤关键词到GUI界面: {len(keywords)} 个")

                # 更新状态显示
                if hasattr(self, 'save_status_label'):
                    self.save_status_label.config(
                        text=f"✅ 已加载过滤关键词: {len(keywords)} 个",
                        foreground="green"
                    )
            else:
                print(f"⚠️ 过滤关键词文件不存在: {filter_keywords_file}")

        except Exception as e:
            print(f"[ERROR] 加载过滤关键词到GUI界面失败: {e}")

    def setup_real_time_sync(self):
        """设置全面的实时同步机制"""
        try:
            print("正在设置实时同步机制...")

            # 1. API Token 实时同步
            if hasattr(self, 'api_token_var'):
                self.api_token_var.trace('w', lambda *args: self.real_time_sync_api_token())

            # 2. 解析设置实时同步
            if hasattr(self, 'wait_time_var'):
                self.wait_time_var.trace('w', lambda *args: self.real_time_sync_parse_settings())
            if hasattr(self, 'page_count_var'):
                self.page_count_var.trace('w', lambda *args: self.real_time_sync_parse_settings())
            if hasattr(self, 'target_count_var'):
                self.target_count_var.trace('w', lambda *args: self.real_time_sync_parse_settings())
            if hasattr(self, 'search_page_wait_var'):
                self.search_page_wait_var.trace('w', lambda *args: self.real_time_sync_parse_settings())

            # 3. 过滤设置实时同步
            filter_vars = [
                'filter_brand_store_var', 'filter_flagship_store_var', 'filter_presale_var',
                'sales_min_var', 'sales_max_var', 'price_min_var', 'price_max_var'
            ]
            for var_name in filter_vars:
                if hasattr(self, var_name):
                    getattr(self, var_name).trace('w', lambda *args: self.real_time_sync_filter_settings())

            # 4. 搜索关键词实时同步（已在create_keywords_tab中设置）

            print("✅ 实时同步机制设置完成")

        except Exception as e:
            print(f"[ERROR] 设置实时同步机制失败: {e}")

    def real_time_sync_api_token(self):
        """实时同步API Token"""
        try:
            if hasattr(self, 'api_token_var'):
                # 立即保存到配置文件
                self.save_config()
                print(f"实时同步API Token")
        except Exception as e:
            print(f"[ERROR] 实时同步API Token失败: {e}")

    def real_time_sync_parse_settings(self):
        """实时同步解析设置"""
        try:
            # 更新全局变量
            if hasattr(self, 'wait_time_var'):
                self.global_wait_time = self.wait_time_var.get()
            if hasattr(self, 'page_count_var'):
                self.global_page_count = self.page_count_var.get()
            if hasattr(self, 'target_count_var'):
                self.global_target_count = self.target_count_var.get()
            if hasattr(self, 'search_page_wait_var'):
                self.global_search_page_wait = self.search_page_wait_var.get()

            # 立即保存到配置文件
            self.save_config()

            # 更新状态显示
            if hasattr(self, 'save_status_label'):
                self.save_status_label.config(
                    text="🔄 实时同步解析设置",
                    foreground="blue"
                )

            print(f"实时同步解析设置: 等待{self.global_wait_time}s, 翻页{self.global_page_count}, 目标{self.global_target_count}")

        except Exception as e:
            print(f"[ERROR] 实时同步解析设置失败: {e}")

    def real_time_sync_filter_settings(self):
        """实时同步过滤设置"""
        try:
            # 更新全局过滤设置
            if hasattr(self, 'filter_brand_store_var'):
                self.global_filter_settings["filter_brand_store"] = self.filter_brand_store_var.get()
            if hasattr(self, 'filter_flagship_store_var'):
                self.global_filter_settings["filter_flagship_store"] = self.filter_flagship_store_var.get()
            if hasattr(self, 'filter_presale_var'):
                self.global_filter_settings["filter_presale"] = self.filter_presale_var.get()
            if hasattr(self, 'sales_min_var'):
                self.global_filter_settings["sales_min"] = self.sales_min_var.get()
            if hasattr(self, 'sales_max_var'):
                self.global_filter_settings["sales_max"] = self.sales_max_var.get()
            if hasattr(self, 'price_min_var'):
                self.global_filter_settings["price_min"] = self.price_min_var.get()
            if hasattr(self, 'price_max_var'):
                self.global_filter_settings["price_max"] = self.price_max_var.get()

            # 立即保存到配置文件
            self.save_config()

            # 更新状态显示
            if hasattr(self, 'save_status_label'):
                self.save_status_label.config(
                    text="🔄 实时同步过滤设置",
                    foreground="blue"
                )

            print(f"实时同步过滤设置")

        except Exception as e:
            print(f"[ERROR] 实时同步过滤设置失败: {e}")

    def real_time_sync_search_keywords(self):
        """实时同步搜索关键词"""
        try:
            if hasattr(self, 'search_keywords_text') and self.search_keywords_text.winfo_exists():
                text = self.search_keywords_text.get(1.0, tk.END).strip()
                new_keywords = [line.strip() for line in text.split('\n') if line.strip()]

                # 检查是否有变化
                if new_keywords != self.global_search_keywords:
                    self.global_search_keywords = new_keywords

                    # 立即保存到配置文件
                    self.save_config()

                    # 更新状态显示
                    if hasattr(self, 'save_status_label'):
                        self.save_status_label.config(
                            text=f"🔄 实时同步搜索关键词: {len(new_keywords)} 个",
                            foreground="blue"
                        )

                    print(f"实时同步搜索关键词: {len(new_keywords)} 个")

        except tk.TclError:
            pass
        except Exception as e:
            print(f"[ERROR] 实时同步搜索关键词失败: {e}")

    def get_filter_settings(self):
        """获取过滤设置"""
        # 先更新全局设置
        self.auto_save_filter_settings()
        return self.global_filter_settings.copy()



    def create_timer_tab(self, parent):
        """创建定时功能标签页"""
        timer_frame = ttk.Frame(parent, padding="10")
        parent.add(timer_frame, text="定时功能")

        # 定时设置
        timer_group = ttk.LabelFrame(timer_frame, text="定时设置", padding="10")
        timer_group.pack(fill=tk.X, pady=(0, 10))

        # 开始时间设置
        time_frame = ttk.Frame(timer_group)
        time_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(time_frame, text="定时开始时间:").pack(side=tk.LEFT)

        # 时间选择
        self.hour_var = tk.StringVar(value="09")
        self.minute_var = tk.StringVar(value="00")

        hour_spinbox = ttk.Spinbox(time_frame, from_=0, to=23, textvariable=self.hour_var, width=5, format="%02.0f")
        hour_spinbox.pack(side=tk.LEFT, padx=(10, 5))

        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)

        minute_spinbox = ttk.Spinbox(time_frame, from_=0, to=59, textvariable=self.minute_var, width=5, format="%02.0f")
        minute_spinbox.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Button(time_frame, text="📅 当前时间", command=self.set_current_time).pack(side=tk.LEFT, padx=(10, 0))

        # 等待时间设置
        wait_frame = ttk.Frame(timer_group)
        wait_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(wait_frame, text="额外等待时间(分钟):").pack(side=tk.LEFT)
        self.wait_minutes_var = tk.IntVar(value=0)
        ttk.Spinbox(wait_frame, from_=0, to=1440, textvariable=self.wait_minutes_var, width=10).pack(side=tk.LEFT, padx=(10, 0))

        # 定时控制按钮
        timer_btn_frame = ttk.Frame(timer_group)
        timer_btn_frame.pack(fill=tk.X, pady=(10, 0))

        ttk.Button(timer_btn_frame, text="⏰ 设置所有实例定时", command=self.set_all_timer).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(timer_btn_frame, text="⏹️ 取消所有定时", command=self.cancel_all_timer).pack(side=tk.LEFT, padx=(0, 5))

    def set_current_time(self):
        """设置为当前时间"""
        from datetime import datetime
        now = datetime.now()
        self.hour_var.set(f"{now.hour:02d}")
        self.minute_var.set(f"{now.minute:02d}")

    def set_all_timer(self):
        """设置所有实例的定时"""
        try:
            from datetime import datetime, timedelta

            # 构建开始时间
            hour = int(self.hour_var.get())
            minute = int(self.minute_var.get())

            now = datetime.now()
            start_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

            # 如果时间已过，设置为明天
            if start_time <= now:
                start_time += timedelta(days=1)

            wait_minutes = self.wait_minutes_var.get()

            # 为所有运行中的浏览器设置定时
            set_count = 0
            # 定时功能已移除

            if set_count > 0:
                messagebox.showinfo("成功", f"成功为 {set_count} 个实例设置定时\n开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.timer_status_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] 为 {set_count} 个实例设置定时\n")
            else:
                messagebox.showwarning("警告", "没有可设置定时的实例")

        except Exception as e:
            messagebox.showerror("错误", f"设置定时失败: {e}")

    def cancel_all_timer(self):
        """取消所有实例的定时"""
        try:
            # 定时功能已移除
            messagebox.showinfo("信息", "定时功能已移除")

        except Exception as e:
            messagebox.showerror("错误", f"取消定时失败: {e}")

    def import_search_keywords(self):
        """导入搜索关键词"""
        file_path = filedialog.askopenfilename(
            title="导入搜索关键词",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.search_keywords_text.delete(1.0, tk.END)
                self.search_keywords_text.insert(1.0, content)

                # [HOT] 导入后立即实时同步
                self.real_time_sync_search_keywords()

                messagebox.showinfo("成功", f"搜索关键词导入成功\n已同步到配置文件: {len(self.global_search_keywords)} 个")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}")

    def export_search_keywords(self):
        """导出搜索关键词"""
        file_path = filedialog.asksaveasfilename(
            title="导出搜索关键词",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                content = self.search_keywords_text.get(1.0, tk.END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", "搜索关键词导出成功")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def import_filter_keywords(self):
        """导入过滤关键词"""
        file_path = filedialog.askopenfilename(
            title="导入过滤关键词",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.filter_keywords_text.delete(1.0, tk.END)
                self.filter_keywords_text.insert(1.0, content)

                # [HOT] 导入后立即实时同步
                self.real_time_sync_filter_keywords()

                messagebox.showinfo("成功", f"过滤关键词导入成功\n已同步到所有位置: {len(self.global_filter_keywords)} 个")
            except Exception as e:
                messagebox.showerror("错误", f"导入失败: {e}")

    def export_filter_keywords(self):
        """导出过滤关键词"""
        file_path = filedialog.asksaveasfilename(
            title="导出过滤关键词",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                content = self.filter_keywords_text.get(1.0, tk.END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                messagebox.showinfo("成功", "过滤关键词导出成功")
            except Exception as e:
                messagebox.showerror("错误", f"导出失败: {e}")

    def clear_all_filter_keywords(self):
        """清除所有过滤关键词"""
        try:
            # 直接清空过滤关键词文本框
            self.filter_keywords_text.delete(1.0, tk.END)
            
            # 清空全局过滤关键词列表
            self.global_filter_keywords.clear()
            
            # 同步到所有位置
            self.sync_filter_keywords_to_all_locations()
            
            # 显示成功消息
            self.log_message("✅ 已清除所有过滤关键词")
            
        except Exception as e:
            self.log_message(f"[ERROR] 清除过滤关键词失败: {e}")

    def clear_search_keyword_marks(self):
        """清除所有搜索关键词的"---已搜索"标记"""
        try:
            # 获取当前搜索关键词文本内容
            current_content = self.search_keywords_text.get(1.0, tk.END).strip()
            
            if not current_content:
                messagebox.showinfo("提示", "搜索关键词列表为空")
                return
            
            # 分割成行并清除"---已搜索"标记
            lines = current_content.split('\n')
            cleaned_lines = []
            cleared_count = 0
            
            for line in lines:
                line = line.strip()
                if line.endswith('---已搜索'):
                    # 去除"---已搜索"标记
                    cleaned_line = line.replace('---已搜索', '').strip()
                    if cleaned_line:  # 确保不是空行
                        cleaned_lines.append(cleaned_line)
                        cleared_count += 1
                elif line:  # 保留非空行
                    cleaned_lines.append(line)
            
            if cleared_count > 0:
                # 更新界面显示
                self.search_keywords_text.delete(1.0, tk.END)
                self.search_keywords_text.insert(1.0, '\n'.join(cleaned_lines))
                
                # 实时同步到全局变量和配置文件
                self.real_time_sync_search_keywords()
                
                # 同步到已搜索关键词文件
                self._clear_searched_keywords_file()
                
                messagebox.showinfo("成功", f"已清除 {cleared_count} 个关键词的搜索标记\n这些关键词现在可以重新搜索了")
            else:
                messagebox.showinfo("提示", "没有找到带有'---已搜索'标记的关键词")
                
        except Exception as e:
            messagebox.showerror("错误", f"清除标记失败: {e}")
    
    def _clear_searched_keywords_file(self):
        """清除已搜索关键词文件"""
        try:
            # 清除主程序的已搜索关键词文件
            main_keywords_file = Path(__file__).parent.parent / "已搜索关键词.json"
            if main_keywords_file.exists():
                initial_data = {
                    'searched_keywords': [],
                    'last_update': datetime.now().isoformat(),
                    'browser_updates': {}
                }
                with open(main_keywords_file, 'w', encoding='utf-8') as f:
                    json.dump(initial_data, f, ensure_ascii=False, indent=2)
                self.log_message("✅ 已清除主程序已搜索关键词文件")
            
            # 清除各个浏览器的已搜索关键词文件
            scripts_dir = Path("../generated_scripts")
            if scripts_dir.exists():
                cleared_browser_count = 0
                for browser_folder in scripts_dir.iterdir():
                    if browser_folder.is_dir() and browser_folder.name.startswith("browser_"):
                        logs_dir = browser_folder / "logs"
                        if logs_dir.exists():
                            # 查找该浏览器的已搜索关键词文件
                            for file in logs_dir.glob("searched_keywords_*.json"):
                                try:
                                    initial_data = {
                                        'searched_keywords': [],
                                        'last_update': datetime.now().isoformat()
                                    }
                                    with open(file, 'w', encoding='utf-8') as f:
                                        json.dump(initial_data, f, ensure_ascii=False, indent=2)
                                    cleared_browser_count += 1
                                except Exception as e:
                                    print(f"清除浏览器关键词文件失败 {file}: {e}")
                
                if cleared_browser_count > 0:
                    self.log_message(f"✅ 已清除 {cleared_browser_count} 个浏览器的已搜索关键词文件")
                    
        except Exception as e:
            self.log_message(f"[ERROR] 清除已搜索关键词文件失败: {e}")

    def start_all_filter(self):
        """一键开始所有实例的解析"""
        if not self.global_search_keywords:
            messagebox.showwarning("警告", "请先设置搜索关键词")
            return

        started_count = 0
        for browser_id, browser in self.browsers.items():
            if browser.get('is_running', False):
                if self.start_instance_filter(browser_id):
                    started_count += 1

        if started_count > 0:
            messagebox.showinfo("成功", f"成功启动 {started_count} 个实例的解析")
            self.refresh_browsers()  # 刷新显示
        else:
            messagebox.showwarning("警告", "没有可启动的实例")

    def stop_all_filter(self):
        """一键停止所有实例的解析"""
        # 解析功能已移除
        messagebox.showinfo("信息", "解析功能已移除")

    def start_instance_filter(self, browser_id: str) -> bool:
        """启动单个实例的解析"""
        # 解析功能已移除
        self.log_message("解析功能已移除，请使用单机版脚本")
        return False

    def stop_instance_filter(self, browser_id: str) -> bool:
        """停止单个实例的解析（不关闭浏览器）"""
        # 解析功能已移除
        return False

    def on_filter_status_changed(self, browser_id: str, status: str):
        """解析状态变化回调"""
        # 解析功能已移除
        pass

    def update_searched_keywords_display(self):
        """[HOT] 统一方法：更新已搜索关键词显示（已废弃，使用refresh_searched_keywords_display）"""
        # 此方法已废弃，统一使用refresh_searched_keywords_display
        pass

    def on_parse_count_changed(self, browser_id: str, total: int, success: int, fail: int):
        """解析数量变化回调"""
        # 更新界面显示
        self.root.after(0, self.update_browser_display)

    def generate_collection_scripts(self):
        """生成采集脚本"""
        def run_generation():
            try:
                self.log_message("🚀 开始生成采集脚本...")

                # 获取运行中的浏览器列表
                running_browsers = []
                for browser_id, browser in self.browsers.items():
                    if browser.get('is_running', False):
                        # [HOT] 修复硬编码：从浏览器信息获取实际端口
                        debug_port = browser.get('debug_port')
                        if not debug_port or debug_port == 9222:
                            # 如果没有端口或是默认端口，尝试从配置文件获取
                            debug_port = self._get_debug_port_from_config()

                        running_browsers.append({
                            'id': browser_id,
                            'name': browser.get('name', f'Browser_{browser_id}'),
                            'debug_port': debug_port,
                            'is_running': True
                        })

                if not running_browsers:
                    self.log_message("[ERROR] 没有运行中的浏览器实例")
                    messagebox.showwarning("警告", "没有运行中的浏览器实例")
                    return

                # 检查是否设置了搜索关键词
                if not self.global_search_keywords:
                    self.log_message("[ERROR] 请先设置搜索关键词")
                    messagebox.showwarning("警告", "请先设置搜索关键词")
                    return

                # [HOT] 检查是否有待搜索的关键词（过滤掉已搜索的）
                pending_keywords = []
                for keyword in self.global_search_keywords:
                    if "---已搜索" not in keyword:
                        pending_keywords.append(keyword.strip())

                if not pending_keywords:
                    self.log_message("⚠️ 所有关键词都已搜索完成")
                    messagebox.showinfo("提醒", "所有关键词都已搜索完成！\n\n如需重新搜索，请：\n1. 点击'🧹 清理搜索记录'\n2. 或添加新的搜索关键词")
                    return

                self.log_message(f"📊 待搜索关键词: {len(pending_keywords)} 个")

                # 生成脚本
                success = self.script_generator.generate_scripts_for_browsers(running_browsers)

                if success:
                    self.log_message("✅ 采集脚本生成完成")

                    # [HOT] 显示生成结果（仅日志，无弹窗）
                    scripts_info = self.script_generator.get_generated_scripts_info()
                    self.log_message(f"📊 成功为 {len(scripts_info)} 个浏览器生成脚本:")

                    for info in scripts_info:
                        browser_id_short = info['browser_id'][-6:] if len(info['browser_id']) >= 6 else info['browser_id']
                        self.log_message(f"   • 浏览器 {browser_id_short}: {info['keywords_count']} 个关键词")
                        self.log_message(f"     脚本文件: {info.get('script_file', 'N/A')}")
                        self.log_message(f"     配置文件: {info.get('config_file', 'N/A')}")

                    self.log_message("💡 脚本已生成完成，可以使用'▶️️ 开始解析'按钮启动")
                    # [HOT] 去掉弹窗：messagebox.showinfo("生成完成", result_msg)
                else:
                    self.log_message("[ERROR] 脚本生成失败")
                    messagebox.showerror("错误", "脚本生成失败，请查看日志")

            except Exception as e:
                self.log_message(f"[ERROR] 生成脚本异常: {e}")
                messagebox.showerror("错误", f"生成脚本失败: {e}")

        # 在后台线程运行
        threading.Thread(target=run_generation, daemon=True).start()
    
    def _get_debug_port_from_config(self):
        """从配置文件获取调试端口"""
        try:
            import os
            import json
            
            # 尝试从主目录的config_api.json获取
            config_file = os.path.join(os.path.dirname(__file__), "..", "config_api.json")
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    debug_port = config.get('browser_info', {}).get('debug_port')
                    if debug_port:
                        return debug_port
            
            # 如果配置文件不存在或没有端口号，返回None
            return None
        except Exception as e:
            self.log_message(f"⚠️ 无法从配置文件获取端口号: {e}")
            return None

    def start_parsing_scripts(self):
        """[HOT] 开始解析 - 自动生成脚本并启动采集"""
        def run_parsing():
            try:
                self.log_message("🚀 开始解析 - 自动生成脚本并启动采集...")
                
                # [HOT] 第一步：尝试停止所有浏览器的手动解析模式（如果有的话）
                self.log_message("🛑 第一步：检查并停止手动解析模式...")
                self.stop_all_manual_extraction()
                # 等待一下确保手动解析完全停止
                import time
                time.sleep(1)

                # [HOT] 步骤1: 检查浏览器是否运行（通过API获取最新状态）
                if not self.api:
                    self.log_message("[ERROR] API未连接")
                    messagebox.showerror("错误", "API未连接！\n请先连接比特浏览器API")
                    return

                # 获取最新的浏览器列表状态
                browser_list = self.api.get_browser_list()

                # 📊 显示浏览器状态概览
                self.log_message(f"📊 API返回浏览器数量: {len(browser_list)}")
                for browser in browser_list:
                    status_text = "运行中" if browser.get('status') == 1 else "未运行"
                    self.log_message(f"   • {browser.get('name', 'N/A')}: {status_text}")

                # [HOT] 根据调试结果，使用正确的状态检测方式
                running_browsers = [b for b in browser_list if b.get('status') == 1]

                self.log_message(f"🔍 运行状态检测结果:")
                self.log_message(f"   status=1 (运行中): {len(running_browsers)} 个")

                # 显示运行中的浏览器详情
                for browser in running_browsers:
                    self.log_message(f"   ✅ {browser.get('name', 'N/A')} (ID: {browser.get('id', 'N/A')[:10]}...)")

                if not running_browsers:
                    self.log_message("[ERROR] 没有运行中的浏览器实例")
                    messagebox.showerror("错误", "没有运行中的浏览器实例！\n请先启动浏览器实例")
                    return

                self.log_message(f"✅ 检测到 {len(running_browsers)} 个运行中的浏览器")

                # [HOT] 步骤2: 自动生成脚本
                self.log_message("📝 步骤1: 自动生成采集脚本...")

                # 检查UI设置
                ui_settings = self.script_generator.collect_ui_settings()
                if not ui_settings:
                    self.log_message("[ERROR] UI设置收集失败")
                    messagebox.showerror("错误", "UI设置收集失败！\n请检查搜索关键词等设置")
                    return

                # [HOT] 使用前面已获取的运行中浏览器信息
                running_browser_info = running_browsers

                # [HOT] 自动生成脚本（无弹窗）
                self.log_message(f"📋 为 {len(running_browser_info)} 个浏览器生成脚本...")
                generation_success = self.script_generator.generate_scripts_for_browsers(running_browser_info)

                if not generation_success:
                    self.log_message("[ERROR] 脚本生成失败")
                    messagebox.showerror("错误", "脚本生成失败！\n请检查日志信息")
                    return

                self.log_message("✅ 脚本生成完成")

                # [HOT] 步骤3: 获取生成的脚本信息
                self.log_message("📊 步骤2: 获取生成的脚本信息...")
                scripts_info = self.script_generator.get_generated_scripts_info()
                if not scripts_info:
                    self.log_message("[ERROR] 获取脚本信息失败")
                    return

                # [HOT] 启动所有生成的脚本 - 支持间隔启动
                import subprocess
                import sys
                import time
                from pathlib import Path

                self.log_message(f"📋 启动策略: 第1个立即启动，后续每隔6秒启动")

                started_count = 0
                total_scripts = len(scripts_info)

                for i, script_info in enumerate(scripts_info):
                    try:
                        # [HOT] 新的模块化结构：使用pdd_search_simple.py作为主启动脚本
                        browser_folder = Path(script_info.get('folder_path', ''))
                        if not browser_folder:
                            # 兼容旧格式
                            browser_folder = self.script_generator.scripts_dir / script_info['folder']

                        main_script = browser_folder / "pdd_search_simple.py"

                        if main_script.exists():
                            # [HOT] 启动脚本进程 - 显示控制台窗口
                            python_exe = self._get_python_executable()

                            if os.name == 'nt':  # Windows系统
                                startupinfo = subprocess.STARTUPINFO()
                                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                                startupinfo.wShowWindow = 0  # [HOT] 修改：SW_HIDE改为正常显示，让控制台可见

                                # [HOT] 修改：不重定向输出，让日志显示在控制台
                                process = subprocess.Popen(
                                    [python_exe, "pdd_search_simple.py"],
                                    cwd=str(browser_folder),
                                    startupinfo=startupinfo
                                    # [HOT] 移除stdout和stderr重定向，让日志正常显示
                                )
                            else:  # Linux/Mac系统
                                # [HOT] 修改：不重定向输出，让日志显示在控制台
                                process = subprocess.Popen(
                                    [python_exe, "pdd_search_simple.py"],
                                    cwd=str(browser_folder)
                                    # [HOT] 移除stdout和stderr重定向，让日志正常显示
                                )

                            browser_id_short = script_info.get('browser_id', '')[-6:] if script_info.get('browser_id') else 'unknown'
                            keywords_count = script_info.get('keywords_count', 0)

                            self.log_message(f"✅ 启动浏览器 {browser_id_short}: {keywords_count}个关键词 (PID:{process.pid})")
                            self.log_message(f"📋 程序日志将显示在控制台窗口中")
                            started_count += 1

                            # [HOT] 间隔启动：第一个立即启动，后续间隔6秒
                            if i < total_scripts - 1:  # 不是最后一个
                                self.log_message(f"⏰ 等待6秒后启动下一个浏览器...")
                                time.sleep(6)

                        else:
                            self.log_message(f"[ERROR] 主启动脚本不存在: {main_script}")

                    except Exception as e:
                        self.log_message(f"[ERROR] 启动脚本失败 {script_info.get('folder', 'unknown')}: {e}")

                if started_count > 0:
                    self.log_message(f"🎉 所有脚本启动完成: {started_count}/{total_scripts} 个")
                    self.log_message("📊 所有浏览器已开始并行采集，请查看各浏览器窗口的运行状态")
                    # 调用回调函数更新按钮状态
                    self.root.after(0, self._on_start_parsing_complete)
                else:
                    self.log_message("[ERROR] 没有成功启动任何脚本")

            except Exception as e:
                self.log_message(f"[ERROR] 启动解析异常: {e}")
                messagebox.showerror("错误", f"启动解析失败: {e}")

        # 在后台线程运行
        threading.Thread(target=run_parsing, daemon=True).start()

    def stop_parsing_scripts(self):
        """停止解析 - 终止所有运行中的采集脚本"""
        try:
            self.log_message("🛑 开始停止所有采集脚本...")
            
            # [HOT] 第一步：停止所有浏览器的手动解析模式
            self.log_message("🛑 第一步：停止所有浏览器的手动解析模式...")
            self.stop_all_manual_extraction()
            # 等待一下确保手动解析完全停止
            import time
            time.sleep(2)

            # 获取所有Python进程
            import psutil
            import os

            stopped_count = 0
            script_processes = []

            # [HOT] 查找所有包含模块化脚本名称的Python进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        # [HOT] 修改：只查找特定的脚本进程，排除主程序
                        script_names = [
                            'pdd_search_simple.py', 
                            'product_clicker.py', 
                            'zq.py', 
                            'jiex.py', 
                            'sd.py'
                        ]
                        # [HOT] 重要：排除主程序进程
                        if cmdline and any(script_name in ' '.join(cmdline) for script_name in script_names):
                            # 额外检查：确保不是主程序
                            cmdline_str = ' '.join(cmdline)
                            if 'main.py' not in cmdline_str and 'simple_gui.py' not in cmdline_str:
                                script_processes.append(proc)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            if not script_processes:
                self.log_message("[INFO] 没有找到运行中的采集脚本")
                # [HOT] 修复：即使没有脚本进程，也要更新按钮状态
                self.root.after(0, self._on_stop_parsing_complete)
                return

            # [HOT] 新增：安全检查 - 确保不会误杀主程序
            current_pid = os.getpid()
            safe_processes = []
            for proc in script_processes:
                if proc.pid != current_pid:
                    safe_processes.append(proc)
                else:
                    self.log_message(f"⚠️ 跳过主程序进程 PID: {proc.pid}")

            if not safe_processes:
                self.log_message("[INFO] 没有找到需要停止的脚本进程")
                self.root.after(0, self._on_stop_parsing_complete)
                return

            # 终止找到的脚本进程及其子进程
            for proc in safe_processes:
                try:
                    # [HOT] 改进：更安全的停止逻辑
                    self.log_message(f"🛑 正在停止脚本进程 PID: {proc.pid}")
                    
                    # [HOT] 方案2：在终止进程前，清理对应的暂停标志文件
                    try:
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(cmdline)
                            self._cleanup_pause_flags_for_process(cmdline_str)
                    except Exception as e:
                        self.log_message(f"⚠️ 清理暂停标志失败: {e}")
                    
                    # 检查进程是否还在运行
                    if not proc.is_running():
                        self.log_message(f"[INFO] 进程 PID: {proc.pid} 已经停止")
                        continue
                    
                    # 先尝试优雅终止子进程
                    children = proc.children(recursive=True)
                    for child in children:
                        try:
                            if child.is_running():
                                child.terminate()
                                child.wait(timeout=3)
                        except:
                            try:
                                if child.is_running():
                                    child.kill()
                            except:
                                pass

                    # 再尝试优雅终止主进程
                    if proc.is_running():
                        proc.terminate()
                        proc.wait(timeout=5)
                        self.log_message(f"✅ 已停止脚本进程 PID: {proc.pid}")
                        stopped_count += 1
                    else:
                        self.log_message(f"[INFO] 进程 PID: {proc.pid} 已自动停止")
                        stopped_count += 1
                        
                except psutil.TimeoutExpired:
                    try:
                        # [HOT] 强制杀死进程（更安全的方式）
                        if proc.is_running():
                            proc.kill()
                            self.log_message(f"[HOT] 强制终止脚本进程 PID: {proc.pid}")
                            stopped_count += 1
                        else:
                            self.log_message(f"[INFO] 进程 PID: {proc.pid} 已停止")
                            stopped_count += 1
                    except Exception as kill_e:
                        self.log_message(f"[ERROR] 强制杀死进程失败 PID {proc.pid}: {kill_e}")
                        # [HOT] 最后尝试：使用taskkill强制终止（仅对脚本进程）
                        try:
                            import subprocess
                            result = subprocess.run(['taskkill', '/F', '/PID', str(proc.pid)], 
                                                 capture_output=True, timeout=5)
                            if result.returncode == 0:
                                self.log_message(f"🔨 使用taskkill强制终止进程 PID: {proc.pid}")
                                stopped_count += 1
                            else:
                                self.log_message(f"[ERROR] taskkill终止失败 PID {proc.pid}: {result.stderr.decode()}")
                        except Exception as taskkill_e:
                            self.log_message(f"[ERROR] taskkill执行失败 PID {proc.pid}: {taskkill_e}")
                except Exception as e:
                    self.log_message(f"⚠️ 停止进程失败 PID {proc.pid}: {e}")

            if stopped_count > 0:
                self.log_message(f"🎉 成功停止 {stopped_count} 个采集脚本")
                # 调用回调函数更新按钮状态
                self.root.after(0, self._on_stop_parsing_complete)
            else:
                self.log_message("[ERROR] 没有成功停止任何脚本")

        except ImportError:
            self.log_message("[ERROR] 缺少psutil模块，无法停止脚本")
            messagebox.showerror("错误", "缺少psutil模块，无法停止脚本！\n请安装: pip install psutil")
        except Exception as e:
            self.log_message(f"[ERROR] 停止脚本异常: {e}")
            messagebox.showerror("错误", f"停止脚本失败: {e}")

    def _unified_pause_system(self, target_browsers=None):
        """[HOT] 统一的暂停系统 - 支持单浏览器和全局暂停"""
        try:
            import psutil
            
            # 确定目标浏览器
            if target_browsers is None:
                # 全局暂停：所有浏览器
                target_browsers = list(self.browsers.keys())
            elif isinstance(target_browsers, str):
                # 单浏览器暂停
                target_browsers = [target_browsers]
            
            paused_count = 0
            
            # 1. 暂停进程
            for browser_id in target_browsers:
                script_processes = self._find_browser_script_processes(browser_id)
                if script_processes:
                    for proc in script_processes:
                        try:
                            # 只暂停运行中的进程
                            if proc.status() == psutil.STATUS_RUNNING:
                                proc.suspend()
                                paused_count += 1
                        except Exception as e:
                            pass

            # 2. 创建暂停标志文件
            for browser_id in target_browsers:
                try:
                    self._update_browser_pause_status(browser_id, True)
                    self._create_pause_flag_file(browser_id)
                except Exception as e:
                    pass
            
            # 3. 返回结果
            return paused_count, len(target_browsers)
            
        except Exception as e:
            self.log_message(f"[ERROR] 统一暂停系统失败: {e}")
            return 0, 0

    def _unified_continue_system(self, target_browsers=None):
        """[HOT] 统一的继续系统 - 支持单浏览器和全局继续"""
        try:
            import psutil
            
            # 确定目标浏览器
            if target_browsers is None:
                # 全局继续：所有浏览器
                target_browsers = list(self.browsers.keys())
            elif isinstance(target_browsers, str):
                # 单浏览器继续
                target_browsers = [target_browsers]
            
            resumed_count = 0
            skipped_count = 0
            
            # 1. 直接尝试恢复所有被暂停的进程
            for browser_id in target_browsers:
                try:
                    # [HOT] 不依赖_is_browser_paused检查，直接查找并恢复暂停的进程
                    script_processes = self._find_browser_script_processes(browser_id)
                    browser_resumed = False
                    
                    if script_processes:
                        for proc in script_processes:
                            try:
                                # 尝试恢复被暂停的进程
                                if proc.status() == psutil.STATUS_STOPPED:
                                    proc.resume()
                                    resumed_count += 1
                                    browser_resumed = True
                                    self.log_message(f"✅ 恢复浏览器 {browser_id[-6:]} 进程 PID: {proc.pid}")
                                elif proc.status() == psutil.STATUS_RUNNING:
                                    # 进程已在运行
                                    pass
                            except Exception as e:
                                self.log_message(f"⚠️ 恢复进程失败 PID {proc.pid}: {e}")
                    
                    # 清理暂停相关状态
                    if browser_resumed or self._is_browser_paused(browser_id):
                        self._remove_pause_flag_file(browser_id)
                        self._update_browser_pause_status(browser_id, False)
                    else:
                        # 浏览器本来就在正常运行
                        skipped_count += 1
                        
                except Exception as e:
                    pass
            
            # 3. 返回结果
            return resumed_count, len(target_browsers), skipped_count
            
        except Exception as e:
            self.log_message(f"[ERROR] 统一继续系统失败: {e}")
            return 0, 0, 0

    def pause_program(self, browser=None):
        """[HOT] 统一的暂停程序 - 使用统一系统"""
        try:
            if browser:
                # 单浏览器暂停
                browser_id = browser['id']
                self.log_message(f"⏸️️ 正在暂停浏览器 {browser_id}...")
                paused_count, total_browsers = self._unified_pause_system(browser_id)
                
                if paused_count > 0:
                    self.log_message(f"✅ 已暂停浏览器 {browser_id} ({paused_count} 个进程)")
                else:
                    self.log_message(f"[INFO] 浏览器 {browser_id} 没有需要暂停的进程")
            else:
                # 全局暂停
                self.log_message("⏸️️ 正在暂停所有采集脚本...")
                paused_count, total_browsers = self._unified_pause_system()
                
                if paused_count > 0:
                    self.log_message(f"✅ 已暂停 {paused_count} 个进程 ({total_browsers} 个浏览器)")
                    # 调用回调函数更新按钮状态
                    self.root.after(0, self._on_pause_program_complete)
                else:
                    self.log_message("[INFO] 没有需要暂停的进程")

        except Exception as e:
            self.log_message(f"[ERROR] 暂停程序失败: {e}")
    
    def _find_all_script_processes(self):
        """查找所有采集脚本进程"""
        try:
            script_processes = []
            found_processes = 0
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] and 'python' in proc.info['name'].lower():
                        cmdline = proc.info['cmdline']
                        if cmdline:
                            cmdline_str = ' '.join(str(arg) for arg in cmdline)
                            
                            # [HOT] 扩展脚本名称列表，确保覆盖所有可能的脚本
                            script_names = [
                                'pdd_search_simple.py', 'product_clicker.py', 'zq.py',
                                'jiex.py', 'sd.py', 'workflow_manager.py', 'shib.py',
                                'suoyin.py', 'pdd_goods_scraper_final.py', 
                                'real_data_jx_system_regex.py'
                            ]
                            
                            for script_name in script_names:
                                if script_name in cmdline_str:
                                    # [HOT] 修复：只添加running状态的进程
                                    try:
                                        if proc.status() == psutil.STATUS_RUNNING:
                                            script_processes.append(proc)
                                            found_processes += 1
                                        else:
                                            self.log_message(f"⚠️ 跳过非运行状态进程 PID {proc.pid}: {proc.status()}")
                                    except Exception as e:
                                        self.log_message(f"⚠️ 无法检查进程 PID {proc.pid} 状态: {e}")
                                    break  # 避免同一进程被重复添加
                                    
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            return script_processes
        except Exception as e:
            self.log_message(f"[ERROR] 查找所有脚本进程失败: {e}")
            return []

    def continue_program(self, browser=None):
        """继续运行 - 支持全局继续和单浏览器继续"""
        try:
            if browser:
                # 单浏览器继续
                browser_id = browser['id']
                self.log_message(f"▶️️ 正在继续浏览器 {browser_id}...")
                resumed_count, total_browsers, skipped_count = self._unified_continue_system(browser_id)
                
                if resumed_count > 0:
                    self.log_message(f"✅ 已继续浏览器 {browser_id} ({resumed_count} 个进程)")
                elif skipped_count > 0:
                    self.log_message(f"[INFO] 浏览器 {browser_id} 本来就在正常运行")
                else:
                    self.log_message(f"[INFO] 浏览器 {browser_id} 没有需要恢复的进程")
            else:
                # 全局继续
                self.log_message("▶️️ 正在继续所有采集脚本...")
                resumed_count, total_browsers, skipped_count = self._unified_continue_system()
                
                if resumed_count > 0:
                    self.log_message(f"✅ 已继续 {resumed_count} 个进程 ({total_browsers} 个浏览器)")
                    # 调用回调函数更新按钮状态
                    self.root.after(0, self._on_continue_program_complete)
                elif skipped_count > 0:
                    self.log_message(f"[INFO] {skipped_count} 个浏览器本来就在正常运行")
                else:
                    self.log_message("[INFO] 没有需要恢复的进程")

        except Exception as e:
            self.log_message(f"[ERROR] 继续运行失败: {e}")

    def _resume_browser_processes(self, browser_id):
        """恢复浏览器被暂停的进程 - 单浏览器模式使用特定查找逻辑"""
        try:
            # [HOT] 修复：单浏览器模式使用特定浏览器的进程查找逻辑
            script_processes = self._find_browser_script_processes(browser_id)
            
            if script_processes:
                resumed_count = 0
                for proc in script_processes:
                    try:
                        # [HOT] 使用旧版本的简单逻辑：直接恢复，不检查状态
                        proc.resume()
                        resumed_count += 1
                    except Exception as e:
                        # 保留错误日志，不静默忽略
                        self.log_message(f"⚠️ 恢复进程 PID {proc.pid} 失败: {e}")
            
                if resumed_count > 0:
                    self.log_message(f"✅ 已恢复 {resumed_count} 个进程")
                else:
                    self.log_message("[INFO] 没有成功恢复任何进程")
            else:
                self.log_message("[INFO] 未找到需要恢复的进程")
                
        except Exception as e:
            self.log_message(f"[ERROR] 恢复浏览器进程失败: {e}")

    def start_program(self, browser):
        """开始指定浏览器的程序"""
        try:
            browser_id = browser['id']
            self.log_message(f"🚀 正在开始浏览器 {browser_id} 的程序...")
            
            # 第一步：删除停止标志文件
            stop_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "stop_flag.txt"
            )
            
            try:
                if os.path.exists(stop_flag_file):
                    os.remove(stop_flag_file)
                    self.log_message(f"✅ 已删除停止标志")
            except Exception as e:
                self.log_message(f"⚠️ 删除停止标志失败: {e}")
            
            # [HOT] 同时删除暂停标志文件
            pause_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "pause_flag.txt"
            )
            try:
                if os.path.exists(pause_flag_file):
                    os.remove(pause_flag_file)
                    self.log_message(f"✅ 已删除暂停标志")
            except Exception as e:
                self.log_message(f"⚠️ 删除暂停标志失败: {e}")
            
            # 第二步：启动完整的自动化流程
            self.log_message(f"🔄 正在启动完整的自动化流程...")
            
            # 启动工作流程管理器（workflow_manager.py）
            workflow_path = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "workflow_manager.py"
            )
            
            if os.path.exists(workflow_path):
                import subprocess
                import sys
                
                # 启动工作流程管理器
                cmd = [sys.executable, workflow_path]
                process = subprocess.Popen(
                    cmd,
                    cwd=os.path.dirname(workflow_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                # 验证进程是否成功启动
                try:
                    import time
                    time.sleep(0.5)
                    
                    if process.poll() is None:  # 进程还在运行
                        self.log_message(f"✅ 工作流程管理器启动成功: PID {process.pid}")
                        self.log_message(f"📁 脚本路径: {workflow_path}")
                    else:
                        # 进程异常退出，尝试启动pdd_search_simple.py作为备选
                        self.log_message(f"⚠️ 工作流程管理器启动失败，尝试启动搜索脚本...")
                        self._restart_automation_script(browser)
                except Exception as e:
                    self.log_message(f"⚠️ 验证工作流程管理器状态失败: {e}")
                    # 备选方案：启动搜索脚本
                    self._restart_automation_script(browser)
            else:
                # 如果没有工作流程管理器，启动搜索脚本
                self.log_message(f"⚠️ 工作流程管理器不存在，启动搜索脚本...")
                self._restart_automation_script(browser)
            
            self.log_message(f"✅ 浏览器 {browser_id} 的程序已开始")
            # [HOT] 更新浏览器停止状态
            self._update_browser_stop_status(browser_id, False)
            
        except Exception as e:
            self.log_message(f"[ERROR] 开始程序失败: {e}")

    def show_emergency_alert(self, alert):
        """显示紧急警报弹窗"""
        try:
            alert_type = alert.get('emergency_type', alert.get('type', 'unknown'))
            message = alert.get('message', '未知错误')
            details = alert.get('details', {})

            # 根据警报类型设置图标和标题
            if alert_type == 'slider_verification':
                title = "🔒 滑块验证"
                icon = "warning"
            elif alert_type == 'network_error':
                title = "🌐 网络错误"
                icon = "error"
            elif alert_type == 'white_screen':
                title = "⚪ 页面白屏"
                icon = "warning"
            elif alert_type == 'popup_message':
                title = alert.get('title', '💬 系统消息')
                icon = alert.get('message_type', 'info')
            else:
                title = "⚠️ 系统警报"
                icon = "warning"

            # 构建详细信息
            detail_text = f"消息: {message}\n"
            if details.get('browser_id'):
                detail_text += f"浏览器ID: {details['browser_id']}\n"
            if details.get('current_url'):
                detail_text += f"当前页面: {details['current_url']}\n"
            if details.get('timestamp'):
                detail_text += f"时间: {details['timestamp']}\n"

            # 显示弹窗
            if icon == "error":
                messagebox.showerror(title, detail_text)
            elif icon == "warning":
                messagebox.showwarning(title, detail_text)
            else:
                messagebox.showinfo(title, detail_text)

            self.log_message(f"🚨 已显示警报: {title} - {message}")

        except Exception as e:
            self.log_message(f"[ERROR] 显示紧急警报失败: {e}")

    def show_popup_message(self, popup):
        """[HOT] 显示弹窗消息"""
        try:
            title = popup.get('title', '💬 系统消息')
            message = popup.get('message', '无消息内容')
            details = popup.get('details', '')
            message_type = popup.get('type', 'info')
            
            # [HOT] 新增：播放警报声音
            self._play_alert_sound()
            
            # 构建显示内容
            display_text = message
            if details:
                display_text += f"\n\n详细信息:\n{details}"
                
            # 根据消息类型选择弹窗类型
            if message_type == 'error' or message_type == 'emergency':
                messagebox.showerror(title, display_text)
            elif message_type == 'warning':
                messagebox.showwarning(title, display_text)
            else:
                messagebox.showinfo(title, display_text)
            
            self.log_message(f"💬 已显示弹窗: {title}")
            
        except Exception as e:
            self.log_message(f"[ERROR] 显示弹窗消息失败: {e}")

    def _play_alert_sound(self):
        """播放警报声音"""
        try:
            import winsound
            # 播放系统警报声音（频率1000Hz，持续500毫秒）
            winsound.Beep(1000, 500)
            # 再播放一次，形成警报效果
            winsound.Beep(800, 300)
        except ImportError:
            # 如果没有winsound模块，尝试其他方式
            try:
                import os
                # 使用系统命令播放声音（Windows）
                os.system('echo ')  # 响铃字符
            except:
                pass
        except Exception as e:
            self.log_message(f"⚠️ 播放警报声音失败: {e}")

    def check_simple_popup_alerts(self):
        """[HOT] 简化的弹窗检查（只检查popup_messages.json）"""
        try:
            import json
            from pathlib import Path
            
            # 检查弹窗消息文件
            popup_file = Path(__file__).parent.parent / "logs" / "popup_messages.json"
            
            if popup_file.exists():
                with open(popup_file, 'r', encoding='utf-8') as f:
                    popups = json.load(f)
                
                for popup in popups:
                    if popup.get('status') in ('active', 'pending', None):  # None表示新消息
                        self.show_popup_message(popup)
                        popup['status'] = 'processed'
                
                # 更新文件
                with open(popup_file, 'w', encoding='utf-8') as f:
                    json.dump(popups, f, ensure_ascii=False, indent=2)
            
            # 每5秒检查一次
            self.root.after(5000, self.check_simple_popup_alerts)
            
        except Exception as e:
            self.log_message(f"[ERROR] 检查弹窗消息失败: {e}")
            # 即使出错也要继续检查
            self.root.after(5000, self.check_simple_popup_alerts)

    def run(self):
        """运行界面"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("用户中断程序")
        except Exception as e:
            self.logger.error(f"程序运行出错: {e}")
        finally:
            if self.api:
                # 这里可以添加清理代码
                pass

    def init_data_transfer_manager(self):
        """[HOT] 初始化数据传输管理器"""
        try:
            import sys
            import os
            # 添加当前目录到Python路径
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)
            
            from data_transfer_manager import DataTransferManager

            # 创建数据传输管理器，设置UI回调
            self.data_transfer_manager = DataTransferManager(
                main_dir=str(Path(__file__).parent.parent),  # [HOT] 修复：使用绝对路径指向项目根目录
                transfer_interval=600,  # 10分钟
                ui_callback=self.refresh_searched_keywords_display
            )

            # [HOT] 修复：启动时立即读取并显示已搜索的关键词
            self.root.after(50, self.load_and_display_searched_keywords)
            # [HOT] 备用方案：如果第一次没有加载成功，再次尝试
            self.root.after(1000, self.load_and_display_searched_keywords)

            # 启动时传输一次就停止（避免持续占用内存）
            self.data_transfer_manager.start_auto_transfer()

            print("✅ 数据传输管理器初始化完成")

        except Exception as e:
            print(f"[ERROR] 数据传输管理器初始化失败: {e}")

    def load_and_display_searched_keywords(self):
        """[HOT] 启动时加载并显示已搜索的关键词"""
        try:
            if not self.data_transfer_manager:
                print("[ERROR] 数据传输管理器未初始化")
                return

            # 读取主关键词文件
            main_keywords_file = self.data_transfer_manager.main_keywords_file
            if not main_keywords_file.exists():
                print("[INFO] 主关键词文件不存在，跳过加载")
                return

            import json
            with open(main_keywords_file, 'r', encoding='utf-8') as f:
                keywords_data = json.load(f)

            searched_keywords = set(keywords_data.get('searched_keywords', []))
            if searched_keywords:
                print(f"启动时加载已搜索关键词: {len(searched_keywords)} 个")
                # 调用刷新函数更新UI显示
                self.refresh_searched_keywords_display(searched_keywords)
            else:
                print("[INFO] 没有已搜索的关键词需要显示")

        except Exception as e:
            print(f"[ERROR] 启动时加载已搜索关键词失败: {e}")

    def refresh_searched_keywords_display(self, searched_keywords_set):
        """[HOT] 刷新UI中的已搜索关键词显示"""
        try:
            print(f"刷新UI显示: {len(searched_keywords_set)} 个已搜索关键词")

            # 在主线程中更新UI - 优先更新解析设置窗口
            self.root.after(0, lambda: self.update_parse_settings_keywords(searched_keywords_set))

        except Exception as e:
            print(f"[ERROR] 刷新已搜索关键词显示失败: {e}")

    def _update_searched_keywords_ui(self, searched_keywords_set):
        """在主线程中更新已搜索关键词UI"""
        try:
            # [HOT] 检查search_keywords_text属性是否存在
            if not hasattr(self, 'search_keywords_text'):
                print(f"⚠️ search_keywords_text属性不存在，跳过UI更新")
                return
                
            # 检查控件是否有效
            if not self.search_keywords_text.winfo_exists():
                print(f"⚠️ search_keywords_text控件不存在，跳过UI更新")
                return

            # 获取当前搜索关键词文本
            current_text = self.search_keywords_text.get("1.0", tk.END).strip()

            if not current_text:
                return

            # 分割关键词
            keywords = [kw.strip() for kw in current_text.split('\n') if kw.strip()]

            # 更新关键词状态
            updated_keywords = []
            updated_count = 0

            for keyword in keywords:
                # 移除现有的---已搜索标记
                clean_keyword = keyword.replace('---已搜索', '').strip()

                # 检查是否在已搜索列表中
                if clean_keyword in searched_keywords_set:
                    if not keyword.endswith('---已搜索'):
                        updated_keywords.append(f"{clean_keyword}---已搜索")
                        updated_count += 1
                    else:
                        updated_keywords.append(keyword)
                else:
                    updated_keywords.append(clean_keyword)

            # 更新UI显示
            if updated_count > 0:
                self.search_keywords_text.delete("1.0", tk.END)
                self.search_keywords_text.insert("1.0", '\n'.join(updated_keywords))

                # 显示更新提示
                self.log_message(f"🔄 UI已刷新: {updated_count} 个关键词标记为已搜索")

                # 保存配置
                self.save_config()

        except Exception as e:
            print(f"[ERROR] 更新已搜索关键词UI失败: {e}")
            import traceback
            print(f"详细错误: {traceback.format_exc()}")
            
    def update_parse_settings_keywords(self, searched_keywords_set):
        """[HOT] 更新解析设置窗口中的已搜索关键词显示"""
        try:
            # 检查解析设置窗口是否打开
            if not hasattr(self, 'search_keywords_text') or not self.search_keywords_text.winfo_exists():
                # 如果窗口没打开，先更新内存中的关键词列表
                self._update_memory_keywords(searched_keywords_set)
                return
                
            # 获取当前搜索关键词文本
            current_text = self.search_keywords_text.get("1.0", tk.END).strip()
            if not current_text:
                return

            # 分割关键词
            keywords = [kw.strip() for kw in current_text.split('\n') if kw.strip()]

            # 更新关键词状态
            updated_keywords = []
            updated_count = 0

            for keyword in keywords:
                # 移除现有的---已搜索标记
                clean_keyword = keyword.replace('---已搜索', '').strip()

                # 检查是否在已搜索列表中
                if clean_keyword in searched_keywords_set:
                    if not keyword.endswith('---已搜索'):
                        updated_keywords.append(f"{clean_keyword}---已搜索")
                        updated_count += 1
                    else:
                        updated_keywords.append(keyword)
                else:
                    updated_keywords.append(clean_keyword)

            # 更新UI显示
            if updated_count > 0:
                self.search_keywords_text.delete("1.0", tk.END)
                self.search_keywords_text.insert("1.0", '\n'.join(updated_keywords))
                print(f"解析设置UI已刷新: {updated_count} 个关键词标记为已搜索")

        except Exception as e:
            print(f"[ERROR] 更新解析设置关键词失败: {e}")
            
    def _update_memory_keywords(self, searched_keywords_set):
        """[HOT] 更新内存中的关键词列表（当UI未打开时）"""
        try:
            # 更新内存中的关键词状态
            updated_keywords = []
            for keyword in self.global_search_keywords:
                clean_keyword = keyword.replace('---已搜索', '').strip()
                if clean_keyword in searched_keywords_set:
                    if not keyword.endswith('---已搜索'):
                        updated_keywords.append(f"{clean_keyword}---已搜索")
                    else:
                        updated_keywords.append(keyword)
                else:
                    updated_keywords.append(clean_keyword)
            
            # 更新内存中的关键词
            self.global_search_keywords = updated_keywords
            print(f"内存关键词已更新: {len(updated_keywords)} 个关键词")
            
        except Exception as e:
            print(f"[ERROR] 更新内存关键词失败: {e}")

    def hide_all_browsers(self):
        """隐藏所有浏览器窗口"""
        try:
            if not self.api:
                self.log_message("[ERROR] 错误：请先连接API")
                return
            
            self.log_message("👻 正在隐藏所有浏览器窗口...")
            
            # 在后台线程中执行，避免阻塞UI
            def hide_browsers_thread():
                try:
                    # 调用API隐藏所有浏览器
                    results = self.api.hide_all_browsers()
                    
                    # 在主线程中更新UI
                    self.root.after(0, lambda: self._on_hide_browsers_complete(results))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"[ERROR] 隐藏浏览器异常: {e}"))
            
            # 启动后台线程
            import threading
            thread = threading.Thread(target=hide_browsers_thread, daemon=True)
            thread.start()
                
        except Exception as e:
            self.log_message(f"[ERROR] 隐藏浏览器异常: {e}")



    def show_all_browsers(self):
        """显示所有浏览器窗口"""
        try:
            if not self.api:
                self.log_message("[ERROR] 错误：请先连接API")
                return
            
            self.log_message("👁️ 正在显示所有浏览器窗口...")
            
            # 在后台线程中执行，避免阻塞UI
            def show_browsers_thread():
                try:
                    # 调用API显示所有浏览器
                    results = self.api.show_all_browsers()
                    
                    # 在主线程中更新UI
                    self.root.after(0, lambda: self._on_show_browsers_complete(results))
                    
                except Exception as e:
                    self.root.after(0, lambda: self.log_message(f"[ERROR] 显示浏览器异常: {e}"))
            
            # 启动后台线程
            import threading
            thread = threading.Thread(target=show_browsers_thread, daemon=True)
            thread.start()
                
        except Exception as e:
            self.log_message(f"[ERROR] 显示浏览器异常: {e}")

    def _on_show_browsers_complete(self, results):
        """显示浏览器完成后的回调"""
        try:
            if results:
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    self.log_message(f"✅ 显示浏览器完成: 成功 {success_count}/{total_count} 个")
                    # 更新按钮状态（不刷新列表，避免闪烁）
                    self.browsers_hidden = False
                    self.hide_show_button.config(text="👻 隐藏实例", bg="#2E8B57")
                else:
                    self.log_message("[ERROR] 所有浏览器显示失败")
            else:
                self.log_message("[ERROR] 没有找到可显示的浏览器")
                
        except Exception as e:
            self.log_message(f"[ERROR] 处理显示结果异常: {e}")

    def toggle_browser_visibility(self):
        """切换浏览器显示/隐藏状态"""
        if self.browsers_hidden:
            # 当前是隐藏状态，点击后显示
            self.show_all_browsers()
        else:
            # 当前是显示状态，点击后隐藏
            self.hide_all_browsers()

    def _on_hide_browsers_complete(self, results):
        """隐藏浏览器完成后的回调"""
        try:
            if results:
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    self.log_message(f"✅ 隐藏浏览器完成: 成功 {success_count}/{total_count} 个")
                    # 更新按钮状态（不刷新列表，避免闪烁）
                    self.browsers_hidden = True
                    self.hide_show_button.config(text="👀 显示实例", bg="#FF6B35")
                else:
                    self.log_message("[ERROR] 所有浏览器隐藏失败")
            else:
                self.log_message("[ERROR] 没有找到可隐藏的浏览器")
                
        except Exception as e:
            self.log_message(f"[ERROR] 处理隐藏结果异常: {e}")

    def open_details_folder(self):
        """打开保存目录（details文件夹）"""
        try:
            import os
            import subprocess
            import platform
            
            # 获取项目根目录（从bite_browser目录向上一级）
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            details_folder = os.path.join(project_root, "details")
            
            # 如果details文件夹不存在，创建它
            if not os.path.exists(details_folder):
                os.makedirs(details_folder)
                self.save_status_label.config(text="📂 已创建details文件夹", foreground="blue")
            
            # 根据操作系统打开文件夹
            if platform.system() == "Windows":
                # Windows: 使用os.startfile或subprocess.Popen，避免check=True导致的错误
                try:
                    os.startfile(details_folder)
                except AttributeError:
                    # 如果os.startfile不可用，使用subprocess.Popen
                    subprocess.Popen(["explorer", details_folder], shell=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", details_folder], check=False)
            else:  # Linux
                subprocess.run(["xdg-open", details_folder], check=False)
                
            self.save_status_label.config(text="📂 已打开details文件夹", foreground="blue")
            
        except Exception as e:
            self.save_status_label.config(text=f"[ERROR] 打开文件夹失败: {e}", foreground="red")
            print(f"打开details文件夹失败: {e}")

    def toggle_open_close(self):
        """切换开启/关闭所有浏览器状态"""
        if self.browsers_open:
            # 当前是开启状态，点击后关闭
            self.close_all_browsers()
        else:
            # 当前是关闭状态，点击后开启
            self.open_all_browsers()

    def _on_open_browsers_complete(self, results):
        """开启浏览器完成后的回调"""
        try:
            if results:
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    self.log_message(f"✅ 开启浏览器完成: 成功 {success_count}/{total_count} 个")
                    # 更新按钮状态（不刷新列表，避免闪烁）
                    self.browsers_open = True
                    self.open_close_button.config(text="[ERROR]关闭所有", bg="#FF0000")
                else:
                    self.log_message("[ERROR] 所有浏览器开启失败")
            else:
                self.log_message("[ERROR] 没有找到可开启的浏览器")
                
        except Exception as e:
            self.log_message(f"[ERROR] 处理开启结果异常: {e}")

    def _on_close_browsers_complete(self, results):
        """关闭浏览器完成后的回调"""
        try:
            if results:
                success_count = sum(1 for success in results.values() if success)
                total_count = len(results)
                
                if success_count > 0:
                    self.log_message(f"✅ 关闭浏览器完成: 成功 {success_count}/{total_count} 个")
                    # 更新按钮状态（不刷新列表，避免闪烁）
                    self.browsers_open = False
                    self.open_close_button.config(text="🚀开启所有", bg="#2E8B57")
                else:
                    self.log_message("[ERROR] 所有浏览器关闭失败")
            else:
                self.log_message("[ERROR] 没有找到可关闭的浏览器")
                
        except Exception as e:
            self.log_message(f"[ERROR] 处理关闭结果异常: {e}")

    def toggle_start_stop(self):
        """切换开始/停止解析状态"""
        if self.parsing_active:
            # 当前是解析状态，点击后停止
            self.stop_parsing_scripts()
        else:
            # 当前是停止状态，点击后开始
            self.start_parsing_scripts()

    def _on_start_parsing_complete(self):
        """开始解析完成后的回调"""
        try:
            # 更新按钮状态
            self.parsing_active = True
            self.start_stop_button.config(text="⏹停止解析", bg="#FF0000")
            self.log_message("✅ 解析已开始")
        except Exception as e:
            self.log_message(f"[ERROR] 更新开始解析按钮状态异常: {e}")

    def _on_stop_parsing_complete(self):
        """停止解析完成后的回调"""
        try:
            # 更新按钮状态
            self.parsing_active = False
            self.start_stop_button.config(text="▶️开始解析", bg="#2E8B57")
            self.log_message("✅ 解析已停止")
        except Exception as e:
            self.log_message(f"[ERROR] 更新停止解析按钮状态异常: {e}")

    def toggle_pause_continue(self):
        """切换暂停/继续运行状态"""
        if self.program_paused:
            # 当前是暂停状态，点击后继续
            self.continue_program()
        else:
            # 当前是继续状态，点击后暂停
            self.pause_program()

    def _on_pause_program_complete(self):
        """暂停程序完成后的回调"""
        try:
            # 更新按钮状态
            self.program_paused = True
            self.pause_continue_button.config(text="▶️继续运行", bg="#2E8B57")
            self.log_message("✅ 程序已暂停")
        except Exception as e:
            self.log_message(f"[ERROR] 更新暂停程序按钮状态异常: {e}")

    def _on_continue_program_complete(self):
        """继续运行完成后的回调"""
        try:
            # 更新按钮状态
            self.program_paused = False
            self.pause_continue_button.config(text="⏸️暂停程序", bg="#FF0000")
            self.log_message("✅ 程序已继续")
        except Exception as e:
            self.log_message(f"[ERROR] 更新继续运行按钮状态异常: {e}")


    
    def stop_program(self, browser):
        """停止指定浏览器的程序（保留浏览器窗口）"""
        try:
            browser_id = browser['id']
            self.log_message(f"⏹️ 正在停止浏览器 {browser_id} 的程序...")
            
            # 第一步：停止所有相关的脚本进程
            self.log_message(f"🔄 正在停止脚本进程...")
            script_processes = self._find_browser_script_processes(browser_id)
            
            if script_processes:
                killed_count = 0
                for process in script_processes:
                    try:
                        process.terminate()
                        process.wait(timeout=3)  # 等待进程正常退出
                        killed_count += 1
                        self.log_message(f"✅ 已停止脚本进程: PID {process.pid}")
                    except Exception as e:
                        self.log_message(f"⚠️ 停止进程 PID {process.pid} 失败: {e}")
                        # 如果正常终止失败，强制终止
                        try:
                            process.kill()
                            killed_count += 1
                            self.log_message(f"🔄 已强制终止进程: PID {process.pid}")
                        except:
                            pass
                
                self.log_message(f"✅ 已停止 {killed_count} 个脚本进程")
            else:
                self.log_message("[INFO] 未找到需要停止的脚本进程")
            
            # 第二步：停止手动解析模式（如果正在运行）
            if hasattr(self, 'manual_extraction_processes') and browser_id in self.manual_extraction_processes:
                try:
                    self.log_message(f"🛑 正在停止手动解析模式...")
                    
                    # 构建sd.py的路径
                    sd_path = os.path.join(
                        os.path.dirname(__file__), 
                        "..", 
                        "generated_scripts", 
                        f"browser_{browser_id}", 
                        "sd.py"
                    )
                    
                    if os.path.exists(sd_path):
                        # 将sd.py所在目录添加到Python路径
                        import sys
                        sd_dir = os.path.dirname(sd_path)
                        if sd_dir not in sys.path:
                            sys.path.insert(0, sd_dir)
                        
                        # 使用统一的方法停止手动解析
                        self._stop_manual_extraction_for_browser(browser_id)
                        
                        # 从手动抓取进程字典中移除
                        del self.manual_extraction_processes[browser_id]
                    else:
                        self.log_message(f"⚠️ 找不到sd.py文件，无法停止手动解析")
                        
                except Exception as e:
                    self.log_message(f"⚠️ 停止手动解析模式时出错: {e}")
            
            # 第三步：设置停止标志（供其他脚本检查）
            # 这里可以创建一个停止标志文件，让脚本知道应该停止运行
            stop_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "stop_flag.txt"
            )
            
            try:
                os.makedirs(os.path.dirname(stop_flag_file), exist_ok=True)
                with open(stop_flag_file, 'w', encoding='utf-8') as f:
                    f.write(f"stopped_at:{time.time()}")
                self.log_message(f"✅ 已设置停止标志")
            except Exception as e:
                self.log_message(f"⚠️ 设置停止标志失败: {e}")
            
            self.log_message(f"✅ 浏览器 {browser_id} 的程序已停止，浏览器窗口保留")
            # [HOT] 更新浏览器停止状态
            self._update_browser_stop_status(browser_id, True)
            
        except Exception as e:
            self.log_message(f"[ERROR] 停止程序失败: {e}")

    def _force_kill_browser_process(self, browser_id):
        """强制终止浏览器进程"""
        try:
            import psutil
            
            # 查找并终止所有相关进程
            killed_processes = []
            
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    # 查找包含browser_id的进程
                    if proc.info['cmdline']:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if browser_id in cmdline or 'chrome' in proc.info['name'].lower():
                            proc.terminate()
                            killed_processes.append(proc.info['pid'])
                            self.log_message(f"🔄 已终止进程: {proc.info['name']} (PID: {proc.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            if killed_processes:
                self.log_message(f"✅ 已强制终止 {len(killed_processes)} 个相关进程")
            else:
                self.log_message("[INFO] 未找到需要终止的相关进程")
                
        except Exception as e:
            self.log_message(f"[ERROR] 强制终止进程失败: {e}")

    # [HOT] 新增：程序状态检查和新的控制方法
    def _is_browser_paused(self, browser_id: str) -> bool:
        """检查浏览器是否处于暂停状态 - 方案1+2结合：验证文件标志和进程状态"""
        try:
            # 检查暂停标志文件
            pause_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "pause_flag.txt"
            )
            
            # 如果暂停标志文件不存在，直接返回False
            if not os.path.exists(pause_flag_file):
                return False
            
            # [HOT] 方案1：验证进程状态是否真实暂停
            script_processes = self._get_script_processes(browser_id)
            if not script_processes:
                # 没有找到脚本进程，说明进程已结束，清理无效的暂停标志
                try:
                    os.remove(pause_flag_file)
                    self.log_message(f"🧹 清理无效暂停标志：浏览器 {browser_id[-6:]} 进程已结束")
                except Exception as e:
                    self.log_message(f"⚠️ 清理暂停标志失败: {e}")
                return False
            
            # 检查进程状态
            for process in script_processes:
                try:
                    status = process.status()
                    # 如果进程正在运行，说明不是真正的暂停状态
                    if status == psutil.STATUS_RUNNING:
                        # [HOT] 方案2：清理无效的暂停标志
                        try:
                            os.remove(pause_flag_file)
                            self.log_message(f"🧹 清理无效暂停标志：浏览器 {browser_id[-6:]} 进程正在运行")
                        except Exception as e:
                            self.log_message(f"⚠️ 清理暂停标志失败: {e}")
                        return False
                    # 如果进程已停止，说明确实被暂停了
                    elif status == psutil.STATUS_STOPPED:
                        # ✅ 进程确实被暂停了，返回True
                        return True
                    # 如果进程已终止，清理暂停标志
                    elif status == psutil.STATUS_TERMINATED:
                        try:
                            os.remove(pause_flag_file)
                            self.log_message(f"🧹 清理无效暂停标志：浏览器 {browser_id[-6:]} 进程已终止")
                        except Exception as e:
                            self.log_message(f"⚠️ 清理暂停标志失败: {e}")
                        return False
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # 只有当进程存在且状态为暂停时，才返回True
            return True
            
        except Exception as e:
            self.log_message(f"⚠️ 检查暂停状态失败: {e}")
            return False

    def _is_browser_stopped(self, browser_id: str) -> bool:
        """检查浏览器是否处于停止状态"""
        try:
            # 检查停止标志文件
            stop_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "stop_flag.txt"
            )
            return os.path.exists(stop_flag_file)
        except Exception as e:
            self.log_message(f"⚠️ 检查停止状态失败: {e}")
            return False

    def _update_browser_pause_status(self, browser_id, is_paused):
        """更新浏览器暂停状态"""
        try:
            # 更新浏览器状态
            if browser_id in self.browsers:
                self.browsers[browser_id]['is_paused'] = is_paused
        except Exception as e:
            self.log_message(f"[ERROR] 更新浏览器暂停状态失败: {e}")

    def _update_browser_stop_status(self, browser_id, is_stopped):
        """更新浏览器停止状态"""
        try:
            # 更新浏览器状态
            if browser_id in self.browsers:
                self.browsers[browser_id]['is_stopped'] = is_stopped
                self.log_message(f"✅ 已更新浏览器 {browser_id} 停止状态: {is_stopped}")
        except Exception as e:
            self.log_message(f"[ERROR] 更新浏览器停止状态失败: {e}")

    def _create_pause_flag_file(self, browser_id):
        """创建暂停标志文件"""
        try:
            pause_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "pause_flag.txt"
            )
            os.makedirs(os.path.dirname(pause_flag_file), exist_ok=True)
            with open(pause_flag_file, 'w', encoding='utf-8') as f:
                f.write(f"paused_at:{time.time()}")
        except Exception as e:
            self.log_message(f"[ERROR] 创建暂停标志文件失败: {e}")

    def _remove_pause_flag_file(self, browser_id):
        """删除暂停标志文件"""
        try:
            pause_flag_file = os.path.join(
                os.path.dirname(__file__), 
                "..", 
                "generated_scripts", 
                f"browser_{browser_id}", 
                "pause_flag.txt"
            )
            if os.path.exists(pause_flag_file):
                os.remove(pause_flag_file)
        except Exception as e:
            self.log_message(f"[ERROR] 删除暂停标志文件失败: {e}")

    def _get_script_processes(self, browser_id: str) -> list:
        """获取浏览器对应的脚本进程列表"""
        try:
            script_processes = []
            
            # 查找可能的脚本文件名
            script_names = [
                f"product_clicker_{browser_id[-6:]}.py",
                "product_clicker.py",
                f"jiex_{browser_id[-6:]}.py", 
                "jiex.py"
            ]
            
            # 遍历所有进程
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
                    
                    # 检查是否包含浏览器ID和脚本名
                    if browser_id in cmdline:
                        for script_name in script_names:
                            if script_name in cmdline:
                                script_processes.append(proc)
                                break
                                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            return script_processes
            
        except Exception as e:
            self.log_message(f"⚠️ 获取脚本进程失败: {e}")
            return []

