# -*- coding: utf-8 -*-
# Copyright 2015-2018 The Wazo Authors  (see the AUTHORS file)
# SPDX-License-Identifier: GPL-3.0+

from fabric.api import run, sudo, env

env.hosts = ['root@xivo-benchmark.lan.proformatique.com']


def reset_server():
    run("wazo-service stop")
    reset_database()
    run("wazo-service start")
    upgrade_server()
    snapshot_server()


def reset_database():
    drop_database()
    restore_database()


def drop_database():
    sudo("dropdb asterisk", user="postgres")


def restore_database():
    run("rm -rf /var/tmp/pg-backup")
    run("tar xvf /var/tmp/snapshot/db.tgz -C /var/tmp")
    sudo("pg_restore -C -d postgres /var/tmp/pg-backup/asterisk-*.dump", user="postgres")


def upgrade_server():
    run("wazo-upgrade -f")


def snapshot_server():
    run("mkdir -p /var/tmp/snapshot")
    run("xivo-backup db /var/tmp/snapshot/db")
