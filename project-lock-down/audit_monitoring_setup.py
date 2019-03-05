from utils import *
from parameters import *
from datetime import datetime
import time


def enable_audit_monitoring():
    """
    Enables audit logging for all services;
    Sets up a stream of log exports to BigQuery;
    Defines alerts that fire off when "offensive" actions are detected among audit logs; and
    Defines a query that extracts the history of "offensive" actions from BigQuery

    Note: Any of the following actions is considered "offensive" in this context:
    1. Altering IAM policies;
    2. Altering bucket permissions;
    3. Anyone other than the named users accessing the data bucket.

    :return: None
    """
    __enable_data_access_logging()
    __enable_log_streaming()
    __create_audit_alerts()
    __get_incidents_history()


def __enable_data_access_logging():
    """
    Enables data access audit logging for all services.

    :return: None
    """
    _tempFile = "tmp_audit_config.json"

    auditConfig = {
        "auditConfigs": [
            {
                "auditLogConfigs": [
                    {
                        "logType": "ADMIN_READ"
                    },
                    {
                        "logType": "DATA_WRITE"
                    },
                    {
                        "logType": "DATA_READ"
                    }
                ],
                "service": "allServices",
            }
        ]
    }

    # get current policy
    run_command('gcloud projects get-iam-policy {} --format=json >>{}'.format(PROJECT_ID, _tempFile))

    # merge it with above-defined config
    merge_JSON(auditConfig, _tempFile)

    # set the policy
    run_command('gcloud projects set-iam-policy {} {}'.format(PROJECT_ID, _tempFile))

    # delete the temp file
    run_command('rm {}'.format(_tempFile))


def __enable_log_streaming():
    """
    Creates a stream of Stackdriver log exports into a BigQuery dataset.

    :return: None
    """
    # Enable BigQuery service for the project:
    run_command('gcloud services enable bigquery --project {}'.format(PROJECT_ID))

    # Create the BigQuery dataset to store the logs:
    # For details refer to https://cloud.google.com/bigquery/docs/datasets#bigquery-create-dataset-cli
    run_command('bq mk --data_location {} --description \"Cloud logging export.\" {}'
                .format(LOGS_LOCATION, LOGS_SINK_DATASET_ID), 'already exists')

    # Set up a log sink to the above-created BigQuery dataset:
    output_message = run_command('gcloud logging sinks create {} {} --project {} \
                        --log-filter=\'resource.type=\"gcs_bucket\" OR resource.type=\"project\"\''
                        .format(LOGS_SINK_NAME, LOGS_SINK_DESTINATION, PROJECT_ID))

    # The service account that will be writing to BQ dataset is listed by the previous command.
    # After extracting the service account from the message, you need to give it BQ Writer role to that service account.
    __set_dataset_access( __find_service_account_in_message(output_message) )


def __set_dataset_access(service_account):
    """
    Creates a temp json file to define the IAM roles according to best practices
    and uses the JSON file to set the access rights against the BigQuery dataset
    where Stackdriver logs are streamed to.

    Note: Aside from the user groups, the service account that streams
    Stackdriver logs into BiqQuery needs write access to the dataset as well;
    the service account is passed in as an input parameter.

    :param service_account: The service account streaming Stackdriver logs into BiqQuery

    :return: None
    """

    assert service_account, 'service_account cannot be blank!'

    dataset_roles = {
        "access": [
            {
                "role": "WRITER",
                "userByEmail": service_account
            },
            {
                "role": "OWNER",
                "groupByEmail": OWNERS_GROUP
            },
            {
                "role": "OWNER",
                "groupByEmail": AUDITORS_GROUP
            },
            {
                "role": "READER",
                "groupByEmail": LOG_READER_GROUP
            }
        ]
    }

    save_JSON (dataset_roles, 'tmp_ds_roles.json')

    # Use the temp json file to overwrite existing policies with above-defined roles.
    run_command('bq update --source=tmp_ds_roles.json {}'.format(LOGS_SINK_DATASET_ID) )

    # When done, remove the temp file.
    run_command('rm tmp_ds_roles.json')


