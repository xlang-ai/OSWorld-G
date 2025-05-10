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
        # Windows specific command to find process using port
        cmd = f"netstat -ano | findstr :{port}"
        output = subprocess.check_output(cmd, shell=True).decode()

        if output:
            # Extract PID from netstat output
            for line in output.split("\n"):
                if line.strip():
                    try:
                        # The PID is the last column in netstat output
                        pid = line.strip().split()[-1]
                        # Kill the process
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True)
                        logger.info(f"Successfully killed process {pid} on port {port}")
                    except Exception as e:
                        logger.error(f"Error killing process on port {port}: {e}")
        else:
            logger.info(f"No process found running on port {port}")

    except subprocess.CalledProcessError:
        logger.info(f"No process found running on port {port}")
    except Exception as e:
        logger.error(f"Error killing process: {e}")


if __name__ == "__main__":
    # Kill all processes on ports 3000-3047
    for i in range(3000, 3048):
        kill_port(i)

    # Kill all Python processes running main_bbox.py
    try:
        subprocess.run(
            'taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *main_bbox.py*"',
            shell=True,
        )
        logger.info("Successfully killed all main_bbox.py processes")
    except Exception as e:
        logger.error(f"Error killing Python processes: {e}")
