# -*- coding: UTF-8 -*-

# Copyright (C) 2015 Avencall
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os.path

from datetime import datetime, timedelta

from xivo_confd_client import Client

MAX_TIME = timedelta(seconds=60)

ASSET_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)),
    "..", "assets")

client = Client('xivo-benchmark.lan-quebec.avencall.com',
                https=True,
                verify_certificate=False,
                port=9486,
                username='admin',
                password='proformatique')


def test_csv_import():
    start = datetime.now()
    upload_csv()
    stop = datetime.now()
    assert stop - start <= MAX_TIME, "CSV import exceeded max time ({})".format(MAX_TIME)


def upload_csv():
    filepath = os.path.join(ASSET_DIR, "100entries.csv")
    with open(filepath) as f:
        csvdata = f.read()
        client.users.import_csv(csvdata)
