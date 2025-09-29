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

            # If production config doesn't exist, fall back to test config
            if not os.path.exists(config_file) and os.path.exists('/tmp/devicemonitor_test/devicemonitor.conf'):
                config_file = '/tmp/devicemonitor_test/devicemonitor.conf'
                logger.warning(f"Production config not found, using fallback: {config_file}")
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
        logger.info("Starting comprehensive system metrics collection cycle")
        start_time = time.time()
        try:
            metrics = {}

            # Check which metrics to collect based on configuration
            collect_cpu = self.config.getboolean('general', 'CollectCPU', fallback=True)
            collect_memory = self.config.getboolean('general', 'CollectMemory', fallback=True)
            collect_network = self.config.getboolean('general', 'CollectNetwork', fallback=True)
            collect_disk = self.config.getboolean('general', 'CollectDisk', fallback=True)
            collect_temperature = self.config.getboolean('general', 'CollectTemperature', fallback=False)

            # Basic system info
            logger.debug("Starting system metrics collection")
            try:
                logger.debug("Collecting system boot time and uptime")
                boot_time = psutil.boot_time()
                uptime_seconds = int(time.time() - boot_time)
                logger.debug(f"System uptime: {uptime_seconds} seconds ({uptime_seconds/3600:.2f} hours)")

                logger.debug("Collecting system load averages")
                load_avg = os.getloadavg()
                logger.debug(f"Load averages: 1min={load_avg[0]:.2f}, 5min={load_avg[1]:.2f}, 15min={load_avg[2]:.2f}")

                logger.debug("Collecting process count")
                process_count = len(psutil.pids())
                logger.debug(f"Total processes: {process_count}")

                # Additional system information
                logger.debug("Collecting additional system information")
                users = psutil.users()
                logger.debug(f"Active users: {len(users)}")

                metrics["system"] = {
                    "uptime_seconds": uptime_seconds,
                    "load_average": {
                        "1min": load_avg[0],
                        "5min": load_avg[1],
                        "15min": load_avg[2]
                    },
                    "process_count": process_count,
                    "active_users": len(users)
                }

                logger.info(f"System metrics collected successfully: uptime={uptime_seconds/3600:.2f}h, "
                          f"load={load_avg[0]:.2f}, processes={process_count}, users={len(users)}")
            except Exception as e:
                logger.error(f"Error collecting system metrics: {e}")
                logger.exception("System metrics collection failed")
                metrics["system"] = {"error": str(e)}

            # CPU metrics
            if collect_cpu:
                logger.debug("Starting CPU metrics collection")
                try:
                    logger.debug("Collecting CPU usage percentage with 1-second interval")
                    cpu_percent = psutil.cpu_percent(interval=1)
                    logger.debug(f"CPU usage: {cpu_percent}%")

                    logger.debug("Collecting CPU core count")
                    cpu_count = psutil.cpu_count()
                    logger.debug(f"CPU cores: {cpu_count}")

                    logger.debug("Collecting CPU frequency information")
                    cpu_freq = psutil.cpu_freq()
                    if cpu_freq:
                        logger.debug(f"CPU frequency: current={cpu_freq.current}MHz, min={cpu_freq.min}MHz, max={cpu_freq.max}MHz")
                    else:
                        logger.debug("CPU frequency information not available")

                    # Collect per-core CPU usage
                    logger.debug("Collecting per-core CPU usage")
                    cpu_per_core = psutil.cpu_percent(percpu=True)
                    logger.debug(f"Per-core CPU usage: {cpu_per_core}")

                    metrics["cpu"] = {
                        "usage_percent": cpu_percent,
                        "core_count": cpu_count,
                        "frequency_mhz": cpu_freq.current if cpu_freq else None,
                        "per_core_usage": cpu_per_core
                    }

                    logger.info(f"CPU metrics collected successfully: {cpu_percent}% usage across {cpu_count} cores")
                except Exception as e:
                    logger.error(f"Error collecting CPU metrics: {e}")
                    logger.exception("CPU metrics collection failed")
                    metrics["cpu"] = {"error": str(e)}

            # Memory metrics
            if collect_memory:
                logger.debug("Starting memory metrics collection")
                try:
                    logger.debug("Collecting virtual memory information")
                    memory = psutil.virtual_memory()
                    logger.debug(f"Virtual memory: total={memory.total/1024/1024/1024:.2f}GB, "
                               f"available={memory.available/1024/1024/1024:.2f}GB, "
                               f"used={memory.used/1024/1024/1024:.2f}GB, usage={memory.percent}%")

                    logger.debug("Collecting swap memory information")
                    swap = psutil.swap_memory()
                    logger.debug(f"Swap memory: total={swap.total/1024/1024/1024:.2f}GB, "
                               f"used={swap.used/1024/1024/1024:.2f}GB, usage={swap.percent}%")

                    metrics["memory"] = {
                        "total_bytes": memory.total,
                        "available_bytes": memory.available,
                        "used_bytes": memory.used,
                        "usage_percent": memory.percent,
                        "cached_bytes": getattr(memory, 'cached', 0),
                        "buffers_bytes": getattr(memory, 'buffers', 0),
                        "swap_total_bytes": swap.total,
                        "swap_used_bytes": swap.used,
                        "swap_usage_percent": swap.percent
                    }

                    logger.info(f"Memory metrics collected successfully: {memory.percent}% RAM usage, {swap.percent}% swap usage")
                except Exception as e:
                    logger.error(f"Error collecting memory metrics: {e}")
                    logger.exception("Memory metrics collection failed")
                    metrics["memory"] = {"error": str(e)}

            # Disk metrics
            if collect_disk:
                logger.debug("Starting disk metrics collection")
                try:
                    logger.debug("Collecting root filesystem usage")
                    disk_usage = psutil.disk_usage('/')
                    usage_percent = (disk_usage.used / disk_usage.total) * 100
                    logger.debug(f"Root disk usage: total={disk_usage.total/1024/1024/1024:.2f}GB, "
                               f"used={disk_usage.used/1024/1024/1024:.2f}GB, "
                               f"free={disk_usage.free/1024/1024/1024:.2f}GB, usage={usage_percent:.2f}%")

                    logger.debug("Collecting disk I/O counters")
                    disk_io = psutil.disk_io_counters()
                    if disk_io:
                        logger.debug(f"Disk I/O: read_bytes={disk_io.read_bytes/1024/1024:.2f}MB, "
                                   f"write_bytes={disk_io.write_bytes/1024/1024:.2f}MB, "
                                   f"read_count={disk_io.read_count}, write_count={disk_io.write_count}")
                    else:
                        logger.debug("Disk I/O counters not available")

                    # Collect per-disk usage for all mounted filesystems
                    logger.debug("Collecting per-disk usage for all mounted filesystems")
                    disk_partitions = psutil.disk_partitions()
                    per_disk_usage = {}
                    for partition in disk_partitions:
                        try:
                            partition_usage = psutil.disk_usage(partition.mountpoint)
                            partition_usage_percent = (partition_usage.used / partition_usage.total) * 100
                            per_disk_usage[partition.device] = {
                                "mountpoint": partition.mountpoint,
                                "fstype": partition.fstype,
                                "total_bytes": partition_usage.total,
                                "used_bytes": partition_usage.used,
                                "free_bytes": partition_usage.free,
                                "usage_percent": partition_usage_percent
                            }
                            logger.debug(f"Partition {partition.device} at {partition.mountpoint}: {partition_usage_percent:.2f}% used")
                        except PermissionError:
                            logger.debug(f"Permission denied accessing partition {partition.device}")
                        except Exception as pe:
                            logger.debug(f"Error accessing partition {partition.device}: {pe}")

                    metrics["disk"] = {
                        "total_bytes": disk_usage.total,
                        "used_bytes": disk_usage.used,
                        "free_bytes": disk_usage.free,
                        "usage_percent": usage_percent,
                        "read_bytes": disk_io.read_bytes if disk_io else 0,
                        "write_bytes": disk_io.write_bytes if disk_io else 0,
                        "read_count": disk_io.read_count if disk_io else 0,
                        "write_count": disk_io.write_count if disk_io else 0,
                        "partitions": per_disk_usage
                    }

                    logger.info(f"Disk metrics collected successfully: {usage_percent:.2f}% root disk usage, {len(per_disk_usage)} partitions monitored")
                except Exception as e:
                    logger.error(f"Error collecting disk metrics: {e}")
                    logger.exception("Disk metrics collection failed")
                    metrics["disk"] = {"error": str(e)}

            # Network metrics
            if collect_network:
                logger.debug("Starting network metrics collection")
                try:
                    logger.debug("Collecting global network I/O counters")
                    net_io = psutil.net_io_counters()
                    logger.debug(f"Global network I/O: sent={net_io.bytes_sent/1024/1024:.2f}MB, "
                               f"recv={net_io.bytes_recv/1024/1024:.2f}MB, "
                               f"packets_sent={net_io.packets_sent}, packets_recv={net_io.packets_recv}")
                    logger.debug(f"Network errors: errin={net_io.errin}, errout={net_io.errout}, "
                               f"dropin={net_io.dropin}, dropout={net_io.dropout}")

                    # Collect per-interface statistics
                    logger.debug("Collecting per-interface network statistics")
                    net_io_per_nic = psutil.net_io_counters(pernic=True)
                    per_interface_stats = {}
                    active_interfaces = 0
                    for interface, stats in net_io_per_nic.items():
                        if stats.bytes_sent > 0 or stats.bytes_recv > 0:
                            active_interfaces += 1
                            per_interface_stats[interface] = {
                                "bytes_sent": stats.bytes_sent,
                                "bytes_recv": stats.bytes_recv,
                                "packets_sent": stats.packets_sent,
                                "packets_recv": stats.packets_recv,
                                "errin": stats.errin,
                                "errout": stats.errout,
                                "dropin": stats.dropin,
                                "dropout": stats.dropout
                            }
                            logger.debug(f"Interface {interface}: sent={stats.bytes_sent/1024/1024:.2f}MB, "
                                       f"recv={stats.bytes_recv/1024/1024:.2f}MB")

                    # Collect network interface addresses
                    logger.debug("Collecting network interface addresses")
                    net_addresses = psutil.net_if_addrs()
                    interface_addresses = {}
                    for interface, addresses in net_addresses.items():
                        interface_addresses[interface] = []
                        for addr in addresses:
                            interface_addresses[interface].append({
                                "family": str(addr.family),
                                "address": addr.address,
                                "netmask": addr.netmask,
                                "broadcast": addr.broadcast
                            })

                    metrics["network"] = {
                        "bytes_sent": net_io.bytes_sent,
                        "bytes_recv": net_io.bytes_recv,
                        "packets_sent": net_io.packets_sent,
                        "packets_recv": net_io.packets_recv,
                        "errin": net_io.errin,
                        "errout": net_io.errout,
                        "dropin": net_io.dropin,
                        "dropout": net_io.dropout,
                        "interfaces": per_interface_stats,
                        "interface_addresses": interface_addresses
                    }

                    logger.info(f"Network metrics collected successfully: {active_interfaces} active interfaces, "
                              f"total sent={net_io.bytes_sent/1024/1024:.2f}MB, total recv={net_io.bytes_recv/1024/1024:.2f}MB")
                except Exception as e:
                    logger.error(f"Error collecting network metrics: {e}")
                    logger.exception("Network metrics collection failed")
                    metrics["network"] = {"error": str(e)}

            # Temperature metrics (if enabled and available)
            if collect_temperature:
                logger.debug("Starting temperature metrics collection")
                temperature_data = {}
                try:
                    logger.debug("Attempting to collect system temperature sensors")
                    temps = psutil.sensors_temperatures()
                    if temps:
                        sensor_count = 0
                        for name, entries in temps.items():
                            logger.debug(f"Found temperature sensor group: {name}")
                            temperature_data[name] = []
                            for entry in entries:
                                temp_info = {
                                    "label": entry.label or name,
                                    "current": entry.current,
                                    "high": getattr(entry, 'high', None),
                                    "critical": getattr(entry, 'critical', None)
                                }
                                temperature_data[name].append(temp_info)
                                sensor_count += 1
                                logger.debug(f"Sensor {entry.label or name}: {entry.current}°C "
                                           f"(high: {getattr(entry, 'high', 'N/A')}, "
                                           f"critical: {getattr(entry, 'critical', 'N/A')})")

                        metrics["temperature"] = temperature_data
                        logger.info(f"Temperature metrics collected successfully: {sensor_count} sensors from {len(temps)} groups")
                    else:
                        logger.info("No temperature sensors found or not available on this system")
                        metrics["temperature"] = {"note": "No temperature sensors available"}
                except AttributeError:
                    logger.debug("Temperature sensors not supported on this system (AttributeError)")
                    metrics["temperature"] = {"note": "Temperature sensors not supported"}
                except Exception as e:
                    logger.error(f"Error collecting temperature metrics: {e}")
                    logger.exception("Temperature metrics collection failed")
                    metrics["temperature"] = {"error": str(e)}

            # Construct final telemetry payload
            collection_time = time.time() - start_time
            logger.debug(f"Metrics collection completed in {collection_time:.3f} seconds")

            telemetry_data = {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "device_id": self.config.get('general', 'DeviceID'),
                "collection_time_seconds": round(collection_time, 3),
                "metrics_enabled": {
                    "cpu": self.config.getboolean('general', 'CollectCPU', fallback=True),
                    "memory": self.config.getboolean('general', 'CollectMemory', fallback=True),
                    "network": self.config.getboolean('general', 'CollectNetwork', fallback=True),
                    "disk": self.config.getboolean('general', 'CollectDisk', fallback=True),
                    "temperature": self.config.getboolean('general', 'CollectTemperature', fallback=False)
                },
                **metrics
            }

            # Calculate payload size for logging
            payload_preview = json.dumps(telemetry_data, default=str)
            payload_size = len(payload_preview)

            logger.info(f"System metrics collection completed successfully in {collection_time:.3f}s, payload size: {payload_size} bytes")
            logger.debug(f"Collected metrics categories: {list(metrics.keys())}")

            return telemetry_data

        except Exception as e:
            collection_time = time.time() - start_time
            logger.error(f"Error collecting system metrics after {collection_time:.3f}s: {e}")
            logger.exception("System metrics collection failed")
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
        logger.info("=== Starting Device Telemetry Collector with MQTT ===")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Process PID: {os.getpid()}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Configuration file: {self.config_file}")

        # Load configuration
        logger.info("Loading configuration...")
        if not self.load_config():
            logger.error("Failed to load configuration, exiting")
            sys.exit(1)
        logger.info("Configuration loaded successfully")

        # Connect to MQTT broker
        logger.info("Establishing MQTT connection...")
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker, exiting")
            sys.exit(1)
        logger.info("MQTT connection established successfully")

        interval = self.config.getint('general', 'TelemetryInterval', fallback=60)
        logger.info(f"Telemetry collection interval: {interval} seconds")

        # Log what metrics will be collected
        enabled_metrics = []
        if self.config.getboolean('general', 'CollectCPU', fallback=True):
            enabled_metrics.append('CPU')
        if self.config.getboolean('general', 'CollectMemory', fallback=True):
            enabled_metrics.append('Memory')
        if self.config.getboolean('general', 'CollectNetwork', fallback=True):
            enabled_metrics.append('Network')
        if self.config.getboolean('general', 'CollectDisk', fallback=True):
            enabled_metrics.append('Disk')
        if self.config.getboolean('general', 'CollectTemperature', fallback=False):
            enabled_metrics.append('Temperature')

        logger.info(f"Enabled metrics collection: {', '.join(enabled_metrics)}")
        logger.info("=== Device Telemetry Collector startup complete, entering main loop ===")

        cycle_count = 0
        try:
            while self.running:
                cycle_count += 1
                cycle_start_time = time.time()
                logger.debug(f"=== Starting telemetry collection cycle #{cycle_count} ===")

                try:
                    # Collect system metrics
                    logger.debug("Initiating system metrics collection")
                    telemetry_data = self.collect_system_metrics()

                    if telemetry_data:
                        # Publish to MQTT broker
                        logger.debug("Initiating telemetry data publication")
                        success = self.publish_telemetry(telemetry_data)
                        if success:
                            cycle_time = time.time() - cycle_start_time
                            logger.info(f"Telemetry cycle #{cycle_count} completed successfully in {cycle_time:.3f}s")
                        else:
                            logger.warning(f"Telemetry cycle #{cycle_count} - publishing failed")
                    else:
                        logger.error(f"Telemetry cycle #{cycle_count} - failed to collect system metrics")

                    # Wait for next interval
                    logger.debug(f"Waiting {interval} seconds until next collection cycle")
                    time.sleep(interval)

                except KeyboardInterrupt:
                    logger.info("Received shutdown signal (KeyboardInterrupt)")
                    self.running = False
                except Exception as e:
                    cycle_time = time.time() - cycle_start_time
                    logger.error(f"Unexpected error in telemetry cycle #{cycle_count} after {cycle_time:.3f}s: {e}")
                    logger.exception("Main loop exception details")
                    logger.info(f"Continuing after error, waiting {interval} seconds...")
                    time.sleep(interval)

        finally:
            # Clean shutdown
            logger.info(f"=== Initiating clean shutdown after {cycle_count} collection cycles ===")
            self.disconnect_mqtt()
            logger.info("=== Device Telemetry Collector stopped gracefully ===")

def main():
    collector = DeviceTelemetryCollector()
    collector.run()

if __name__ == "__main__":
    main()