# Copyright (c) 2018 Ultimaker
# !/usr/bin/env python
# -*- coding: utf-8 -*-
from os import urandom

from base64 import b64encode

from kubernetes.client import V1Secret, V1Status
from typing import List, Dict

from mongoOperator.helpers.resourceCheckers.BaseResourceChecker import BaseResourceChecker
from mongoOperator.models.V1MongoClusterConfiguration import V1MongoClusterConfiguration


class AdminSecretChecker(BaseResourceChecker):
    """
    Class responsible for handling the operator admin secrets for the Mongo cluster.
    The inherited methods do not have documentation, see the parent class for more details.
    """

    # Name of the secret for each cluster.
    NAME_FORMAT = "{}-admin-credentials"

    @classmethod
    def getClusterName(cls, resource_name: str) -> str:
        return resource_name.replace(cls.NAME_FORMAT.format(""), "")

    @classmethod
    def getSecretName(cls, cluster_name: str) -> str:
        """ Returns the correctly formatted name of the secret for this cluster."""
        return cls.NAME_FORMAT.format(cluster_name)

    @staticmethod
    def _generateSecretData(cluster_object: V1MongoClusterConfiguration) -> Dict[str, str]:
        """Generates secret with admin password to use and configured user, pass and dbname."""
        return {"database-admin-password": cluster_object.spec.users.admin_password,
                "database-user": cluster_object.spec.users.user_name,
                "database-password": cluster_object.spec.users.user_password,
                "database-name": cluster_object.spec.users.database_name
                }

    def listResources(self) -> List[V1Secret]:
        return self.kubernetes_service.listAllSecretsWithLabels().items

    def getResource(self, cluster_object: V1MongoClusterConfiguration) -> V1Secret:
        name = self.getSecretName(cluster_object.metadata.name)
        return self.kubernetes_service.getSecret(name, cluster_object.metadata.namespace)

    def createResource(self, cluster_object: V1MongoClusterConfiguration) -> V1Secret:
        name = self.getSecretName(cluster_object.metadata.name)
        return self.kubernetes_service.createSecret(name, cluster_object.metadata.namespace, self._generateSecretData(cluster_object=cluster_object))

    def updateResource(self, cluster_object: V1MongoClusterConfiguration) -> V1Secret:
        name = self.getSecretName(cluster_object.metadata.name)
        return self.kubernetes_service.updateSecret(name, cluster_object.metadata.namespace, self._generateSecretData(cluster_object=cluster_object))

    def deleteResource(self, cluster_name: str, namespace: str) -> V1Status:
        secret_name = self.getSecretName(cluster_name)
        return self.kubernetes_service.deleteSecret(secret_name, namespace)
