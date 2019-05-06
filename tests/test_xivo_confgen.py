# Copyright 2016 by Avencall
# SPDX-License-Identifier: GPL-3.0-or-later

import subprocess

from hamcrest import assert_that, less_than

from . import constants

SSH_BASE_COMMAND = [
    'ssh',
    '-q',
    '-o', 'PreferredAuthentications=publickey',
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'UserKnownHostsFile=/dev/null',
    '-l', 'root',
]


def test_xivo_confgen_user_cpu_time():
    elapsed_user_time = _time_remote_command(['xivo-confgen', 'test/benchmark'], '%U')

    assert_that(elapsed_user_time, less_than(0.1))


def _time_remote_command(remote_command, time_format):
    ssh_command = _format_ssh_command(['/usr/bin/time', '-f', time_format] + remote_command)
    p = subprocess.Popen(ssh_command, stderr=subprocess.PIPE)
    _, output = p.communicate()
    if p.returncode:
        raise Exception('unexpected non-zero return code: {}'.format(p.returncode))

    return float(output)


def _format_ssh_command(remote_command):
    ssh_command = list(SSH_BASE_COMMAND)
    ssh_command.append(constants.HOST)
    ssh_command.extend(remote_command)
    return ssh_command
