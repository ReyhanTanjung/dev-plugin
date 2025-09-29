#!/usr/local/bin/python3

"""
    Copyright (c) 2015-2019 Ad Schellevis <ad@opnsense.org>
    All rights reserved.

    Redistribution and use in source and binary forms, with or without
    modification, are permitted provided that the following conditions are met:

    1. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.

    2. Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.

    THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
    INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
    AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
    AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
    OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
    POSSIBILITY OF SUCH DAMAGE.

    --------------------------------------------------------------------------------------

    Device Monitor service control script
"""

import os
import sys
import signal
import subprocess
import time
import logging
from pathlib import Path
from datetime import datetime

# Configure logging for service management
log_handlers = [logging.StreamHandler()]

# Try to add file handler for service management logs
log_file_paths = [
    '/var/log/devicemonitor_service.log',
    '/tmp/devicemonitor_service.log',
    os.path.expanduser('~/devicemonitor_service.log'),
    './devicemonitor_service.log'
]

log_file_used = None
for log_path in log_file_paths:
    try:
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Test if we can write to the file
        test_handler = logging.FileHandler(log_path)
        test_handler.close()

        log_handlers.append(logging.FileHandler(log_path))
        log_file_used = log_path
        break
    except (PermissionError, OSError):
        continue

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [SERVICE_MANAGER] %(message)s',
    handlers=log_handlers
)

logger = logging.getLogger(__name__)

# Log the logging configuration
if log_file_used:
    logger.info(f"Service management logging to file: {log_file_used}")
else:
    logger.warning("Service management file logging disabled - logging to console only")

# Use different pidfile location for development vs production
if os.path.exists('/home/reyhan/tritronik/plugins/devel/devicemonitor'):
    PIDFILE = '/tmp/devicemonitor.pid'  # Development
    logger.info("Running in development mode")
else:
    PIDFILE = '/var/run/devicemonitor.pid'  # Production
    logger.info("Running in production mode")
# Check for development path first, then production path
SERVICE_SCRIPT_DEV = '/home/reyhan/tritronik/plugins/devel/devicemonitor/src/opnsense/scripts/devicemonitor/telemetry_collector.py'
SERVICE_SCRIPT_PROD = '/usr/local/opnsense/scripts/devicemonitor/telemetry_collector.py'

# Use development script if it exists, otherwise use production
if os.path.exists(SERVICE_SCRIPT_DEV):
    SERVICE_SCRIPT = SERVICE_SCRIPT_DEV
    logger.info(f"Using development service script: {SERVICE_SCRIPT}")
else:
    SERVICE_SCRIPT = SERVICE_SCRIPT_PROD
    logger.info(f"Using production service script: {SERVICE_SCRIPT}")

logger.info(f"PID file location: {PIDFILE}")

def get_pid():
    """Get the PID from pidfile"""
    logger.debug(f"Checking for PID file: {PIDFILE}")
    try:
        if os.path.exists(PIDFILE):
            with open(PIDFILE, 'r') as f:
                pid = int(f.read().strip())
                logger.debug(f"Found PID in file: {pid}")
                return pid
        else:
            logger.debug("PID file does not exist")
    except (ValueError, IOError) as e:
        logger.debug(f"Error reading PID file: {e}")
    return None

def is_running(pid):
    """Check if process is running"""
    if pid is None:
        logger.debug("No PID provided, process not running")
        return False
    try:
        os.kill(pid, 0)
        logger.debug(f"Process {pid} is running")
        return True
    except OSError:
        logger.debug(f"Process {pid} is not running")
        return False

