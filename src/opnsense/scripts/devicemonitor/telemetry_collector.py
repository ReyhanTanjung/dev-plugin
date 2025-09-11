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

    Device telemetry collector for OPNsense - sends system metrics to remote endpoint
"""

import os
import sys
import time
import json
import psutil
import requests
import logging
from datetime import datetime
from configparser import ConfigParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/devicemonitor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class DeviceTelemetryCollector:
    def __init__(self, config_file='/usr/local/etc/devicemonitor/devicemonitor.conf'):
        self.config_file = config_file
        self.config = None
        self.running = True
        
    def load_config(self):
        """Load configuration from config file"""
        if not os.path.exists(self.config_file):
            logger.error(f"Configuration file not found: {self.config_file}")
            return False
            
        try:
            self.config = ConfigParser()
            self.config.read(self.config_file)
            
            if not self.config.has_section('general'):
                logger.error("Configuration section [general] not found")
                return False
                
            # Check if service is enabled
            if not self.config.getboolean('general', 'Enabled', fallback=False):
                logger.info("Device monitor service is disabled")
                return False
                
            # Validate required settings
            required_settings = ['APIEndpoint', 'AuthToken', 'DeviceID']
            for setting in required_settings:
                if not self.config.get('general', setting, fallback=''):
                    logger.error(f"Required setting '{setting}' not found in configuration")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def collect_system_metrics(self):
        """Collect system telemetry data"""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            
            # Memory usage
            memory = psutil.virtual_memory()
            swap = psutil.swap_memory()
            
            # Disk usage
            disk_usage = psutil.disk_usage('/')
            disk_io = psutil.disk_io_counters()
            
            # Network usage
            net_io = psutil.net_io_counters()
            
            # Load averages
            load_avg = os.getloadavg()
            
            # Boot time
            boot_time = psutil.boot_time()
            
            # Process count
            process_count = len(psutil.pids())
            
            # Temperature (if available)
            temperature_data = {}
            try:
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        temperature_data[name] = [{"label": entry.label or name, "current": entry.current} for entry in entries]
            except AttributeError:
                pass
            
            # Construct telemetry payload
            telemetry_data = {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "device_id": self.config.get('general', 'DeviceID'),
                "system": {
                    "uptime_seconds": int(time.time() - boot_time),
                    "load_average": {
                        "1min": load_avg[0],
                        "5min": load_avg[1],
                        "15min": load_avg[2]
                    },
                    "process_count": process_count
                },
                "cpu": {
                    "usage_percent": cpu_percent,
                    "core_count": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else None
                },
                "memory": {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "usage_percent": memory.percent,
                    "swap_total_bytes": swap.total,
                    "swap_used_bytes": swap.used,
                    "swap_usage_percent": swap.percent
                },
                "disk": {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free,
                    "usage_percent": (disk_usage.used / disk_usage.total) * 100,
                    "read_bytes": disk_io.read_bytes if disk_io else 0,
                    "write_bytes": disk_io.write_bytes if disk_io else 0,
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                    "errin": net_io.errin,
                    "errout": net_io.errout,
                    "dropin": net_io.dropin,
                    "dropout": net_io.dropout
                }
            }
            
            # Add temperature data if available
            if temperature_data:
                telemetry_data["temperature"] = temperature_data
                
            return telemetry_data
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None
    
    def send_telemetry(self, data):
        """Send telemetry data to remote endpoint"""
        try:
            endpoint = self.config.get('general', 'APIEndpoint')
            token = self.config.get('general', 'AuthToken')
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'OPNsense-DeviceMonitor/1.0'
            }
            
            response = requests.post(
                endpoint,
                json=data,
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                logger.debug(f"Telemetry sent successfully: {response.status_code}")
                return True
            else:
                logger.warning(f"Failed to send telemetry: HTTP {response.status_code} - {response.text}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error sending telemetry: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending telemetry: {e}")
            return False
    
    def run(self):
        """Main service loop"""
        logger.info("Starting Device Telemetry Collector")
        
        # Load configuration
        if not self.load_config():
            logger.error("Failed to load configuration, exiting")
            sys.exit(1)
        
        interval = self.config.getint('general', 'Interval', fallback=10)
        logger.info(f"Telemetry collection interval: {interval} seconds")
        
        while self.running:
            try:
                # Collect system metrics
                telemetry_data = self.collect_system_metrics()
                
                if telemetry_data:
                    # Send to remote endpoint
                    success = self.send_telemetry(telemetry_data)
                    if success:
                        logger.debug("Telemetry cycle completed successfully")
                    else:
                        logger.warning("Telemetry sending failed")
                else:
                    logger.error("Failed to collect system metrics")
                
                # Wait for next interval
                time.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.running = False
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(interval)
        
        logger.info("Device Telemetry Collector stopped")

def main():
    collector = DeviceTelemetryCollector()
    collector.run()

if __name__ == "__main__":
    main()