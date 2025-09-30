# Device Monitor Plugin for OPNsense

## Overview

The Device Monitor plugin provides telemetry monitoring capabilities for OPNsense. It collects and reports system metrics including CPU usage, memory consumption, disk utilization, network statistics, and optional temperature data via MQTT protocol to remote monitoring endpoints.

## Features

### System Metrics Collection

The plugin collects the following system metrics:

#### Core Metrics (Enabled by Default)

1. **CPU Metrics**
   - Overall CPU usage percentage
   - Per-core CPU usage
   - CPU frequency information
   - CPU core count

2. **Memory Metrics**
   - Total, available, and used RAM
   - Memory usage percentage
   - Cached and buffered memory
   - Swap memory total, used, and usage percentage

3. **Disk Metrics**
   - Root filesystem usage (total, used, free)
   - Disk I/O statistics (read/write bytes and counts)
   - Per-partition usage for all mounted filesystems
   - Partition filesystem types and mount points

4. **Network Metrics**
   - Global network I/O counters (bytes sent/received)
   - Packet statistics (sent/received)
   - Network errors and drops (input/output)
   - Per-interface statistics
   - Network interface addresses and configurations

5. **System Information**
   - System uptime
   - Load averages (1, 5, 15 minutes)
   - Process count
   - Active users

#### Optional Metrics

1. **Temperature Metrics** (Disabled by Default)
   - System temperature sensors
   - Per-sensor current, high, and critical thresholds
   - Multi-group temperature monitoring

### MQTT Integration

- **Protocol**: MQTT
- **QoS**: 1
- **Authentication**: Optional username/password authentication
- **Connection Management**: Automatic reconnection on disconnect
- **Configurable**: Broker address, port, topic, and credentials

### Service Management

- **Start/Stop/Restart**: Full service lifecycle control
- **Status Monitoring**: Real-time service status checking
- **Daemon Mode**: Runs as background daemon
- **PID File Management**: Process tracking via /var/run/devicemonitor.pid
- **Graceful Shutdown**: SIGTERM-based graceful termination with SIGKILL fallback

## Architecture

### File Structure

```
devicemonitor/
├── Makefile
├── pkg-descr
├── README.md
└── src/
    └── opnsense/
        ├── mvc/
        │   └── app/
        │       ├── controllers/
        │       │   └── OPNsense/DeviceMonitor/
        │       │       ├── IndexController.php
        │       │       ├── forms/general.xml
        │       │       └── Api/
        │       │           ├── ServiceController.php
        │       │           └── SettingsController.php
        │       └── models/
        │           └── OPNsense/DeviceMonitor/
        │               ├── DeviceMonitor.xml
        │               ├── DeviceMonitor.php
        │               ├── ACL/ACL.xml
        │               └── Menu/Menu.xml
        ├── scripts/
        │   └── devicemonitor/
        │       ├── telemetry_collector.py
        │       ├── restart_service.py
        │       ├── test_connection.py
        │       ├── paho/
        │       └── psutil/
        └── service/
            ├── conf/actions.d/
            └── templates/
                └── OPNsense/DeviceMonitor/
```

### Core Components

#### 1. Telemetry Collector (`telemetry_collector.py`)

The main service daemon that:
- Loads configuration from `/usr/local/etc/devicemonitor/devicemonitor.conf`
- Establishes and maintains MQTT connection
- Collects system metrics at configurable intervals
- Publishes telemetry data to MQTT broker
- Handles errors and reconnection logic
- Provides comprehensive logging

#### 2. Service Controller (`restart_service.py`)

Service lifecycle management script that provides:
- Start: Launch daemon with PID tracking
- Stop: Graceful shutdown with forced kill fallback
- Restart: Stop and start sequence
- Status: Current service state checking

**Operational Details:**
- PID file location: `/var/run/devicemonitor.pid`
- Graceful shutdown timeout: 10 seconds
- Post-start verification delay: 2 seconds
- Service script: `/usr/local/opnsense/scripts/devicemonitor/telemetry_collector.py`

#### 3. Connection Tester (`test_connection.py`)

MQTT connection validation utility that:
- Tests network connectivity to broker
- Validates MQTT authentication
- Publishes test message
- Confirms message delivery

#### 4. Configuration Model (`DeviceMonitor.xml`)

Defines the data model for plugin configuration:

**General Settings:**
- `Enabled` (Boolean): Enable/disable service
- `MQTTBroker` (NetworkField): MQTT broker address
- `MQTTPort` (Integer): MQTT broker port
- `MQTTUsername` (Text): Optional authentication username
- `MQTTPassword` (Text): Optional authentication password
- `MQTTTopic` (Text): MQTT topic for publishing
- `TelemetryInterval` (Integer): Collection interval in seconds
- `DeviceID` (Text): Unique device identifier

**Metric Toggles:**
- `CollectCPU` (Boolean): Enable CPU metrics
- `CollectMemory` (Boolean): Enable memory metrics
- `CollectNetwork` (Boolean): Enable network metrics
- `CollectDisk` (Boolean): Enable disk metrics
- `CollectTemperature` (Boolean): Enable temperature sensors

## Configuration

### Via OPNsense Web Interface

1. Navigate to **Services → Device Monitor**
2. Configure MQTT broker settings:
   - Broker IP address
   - Port
   - Username and password
   - Topic name for telemetry data
