import oci
import subprocess
import time
import sys
import json
import os
import logging
import argparse

STATE_FILE = "/var/tmp/k8s_scaling_state.json"
CONFIG_FILE = "./config/config.json"  # JSON file containing node pools and resources

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def load_config():
    """Load node pools and resource order from config.json"""
    if not os.path.exists(CONFIG_FILE):
        logger.error(f"Configuration file {CONFIG_FILE} not found.")
        sys.exit(1)

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            node_pool_ids = config.get("node_pool_ids", [])
            resource_order = config.get("resource_order", [])
            
            if not node_pool_ids or not resource_order:
                logger.error("Invalid config: node_pool_ids or resource_order is empty.")
                sys.exit(1)
            
            return node_pool_ids, resource_order
    except json.JSONDecodeError:
        logger.error(f"Error parsing {CONFIG_FILE}. Ensure it's valid JSON.")
        sys.exit(1)

def load_state():
    """Load the saved state of the cluster"""
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"node_counts": {}, "replicas": {}, "last_action": None}

def save_state(state):
    """Save the cluster state"""
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)

def get_current_node_count(container_client, node_pool_id):
    """Fetch the current node count of a node pool"""
    node_pool = container_client.get_node_pool(node_pool_id).data
    return node_pool.node_config_details.size

def are_nodes_ready(container_client, node_pool_ids):
    """Check if all nodes in all node pools are active"""
    for node_pool_id in node_pool_ids:
        node_pool = container_client.get_node_pool(node_pool_id).data
        for node in node_pool.nodes:
            if node.lifecycle_state != "ACTIVE":
                return False
    return True

def wait_for_nodes(container_client, node_pool_ids, timeout):
    """Wait until all nodes are active, with a timeout"""
    elapsed_time = 0
    while elapsed_time < timeout:
        logger.info("Wait until all nodes are active...")
        if are_nodes_ready(container_client, node_pool_ids):
            time.sleep(100)
            logger.info("All nodes are active.")
            return
        time.sleep(360)
        elapsed_time += 360
        logger.info("Checking active nodes...")
    logger.warning("Nodes did not become active within the timeout period.")

def scale_node_pool(container_client, node_pool_id, size):
    """Scale a node pool to the specified size"""
    update_details = oci.container_engine.models.UpdateNodePoolDetails(
        node_config_details=oci.container_engine.models.UpdateNodePoolNodeConfigDetails(size=size)
    )
    container_client.update_node_pool(node_pool_id, update_details)
    logger.info(f"Scaling node pool {node_pool_id} to {size} nodes...")
    time.sleep(5)

def get_current_replicas(resource, namespace):
    """Get the current replica count of a Kubernetes deployment/statefulset"""
    kind, name = resource.split('/')
    cmd = ["kubectl", "get", kind, name, "-n", namespace, "-o", "jsonpath={.spec.replicas}"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not result.stdout.strip().isdigit():
        logger.warning(f"Could not fetch replicas for {resource} in {namespace}, defaulting to 1.")
        return 1
    return int(result.stdout.strip())

def scale_k8s_resources(resources, scale_down, state):
    """Scale Kubernetes resources (deployments/statefulsets)"""
    for resource, namespace in resources:
        kind, name = resource.split('/')
        if scale_down:
            current_replicas = get_current_replicas(resource, namespace)
            state["replicas"].setdefault(namespace, {})[resource] = current_replicas
            replicas = 0
        else:
            replicas = state["replicas"].get(namespace, {}).get(resource)
            if replicas is None:
                logger.warning(f"No saved replica count for {resource} in {namespace}, defaulting to 1.")
                replicas = 1
        cmd = ["kubectl", "scale", kind, name, "--replicas", str(replicas), "-n", namespace]
        subprocess.run(cmd, check=True)
        logger.info(f"Scaled {kind} {name} in {namespace} to {replicas} replicas.")
        time.sleep(5)
    save_state(state)

def get_oci_config():
    """Load OCI configuration"""
    try:
        oci_config_path = os.path.expanduser("~/.oci/config")
        oci_key_path = os.path.expanduser("~/.oci/oci_api_key.pem")

        if not os.path.exists(oci_config_path) or not os.path.exists(oci_key_path):
            raise Exception("Config file auth is not available")

        return oci.config.from_file(oci_config_path)
    except Exception as e:
        logger.error(f"Failed to load OCI config: {str(e)}")
        raise

def shutdown():
    """Shutdown the cluster by scaling down resources and nodes"""
    state = load_state()

    # Check if the last action was already shutdown
    if state.get("last_action") == "shutdown":
        logger.info("Last action was shutdown. No changes will be made.")
        return

    node_pool_ids, resource_order = load_config()
    oci_config = get_oci_config()
    container_client = oci.container_engine.ContainerEngineClient(oci_config)

    logger.info("Starting shutdown process...")
    for node_pool_id in node_pool_ids:
        state["node_counts"][node_pool_id] = get_current_node_count(container_client, node_pool_id)
    scale_k8s_resources(resource_order, scale_down=True, state=state)
    for node_pool_id in node_pool_ids:
        scale_node_pool(container_client, node_pool_id, 0)

    state["last_action"] = "shutdown"  # Save last action
    save_state(state)
    logger.info("Shutdown complete.")

def startup(node_timeout=2500):
    """Start up the cluster by restoring nodes and deployments"""
    node_pool_ids, resource_order = load_config()
    oci_config = get_oci_config()
    container_client = oci.container_engine.ContainerEngineClient(oci_config)
    state = load_state()

    logger.info("Starting startup process...")
    for node_pool_id in node_pool_ids:
        nodes = state["node_counts"].get(node_pool_id, 1)
        scale_node_pool(container_client, node_pool_id, nodes)
    wait_for_nodes(container_client, node_pool_ids, node_timeout)
    time.sleep(5)
    last_namespace = "default"
    for resource, namespace in reversed(resource_order):
        scale_k8s_resources([(resource, namespace)], scale_down=False, state=state)
        if namespace == last_namespace:
            logger.info("Wait 5 sec for pods to run")
            time.sleep(5)
        else:
            logger.info("Wait 15 sec for pods to run")
            time.sleep(15)    
        last_namespace = namespace
        
    state["last_action"] = "startup"  # Save last action
    save_state(state)
    logger.info("Startup complete.")

def parse_arguments():
    """Parse command line arguments with defaults from global variables"""
    parser = argparse.ArgumentParser(description='Oracle Kubernetes Cluster Scaling Tool')

    # Action argument
    parser.add_argument('action', choices=['shutdown', 'startup'], 
                        help='Action to perform: shutdown or startup')
        
    # # Timeout for node readiness
    # parser.add_argument('--node-timeout', type=int, default=2500,
    #                     help='Timeout in seconds to wait for nodes to become ready (default: 2500)')
    
    return parser.parse_args()

if __name__ == "__main__":

    args = parse_arguments()
    
    # Update globals with command line args
    
    if args.action == "shutdown":
        shutdown()
    elif args.action == "startup":
        startup()
    else:
        logger.error("Invalid action.")
