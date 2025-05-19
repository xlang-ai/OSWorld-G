import subprocess
import sys
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def kill_process_by_name(process_name):
    """Kill all processes matching the specified name"""
    try:
        if sys.platform.startswith("win"):
            # Windows
            cmd = f'tasklist /FI "IMAGENAME eq {process_name}" /FO CSV /NH'
            output = subprocess.check_output(cmd, shell=True).decode()
            if output:
                subprocess.run(f'taskkill /F /IM "{process_name}"', shell=True)
        else:
            # Unix/Linux/MacOS
            cmd = f'ps aux | grep "[{process_name[0]}]{process_name[1:]}"'
            output = subprocess.check_output(cmd, shell=True, text=True)
            if output:
                for line in output.strip().split("\n"):
                    try:
                        pid = line.split()[1]
                        subprocess.run(f"kill -9 {pid}", shell=True)
                        logger.info(f"Killed process {pid} matching {process_name}")
                    except (IndexError, subprocess.CalledProcessError) as e:
                        logger.error(f"Error killing process from line '{line}': {e}")
        logger.info(f"Successfully killed processes matching {process_name}")
    except subprocess.CalledProcessError:
        logger.info(f"No process found matching {process_name}")
    except Exception as e:
        logger.error(f"Error killing process: {e}")


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
    # Kill processes by port range
    for i in range(3000, 3048):
        kill_port(i)

    # Kill specific Python scripts
    process_names = [
        "python main_elem.py",
        "python main_comp.py",
    ]
    for process_name in process_names:
        kill_process_by_name(process_name)
