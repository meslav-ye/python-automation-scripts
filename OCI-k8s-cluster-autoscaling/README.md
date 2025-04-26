# Oracle Kubernetes Cluster Scaling Tool

This tool helps **automatically scale down** or **scale up** Oracle Kubernetes (OKE) clusters by:
- Scaling Kubernetes deployments/statefulsets.
- Scaling Oracle node pools.
- Saving/restoring cluster state between shutdown and startup.

---

## Features
- **Shutdown**: Scale Kubernetes resources to 0 and node pools to 0 nodes.
- **Startup**: Restore Kubernetes resources and node pools to their previous sizes.
- **State Persistence**: Saves node counts and replica counts to a state file.
- **Timeout Handling**: Waits for node pools to become active on startup.

---

## Prerequisites

- Python 3.6+
- Oracle Cloud Infrastructure (OCI) SDK for Python:
  ```bash
  pip install oci
  ```
- `kubectl` installed and configured for the cluster.
- OCI configuration files:
  - `~/.oci/config`
  - `~/.oci/oci_api_key.pem`
- Kubernetes `kubeconfig` configured for access.

---

## Configuration

Create a config file at `./config/config.json`:

```json
{
  "node_pool_ids": [
    "ocid1.nodepool.oc1..example1",
    "ocid1.nodepool.oc1..example2"
  ],
  "resource_order": [
    ["deployment/nginx-deployment", "default"],
    ["statefulset/mysql", "database"]
  ]
}
```

- `node_pool_ids`: List of Node Pool OCIDs you want to scale.
- `resource_order`: List of Kubernetes resources (`kind/name`) and their namespaces, in the order you want them scaled.

---

## Usage

```bash
python3 cluster_scaling_tool.py <action>
```

where `<action>` is either:
- `shutdown`
- `startup`

### Example

Shutdown the cluster:

```bash
python3 cluster_scaling_tool.py shutdown
```

Start up the cluster:

```bash
python3 cluster_scaling_tool.py startup
```

---

## How it Works

- On **shutdown**:
  - Saves current node counts and replica counts.
  - Scales Kubernetes resources to 0 replicas.
  - Scales node pools to 0 nodes.
- On **startup**:
  - Restores node pool sizes.
  - Waits for all nodes to become active.
  - Restores Kubernetes resources to their previous replica counts.

State is stored in:

```bash
/var/tmp/k8s_scaling_state.json
```

---

## Logging

Logs are printed to the console with timestamps and levels:

```
2025-04-26 12:00:00 - __main__ - INFO - Starting shutdown process...
```

---

## Notes
- Make sure the config and state files are readable and writable by the user running the script.
- Ensure correct permissions for the `.oci` credentials and `kubectl` access.
- Node activation times may vary based on cluster size and OCI limits.

---

## DEPLOYMENT


# Kubernetes Cluster Scaling Setup

This configuration provides an automated way to scale Kubernetes node pools and manage resources using scheduled CronJobs in the `tools` namespace.

## Contents

- **ConfigMap (`scaling-config`)**: Contains a JSON configuration defining:
  - `node_pool_ids`: OCI Node Pool IDs to be scaled.
  - `resource_order`: Ordered list of Kubernetes resources and their respective namespaces to ensure safe scaling operations.

- **PersistentVolumeClaim (`scaling-state-pvc`)**: Stores state across job executions, using the `nfs` storage class.

- **CronJobs**:
  - `scaling-startup-cronjob`: Runs at 5:00 AM (Mon–Fri), executes the `k8s_cluster_autoscaling.py` script with `startup` argument.
  - `scaling-shutdown-cronjob`: Runs at 7:00 PM (Mon–Fri), executes the script with `shutdown` argument.

Both CronJobs:
- Use secrets to authenticate with OCI and access Kubernetes.
- Mount necessary volumes for configs, keys, kubeconfig, and state.
- Use container images from a private registry (replace `<registry>` with your actual registry URL).

## How to Use

1. **Update `<registry>`** with your container registry path.
2. **Apply the resources** using `kubectl apply -f <filename>.yaml`.
3. Ensure secrets (`oci-automation-config`, `k8s-automation-config`, and `ocirsecret`) are created and available in the `tools` namespace.

## Prerequisites

- NFS Provisioner for `ReadWriteMany` PVC.
- Proper OCI and Kubernetes automation secrets created.


---