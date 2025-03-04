import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def kill_port(port):
    """Kill all processes using the specified port on Ubuntu"""
    try:
        # 使用 lsof 查找进程
        cmd = f"lsof -i :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()
        if output:
            # 遍历输出并提取 PID 并杀死进程
            for line in output.split("\n")[1:]:
                if line:
                    pid = line.split()[1]
                    subprocess.run(f"kill -9 {pid}", shell=True)
            logger.info(f"Successfully killed processes on port {port}")
        else:
            logger.info(f"No process found running on port {port}")
    except subprocess.CalledProcessError:
        logger.info(f"No process found running on port {port}")
    except Exception as e:
        logger.error(f"Error killing process: {e}")

if __name__ == "__main__":
    # 可以直接按范围杀死端口上的进程
    for i in range(3000, 3048):
        kill_port(i)
