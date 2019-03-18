# Copyright (c) 2018 Ultimaker
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import glob
import logging
import os
from subprocess import check_output, CalledProcessError

from time import sleep

from mongoOperator.helpers.MongoResources import MongoResources
from mongoOperator.models.V1MongoClusterConfiguration import V1MongoClusterConfiguration
from mongoOperator.services.KubernetesService import KubernetesService


class RestoreHelper:
    """
    Class responsible for handling the Restores for the Mongo cluster.
    """
    DEFAULT_BACKUP_PREFIX = "backups"
    BACKUP_FILE_FORMAT = "mongodb-backup-{namespace}-{name}-{date}.archive.gz"
    LATEST_BACKUP_KEY = "latest"
    RESTORE_RETRIES = 4
    RESTORE_WAIT = 15.0

    def __init__(self, kubernetes_service: KubernetesService) -> None:
        """
        :param kubernetes_service: The kubernetes service.
        """
        self.kubernetes_service = kubernetes_service

    @staticmethod
    def _lastBackupFile() -> str:
        """
        Gets the name of the last backup file in NFS folder.
        :return: The location of the last backup file.
        """
        list_of_files = glob.glob('/data/mongodb-backup-*.gz')
        latest_file = max(list_of_files, key=os.path.getctime)
        logging.info("Returning backup file %s", latest_file)
        return latest_file

    def restoreIfNeeded(self, cluster_object: V1MongoClusterConfiguration) -> bool:
        """
        Checks whether a restore is requested for the cluster, looking up the restore file if
        necessary.
        :param cluster_object: The cluster object from the YAML file.
        :return: Whether a restore was executed or not.
        """
        if cluster_object.spec.backups.restore_from is None:
            return False

        backup_file = cluster_object.spec.backups.restore_from
        if backup_file == self.LATEST_BACKUP_KEY:
            backup_file = self._lastBackupFile()

        logging.info("Attempting to restore file %s to cluster %s @ ns/%s.", backup_file,
                     cluster_object.metadata.name, cluster_object.metadata.namespace)

        self.restore(cluster_object, backup_file)
        return True

    def restore(self, cluster_object: V1MongoClusterConfiguration, backup_file: str) -> bool:
        """
        Attempts to restore the latest backup in the specified location to the given cluster.
        Creates a new backup for the given cluster saving it in the NFS storage.
        :param cluster_object: The cluster object from the YAML file.
        :param backup_file: The filename of the backup we want to restore.
        """
        hostnames = MongoResources.getMemberHostnames(cluster_object)

        logging.info("Restoring backup file %s to cluster %s @ ns/%s.", backup_file, cluster_object.metadata.name,
                     cluster_object.metadata.namespace)

        # Wait for the replica set to become ready
        for _ in range(self.RESTORE_RETRIES):
            try:
                logging.info("Running mongorestore --host %s --gzip --archive=%s", ",".join(hostnames), backup_file)
                restore_output = check_output(["/opt/rh/rh-mongodb36/root/usr/bin/mongorestore", "--authenticationDatabase=admin", "-u", "admin",
                                               "-p", cluster_object.spec.users.admin_password, "--host", ",".join(hostnames), "--gzip",
                                               "--archive=" + backup_file])
                logging.info("Restore output: %s", restore_output)

                try:
                    os.remove(backup_file)
                except OSError as err:
                    logging.error("Unable to remove '%s': %s", backup_file, err.strerror)

                return True
            except CalledProcessError as err:
                logging.error("Could not restore '%s', attempt %d. Return code: %s stderr: '%s' stdout: '%s'",
                              backup_file, _, err.returncode, err.stderr, err.stdout)
                sleep(self.RESTORE_WAIT)
        raise TimeoutError("Could not restore '{}' after {} retries!".format(backup_file, self.RESTORE_RETRIES))
