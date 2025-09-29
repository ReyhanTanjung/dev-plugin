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
import logging
from datetime import datetime
from configparser import ConfigParser

# Add current directory to path for paho import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paho.mqtt import client as mqtt_client

# Configure logging
log_handlers = [logging.StreamHandler()]

# Try to add file handler, with multiple fallback locations
log_file_paths = [
    '/var/log/devicemonitor.log',
    '/tmp/devicemonitor.log',
    os.path.expanduser('~/devicemonitor.log'),
    './devicemonitor.log'
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
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=log_handlers
)

logger = logging.getLogger(__name__)

# Log the logging configuration
if log_file_used:
    logger.info(f"Logging to file: {log_file_used}")
else:
    logger.warning("File logging disabled - logging to console only")

class DeviceTelemetryCollector:
    def __init__(self, config_file=None):
        if config_file is None:
            # Allow override via environment variable for testing
            config_file = os.environ.get('DEVICEMONITOR_CONFIG', '/usr/local/etc/devicemonitor/devicemonitor.conf')
        self.config_file = config_file
        self.config = None
        self.running = True
        self.mqtt_client = None
        self.mqtt_connected = False
        
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
            required_settings = ['MQTTBroker', 'MQTTPort', 'MQTTTopic', 'DeviceID']
            for setting in required_settings:
                if not self.config.get('general', setting, fallback=''):
                    logger.error(f"Required setting '{setting}' not found in configuration")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return False
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            broker = self.config.get('general', 'MQTTBroker')
            port = self.config.getint('general', 'MQTTPort')
            username = self.config.get('general', 'MQTTUsername', fallback='')
            password = self.config.get('general', 'MQTTPassword', fallback='')
            device_id = self.config.get('general', 'DeviceID')

            logger.info(f"Preparing MQTT connection to {broker}:{port}")
            logger.info(f"Device ID: {device_id}")
            logger.info(f"Authentication: {'Yes' if username and password else 'No'}")

            # Create MQTT client
            client_id = f"opnsense-{device_id}-{int(time.time())}"
            logger.info(f"Creating MQTT client with ID: {client_id}")
            self.mqtt_client = mqtt_client.Client(client_id)

            # Set authentication if provided
            if username and password:
                logger.info("Setting MQTT authentication credentials")
                self.mqtt_client.username_pw_set(username, password)

            # Set callbacks
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_disconnect = self._on_disconnect
            self.mqtt_client.on_publish = self._on_publish
            self.mqtt_client.on_log = self._on_log

            # Connect to broker
            logger.info(f"Attempting to connect to MQTT broker {broker}:{port}")
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start()

            # Wait for connection
            logger.info("Waiting for MQTT connection (timeout: 10 seconds)")
            timeout = 10
            while not self.mqtt_connected and timeout > 0:
                time.sleep(0.5)
                timeout -= 0.5
                if timeout % 2 == 0:  # Log every 1 second
                    logger.debug(f"Still waiting for MQTT connection... {timeout} seconds remaining")

            if not self.mqtt_connected:
                logger.error("Failed to connect to MQTT broker within timeout")
                logger.error("Check network connectivity, broker address, port, and authentication credentials")
                return False

            logger.info("Successfully connected to MQTT broker")
            return True

        except Exception as e:
            logger.exception(f"Error connecting to MQTT broker: {e}")
            return False

    def _on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.mqtt_connected = True
            logger.info("Connected to MQTT broker successfully")
        else:
            self.mqtt_connected = False
            logger.error(f"Failed to connect to MQTT broker with result code {rc}: {self._get_rc_meaning(rc)}")

    def _on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.mqtt_connected = False
        if rc == 0:
            logger.info("Cleanly disconnected from MQTT broker")
        else:
            logger.warning(f"Unexpected disconnection from MQTT broker with result code {rc}")

    def _on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        logger.debug(f"Message published with ID: {mid}")

    def _on_log(self, client, userdata, level, buf):
        """MQTT log callback"""
        logger.debug(f"MQTT Client Log - Level: {level}, Message: {buf}")

    def _get_rc_meaning(self, rc):
        """Get human-readable meaning of MQTT result codes"""
        rc_meanings = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorised"
        }
        return rc_meanings.get(rc, f"Unknown result code: {rc}")

    def collect_system_metrics(self):
        """Collect system telemetry data"""
        try:
            metrics = {}

            # Check which metrics to collect based on configuration
            collect_cpu = self.config.getboolean('general', 'CollectCPU', fallback=True)
            collect_memory = self.config.getboolean('general', 'CollectMemory', fallback=True)
            collect_network = self.config.getboolean('general', 'CollectNetwork', fallback=True)
            collect_disk = self.config.getboolean('general', 'CollectDisk', fallback=True)
            collect_temperature = self.config.getboolean('general', 'CollectTemperature', fallback=False)

            # Basic system info
            boot_time = psutil.boot_time()
            load_avg = os.getloadavg()
            process_count = len(psutil.pids())

            metrics["system"] = {
                "uptime_seconds": int(time.time() - boot_time),
                "load_average": {
                    "1min": load_avg[0],
                    "5min": load_avg[1],
                    "15min": load_avg[2]
                },
                "process_count": process_count
            }

            # CPU metrics
            if collect_cpu:
                cpu_percent = psutil.cpu_percent(interval=1)
                cpu_count = psutil.cpu_count()
                cpu_freq = psutil.cpu_freq()

                metrics["cpu"] = {
                    "usage_percent": cpu_percent,
                    "core_count": cpu_count,
                    "frequency_mhz": cpu_freq.current if cpu_freq else None
                }

            # Memory metrics
            if collect_memory:
                memory = psutil.virtual_memory()
                swap = psutil.swap_memory()

                metrics["memory"] = {
                    "total_bytes": memory.total,
                    "available_bytes": memory.available,
                    "used_bytes": memory.used,
                    "usage_percent": memory.percent,
                    "swap_total_bytes": swap.total,
                    "swap_used_bytes": swap.used,
                    "swap_usage_percent": swap.percent
                }

            # Disk metrics
            if collect_disk:
                disk_usage = psutil.disk_usage('/')
                disk_io = psutil.disk_io_counters()

                metrics["disk"] = {
                    "total_bytes": disk_usage.total,
                    "used_bytes": disk_usage.used,
                    "free_bytes": disk_usage.free,
                    "usage_percent": (disk_usage.used / disk_usage.total) * 100,
                    "read_bytes": disk_io.read_bytes if disk_io else 0,
                    "write_bytes": disk_io.write_bytes if disk_io else 0,
                    "read_count": disk_io.read_count if disk_io else 0,
                    "write_count": disk_io.write_count if disk_io else 0
                }

            # Network metrics
            if collect_network:
                net_io = psutil.net_io_counters()

                metrics["network"] = {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                    "errin": net_io.errin,
                    "errout": net_io.errout,
                    "dropin": net_io.dropin,
                    "dropout": net_io.dropout
                }

            # Temperature metrics (if enabled and available)
            if collect_temperature:
                temperature_data = {}
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        for name, entries in temps.items():
                            temperature_data[name] = [{"label": entry.label or name, "current": entry.current} for entry in entries]
                        metrics["temperature"] = temperature_data
                except AttributeError:
                    pass

            # Construct final telemetry payload
            telemetry_data = {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "device_id": self.config.get('general', 'DeviceID'),
                **metrics
            }

            return telemetry_data

        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None
    
    def publish_telemetry(self, data):
        """Publish telemetry data to MQTT broker"""
        try:
            if not self.mqtt_connected:
                logger.warning("MQTT not connected, attempting to reconnect")
                if not self.connect_mqtt():
                    logger.error("Failed to reconnect to MQTT broker")
                    return False

            topic = self.config.get('general', 'MQTTTopic')

            # Convert data to JSON string
            payload = json.dumps(data, default=str)
            payload_size = len(payload)
            logger.debug(f"Publishing telemetry to topic '{topic}' (payload size: {payload_size} bytes)")

            # Publish message
            result = self.mqtt_client.publish(topic, payload, qos=1)

            if result.rc == mqtt_client.MQTT_ERR_SUCCESS:
                logger.info(f"Telemetry published successfully to topic: {topic}")
                return True
            else:
                logger.error(f"Failed to publish telemetry with error code: {result.rc}")
                return False

        except Exception as e:
            logger.exception(f"Error publishing telemetry: {e}")
            return False

    def disconnect_mqtt(self):
        """Disconnect from MQTT broker"""
        if self.mqtt_client:
            try:
                logger.info("Disconnecting from MQTT broker")
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
                logger.info("Successfully disconnected from MQTT broker")
            except Exception as e:
                logger.exception(f"Error disconnecting from MQTT broker: {e}")
    
    def run(self):
        """Main service loop"""
        logger.info("Starting Device Telemetry Collector with MQTT")

        # Load configuration
        if not self.load_config():
            logger.error("Failed to load configuration, exiting")
            sys.exit(1)

        # Connect to MQTT broker
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker, exiting")
            sys.exit(1)

        interval = self.config.getint('general', 'TelemetryInterval', fallback=60)
        logger.info(f"Telemetry collection interval: {interval} seconds")

        try:
            while self.running:
                try:
                    # Collect system metrics
                    telemetry_data = self.collect_system_metrics()

                    if telemetry_data:
                        # Publish to MQTT broker
                        success = self.publish_telemetry(telemetry_data)
                        if success:
                            logger.debug("Telemetry cycle completed successfully")
                        else:
                            logger.warning("Telemetry publishing failed")
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

        finally:
            # Clean shutdown
            self.disconnect_mqtt()
            logger.info("Device Telemetry Collector stopped")

def main():
    collector = DeviceTelemetryCollector()
    collector.run()

if __name__ == "__main__":
    main()