def __create_audit_alerts():
    """
    Given the fact that this is a locked down environment, you need to implement some proactive measures.
    In this section, you define three alerts that are fired off when:
    1. IAM policies are altered
    2. bucket permissions are altered
    3. anyone other than the named users accesses the data bucket

    Note: This is assuming you already have a Stackdriver account. Refer to the following links for more details:
    https://cloud.google.com/monitoring/accounts/
    https://cloud.google.com/monitoring/accounts/guide

    :return: None
    """

    # Create a log-based metric to count all calls to SetIamPolicy:
    metric1_name = "iam-policy-change"
    run_command('gcloud logging metrics create {} --description="Count of IAM policy changes."  --project={}  --log-filter="\
        resource.type=project AND \
        protoPayload.serviceName=cloudresourcemanager.googleapis.com AND \
        protoPayload.methodName=SetIamPolicy"'.format(metric1_name, PROJECT_ID))

    # Create a log-based metric to count all calls to setIamPermissions or storage.objects.update on GCS buckets:
    metric2_name = "bucket-permission-change"
    run_command('gcloud logging metrics create {} --description="Count of GCS permission changes."  --project={}  --log-filter="\
            resource.type=gcs_bucket AND \
            protoPayload.serviceName=storage.googleapis.com AND \
            (protoPayload.methodName=storage.setIamPermissions OR protoPayload.methodName=storage.objects.update)"'
                .format(metric2_name, PROJECT_ID))

    # Create a log-based metric to count unexpected accesses to the data bucket:
    metric3_name = "unexpected-bucket-access-{}".format(DATA_BUCKET_ID)
    logFilter = 'resource.type=gcs_bucket AND \
            logName=projects/{}/logs/cloudaudit.googleapis.com%2Fdata_access AND \
            protoPayload.resourceName=projects/_/buckets/{} AND \
            protoPayload.authenticationInfo.principalEmail!=({})'\
            .format(PROJECT_ID, DATA_BUCKET_ID, WHITELIST_USERS)

    run_command('gcloud logging metrics create {} \
           --description=\"Count of unexpected data access to {}.\"  \
           --project={} --log-filter=\"{}\"'.format(metric3_name, DATA_BUCKET_ID, PROJECT_ID, logFilter))

    # Create an email notification channel. Refer to https://cloud.google.com/monitoring/support/notification-options
    notification_channel_name = __create_notification_channel()

    # There is a lag between when log-based metrics are created and when they become available in Stackdriver.
    # 30 seconds should work, but you may have to adjust it.
    time.sleep(30)

    # Create an alert based on metric 1:
    __create_alert_policy ("global", metric1_name, notification_channel_name, "IAM Policy Change Alert",
                           "This policy ensures the designated user/group is notified when IAM policies are altered.")

    # Create an alert based on metric 2:
    __create_alert_policy("gcs_bucket", metric2_name, notification_channel_name, "Bucket Permission Change Alert",
                      "This policy ensures the designated user/group is notified when bucket/object permissions are altered.")

    # Create an alert based on metric 3:
    __create_alert_policy ("gcs_bucket", metric3_name, notification_channel_name, "Unexpected Bucket Access Alert",
                           "This policy ensures the designated user/group is notified when data bucket is \
                           accessed by an unexpected user.")


def __create_alert_policy (resource_type, metric_name, notification_channel_name, policy_name, policy_desc):
    """
    Creates a Cloud Monitoring policy. Refer to: https://cloud.google.com/sdk/gcloud/reference/alpha/monitoring/policies/

    Note: This is using an alpha version of CLI, which may change in backward incompatible ways.
    Alternatives include using Cloud Console manually or APIs programmatically: https://cloud.google.com/monitoring/docs/apis

    :param resource_type: the type of resource to monitor. Refer to: https://cloud.google.com/monitoring/api/resources

    :param metric_name: a name to be assigned to the log-based metric

    :param notification_channel_name: the notification channel to be associated with the alert policy

    :param policy_name: a name to be assigned to the alert policy

    :param policy_desc: a brief description to be assigned to the alert policy

    :return: None
    """

    condition_filter = "resource.type=\"{}\" AND metric.type=\"logging.googleapis.com/user/{}\"".format(resource_type, metric_name)

    policy = {
        "displayName": policy_name,
        "documentation": {
            "content": policy_desc,
            "mimeType": "text/markdown"
        },
        "conditions": [
            {
                "conditionThreshold": {
                    "comparison": "COMPARISON_GT",
                    "thresholdValue": 0,
                    "filter": condition_filter,
                    "duration": "0s"
                },
                "displayName": "No tolerance on {}!".format(metric_name)
            }
        ],
        "combiner": "AND",
        "enabled": True,
        "notificationChannels": [
            notification_channel_name
        ]
    }

    save_JSON(policy, 'tmp_alert_policy.json')

    output_message = run_command('gcloud alpha monitoring policies create --policy-from-file tmp_alert_policy.json')

    # When done, remove the temp file.
    run_command('rm tmp_alert_policy.json')


def __create_notification_channel():
        """
        Creates a monitoring channel. Refer to: https://cloud.google.com/sdk/gcloud/reference/alpha/monitoring/channels/

        Note: This is using an alpha version of CLI, which may change in backward incompatible ways.
        Alternatives include using Cloud Console manually or APIs programmatically: https://cloud.google.com/monitoring/docs/apis

        :return: None
        """
        channel = {
            "type": "email",
            "displayName": "Email",
            "labels": {
                "email_address": AUDITORS_GROUP
            }
        }

        save_JSON(channel, 'tmp_notification_channel.json')

        output_message = run_command(
            'gcloud alpha monitoring channels create --channel-content-from-file tmp_notification_channel.json')
        channel_name = __find_notification_channel_name_in_message(output_message)

        # When done, remove the temp file.
        run_command('rm tmp_notification_channel.json')

        return channel_name