def start_service():
    """Start the device monitor service"""
    logger.info("=== Starting Device Monitor Service ===")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    pid = get_pid()
    if pid and is_running(pid):
        logger.info(f"Service is already running with PID {pid}")
        print("Service is already running")
        return "already_running"

    try:
        # Check if service script exists
        logger.info(f"Checking for service script: {SERVICE_SCRIPT}")
        if not os.path.exists(SERVICE_SCRIPT):
            logger.error(f"Service script not found: {SERVICE_SCRIPT}")
            print(f"Service script not found: {SERVICE_SCRIPT}")
            return "script_not_found"

        # Start the service as a daemon
        logger.info(f"Attempting to start service: {SERVICE_SCRIPT}")
        print(f"Starting service: {SERVICE_SCRIPT}")

        # Set up environment for development configuration
        env = os.environ.copy()
        if SERVICE_SCRIPT == SERVICE_SCRIPT_DEV and os.path.exists('/tmp/devicemonitor_test/devicemonitor.conf'):
            env['DEVICEMONITOR_CONFIG'] = '/tmp/devicemonitor_test/devicemonitor.conf'
            logger.info("Using development configuration: /tmp/devicemonitor_test/devicemonitor.conf")
        else:
            logger.info("Using default production configuration")

        # Start the service as a daemon and capture both stdout and stderr
        start_command = ['nohup', 'python3', SERVICE_SCRIPT]
        logger.info(f"Executing command: {' '.join(start_command)}")
        logger.debug(f"Environment variables: DEVICEMONITOR_CONFIG={env.get('DEVICEMONITOR_CONFIG', 'default')}")

        process = subprocess.Popen(
            start_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )

        # Write PID file
        logger.info(f"Writing PID {process.pid} to file: {PIDFILE}")
        with open(PIDFILE, 'w') as f:
            f.write(str(process.pid))

        # Give it a moment to start and check for immediate failures
        logger.info("Waiting 3 seconds for service startup...")
        time.sleep(3)

        # Check if process is still running
        if is_running(process.pid):
            logger.info(f"Service started successfully with PID {process.pid}")
            print("Service started successfully")
            return "started"
        else:
            logger.error(f"Service with PID {process.pid} failed to start or exited immediately")
            # Try to get error output
            try:
                stdout_output, _ = process.communicate(timeout=1)
                if stdout_output:
                    print(f"Service failed to start: {stdout_output.strip()}")
                else:
                    print("Service failed to start (no error output)")
            except subprocess.TimeoutExpired:
                # Process is taking too long, kill it and get partial output
                process.kill()
                try:
                    stdout_output, _ = process.communicate(timeout=1)
                    if stdout_output:
                        print(f"Service failed to start: {stdout_output.strip()}")
                    else:
                        print("Service failed to start (timeout)")
                except:
                    print("Service failed to start (timeout, no output)")

            # Clean up pidfile if service failed
            if os.path.exists(PIDFILE):
                logger.info(f"Cleaning up PID file: {PIDFILE}")
                os.remove(PIDFILE)
            logger.error("Service startup failed")
            return "failed"

    except Exception as e:
        logger.exception(f"Exception occurred while starting service: {e}")
        print(f"Error starting service: {e}")
        return "error"

def stop_service():
    """Stop the device monitor service"""
    logger.info("=== Stopping Device Monitor Service ===")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    pid = get_pid()
    if not pid or not is_running(pid):
        logger.info("Service is not running")
        print("Service is not running")
        # Clean up stale pidfile
        if os.path.exists(PIDFILE):
            logger.info(f"Cleaning up stale PID file: {PIDFILE}")
            os.remove(PIDFILE)
        return "not_running"
    
    try:
        # Send TERM signal
        logger.info(f"Sending SIGTERM to process {pid}")
        os.kill(pid, signal.SIGTERM)

        # Wait for graceful shutdown
        logger.info("Waiting up to 10 seconds for graceful shutdown...")
        for i in range(10):
            if not is_running(pid):
                logger.info(f"Process stopped gracefully after {i+1} seconds")
                break
            time.sleep(1)

        # Force kill if still running
        if is_running(pid):
            logger.warning(f"Process {pid} did not stop gracefully, sending SIGKILL")
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
            if is_running(pid):
                logger.error(f"Process {pid} still running after SIGKILL")
            else:
                logger.info(f"Process {pid} force-killed successfully")

        # Clean up pidfile
        if os.path.exists(PIDFILE):
            logger.info(f"Cleaning up PID file: {PIDFILE}")
            os.remove(PIDFILE)

        logger.info("Service stopped successfully")
        print("Service stopped")
        return "stopped"
        
    except Exception as e:
        logger.exception(f"Exception occurred while stopping service: {e}")
        print(f"Error stopping service: {e}")
        return "error"

def restart_service():
    """Restart the device monitor service"""
    logger.info("=== Restarting Device Monitor Service ===")
    logger.info(f"Timestamp: {datetime.now().isoformat()}")

    logger.info("Step 1: Stopping service")
    stop_result = stop_service()
    logger.info(f"Stop result: {stop_result}")

    logger.info("Waiting 2 seconds between stop and start...")
    time.sleep(2)

    logger.info("Step 2: Starting service")
    start_result = start_service()
    logger.info(f"Start result: {start_result}")

    result = f"stop_{stop_result}_start_{start_result}"
    logger.info(f"Restart operation completed: {result}")
    return result

def status_service():
    """Get service status"""
    logger.debug("Checking service status")
    pid = get_pid()
    if pid and is_running(pid):
        logger.info(f"Service is running with PID {pid}")
        return "running"
    else:
        logger.info("Service is stopped")
        return "stopped"

def main():
    if len(sys.argv) < 2:
        print("Usage: restart_service.py {start|stop|restart|status}")
        logger.error("No action specified")
        sys.exit(1)

    action = sys.argv[1].lower()
    logger.info(f"=== Device Monitor Service Manager - Action: {action.upper()} ===")
    logger.info(f"Script started at: {datetime.now().isoformat()}")
    logger.info(f"Called with arguments: {sys.argv[1:]}")
    
    if action == "start":
        result = start_service()
    elif action == "stop":
        result = stop_service()
    elif action == "restart":
        result = restart_service()
    elif action == "status":
        result = status_service()
    else:
        logger.error(f"Invalid action: {action}")
        print("Invalid action. Use: start|stop|restart|status")
        sys.exit(1)

    logger.info(f"Final result: {result}")
    logger.info(f"=== Service Manager operation completed at: {datetime.now().isoformat()} ===")
    print(result)

if __name__ == "__main__":
    main()