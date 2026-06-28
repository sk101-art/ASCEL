import subprocess
import time
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting FastAPI Capture Server...")
    api = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"])
    
    logger.info("Starting Event-Driven Distiller Worker...")
    distiller = subprocess.Popen([sys.executable, "distiller.py"])
    
    logger.info("All services started. Press Ctrl+C to terminate.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Terminating services...")
        api.terminate()
        distiller.terminate()
        logger.info("Services terminated.")

if __name__ == "__main__":
    main()
