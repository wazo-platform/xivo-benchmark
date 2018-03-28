XiVO Benchmark
==============

Tests for measuring performance issues on physical servers

Setup
=====

These tests require a recent XiVO business server installed with a software RAID. Once the
installation is finished you must go through the following steps:

 * Go through wizard setup
 * Add context ranges
  * user : 6000-9999
  * from-extern: 1000-9999
 * add a webservice user
  * username: admin
  * password: proformatique
  * acls:
    * auth.users.create
    * confd.users.import.create

Once the server is ready, install the python dependencies for running the tests:

    pip install -r requirements.txt

Running tests
=============

These tests require a "fresh" install of Wazo before every run.  In order to avoid reinstalling a
physical server every time, a fabfile with commands to reset the database and upgrade the Wazo is
included. Resetting the server is done by running:

    fab reset_server

Once the server is reset, run the tests with nose:

    nosetests tests


Modifying the server
==

When the server needs to be modified to include new configurations the following steps should be taken.

#. Restore the server to its initial state `fab reset_server`
#. Make the required configurations
#. Create a new snapshot such that reset_server take the modification into account `fab snapshot_server`
