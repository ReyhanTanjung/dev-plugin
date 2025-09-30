{#

OPNsense® is Copyright © 2014 – 2015 by Deciso B.V.
All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1.  Redistributions of source code must retain the above copyright notice,
this list of conditions and the following disclaimer.

2.  Redistributions in binary form must reproduce the above copyright notice,
this list of conditions and the following disclaimer in the documentation
and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

#}

<script>
    $( document ).ready(function() {
        mapDataToFormUI({'frm_GeneralSettings':"/api/devicemonitor/settings/get"}).done(function(data){
            // place actions to run after load, for example update form styles.
            updateServiceStatus();
        });

        // link save button to API set action
        $("#saveAct").click(function(){
            saveFormToEndpoint("/api/devicemonitor/settings/set",'frm_GeneralSettings',function(){
                // Show success notification
                $("#responseMsg").removeClass("hidden").html('<span class="text-success">Configuration saved successfully!</span>');

                // action to run after successful save, for example reconfigure service.
                ajaxCall(url="/api/devicemonitor/service/reload", sendData={},callback=function(data,status) {
                    // action to run after reload
                    updateServiceStatus();

                    // Show reload status
                    if (data && data.status === 'ok') {
                        $("#responseMsg").html('<span class="text-success">Configuration saved and reloaded successfully!</span>');
                    } else {
                        $("#responseMsg").html('<span class="text-warning">Configuration saved but reload failed. Status: ' + (data.status || 'unknown') + '</span>');
                    }
                });
            }, function(data, status) {
                // Error callback - show error message
                var errorMsg = 'Failed to save configuration';
                if (data && data.responseJSON && data.responseJSON.message) {
                    errorMsg += ': ' + data.responseJSON.message;
                }
                $("#responseMsg").removeClass("hidden").html('<span class="text-danger">' + errorMsg + '</span>');
            });
        });

        // Test connection button
        $("#testAct").SimpleActionButton({
            onAction: function(data) {
                $("#responseMsg").removeClass("hidden").html(data['message']);
            }
        });

        // Service control buttons
        $("#startAct").SimpleActionButton({
            onAction: function(data) {
                if (data && data.status) {
                    var statusMsg = "Service start: " + data.status;
                    var statusClass = data.status.includes('started') || data.status.includes('already_running') ? 'text-success' : 'text-warning';
                    $("#responseMsg").removeClass("hidden").html('<span class="' + statusClass + '">' + statusMsg + '</span>');
                } else {
                    $("#responseMsg").removeClass("hidden").html('<span class="text-danger">Service start failed - no response</span>');
                }
                updateServiceStatus();
            },
            onError: function(data) {
                $("#responseMsg").removeClass("hidden").html('<span class="text-danger">Service start failed: ' + (data.responseText || 'Unknown error') + '</span>');
            }
        });

        $("#stopAct").SimpleActionButton({
            onAction: function(data) {
                if (data && data.status) {
                    var statusMsg = "Service stop: " + data.status;
                    var statusClass = data.status.includes('stopped') || data.status.includes('not_running') ? 'text-success' : 'text-warning';
                    $("#responseMsg").removeClass("hidden").html('<span class="' + statusClass + '">' + statusMsg + '</span>');
                } else {
                    $("#responseMsg").removeClass("hidden").html('<span class="text-danger">Service stop failed - no response</span>');
                }
                updateServiceStatus();
            },
            onError: function(data) {
                $("#responseMsg").removeClass("hidden").html('<span class="text-danger">Service stop failed: ' + (data.responseText || 'Unknown error') + '</span>');
            }
        });

        $("#restartAct").SimpleActionButton({
            onAction: function(data) {
                if (data && data.status) {
                    var statusMsg = "Service restart: " + data.status;
                    var statusClass = data.status.includes('started') ? 'text-success' : 'text-warning';
                    $("#responseMsg").removeClass("hidden").html('<span class="' + statusClass + '">' + statusMsg + '</span>');
                } else {
                    $("#responseMsg").removeClass("hidden").html('<span class="text-danger">Service restart failed - no response</span>');
                }
                updateServiceStatus();
            },
            onError: function(data) {
                $("#responseMsg").removeClass("hidden").html('<span class="text-danger">Service restart failed: ' + (data.responseText || 'Unknown error') + '</span>');
            }
        });

        // Function to update service status
        function updateServiceStatus() {
            ajaxCall(url="/api/devicemonitor/service/status", sendData={}, callback=function(data,status) {
                var statusText = data['status'] || 'unknown';
                var statusClass = statusText === 'running' ? 'success' : 'danger';
                $("#serviceStatus").html('<span class="label label-' + statusClass + '">' + statusText.toUpperCase() + '</span>');
            });
        }

        // Update status every 5 seconds
        setInterval(updateServiceStatus, 5000);
    });
</script>

<div class="alert alert-info hidden" role="alert" id="responseMsg">

</div>

<div class="row">
    <div class="col-md-12">
        <div class="panel panel-default">
            <div class="panel-heading">
                <h3 class="panel-title">Service Status</h3>
            </div>
            <div class="panel-body">
                <p>Current Status: <span id="serviceStatus"><span class="label label-default">UNKNOWN</span></span></p>
            </div>
        </div>
    </div>
</div>

<div class="col-md-12">
    {{ partial("layout_partials/base_form",['fields':generalForm,'id':'frm_GeneralSettings'])}}
</div>

<div class="col-md-12">
    <hr/>
    <button class="btn btn-primary" id="saveAct" type="button"><b>{{ lang._('Save') }}</b></button>
    <button class="btn btn-info" id="testAct" data-endpoint="/api/devicemonitor/service/test" data-label="{{ lang._('Test Connection') }}"></button>
    
    <div class="btn-group" role="group" style="margin-left: 20px;">
        <button class="btn btn-success" id="startAct" data-endpoint="/api/devicemonitor/service/start" data-label="{{ lang._('Start') }}"></button>
        <button class="btn btn-warning" id="stopAct" data-endpoint="/api/devicemonitor/service/stop" data-label="{{ lang._('Stop') }}"></button>
        <button class="btn btn-primary" id="restartAct" data-endpoint="/api/devicemonitor/service/restart" data-label="{{ lang._('Restart') }}"></button>
    </div>
</div>