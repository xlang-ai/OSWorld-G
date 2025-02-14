import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def kill_port(port):
    """Kill all processes using the specified port"""
    try:
        if sys.platform.startswith("win"):
            # Windows
            cmd = f"netstat -ano | findstr :{port}"
            output = subprocess.check_output(cmd, shell=True).decode()
            if output:
                pid = output.split()[-1]
                subprocess.run(f"taskkill /F /PID {pid}", shell=True)
        else:
            # Unix/Linux/MacOS
            cmd = f"lsof -i :{port}"
            output = subprocess.check_output(cmd, shell=True).decode()
            if output:
                for line in output.split("\n")[1:]:
                    if line:
                        pid = line.split()[1]
                        subprocess.run(f"kill -9 {pid}", shell=True)
        logger.info(f"Successfully killed processes on port {port}")
    except subprocess.CalledProcessError:
        logger.info(f"No process found running on port {port}")
    except Exception as e:
        logger.error(f"Error killing process: {e}")


if __name__ == "__main__":
    kill_port(3000)
    kill_port(3001)
    kill_port(3002)
    kill_port(3003)
    kill_port(3004)
    kill_port(3005)
    kill_port(3006)
    kill_port(3007)
    kill_port(3008)
