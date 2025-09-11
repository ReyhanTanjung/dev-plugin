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

    Test connection to the telemetry endpoint
"""

import os
import json
import requests
from datetime import datetime
from configparser import ConfigParser

device_monitor_config = '/usr/local/etc/devicemonitor/devicemonitor.conf'

result = {}

if os.path.exists(device_monitor_config):
    cnf = ConfigParser()
    cnf.read(device_monitor_config)
    
    if cnf.has_section('general'):
        try:
            # Get configuration values
            endpoint = cnf.get('general', 'APIEndpoint')
            token = cnf.get('general', 'AuthToken')
            device_id = cnf.get('general', 'DeviceID', fallback='DEVICE_1')
            
            # Create test payload
            test_data = {
                "timestamp": datetime.utcnow().isoformat() + 'Z',
                "device_id": device_id,
                "test": True,
                "message": "Connection test from OPNsense Device Monitor"
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'User-Agent': 'OPNsense-DeviceMonitor-Test/1.0'
            }
            
            # Send test request
            response = requests.post(
                endpoint,
                json=test_data,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result['message'] = f'Connection test successful! HTTP {response.status_code}'
                result['response'] = response.text[:200] if response.text else 'No response body'
            else:
                result['message'] = f'Connection test failed: HTTP {response.status_code}'
                result['response'] = response.text[:200] if response.text else 'No response body'
                
        except requests.exceptions.ConnectionError as error:
            result['message'] = f'Connection error: Unable to reach endpoint - {str(error)}'
        except requests.exceptions.Timeout as error:
            result['message'] = f'Connection timeout: Request took too long - {str(error)}'
        except requests.exceptions.HTTPError as error:
            result['message'] = f'HTTP error: {str(error)}'
        except requests.exceptions.RequestException as error:
            result['message'] = f'Request error: {str(error)}'
        except Exception as error:
            result['message'] = f'Unexpected error: {str(error)}'
    else:
        result['message'] = 'Configuration section [general] not found'
else:
    result['message'] = f'Configuration file not found: {device_monitor_config}'

print(json.dumps(result))