import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from Ctrip_Spider.log import CtripSpiderLogger


def test_logger():
    """
    测试日志类功能
    """
    # 创建日志实例
    logger = CtripSpiderLogger("TestSpider", "logs")
    
    # 测试不同级别的日志
    logger.debug("这是调试信息")
    logger.info("这是信息日志")
    logger.warning("这是警告信息")
    logger.error("这是错误信息")
    logger.critical("这是严重错误")
    
    # 测试特定功能日志
    logger.log_request("https://example.com", 200, 0.5, "GET")
    logger.log_error("连接超时", "https://example.com", "GET")
    logger.log_data_extraction(10, "景点评论")
    logger.log_progress(50, 100, "数据提取")
    
    print("日志测试完成，请查看 logs 目录下的日志文件")


if __name__ == "__main__":
    test_logger()