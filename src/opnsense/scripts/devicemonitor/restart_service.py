#!/usr/local/bin/python3

import os
import sys
import signal
import subprocess
import time
from pathlib import Path

PIDFILE = '/var/run/devicemonitor.pid'
SERVICE_SCRIPT = '/usr/local/opnsense/scripts/devicemonitor/telemetry_collector.py'

def get_pid():
    try:
        if os.path.exists(PIDFILE):
            with open(PIDFILE, 'r') as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        pass
    return None

def is_running(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def start_service():
    pid = get_pid()
    if pid and is_running(pid):
        print("Service is already running")
        return "already_running"
    
    try:
        process = subprocess.Popen([
            'nohup', 'python3', SERVICE_SCRIPT
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        with open(PIDFILE, 'w') as f:
            f.write(str(process.pid))

        time.sleep(2)
        
        if is_running(process.pid):
            print("Service started successfully")
            return "started"
        else:
            print("Failed to start service")
            return "failed"
            
    except Exception as e:
        print(f"Error starting service: {e}")
        return "error"

def stop_service():
    pid = get_pid()
    if not pid or not is_running(pid):
        print("Service is not running")
        if os.path.exists(PIDFILE):
            os.remove(PIDFILE)
        return "not_running"
    
    try:
        os.kill(pid, signal.SIGTERM)

        for _ in range(10):
            if not is_running(pid):
                break
            time.sleep(1)

        if is_running(pid):
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)

        if os.path.exists(PIDFILE):
            os.remove(PIDFILE)
        
        print("Service stopped")
        return "stopped"
        
    except Exception as e:
        print(f"Error stopping service: {e}")
        return "error"

def restart_service():
    stop_result = stop_service()
    time.sleep(2)
    start_result = start_service()
    return f"stop_{stop_result}_start_{start_result}"

def status_service():
    pid = get_pid()
    if pid and is_running(pid):
        return "running"
    else:
        return "stopped"

def main():
    if len(sys.argv) < 2:
        print("Usage: restart_service.py {start|stop|restart|status}")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    
    if action == "start":
        result = start_service()
    elif action == "stop":
        result = stop_service()
    elif action == "restart":
        result = restart_service()
    elif action == "status":
        result = status_service()
    else:
        print("Invalid action. Use: start|stop|restart|status")
        sys.exit(1)
    
    print(result)

if __name__ == "__main__":
    main()