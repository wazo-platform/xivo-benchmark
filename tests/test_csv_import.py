# -*- coding: utf-8 -*-
# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

import os.path

from datetime import datetime, timedelta

from xivo_auth_client import Client as AuthClient
from xivo_confd_client import Client as ConfdClient

from . import constants

MAX_TIME = timedelta(seconds=150)


def test_csv_import():
    auth_client = AuthClient(
        constants.HOST,
        verify_certificate=False,
        username='admin',
        password='proformatique',
    )
    token_data = auth_client.token.new(expiration=300)
    token = token_data['token']
    auth_client.set_token(token)

    client = ConfdClient(
        constants.HOST,
        https=True,
        verify_certificate=False,
        port=9486,
        token=token,
    )

    start = datetime.now()
    result = upload_csv(client, token_data['metadata']['tenant_uuid'])
    stop = datetime.now()

    assert 'created' in result, 'Result should contains the created users:\n{}'.format(result)
    assert len(result['created']) == 100, 'Should have created 100 users\n{}'.format(result)
    assert stop - start <= MAX_TIME, "CSV import exceeded max time ({})".format(MAX_TIME)


def upload_csv(client, tenant_uuid):
    filepath = os.path.join(constants.ASSET_DIR, "100entries.csv")
    with open(filepath) as f:
        csvdata = f.read()
        return client.users.import_csv(csvdata, tenant_uuid=tenant_uuid)
