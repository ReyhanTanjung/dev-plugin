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
from pathlib import Path

PIDFILE = '/var/run/devicemonitor.pid'
SERVICE_SCRIPT = '/usr/local/opnsense/scripts/devicemonitor/telemetry_collector.py'

def get_pid():
    """Get the PID from pidfile"""
    try:
        if os.path.exists(PIDFILE):
            with open(PIDFILE, 'r') as f:
                return int(f.read().strip())
    except (ValueError, IOError):
        pass
    return None

def is_running(pid):
    """Check if process is running"""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def start_service():
    """Start the device monitor service"""
    pid = get_pid()
    if pid and is_running(pid):
        print("Service is already running")
        return "already_running"
    
    try:
        # Start the service as a daemon
        process = subprocess.Popen([
            'nohup', 'python3', SERVICE_SCRIPT
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Write PID file
        with open(PIDFILE, 'w') as f:
            f.write(str(process.pid))
        
        # Give it a moment to start
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
    """Stop the device monitor service"""
    pid = get_pid()
    if not pid or not is_running(pid):
        print("Service is not running")
        # Clean up stale pidfile
        if os.path.exists(PIDFILE):
            os.remove(PIDFILE)
        return "not_running"
    
    try:
        # Send TERM signal
        os.kill(pid, signal.SIGTERM)
        
        # Wait for graceful shutdown
        for _ in range(10):
            if not is_running(pid):
                break
            time.sleep(1)
        
        # Force kill if still running
        if is_running(pid):
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
        
        # Clean up pidfile
        if os.path.exists(PIDFILE):
            os.remove(PIDFILE)
        
        print("Service stopped")
        return "stopped"
        
    except Exception as e:
        print(f"Error stopping service: {e}")
        return "error"

def restart_service():
    """Restart the device monitor service"""
    stop_result = stop_service()
    time.sleep(2)
    start_result = start_service()
    return f"stop_{stop_result}_start_{start_result}"

def status_service():
    """Get service status"""
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