3. Set device identifier
4. Configure collection interval
5. Enable/disable specific metrics
6. Enable the service
7. Click "Test Connection" to validate settings
8. Click "Apply" to save configuration
9. Click "Start" to begin monitoring

### Configuration File Location

**Primary:** `/usr/local/etc/devicemonitor/devicemonitor.conf`
**Fallback (Testing):** `/tmp/devicemonitor_test/devicemonitor.conf`

Configuration can be overridden via environment variable:
```bash
export DEVICEMONITOR_CONFIG=/path/to/custom/config.conf
```

### Sample Configuration

```ini
[general]
Enabled = 1
MQTTBroker = mqtt.example.com
MQTTPort = 1883
MQTTUsername = opnsense_device
MQTTPassword = secure_password_here
MQTTTopic = opnsense/telemetry/fw01
TelemetryInterval = 60
DeviceID = opnsense-fw01
CollectCPU = 1
CollectMemory = 1
CollectNetwork = 1
CollectDisk = 1
CollectTemperature = 0
```

## Usage

### Service Commands

#### Start Service
```bash
/usr/local/opnsense/scripts/devicemonitor/restart_service.py start
```

#### Stop Service
```bash
/usr/local/opnsense/scripts/devicemonitor/restart_service.py stop
```

#### Restart Service
```bash
/usr/local/opnsense/scripts/devicemonitor/restart_service.py restart
```

#### Check Status
```bash
/usr/local/opnsense/scripts/devicemonitor/restart_service.py status
```

### Test MQTT Connection

```bash
python3 /usr/local/opnsense/scripts/devicemonitor/test_connection.py
```

**Output Format:** JSON with test results
```json
{
  "status": "success",
  "message": "MQTT connection test successful! Connected to broker:1883 and published to topic 'opnsense/telemetry' in 1.234s",
  "test_duration_seconds": 1.234,
  "test_timestamp": "2025-09-30T12:00:00.000000Z",
  "test_completed_at": "2025-09-30T14:00:00.000000"
}
```

## Telemetry Data Format

### MQTT Message Structure

```json
{
  "timestamp": "2025-09-30T12:00:00.000000Z",
  "device_id": "opnsense-fw01",
  "collection_time_seconds": 1.234,
  "metrics_enabled": {
    "cpu": true,
    "memory": true,
    "network": true,
    "disk": true,
    "temperature": false
  },
  "system": {
    "uptime_seconds": 86400,
    "load_average": {
      "1min": 0.5,
      "5min": 0.3,
      "15min": 0.2
    },
    "process_count": 150,
    "active_users": 1
  },
  "cpu": {
    "usage_percent": 25.5,
    "core_count": 4,
    "frequency_mhz": 2400.0,
    "per_core_usage": [20.0, 25.0, 30.0, 26.0]
  },
  "memory": {
    "total_bytes": 8589934592,
    "available_bytes": 4294967296,
    "used_bytes": 4294967296,
    "usage_percent": 50.0,
    "cached_bytes": 1073741824,
    "buffers_bytes": 536870912,
    "swap_total_bytes": 2147483648,
    "swap_used_bytes": 0,
    "swap_usage_percent": 0.0
  },
  "disk": {
    "total_bytes": 107374182400,
    "used_bytes": 53687091200,
    "free_bytes": 53687091200,
    "usage_percent": 50.0,
    "read_bytes": 10737418240,
    "write_bytes": 5368709120,
    "read_count": 10000,
    "write_count": 5000,
    "partitions": {
      "/dev/ada0p2": {
        "mountpoint": "/",
        "fstype": "ufs",
        "total_bytes": 107374182400,
        "used_bytes": 53687091200,
        "free_bytes": 53687091200,
        "usage_percent": 50.0
      }
    }
  },
  "network": {
    "bytes_sent": 1073741824,
    "bytes_recv": 2147483648,
    "packets_sent": 1000000,
    "packets_recv": 1500000,
    "errin": 0,
    "errout": 0,
    "dropin": 0,
    "dropout": 0,
    "interfaces": {
      "em0": {
        "bytes_sent": 536870912,
        "bytes_recv": 1073741824,
        "packets_sent": 500000,
        "packets_recv": 750000,
        "errin": 0,
        "errout": 0,
        "dropin": 0,
        "dropout": 0
      }
    },
    "interface_addresses": {
      "em0": [
        {
          "family": "AddressFamily.AF_INET",
          "address": "192.168.1.1",
          "netmask": "255.255.255.0",
          "broadcast": "192.168.1.255"
        }
      ]
    }
  }
}
```

### Message Publishing

- **QoS Level**: 1
- **Retained**: No
- **Format**: JSON with UTC timestamps

## Logging

### Log Locations

1. `/var/log/devicemonitor.log` (production)
2. `/tmp/devicemonitor.log` (fallback)
3. `~/devicemonitor.log` (user home)
4. `./devicemonitor.log` (current directory)

## Dependencies

### Embedded Libraries

- **paho-mqtt**: MQTT client library (embedded in plugin)
- **psutil**: Cross-platform system utilities (embedded in plugin)

## References

- OPNsense Documentation: https://docs.opnsense.org/
- MQTT Protocol: https://mqtt.org/
- Paho MQTT Python Client: https://www.eclipse.org/paho/
- psutil Documentation: https://psutil.readthedocs.io/