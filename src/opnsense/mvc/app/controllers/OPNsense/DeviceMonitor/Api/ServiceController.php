<?php

/**
 *    Copyright (C) 2015 Deciso B.V.
 *
 *    All rights reserved.
 *
 *    Redistribution and use in source and binary forms, with or without
 *    modification, are permitted provided that the following conditions are met:
 *
 *    1. Redistributions of source code must retain the above copyright notice,
 *       this list of conditions and the following disclaimer.
 *
 *    2. Redistributions in binary form must reproduce the above copyright
 *       notice, this list of conditions and the following disclaimer in the
 *       documentation and/or other materials provided with the distribution.
 *
 *    THIS SOFTWARE IS PROVIDED ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES,
 *    INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY
 *    AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 *    AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY,
 *    OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 *    SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 *    INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 *    CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 *    ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 *    POSSIBILITY OF SUCH DAMAGE.
 *
 */

namespace OPNsense\DeviceMonitor\Api;

use OPNsense\Base\ApiControllerBase;
use OPNsense\Core\Backend;

/**
 * Class ServiceController
 * @package OPNsense\DeviceMonitor
 */
class ServiceController extends ApiControllerBase
{
    /**
     * reconfigure DeviceMonitor
     */
    public function reloadAction()
    {
        $status = "failed";
        if ($this->request->isPost()) {
            $status = strtolower(trim((new Backend())->configdRun('template reload OPNsense/DeviceMonitor')));
        }
        return ["status" => $status];
    }

    /**
     * start DeviceMonitor service
     */
    public function startAction()
    {
        $status = "failed";
        if ($this->request->isPost()) {
            $status = strtolower(trim((new Backend())->configdRun("devicemonitor start")));
        }
        return ["status" => $status];
    }

    /**
     * stop DeviceMonitor service
     */
    public function stopAction()
    {
        $status = "failed";
        if ($this->request->isPost()) {
            $status = strtolower(trim((new Backend())->configdRun("devicemonitor stop")));
        }
        return ["status" => $status];
    }

    /**
     * restart DeviceMonitor service
     */
    public function restartAction()
    {
        $status = "failed";
        if ($this->request->isPost()) {
            $status = strtolower(trim((new Backend())->configdRun("devicemonitor restart")));
        }
        return ["status" => $status];
    }

    /**
     * get DeviceMonitor service status
     */
    public function statusAction()
    {
        $status = strtolower(trim((new Backend())->configdRun("devicemonitor status")));
        return ["status" => $status];
    }

    /**
     * test DeviceMonitor connection
     */
    public function testAction()
    {
        if ($this->request->isPost()) {
            $bckresult = json_decode(trim((new Backend())->configdRun("devicemonitor test")), true);
            if ($bckresult !== null) {
                return $bckresult;
            }
        }
        return ["message" => "unable to run config action"];
    }
}