# -*- coding: utf-8 -*-
# Copyright 2016-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os.path
import time

from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient
from xivo_dird_client import Client as DirdClient

from . import constants

MAX_TIME = 10
USERNAME = 'alice'
PASSWORD = 'alice'
FIRSTNAME = 'Alice'

confd_data = """\
firstname,cti_profile_enabled,username,password,cti_profile_name
alice,1,alice,alice,Client
"""


def test_csv_import():
    auth_client = AuthClient(constants.HOST,
                             verify_certificate=False,
                             username=USERNAME,
                             password=PASSWORD)
    dird_client = DirdClient(constants.HOST,
                             https=True,
                             verify_certificate=False,
                             timeout=MAX_TIME)
    confd_client = ConfdClient(constants.HOST,
                               https=True,
                               verify_certificate=False,
                               port=9486,
                               username='admin',
                               password='proformatique')

    confd_client.users.import_csv(confd_data)
    token = auth_client.token.new('wazo_user', expiration=300)['token']

    result, time_to_complete = upload_csv(dird_client, token)

    assert 'created' in result, 'The result does not contain created contacts'
    assert len(result['created']) == 1000, 'expected 1000 created contacts: {}'.format(len(result['created']))
    assert time_to_complete < MAX_TIME, 'The import took too long {}s > {}s'.format(time_to_complete,
                                                                                    MAX_TIME)


def upload_csv(dird_client, token):
    filepath = os.path.join(constants.ASSET_DIR, "1000contacts.csv")
    with open(filepath) as f:
        csvdata = f.read()
        start = time.time()
        result = dird_client.personal.import_csv(csvdata, token=token)
        end = time.time()
        return result, end - start
