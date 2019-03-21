# k8s-mongo-operator
MongoDB Operator for Kubernetes.
This is a fork of Ultimakers k8s mongo operator heavily modified for use with RHEL mongodb image.

Unlike Ultimakers version this uses Event watches and extends configuration possibilities.
Backup scheme has been reworked to use persistent volume connected directly to Operator POD.
New entrypoint was introduced and operator image is based on RHEL image.

## Features
The following feature are currently available in this operator:

* Create, update or delete MongoDB replica sets.
* Automatically initialize the replica set configuration in the master node.
* Schedule backups to persitent volume using `mongodump`.

## Limitations
The current version has the limitations that shall be addressed in a later version:
- Mongo instances are not using SSL certificates yet.

## Cluster interaction
Please refer to our [simplified diagram](./docs/architecture.png) to get an overview of the operator interactions with your Kubernetes cluster.

## Deployment
To deploy this operator in your own cluster, you'll need to create some configuration files.
An example of these configuration files can be found in [kubernetes/operators/mongo-operator](./kubernetes/operators/mongo-operator)

As you can see there is a service account (mongo-operator-service-account) which has some specific permissions in the cluster.
These permissions are registered in the cluster role and cluster role binding.

Lastly there is a deployment configuration to deploy the actual operator.
Usually you'd use an image value like `base-images/k8s-mongo-operator:latest`, or a specific version.

## Creating a Mongo object
To deploy a new replica set in your cluster using the operator, create a Kubernetes configuration file similar to this:

```yaml
apiVersion: "operators.javamachr.cz/v1"
kind: Mongo
metadata:
  name: mongo-cluster

spec:
  users:
    admin_password: admin
    user_name: webapp
    user_password: passwd1
    databasename: web
  mongodb:
    cpu_limit: 1000m
    host_path: /mongodb/data
    memory_limit: 2048Mi
    replicas: 3
    run_as_user: 50002
    service_account: hostpath
  backups:
    cron: "0 * * * *" # hourly
    from_file: mongodb-backup-{namespace}-{name}-{date}.archive.gz    
```

Then deploy it to the cluster like any other object:

```bash
kubectl apply -f mongo.yaml
```

### Configuration options
The following options are available to use in the `spec` section of the `yaml` configuration file. Keys with a `*` in front are required.

| Config key | Default | Description |
| --- | --- | --- |
| * `users.admin_password` | - | The admin password to set inside mongo |
| * `users.user_name` | - | The user to create inside mongo. |
| * `users.user_password` | - | The users password to create inside mongo. |
| * `users.databasename` | - | The DB name to create inside mongo. |
| * `backups.cron` | - | The cron on which to create a backup to nfs storage.
| `backups.restore_from` | - | Filename of the backup  we wish to restore. If not specified, or set to 'latest', the last backup created is used. |
| * `mongodb.host_path` | /data/db | The path on host to mount as volume in containers. |
| * `mongodb.service_account` | hostpath | The service account to run container. |
| * `mongodb.run_as_user` | 50000 | The user to run container - must have rights for host_path. |
| `mongodb.storage_mount_path` | /mongodb/bm-cz/bet | The path on which the persistent volumes are mounted in the Mongo containers. |
| `mongodb.cpu_limit` | 1 | The CPU limit of each container. |
| `mongodb.memory_limit` | 2Gi | The memory limit of each container. |
| `mongodb.wired_tiger_cache_size` | 0.25 | The wired tiger cache size. |
| `mongodb.replicas` | - | The amount of MongoDB replicas that should be available in the replica set. Must be an uneven positive integer and minimum 3. |


> Please read https://docs.mongodb.com/manual/administration/production-notes/#allocate-sufficient-ram-and-cpu for details about why setting the WiredTiger cache size is important when you change the container memory limit from the default value.

## Testing locally
To run the tests in a local Kubernetes (MiniKube) cluster, we have created a simple test script.

Ensure you have the following tools installed on your system:
- [Docker](https://store.docker.com/search?type=edition&offering=community)
- [MiniKube v0.25.2](https://github.com/kubernetes/minikube/releases/tag/v0.25.2) (please use this version specifically)

Then start a new MiniKube cluster using the following commands:

```bash
minikube start
```

Then you can run our test script to deploy the operator and execute some end-to-end tests.

```bash
./build-and-deploy-local.sh
```

You will also see the operator logs streamed to your console.
