# Copyright (c) 2018 Ultimaker
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
import os
from subprocess import check_output, CalledProcessError, SubprocessError

from croniter import croniter
from datetime import datetime
from typing import Dict, Tuple

from mongoOperator.helpers.MongoResources import MongoResources
from mongoOperator.models.V1MongoClusterConfiguration import V1MongoClusterConfiguration
from mongoOperator.services.KubernetesService import KubernetesService


class BackupHelper:
    """
    Class responsible for handling the Backups for the Mongo cluster.
    """
    DEFAULT_BACKUP_PREFIX = "backups"
    BACKUP_FILE_FORMAT = "mongodb-backup-{namespace}-{name}-{date}.archive.gz"

    @staticmethod
    def _utc_now() -> datetime:
        """
        :return: The current date in UTC timezone.
        """
        return datetime.utcnow()

    def __init__(self, kubernetes_service: KubernetesService):
        """
        :param kubernetes_service: The kubernetes service.
        """
        self.kubernetes_service = kubernetes_service
        self._last_backups = {}  # type: Dict[Tuple[str, str], datetime]  # format: {(cluster_name, namespace): date}

    def backup_if_needed(self, cluster_object: V1MongoClusterConfiguration) -> bool:
        """
        Checks whether a backup is needed for the cluster, backing it up if necessary.
        :param cluster_object: The cluster object from the YAML file.
        :return: Whether a backup was created or not.
        """
        now = self._utc_now()

        cluster_key = (cluster_object.metadata.name, cluster_object.metadata.namespace)
        last_backup = self._last_backups.get(cluster_key)
        next_backup = croniter(cluster_object.spec.backups.cron, last_backup, datetime).get_next() \
            if last_backup else now

        if next_backup <= now:
            self.backup(cluster_object, now)
            self._last_backups[cluster_key] = now
            return True

        logging.debug("Cluster %s @ ns/%s will need a backup at %s.", cluster_object.metadata.name,
                     cluster_object.metadata.namespace, next_backup.isoformat())
        return False

    @staticmethod
    def ensure_dir(file_path):
        directory = os.path.dirname(file_path)
        if not os.path.exists(directory):
            os.makedirs(directory)

    def backup(self, cluster_object: V1MongoClusterConfiguration, now: datetime):
        """
        Creates a new backup for the given cluster saving it in the cloud storage.
        :param cluster_object: The cluster object from the YAML file.
        :param now: The current date, used in the date format.
        """
        backup_file = "/data/" + cluster_object.metadata.name + "/" + self.BACKUP_FILE_FORMAT.format(namespace=cluster_object.metadata.namespace,
                                                               name=cluster_object.metadata.name,
                                                               date=now.strftime("%Y-%m-%d_%H%M%S"))
        self.ensure_dir(backup_file)

        pod_index = cluster_object.spec.mongodb.replicas - 1  # take last pod
        hostname = MongoResources.getMemberHostname(pod_index, cluster_object.metadata.name,
                                                    cluster_object.metadata.namespace)

        logging.info("Backing up cluster %s @ ns/%s from %s to %s.", cluster_object.metadata.name,
                     cluster_object.metadata.namespace, hostname, backup_file)

        try:
            backup_output = check_output(["/opt/rh/rh-mongodb36/root/usr/bin/mongodump", "--authenticationDatabase=admin", "-u", "admin", "-p", cluster_object.spec.users.admin_password, "--host", hostname, "--gzip", "--archive=" + backup_file])
        except CalledProcessError as err:
            raise SubprocessError("Could not backup '{}' to '{}'. Return code: {}\n stderr: '{}'\n stdout: '{}'"
                                  .format(hostname, backup_file, err.returncode, err.stderr, err.stdout))

        logging.debug("Backup output: %s", backup_output)
