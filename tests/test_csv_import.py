# -*- coding: utf-8 -*-
# Copyright 2015-2016 by Avencall
# SPDX-License-Identifier: GPL-3.0+

import os.path

from datetime import datetime, timedelta

from xivo_confd_client import Client

from . import constants

MAX_TIME = timedelta(seconds=60)

client = Client(constants.HOST,
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
    filepath = os.path.join(constants.ASSET_DIR, "100entries.csv")
    with open(filepath) as f:
        csvdata = f.read()
        client.users.import_csv(csvdata)
