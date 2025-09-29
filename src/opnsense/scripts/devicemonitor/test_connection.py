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

    Test connection to the MQTT broker for telemetry
"""

import os
import sys
import json
import time
import logging
from datetime import datetime
from configparser import ConfigParser

# Add current directory to path for paho import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paho.mqtt import client as mqtt_client

# Configure logging for test connection
log_handlers = [logging.StreamHandler()]

# Try to add file handler, but continue if we don't have permissions
try:
    log_handlers.append(logging.FileHandler('/var/log/devicemonitor_test.log'))
except PermissionError:
    try:
        # Try user's home directory instead
        import os
        log_file = os.path.expanduser('~/devicemonitor_test.log')
        log_handlers.append(logging.FileHandler(log_file))
    except:
        pass  # Continue with just console logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [MQTT_TEST] %(message)s',
    handlers=log_handlers
)

logger = logging.getLogger(__name__)

device_monitor_config = '/usr/local/etc/devicemonitor/devicemonitor.conf'

# For testing purposes, allow override via environment variable
import os
if 'DEVICEMONITOR_CONFIG' in os.environ:
    device_monitor_config = os.environ['DEVICEMONITOR_CONFIG']

class MQTTConnectionTester:
    def __init__(self):
        self.connected = False
        self.published = False
        self.error_message = None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            logger.info(f"Successfully connected to MQTT broker with result code {rc}")
        else:
            self.error_message = f"Connection failed with result code {rc}"
            logger.error(f"MQTT connection failed with result code {rc}: {self._get_rc_meaning(rc)}")

    def on_publish(self, client, userdata, mid):
        self.published = True
        logger.info(f"Message published successfully with message ID: {mid}")

    def on_log(self, client, userdata, level, buf):
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

    def test_mqtt_connection(self, broker, port, username, password, topic, device_id):
        test_start_time = time.time()
        try:
            logger.info(f"Starting MQTT connection test")
            logger.info(f"Target broker: {broker}:{port}")
            logger.info(f"Topic: {topic}")
            logger.info(f"Device ID: {device_id}")
            logger.info(f"Authentication: {'Yes' if username and password else 'No'}")

            # Network connectivity check
            logger.debug(f"Testing basic network connectivity to {broker}")
            import socket
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                result = sock.connect_ex((broker, port))
                sock.close()
                if result == 0:
                    logger.debug(f"Basic network connectivity to {broker}:{port} successful")
                else:
                    logger.warning(f"Basic network connectivity to {broker}:{port} failed with code {result}")
            except Exception as e:
                logger.warning(f"Network connectivity test failed: {e}")

            # Create test payload
            test_data = {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "device_id": device_id,
                "test": True,
                "message": "MQTT connection test from OPNsense Device Monitor"
            }

            # Create MQTT client
            client_id = f"opnsense-test-{device_id}-{int(time.time())}"
            logger.info(f"Creating MQTT client with ID: {client_id}")
            client = mqtt_client.Client(client_id)

            # Set authentication if provided
            if username and password:
                logger.info("Setting MQTT authentication credentials")
                client.username_pw_set(username, password)

            # Set callbacks
            client.on_connect = self.on_connect
            client.on_publish = self.on_publish
            client.on_log = self.on_log

            # Connect to broker
            logger.info(f"Attempting to connect to MQTT broker at {broker}:{port}")
            client.connect(broker, port, 60)
            client.loop_start()

            # Wait for connection (max 10 seconds)
            logger.info("Waiting for MQTT connection (timeout: 10 seconds)")
            timeout = 10
            while not self.connected and timeout > 0 and not self.error_message:
                time.sleep(0.5)
                timeout -= 0.5
                if timeout % 2 == 0:  # Log every 1 second
                    logger.debug(f"Still waiting for connection... {timeout} seconds remaining")

            if not self.connected:
                if self.error_message:
                    logger.error(f"Connection failed: {self.error_message}")
                    return {"success": False, "message": self.error_message}
                else:
                    logger.error("Connection timeout - unable to connect to MQTT broker")
                    return {"success": False, "message": "Connection timeout - unable to connect to MQTT broker"}

            # Publish test message
            logger.info(f"Publishing test message to topic: {topic}")
            payload = json.dumps(test_data, default=str)
            logger.debug(f"Test payload: {payload}")
            result = client.publish(topic, payload, qos=1)
            logger.info(f"Publish result code: {result.rc}")

            # Wait for publish confirmation
            logger.info("Waiting for publish confirmation (timeout: 5 seconds)")
            timeout = 5
            while not self.published and timeout > 0:
                time.sleep(0.1)
                timeout -= 0.1

            client.loop_stop()
            client.disconnect()
            logger.info("Disconnected from MQTT broker")

            test_duration = time.time() - test_start_time

            if self.published:
                success_msg = f"MQTT connection test successful! Connected to {broker}:{port} and published to topic '{topic}' in {test_duration:.3f}s"
                logger.info(success_msg)
                return {
                    "success": True,
                    "message": success_msg,
                    "duration_seconds": round(test_duration, 3)
                }
            else:
                failure_msg = f"Connected to MQTT broker but failed to publish message to topic '{topic}' after {test_duration:.3f}s"
                logger.warning(failure_msg)
                return {
                    "success": False,
                    "message": failure_msg,
                    "duration_seconds": round(test_duration, 3)
                }

        except Exception as e:
            test_duration = time.time() - test_start_time
            logger.exception(f"MQTT connection test failed with exception after {test_duration:.3f}s: {str(e)}")
            return {
                "success": False,
                "message": f"MQTT connection test failed: {str(e)}",
                "duration_seconds": round(test_duration, 3)
            }

result = {}

logger.info("=== MQTT Connection Test Started ===")
logger.info(f"Python version: {sys.version}")
logger.info(f"Process PID: {os.getpid()}")
logger.info(f"Working directory: {os.getcwd()}")
logger.info(f"Configuration file: {device_monitor_config}")
logger.info(f"Test started at: {datetime.utcnow().isoformat()}Z")

if os.path.exists(device_monitor_config):
    logger.info(f"Configuration file found: {device_monitor_config}")
    logger.debug(f"Configuration file size: {os.path.getsize(device_monitor_config)} bytes")
    logger.debug(f"Configuration file last modified: {datetime.fromtimestamp(os.path.getmtime(device_monitor_config)).isoformat()}")

    cnf = ConfigParser()
    logger.debug("Parsing configuration file...")
    cnf.read(device_monitor_config)

    if cnf.has_section('general'):
        logger.info("Configuration section [general] found")

        # Log all available configuration keys (without values for security)
        available_keys = list(cnf['general'].keys())
        logger.debug(f"Available configuration keys: {available_keys}")

        try:
            # Get configuration values
            logger.debug("Reading MQTT broker configuration...")
            broker = cnf.get('general', 'MQTTBroker')
            port = cnf.getint('general', 'MQTTPort', fallback=1883)
            username = cnf.get('general', 'MQTTUsername', fallback='')
            password = cnf.get('general', 'MQTTPassword', fallback='')
            topic = cnf.get('general', 'MQTTTopic', fallback='opnsense/telemetry')
            device_id = cnf.get('general', 'DeviceID', fallback='opnsense-device')

            logger.info("Configuration loaded successfully")
            logger.debug(f"Broker: {broker}, Port: {port}, Topic: {topic}, Device ID: {device_id}")
            logger.debug(f"Authentication configured: {'Yes' if username and password else 'No'}")

            # Test MQTT connection
            logger.info("Initializing MQTT connection tester...")
            tester = MQTTConnectionTester()

            logger.info("Starting MQTT connection test...")
            test_start_time = time.time()
            test_result = tester.test_mqtt_connection(broker, port, username, password, topic, device_id)
            test_duration = time.time() - test_start_time

            logger.info(f"MQTT connection test completed in {test_duration:.3f} seconds")

            result['message'] = test_result['message']
            result['test_duration_seconds'] = round(test_duration, 3)
            if test_result['success']:
                result['status'] = 'success'
                logger.info("=== MQTT Connection Test PASSED ===")
                logger.info(f"Test summary: Connected to {broker}:{port}, published to '{topic}' in {test_duration:.3f}s")
            else:
                result['status'] = 'error'
                logger.error("=== MQTT Connection Test FAILED ===")
                logger.error(f"Test summary: Failed to connect/publish to {broker}:{port} after {test_duration:.3f}s")

        except Exception as error:
            error_msg = f'Configuration error: {str(error)}'
            logger.exception(error_msg)
            logger.error(f"Configuration error details: {error}")
            result['message'] = error_msg
            result['status'] = 'error'
    else:
        error_msg = 'Configuration section [general] not found'
        logger.error(error_msg)
        result['message'] = error_msg
        result['status'] = 'error'
else:
    error_msg = f'Configuration file not found: {device_monitor_config}'
    logger.error(error_msg)
    result['message'] = error_msg
    result['status'] = 'error'

# Add timestamp to final result
result['test_timestamp'] = datetime.utcnow().isoformat() + 'Z'
result['test_completed_at'] = datetime.now().isoformat()

logger.info(f"=== Test completed at: {datetime.now().isoformat()} ===")
logger.info(f"Final result: {json.dumps(result, indent=2)}")
print(json.dumps(result))