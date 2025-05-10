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
        cmd = f"lsof -i :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()
        if output:
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
    for i in range(3000, 3048):
        kill_port(i)
    subprocess.run(f"tmux kill-server", shell=True)
