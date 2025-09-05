"""
比特浏览器管理程序主入口
专注于多实例管理
"""

import sys
import os
import traceback
import locale

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from log_manager import setup_logging, get_logger
from cleanup_manager import setup_cleanup
from simple_gui import SimpleBitBrowserGUI


def main(silent=False):
    """主函数"""
    try:
        # 🔥 添加静默模式支持
        if not silent:
            print("鱼非子DD解析V2.5 - 比特浏览器多实例管理")
            print("正在初始化...")
            
            # 编码安全检查
            print(f"系统编码: {locale.getpreferredencoding()}")
            print(f"文件系统编码: {sys.getfilesystemencoding()}")
            print(f"标准输出编码: {sys.stdout.encoding}")
            
            # 编码兼容性检查
            try:
                test_str = "测试中文编码和emoji🔥"
                print(f"编码测试: {test_str}")
                print("编码系统正常")
            except UnicodeEncodeError as e:
                print(f"编码警告: {e}")
                print("建议检查系统区域设置")

        # 设置日志
        setup_logging()
        logger = get_logger()
        if not silent:
            print("日志系统初始化完成")

        # 设置清理管理
        setup_cleanup()
        if not silent:
            print("清理管理器初始化完成")

        logger.info("比特浏览器管理程序启动")
        if not silent:
            print("正在启动GUI界面...")

        # 创建并运行GUI
        app = SimpleBitBrowserGUI()
        if not silent:
            print("GUI创建完成，开始运行...")
        app.run()

        logger.info("比特浏览器管理程序正常退出")
        
    except KeyboardInterrupt:
        print("\n用户中断程序")
        sys.exit(0)
    except Exception as e:
        print(f"程序运行出错: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
