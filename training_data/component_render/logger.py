import os
import logging


def setup_logger(port):
    """设置日志记录器，动态指定日志文件路径"""
    # Configure the logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Create a console handler for logging to the console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create a file handler for logging to a log file with dynamic filename
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/log_{port}.txt"
    file_handler = logging.FileHandler(log_filename)
    file_handler.setLevel(logging.INFO)

    # Create a formatter and set it for both handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s [Line: %(lineno)d] [Module: %(module)s] [Function: %(funcName)s]"
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add the handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


logger = setup_logger(0)

# Example logging usage
if __name__ == "__main__":
    port = 3000  # 你可以根据需要修改端口
    logger = setup_logger(port)

    logger.info("This is an informational message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
