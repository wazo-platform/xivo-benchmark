# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

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