def __get_incidents_history(date='*'):
    """
    Builds a query against the logs in BigQuery.
    Unless a specific date is specified, the entire history is scanned.

    :param date: date of interest in YYYYMMDD format for e.g:  20180611

    :return: None
    """
    assert (date == '*' or datetime.strptime(date, "%Y%m%d") ), "date must be of format YYYYMMDD!"

    # Prepare the IN clause from WHITELIST_USERS. For e.g:
    # Convert: "user1@google.com AND user2@google.com" to "'user1@google.com', 'user2@google.com'"
    IN_clause = map(lambda x: x.replace(' ', ''), WHITELIST_USERS.split('AND'))
    IN_clause = map(lambda x: '\'{}\''.format(x), IN_clause)
    IN_clause = ','.join(IN_clause)

    query1 = 'SELECT timestamp, resource.labels.project_id as project, protopayload_auditlog.authenticationInfo.principalEmail as offender, \
    \'IAM Policy Tampering\' as offenceType FROM `{}.{}.cloudaudit_googleapis_com_activity_{}` \
    WHERE resource.type = "project" AND protopayload_auditlog.serviceName = "cloudresourcemanager.googleapis.com" \
    AND protopayload_auditlog.methodName = "SetIamPolicy"'.format(PROJECT_ID, LOGS_SINK_DATASET_ID, date)

    query2 = 'SELECT timestamp, resource.labels.project_id as project, protopayload_auditlog.authenticationInfo.principalEmail as offender, \
    \'Bucket Permission Tampering\' as offenceType FROM `{}.{}.cloudaudit_googleapis_com_activity_{}` \
    WHERE resource.type = "gcs_bucket" AND protopayload_auditlog.serviceName = "storage.googleapis.com" \
    AND(protopayload_auditlog.methodName = "storage.setIamPermissions" OR protopayload_auditlog.methodName = "storage.objects.update")'.\
        format(PROJECT_ID, LOGS_SINK_DATASET_ID, date)

    query3 = 'SELECT timestamp, resource.labels.project_id as project, protoPayload_auditlog.authenticationInfo.principalEmail as offender, \
    \'Unexpected Bucket Access\' as offenceType FROM `{}.{}.cloudaudit_googleapis_com_data_access_{}` \
    WHERE resource.type = \'gcs_bucket\' AND(protoPayload_auditlog.resourceName LIKE \'%{}\' OR \
    protoPayload_auditlog.resourceName LIKE \'%{}\') AND protoPayload_auditlog.authenticationInfo.principalEmail \
    NOT IN({})'.format(PROJECT_ID, LOGS_SINK_DATASET_ID, date, LOGS_BUCKET_ID, DATA_BUCKET_ID, IN_clause)

    final_query = '{} UNION DISTINCT {} UNION DISTINCT {} ORDER BY timestamp DESC'.format(query1, query2, query3)

    save_string(final_query, 'tmp_query.sql')

    run_command('bq query --use_legacy_sql=false < tmp_query.sql')

    # When done, remove the temp file.
    run_command('rm tmp_query.sql')


def __find_service_account_in_message(message):
        """
        The command "gcloud logging sinks create", communicates a service account Id as part of its message.
        Knowing the message format, this function extracts the service account Id and returns it to the caller,
        which will grant it with BQ permissions.

        Sample message:
        "Created [https://logging.googleapis.com/v2/projects/hipaa-sample-project/sinks/audit-logs-to-bigquery].
        Please remember to grant `serviceAccount:p899683180883-075251@gcp-sa-logging.iam.gserviceaccount.com` the WRITER role on the dataset.
        More information about sinks can be found at https://cloud.google.com/logging/docs/export/configure_export"

        :param message: the message communicated by "gcloud logging sinks create" command

        :return: the service account Id that requires BQ permissions
        """
        service_account = [t for t in message.split() if t.startswith('`serviceAccount:')]
        if service_account:
            service_account = service_account[0].replace('`', '')
            service_account = service_account.replace('serviceAccount:', '')

        return service_account


def __find_notification_channel_name_in_message(message):
        """
        The command "gcloud alpha monitoring channels create", communicates a notification channel Id as part of its output.
        Knowing the message format, this function extracts the channel Id and returns it to the caller.

        Sample message:
        "Created notification channel [projects/hipaa-sample-project/notificationChannels/1095329235450268453]."

        :param message: the message communicated by "gcloud alpha monitoring channels create" command

        :return: the notification channel Id to be used for defining a stack driver alert
        """
        channel_name = [t for t in message.split() if t.startswith('[projects')]
        return channel_name[0].translate(None, '[].')