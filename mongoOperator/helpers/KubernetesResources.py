# Copyright (c) 2018 Ultimaker
# !/usr/bin/env python
# -*- coding: utf-8 -*-
from os import urandom
from base64 import b64encode

from kubernetes import client
from kubernetes.client import models as k8s_models
from typing import Dict, Optional

from Settings import Settings
from mongoOperator.models.V1MongoClusterConfiguration import V1MongoClusterConfiguration


# bellow is patch for https://github.com/kubernetes-client/python/issues/376
from kubernetes.client.models import V1beta1CustomResourceDefinitionStatus


def stored_versions(self, stored_versions):
    if stored_versions is None:
        subsets = []

    self._stored_versions = stored_versions


setattr(V1beta1CustomResourceDefinitionStatus, 'stored_versions', property(fget=V1beta1CustomResourceDefinitionStatus.stored_versions.fget, fset=stored_versions))
# end of patch


class KubernetesResources:
    """ Helper class responsible for creating the Kubernetes model objects. """

    # These are fixed values. They need to be these exact values for Mongo to work properly with the operator.
    MONGO_IMAGE = "docker-registry.default.svc:5000/build-images/mongodb-36-rhel7:1-28"
    #MONGO_IMAGE = "docker-registry.default.svc:5000/base-images/ftn_mongodb-rhel7:3.6.10"

    MONGO_PORT = 27017
    MONGO_COMMAND = "run-mongod-replication"

    # taken from AdminSecretChecker.py
    ADMIN_SECRET_NAME_FORMAT = "{}-admin-credentials"

    # These are default values and are overridable in the custom resource definition.
    DEFAULT_STORAGE_NAME = "mongo-storage"
    DEFAULT_STORAGE_MOUNT_PATH = "/var/lib/mongodb/data/"
    DEFAULT_MONGO_NAME = "mongodb"
    DEFAULT_SERVICE_ACCOUNT = "hostpath"
    DEFAULT_RUN_AS_USER = "50000"

    # Default resource allocation.
    # See https://docs.mongodb.com/manual/administration/production-notes/#allocate-sufficient-ram-and-cpu.
    DEFAULT_CPU_LIMIT = "1"
    DEFAULT_MEMORY_LIMIT = "2Gi"
    DEFAULT_CACHE_SIZE = "256M"

    @classmethod
    def createSecret(cls, secret_name: str, namespace: str, secret_data: Dict[str, str],
                     labels: Optional[Dict[str, str]] = None) -> client.V1Secret:
        """
        Creates a secret object.
        :param secret_name: The name of the secret.
        :param namespace: The name space for the secret.
        :param secret_data: The secret data.
        :param labels: Optional labels for this secret, defaults to the default labels (see `cls.createDefaultLabels`).
        :return: The secret model object.
        """
        return client.V1Secret(
            metadata=client.V1ObjectMeta(
                name=secret_name,
                namespace=namespace,
                labels=cls.createDefaultLabels(secret_name) if labels is None else labels
            ),
            string_data=secret_data,
        )

    @staticmethod
    def createDefaultLabels(name: str = None) -> Dict[str, str]:
        """
        Creates the labels for the object with the given name.
        :param name: The name of the object.
        :return: The object's metadata dictionary.
        """
        return {
            "operated-by": Settings.CUSTOM_OBJECT_API_GROUP,
            "heritage": Settings.CUSTOM_OBJECT_RESOURCE_PLURAL,
            "name": name if name else "",
            "app": name if name else ""
        }

    @classmethod
    def createService(cls, cluster_object: V1MongoClusterConfiguration) -> client.V1Service:
        """
        Creates a service model object.
        :param cluster_object: The cluster object from the YAML file.
        :return: The service object.
        """
        # Parse cluster data object.
        name = cluster_object.metadata.name

        # Create service.
        return client.V1Service(
            metadata=client.V1ObjectMeta(
                name=name,
                namespace=cluster_object.metadata.namespace,
                labels=cls.createDefaultLabels(name),
            ),
            spec=client.V1ServiceSpec(
                type="ClusterIP",
                selector=cls.createDefaultLabels(name),
                ports=[client.V1ServicePort(
                    name="mongod",
                    port=cls.MONGO_PORT,
                    protocol="TCP",
                    target_port=cls.MONGO_PORT
                )],
            ),
        )

    @classmethod
    def createHeadlessService(cls, cluster_object: V1MongoClusterConfiguration) -> client.V1Service:
        """
        Creates a headless service model object.
        :param cluster_object: The cluster object from the YAML file.
        :return: The service object.
        """
        # Parse cluster data object.
        name = "svc-" + cluster_object.metadata.name + "-internal"

        # Create service.
        return client.V1Service(
            metadata=client.V1ObjectMeta(
                annotations={"service.alpha.kubernetes.io/tolerate-unready-endpoints": "true"},
                name=name,
                namespace=cluster_object.metadata.namespace,
                labels=cls.createDefaultLabels(cluster_object.metadata.name),
            ),
            spec=client.V1ServiceSpec(
                cluster_ip="None",  # create headless service, no load-balancing and a single service IP
                selector=cls.createDefaultLabels(cluster_object.metadata.name),
                ports=[client.V1ServicePort(
                    name="mongod",
                    port=cls.MONGO_PORT,
                    protocol="TCP"
                )],
            ),
        )

    @classmethod
    def createStatefulSet(cls, cluster_object: V1MongoClusterConfiguration) -> client.V1beta1StatefulSet:
        """
        Creates a the stateful set configuration for the given cluster.
        :param cluster_object: The cluster object from the YAML file.
        :return: The stateful set object.
        """

        # Parse cluster data object.
        name = cluster_object.metadata.name
        namespace = cluster_object.metadata.namespace
        replicas = cluster_object.spec.mongodb.replicas
        storage_mount_path = cluster_object.spec.mongodb.host_path or cls.DEFAULT_STORAGE_MOUNT_PATH
        host_path = cluster_object.spec.mongodb.host_path
        cpu_limit = cluster_object.spec.mongodb.cpu_limit or cls.DEFAULT_CPU_LIMIT
        memory_limit = cluster_object.spec.mongodb.memory_limit or cls.DEFAULT_MEMORY_LIMIT
        run_as_user = cluster_object.spec.mongodb.run_as_user or cls.DEFAULT_RUN_AS_USER
        service_account = cluster_object.spec.mongodb.service_account or cls.DEFAULT_SERVICE_ACCOUNT
        wired_tiger_cache_size = cluster_object.spec.mongodb.wired_tiger_cache_size or cls.DEFAULT_CACHE_SIZE
        secret_name = cls.ADMIN_SECRET_NAME_FORMAT.format(name)

        # create container
        mongo_container = client.V1Container(
            name=name,
            env=[client.V1EnvVar(
                name="POD_IP",
                value_from=client.V1EnvVarSource(
                    field_ref = client.V1ObjectFieldSelector(
                        api_version = "v1",
                        field_path = "status.podIP"
                    )
                )
            ),
            client.V1EnvVar(
                name="MONGODB_PASSWORD",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        key="database-password",
                        name=secret_name
                    )
                )
            ),
            client.V1EnvVar(
                name="MONGODB_USER",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        key="database-user",
                        name=secret_name
                    )
                )
            ),
            client.V1EnvVar(
                name="MONGODB_DATABASE",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        key="database-name",
                        name=secret_name
                    )
                )
            ),
            client.V1EnvVar(
                name="MONGODB_ADMIN_PASSWORD",
                value_from=client.V1EnvVarSource(
                    secret_key_ref=client.V1SecretKeySelector(
                        key="database-admin-password",
                        name=secret_name
                    )
                )
            ),
            client.V1EnvVar(
              name="WIREDTIGER_CACHE_SIZE",
              value=wired_tiger_cache_size
            ),
            client.V1EnvVar(
                name="MONGODB_REPLICA_NAME",
                value=name
            ),
            client.V1EnvVar(
                name="MONGODB_SERVICE_NAME",
                value="svc-" + name + "-internal"
            ),
            client.V1EnvVar(
                name="MONGODB_KEYFILE_VALUE",
                value="supersecretkeyfile123"
            )],
            liveness_probe=client.V1Probe(failure_threshold=3,
                                          initial_delay_seconds=30,
                                          period_seconds=30,
                                          success_threshold=1,
                                          tcp_socket=client.V1TCPSocketAction(port=cls.MONGO_PORT),
                                          timeout_seconds=1
            ),
            command=cls.MONGO_COMMAND.split(),
            image=cls.MONGO_IMAGE,
            image_pull_policy="Always",
            ports=[client.V1ContainerPort(
                name="mongodb",
                container_port=cls.MONGO_PORT,
                protocol="TCP"
            )],
            readiness_probe=client.V1Probe(_exec=client.V1ExecAction(command=["/bin/sh", "-i", "-c", "mongo 127.0.0.1:27017/$MONGODB_DATABASE -u $MONGODB_USER -p $MONGODB_PASSWORD --eval=\"quit()\""]),
                                           failure_threshold=3,
                                           initial_delay_seconds=10,
                                           period_seconds=10,
                                           success_threshold=1,
                                           timeout_seconds=1
                                           ),
            security_context=client.V1SecurityContext(
                run_as_user=int(run_as_user),
                se_linux_options=client.V1SELinuxOptions(
                    level="s0",
                    type="spc_t"
                )
            ),
            termination_message_path="/dev/termination-log",
            volume_mounts=[client.V1VolumeMount(
                name="mongo-data",
                read_only=False,
                mount_path=storage_mount_path
            )],
            resources=client.V1ResourceRequirements(
                limits={"cpu": cpu_limit, "memory": memory_limit},
                requests={"cpu": cpu_limit, "memory": memory_limit}
            )
        )

        #create affinity rules
        affinity = client.V1Affinity(
            pod_anti_affinity=client.V1PodAntiAffinity(
                required_during_scheduling_ignored_during_execution=[
                    client.V1PodAffinityTerm(label_selector=client.V1LabelSelector(
                        match_expressions=[client.V1LabelSelectorRequirement(
                            key="app",
                            operator="In",
                            values=[name]
                        )]
                    ),
                     topology_key="kubernetes.io/hostname")
                ]
            )
        )

        volumes = [client.V1Volume(
            name="mongo-data",
            host_path=client.V1HostPathVolumeSource(path=host_path)
        )]

        # Create stateful set.
        return client.V1beta1StatefulSet(
            metadata = client.V1ObjectMeta(annotations={"service.alpha.kubernetes.io/tolerate-unready-endpoints": "true"},
                                           name=name,
                                           namespace=namespace,
                                           labels=cls.createDefaultLabels(name)),
            spec = client.V1beta1StatefulSetSpec(
                replicas = replicas,
                service_name = "svc-" + name + "-internal",
                template = client.V1PodTemplateSpec(
                    metadata = client.V1ObjectMeta(labels=cls.createDefaultLabels(name)),
                    spec = client.V1PodSpec(affinity = affinity,
                                            containers=[mongo_container],
                                            node_selector={"compute":"mongodb"},
                                            service_account=service_account,
                                            #restart_policy="Never",
                                            volumes=volumes
                    )
                ),
            ),
        )

    @classmethod
    def createLabelSelector(cls, labels: Dict[str, str]) -> str:
        """
        Converts the given label dictionary into a label selector string.
        :param labels: The labels dict, e.g. {"name": "test"}.
        :return: The label selector, e.g. "name=test".
        """
        return ",".join("{}={}".format(k, v) for k, v in labels.items() if v)

    @classmethod
    def deserialize(cls, data: dict, model_name: str) -> any:
        """
        Deserializes the dictionary into a kubernetes model.
        :param data: The data dictionary.
        :param model_name: The name of the model.
        :return: An instance of the model with the given name.
        """
        model_class = getattr(k8s_models, model_name, None)
        if not model_class or not isinstance(data, dict):
            return data
        kwargs = {}
        if model_class.swagger_types is not None:
            for attr, attr_type in model_class.swagger_types.items():
                if model_class.attribute_map.get(attr):
                    value = data.get(model_class.attribute_map[attr])
                    kwargs[attr] = cls.deserialize(value, attr_type)

        return model_class(**kwargs)
