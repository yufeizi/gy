"""
多账号管理器
支持多个比特浏览器账号切换和配置备份
"""

import json
import os
import time
from typing import Dict, List, Optional
try:
    from .bitbrowser_api import BitBrowserAPI
    from .log_manager import get_logger
except ImportError:
    from bitbrowser_api import BitBrowserAPI
    from log_manager import get_logger


class AccountManager:
    """多账号管理器"""
    
    def __init__(self):
        self.logger = get_logger()
        self.accounts_file = "accounts.json"
        self.backups_dir = "browser_backups"
        self.accounts: List[Dict] = []
        self.current_account_index = 0
        
        # 创建备份目录
        if not os.path.exists(self.backups_dir):
            os.makedirs(self.backups_dir)
        
        self.load_accounts()
    
    def load_accounts(self):
        """加载账号配置"""
        try:
            if os.path.exists(self.accounts_file):
                with open(self.accounts_file, 'r', encoding='utf-8') as f:
                    self.accounts = json.load(f)
                self.logger.info(f"加载了 {len(self.accounts)} 个账号配置")
        except Exception as e:
            self.logger.error(f"加载账号配置失败: {e}")
            self.accounts = []
    
    def save_accounts(self):
        """保存账号配置"""
        try:
            with open(self.accounts_file, 'w', encoding='utf-8') as f:
                json.dump(self.accounts, f, ensure_ascii=False, indent=2)
            self.logger.info("账号配置已保存")
        except Exception as e:
            self.logger.error(f"保存账号配置失败: {e}")
    
    def add_account(self, name: str, token: str, max_browsers: int = 10):
        """添加账号"""
        account = {
            "name": name,
            "token": token,
            "max_browsers": max_browsers,
            "current_browsers": 0,
            "created_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_used": None
        }
        
        self.accounts.append(account)
        self.save_accounts()
        self.logger.info(f"添加账号成功: {name}")
    
    def get_current_account(self) -> Optional[Dict]:
        """获取当前账号"""
        if 0 <= self.current_account_index < len(self.accounts):
            return self.accounts[self.current_account_index]
        return None
    
    def switch_to_next_account(self) -> Optional[Dict]:
        """切换到下一个可用账号"""
        for i in range(len(self.accounts)):
            account = self.accounts[i]
            if account['current_browsers'] < account['max_browsers']:
                self.current_account_index = i
                account['last_used'] = time.strftime("%Y-%m-%d %H:%M:%S")
                self.save_accounts()
                self.logger.info(f"切换到账号: {account['name']}")
                return account
        
        self.logger.warning("没有可用的账号")
        return None
    
    def backup_browser_config(self, api: BitBrowserAPI, browser_id: str, browser_name: str):
        """备份浏览器配置"""
        try:
            # 获取完整配置
            config = api.get_browser_detail(browser_id)
            if not config:
                self.logger.error(f"无法获取浏览器配置: {browser_name}")
                return False
            
            # 添加备份信息
            backup_data = {
                "browser_id": browser_id,
                "browser_name": browser_name,
                "backup_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                "account": self.get_current_account()['name'] if self.get_current_account() else "unknown",
                "config": config
            }
            
            # 保存到文件
            backup_file = os.path.join(self.backups_dir, f"{browser_name}_{int(time.time())}.json")
            with open(backup_file, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"浏览器配置备份成功: {backup_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"备份浏览器配置失败: {e}")
            return False
    
    def restore_browser_from_backup(self, api: BitBrowserAPI, backup_file: str) -> Optional[str]:
        """从备份恢复浏览器"""
        try:
            # 读取备份文件
            with open(backup_file, 'r', encoding='utf-8') as f:
                backup_data = json.load(f)
            
            config = backup_data['config']
            original_name = backup_data['browser_name']
            
            # 生成新名称（避免重复）
            new_name = f"{original_name}_restored_{int(time.time())}"
            config['name'] = new_name
            
            # 移除ID（让API自动生成新ID）
            if 'id' in config:
                del config['id']
            
            # 创建新浏览器
            new_id = api.create_browser(new_name, **config)
            if new_id:
                self.logger.info(f"从备份恢复浏览器成功: {new_name}")
                return new_id
            else:
                self.logger.error(f"从备份恢复浏览器失败: {original_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"从备份恢复浏览器异常: {e}")
            return None
    
    def get_backup_list(self) -> List[Dict]:
        """获取备份列表"""
        backups = []
        try:
            for filename in os.listdir(self.backups_dir):
                if filename.endswith('.json'):
                    filepath = os.path.join(self.backups_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            backup_data = json.load(f)
                        
                        backups.append({
                            "filename": filename,
                            "filepath": filepath,
                            "browser_name": backup_data.get('browser_name', 'Unknown'),
                            "backup_time": backup_data.get('backup_time', 'Unknown'),
                            "account": backup_data.get('account', 'Unknown')
                        })
                    except Exception as e:
                        self.logger.error(f"读取备份文件失败 {filename}: {e}")
        except Exception as e:
            self.logger.error(f"获取备份列表失败: {e}")
        
        return sorted(backups, key=lambda x: x['backup_time'], reverse=True)
    
    def auto_switch_account_if_needed(self, api: BitBrowserAPI) -> Optional[BitBrowserAPI]:
        """如果当前账号达到限制，自动切换账号"""
        current_account = self.get_current_account()
        if not current_account:
            return None
        
        # 获取当前账号的浏览器数量
        browsers = api.get_browser_list()
        current_count = len(browsers) if browsers else 0
        
        # 更新当前浏览器数量
        current_account['current_browsers'] = current_count
        
        # 如果达到限制，尝试切换账号
        if current_count >= current_account['max_browsers']:
            self.logger.warning(f"账号 {current_account['name']} 已达到浏览器限制 ({current_count}/{current_account['max_browsers']})")
            
            next_account = self.switch_to_next_account()
            if next_account:
                # 创建新的API实例
                new_api = BitBrowserAPI(next_account['token'])
                if new_api.test_connection():
                    self.logger.info(f"成功切换到账号: {next_account['name']}")
                    return new_api
                else:
                    self.logger.error(f"切换账号失败，无法连接: {next_account['name']}")
        
        return api
    
    def get_account_status(self) -> List[Dict]:
        """获取所有账号状态"""
        status_list = []
        for i, account in enumerate(self.accounts):
            try:
                api = BitBrowserAPI(account['token'])
                if api.test_connection():
                    browsers = api.get_browser_list()
                    current_count = len(browsers) if browsers else 0
                    account['current_browsers'] = current_count
                    
                    status_list.append({
                        "index": i,
                        "name": account['name'],
                        "current_browsers": current_count,
                        "max_browsers": account['max_browsers'],
                        "usage_rate": f"{current_count}/{account['max_browsers']}",
                        "status": "正常" if current_count < account['max_browsers'] else "已满",
                        "last_used": account.get('last_used', '从未使用')
                    })
                else:
                    status_list.append({
                        "index": i,
                        "name": account['name'],
                        "current_browsers": 0,
                        "max_browsers": account['max_browsers'],
                        "usage_rate": "0/0",
                        "status": "连接失败",
                        "last_used": account.get('last_used', '从未使用')
                    })
            except Exception as e:
                self.logger.error(f"获取账号状态失败 {account['name']}: {e}")
                status_list.append({
                    "index": i,
                    "name": account['name'],
                    "current_browsers": 0,
                    "max_browsers": account['max_browsers'],
                    "usage_rate": "0/0",
                    "status": "错误",
                    "last_used": account.get('last_used', '从未使用')
                })
        
        self.save_accounts()
        return status_list
