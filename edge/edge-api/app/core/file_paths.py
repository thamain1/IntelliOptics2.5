DEFAULT_EDGE_CONFIG_PATH = "/config/edge-config.yaml"  # Docker Compose mount location
INFERENCE_DEPLOYMENT_TEMPLATE_PATH = "/etc/intellioptics/inference-deployment/inference_deployment_template.yaml"

# A file with the namespace to be operating within
# TODO: this should just be an environment variable
KUBERNETES_NAMESPACE_PATH = "/etc/intellioptics/kubernetes-namespace/namespace"

# Path to the database file (Docker Compose uses /data volume)
DATABASE_FILEPATH = "/data/sqlite.db"

# Path to the model repository.
MODEL_REPOSITORY_PATH = "/models"  # Docker Compose mount location

# Path to the database log file. This will contain all SQL queries executed by the ORM.
DATABASE_ORM_LOG_FILE = "sqlalchemy.log"
DATABASE_ORM_LOG_FILE_SIZE = 10_000_000  # 10 MB
