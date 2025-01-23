import logging

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create a console handler for logging to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a file handler for logging to a log file
file_handler = logging.FileHandler("log.txt")
file_handler.setLevel(logging.INFO)

# Create a formatter and set it for both handlers
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s [Line: %(lineno)d]"
)
console_handler.setFormatter(formatter)
file_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(console_handler)
logger.addHandler(file_handler)

# Example logging usage
if __name__ == "__main__":
    logger.info("This is an informational message.")
    logger.warning("This is a warning message.")
    logger.error("This is an error message.")
