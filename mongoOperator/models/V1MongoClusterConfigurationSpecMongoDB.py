# !/usr/bin/env python
# -*- coding: utf-8 -*-
from mongoOperator.models.BaseModel import BaseModel
from mongoOperator.models.fields import StringField, MongoReplicaCountField


class V1MongoClusterConfigurationSpecMongoDB(BaseModel):
    """
    Model for the `spec.mongodb` field of the V1MongoClusterConfiguration.
    """

    # Kubernetes CPU limit of each Mongo container. Defaults to 1 (vCPU).
    cpu_limit = StringField(required=False)

    # Kubernetes memory limit of each Mongo container. Defaults to 2Gi.
    memory_limit = StringField(required=False)

    # Amount of Mongo container replicas. Defaults to 3.
    replicas = MongoReplicaCountField(required=True)

    # The wired tiger cache size. Defaults to 0.25.
    # Should be half of the memory limit minus 1 GB.
    # See https://docs.mongodb.com/manual/administration/production-notes/#allocate-sufficient-ram-and-cpu for details.
    wired_tiger_cache_size = StringField(required=False)

    # host path user for given namespace that has access to hostpath dirs defaults to "hostpath"
    run_as_user = StringField(required=True)

    # Service account to run as defaults to "50000"
    service_account = StringField(required=True)

    # storage data path
    host_path = StringField(required=True)

    # storage mount path in container defaults to /opt/app-root/src
    storage_mount_path = StringField(required=False)
