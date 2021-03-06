# Copyright 2015, 2017 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import fixtures
import mock
from pypowervm import exceptions as pvm_exc

from nova import test
from nova.virt.powervm.tasks import storage as tf_stg


class TestStorage(test.TestCase):

    def setUp(self):
        super(TestStorage, self).setUp()

        self.adapter = mock.Mock()
        self.disk_dvr = mock.MagicMock()
        self.mock_cfg_drv = self.useFixture(fixtures.MockPatch(
            'nova.virt.powervm.media.ConfigDrivePowerVM')).mock
        self.mock_mb = self.mock_cfg_drv.return_value
        self.instance = mock.MagicMock()
        self.context = 'context'

    def test_create_and_connect_cfg_drive(self):
        # With a specified FeedTask
        task = tf_stg.CreateAndConnectCfgDrive(
            self.adapter, self.instance, 'injected_files',
            'network_info', 'stg_ftsk', admin_pass='admin_pass')
        task.execute()
        self.mock_cfg_drv.assert_called_once_with(self.adapter)
        self.mock_mb.create_cfg_drv_vopt.assert_called_once_with(
            self.instance, 'injected_files', 'network_info', 'stg_ftsk',
            admin_pass='admin_pass')

        # Normal revert
        task.revert('result', 'flow_failures')
        self.mock_mb.dlt_vopt.assert_called_once_with(self.instance,
                                                      'stg_ftsk')

        self.mock_mb.reset_mock()

        # Revert when dlt_vopt fails
        self.mock_mb.dlt_vopt.side_effect = pvm_exc.Error('fake-exc')
        task.revert('result', 'flow_failures')
        self.mock_mb.dlt_vopt.assert_called_once()

        self.mock_mb.reset_mock()

        # Revert when media builder not created
        task.mb = None
        task.revert('result', 'flow_failures')
        self.mock_mb.assert_not_called()

    def test_delete_vopt(self):
        # Test with no FeedTask
        task = tf_stg.DeleteVOpt(self.adapter, self.instance)
        task.execute()
        self.mock_cfg_drv.assert_called_once_with(self.adapter)
        self.mock_mb.dlt_vopt.assert_called_once_with(
            self.instance, stg_ftsk=None)

        self.mock_cfg_drv.reset_mock()
        self.mock_mb.reset_mock()

        # With a specified FeedTask
        task = tf_stg.DeleteVOpt(self.adapter, self.instance, stg_ftsk='ftsk')
        task.execute()
        self.mock_cfg_drv.assert_called_once_with(self.adapter)
        self.mock_mb.dlt_vopt.assert_called_once_with(
            self.instance, stg_ftsk='ftsk')

    def test_delete_disk(self):
        stor_adpt_mappings = mock.Mock()

        task = tf_stg.DeleteDisk(self.disk_dvr)
        task.execute(stor_adpt_mappings)
        self.disk_dvr.delete_disks.assert_called_once_with(stor_adpt_mappings)

    def test_detach_disk(self):
        task = tf_stg.DetachDisk(self.disk_dvr, self.instance)
        task.execute()
        self.disk_dvr.detach_disk.assert_called_once_with(self.instance)

    def test_attach_disk(self):
        stg_ftsk = mock.Mock()
        disk_dev_info = mock.Mock()

        task = tf_stg.AttachDisk(self.disk_dvr, self.instance, stg_ftsk)
        task.execute(disk_dev_info)
        self.disk_dvr.attach_disk.assert_called_once_with(
            self.instance, disk_dev_info, stg_ftsk)

        task.revert(disk_dev_info, 'result', 'flow failures')
        self.disk_dvr.detach_disk.assert_called_once_with(self.instance)

        self.disk_dvr.detach_disk.reset_mock()

        # Revert failures are not raised
        self.disk_dvr.detach_disk.side_effect = pvm_exc.TimeoutError(
            "timed out")
        task.revert(disk_dev_info, 'result', 'flow failures')
        self.disk_dvr.detach_disk.assert_called_once_with(self.instance)

    def test_create_disk_for_img(self):
        image_meta = mock.Mock()

        task = tf_stg.CreateDiskForImg(
            self.disk_dvr, self.context, self.instance, image_meta)
        task.execute()
        self.disk_dvr.create_disk_from_image.assert_called_once_with(
            self.context, self.instance, image_meta)

        task.revert('result', 'flow failures')
        self.disk_dvr.delete_disks.assert_called_once_with(['result'])

        self.disk_dvr.delete_disks.reset_mock()

        # Delete not called if no result
        task.revert(None, None)
        self.disk_dvr.delete_disks.assert_not_called()

        # Delete exception doesn't raise
        self.disk_dvr.delete_disks.side_effect = pvm_exc.TimeoutError(
            "timed out")
        task.revert('result', 'flow failures')
        self.disk_dvr.delete_disks.assert_called_once_with(['result'])
