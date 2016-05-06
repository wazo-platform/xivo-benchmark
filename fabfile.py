# -*- coding: utf-8 -*-
# Copyright 2015 by Avencall
# SPDX-License-Identifier: GPL-3.0+

from fabric.api import run, sudo, env

env.hosts = ['root@xivo-benchmark.lan.proformatique.com']


def reset_server():
    run("xivo-service stop")
    reset_files()
    reset_database()
    run("xivo-service start")
    upgrade_server()
    snapshot_server()


def reset_files():
    clean_files()
    restore_files()


def clean_files():
    run(r"""rm -rf \
            /etc/asterisk \
            /etc/xivo* \
            /var/lib/asterisk \
            /var/lib/consul \
            /var/lib/xivo-provd \
            /var/lib/xivo \
            /var/log/asterisk \
            /var/spool/asterisk
        """)


def restore_files():
    run("tar xvfp /var/tmp/snapshot/data.tgz -C /")


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
    run("xivo-upgrade -f")


def snapshot_server():
    run("mkdir -p /var/tmp/snapshot")
    run("xivo-backup db /var/tmp/snapshot/db")
    run("xivo-backup data /var/tmp/snapshot/data")
