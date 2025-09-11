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

    perform some tests for the helloworld application
"""
import os
import socket
import smtplib
import json
from configparser import ConfigParser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# set default timeout to 10 seconds for SMTP
socket.setdefaulttimeout(10)

hello_world_config = '/usr/local/etc/helloworld/helloworld.conf'

result = {}
if os.path.exists(hello_world_config):
    cnf = ConfigParser()
    cnf.read(hello_world_config)
    if cnf.has_section('general'):
        try:
            # Get configuration values
            smtp_host = cnf.get('general', 'SMTPHost')
            smtp_port = int(cnf.get('general', 'SMTPPort', fallback='587'))
            smtp_username = cnf.get('general', 'SMTPUsername')
            smtp_password = cnf.get('general', 'SMTPPassword')
            from_email = cnf.get('general', 'FromEmail')
            to_email = cnf.get('general', 'ToEmail')
            subject = cnf.get('general', 'Subject', fallback='Test Email from OPNsense')
            description = cnf.get('general', 'Description', fallback='Test message!')

            # Create message
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(description, 'plain'))

            # Connect to SMTP server with TLS
            smtpObj = smtplib.SMTP(smtp_host, smtp_port)
            smtpObj.starttls()  # Enable TLS encryption
            smtpObj.login(smtp_username, smtp_password)  # Authenticate
            
            # Send email
            smtpObj.sendmail(from_email, [to_email], msg.as_string())
            smtpObj.quit()
            result['message'] = 'Email sent successfully!'
            
        except smtplib.SMTPAuthenticationError as error:
            result['message'] = 'SMTP Authentication failed: %s' % error
        except smtplib.SMTPException as error:
            result['message'] = 'SMTP error: %s' % error
        except socket.error as error:
            if error.strerror is None:
                result['message'] = 'Connection timeout!'
            else:
                result['message'] = 'Connection error: %s' % error.strerror
        except ValueError as error:
            result['message'] = 'Configuration error: %s' % error
        except Exception as error:
            result['message'] = 'Unexpected error: %s' % error
    else:
        result['message'] = 'Configuration section [general] not found'
else:
    result['message'] = 'Configuration file not found: %s' % hello_world_config


print (json.dumps(result))
