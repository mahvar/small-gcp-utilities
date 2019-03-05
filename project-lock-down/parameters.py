CONFIG_NAME = "hippa-config"              # CHANGE ME! This is a placeholder; name your gcloud config as your wish.
ORGANIZATION_ID="111111111111"            # CHANGE ME! This is a placeholder; replace it with your organization Id.
PROJECT_ID="hipaa-sample-project"         # CHANGE ME! This is a placeholder; replace it with a unique ID for your project.
DOMAIN="google.com"                       # CHANGE ME! This is a placeholder; replace it with your domain name.
ACCOUNT="janedoe@acme.com"                # CHANGE ME! This is a placeholder; replace it with the GCP account you used to authenticate with gcloud SDK
BILLING_ACCOUNT = "00X111-X11XXX-00X000"  # CHANGE ME! This is a placeholder; replace it with your billing account.

LOGS_STORAGE_CLASS="multi_regional"       # CHANGE ME! This is a placeholder; define it according to your requirements.
LOGS_LOCATION="US"                        # CHANGE ME! This is a placeholder; define it according to your data locality requirements.
LOGS_TTL=365                              # CHANGE ME! This is the number of days logs will live in the bucket, you may wish to adjust it. Please note that
                                          # this is referring to supplemental logs stored in a GCS bucket and NOT Cloud Audit Logs. Refer to step 3 in README file for more details.

DATA_STORAGE_CLASS="regional"             # CHANGE ME! This is a placeholder; define it according to your requirements.
DATA_BUCKET_LOCATION="us-central1"        # CHANGE ME! This is a placeholder; define it according to your data locality requirements.
CONTENT_TYPE="bio-medical"                # CHANGE ME! This is a placeholder, change it according to your use case. It is used to name the GCS bucket; see DATA_BUCKET_ID below.

WHITELIST_USERS = "user1@acme.com AND user2@acme.com" # CHANGE ME! This is a placeholder, whitelist users for access to the main GCS bucket: DATA_BUCKET_ID

# YOU SHOULD NOT CHANGE THE following. They are defined based on best practices: 
OWNERS_GROUP='{}-owners@{}'.format(PROJECT_ID, DOMAIN)            # Given the placeholder values above, it resolves to hipaa-sample-project-owners@google.com
AUDITORS_GROUP='{}-auditors@{}'.format(PROJECT_ID, DOMAIN)        # Given the placeholder values above, it resolves to hipaa-sample-project-auditors@google.com
LOG_READER_GROUP='{}-logs@{}'.format(PROJECT_ID, DOMAIN)          # Given the placeholder values above, it resolves to hipaa-sample-project-logs@google.com
DATA_READER_GROUP='{}-readonly@{}'.format(PROJECT_ID, DOMAIN)     # Given the placeholder values above, it resolves to hipaa-sample-project-readonly@google.com
DATA_CREATOR_GROUP='{}-readwrite@{}'.format(PROJECT_ID, DOMAIN)   # Given the placeholder values above, it resolves to hipaa-sample-project-readwrite@google.com

LOGS_BUCKET_ID='{}-logs'.format(PROJECT_ID)                       # Given the placeholder values above, it resolves to hipaa-sample-project-logs
DATA_BUCKET_ID='{}-{}-data'.format(PROJECT_ID, CONTENT_TYPE )     # Given the placeholder values above, it resolves to hipaa-sample-project-bio-medical-data

LOGS_SINK_NAME="audit-logs-to-bigquery"
LOGS_SINK_DATASET_ID="cloudlogs"
LOGS_SINK_DESTINATION='bigquery.googleapis.com/projects/{}/datasets/{}'.format(PROJECT_ID, LOGS_SINK_DATASET_ID)
