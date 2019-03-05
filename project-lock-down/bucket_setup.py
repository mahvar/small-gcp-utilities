# Copyright 2019 Google LLC. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from utils import *
from parameters import *


def create_logs_bucket():
    """
    Creates a GCS bucket for storing logs; sets/overwrites access rights according to best practices
    and defines a life cycle to purge aging logs.

    Note: This script, at a later step, will build alerting and monitoring based on Cloud Audit Logs,
    not the logs in this bucket. Refer to the following link to understand when to use these logs vs. Cloud Audit logs:
    https://cloud.google.com/storage/docs/access-logs#should-you-use

    :return: None
    """

    run_command('gsutil mb -p {} -c {} -l {} gs://{}'
                .format(PROJECT_ID, LOGS_STORAGE_CLASS, LOGS_LOCATION, LOGS_BUCKET_ID), 'already exists')
    __set_log_bucket_access()
    __set_log_life_cycle()


def create_data_bucket():
    """
    Creates the main GCS data bucket; enables logging and versioning for the bucket
    and sets/overwrites access rights according to best practices.

    :return: None
    """

    run_command('gsutil mb -p {} -c {} -l {} gs://{}'
                .format(PROJECT_ID, DATA_STORAGE_CLASS, DATA_BUCKET_LOCATION, DATA_BUCKET_ID),'already exists')
    run_command('gsutil logging set on -b gs://{} gs://{}'.format(LOGS_BUCKET_ID, DATA_BUCKET_ID))
    run_command('gsutil versioning set on gs://{}'.format(DATA_BUCKET_ID) )
    __set_data_bucket_access()


def __set_log_bucket_access():
    """
    Creates a temp json file to define the IAM roles according to best practices
    and uses the JSON file to set the access rights against the log bucket.
    Note: For details refer to https://cloud.google.com/storage/docs/access-control/iam-roles

    :return: None
    """

    iam_binding = {
        "bindings": [
            {
                # Grant admin access to AUDITORS_GROUP:
                "members": [
                    "group:{}".format(AUDITORS_GROUP),
                    "group:{}".format(OWNERS_GROUP)
                ],
                "role": "roles/storage.admin"
            },
            {
                # You must grant cloud-storage-analytics@google.com write access to the logs bucket.
                # Refer to https://cloud.google.com/storage/docs/access-logs#delivery to see why it is required.
                "members": ["group:cloud-storage-analytics@google.com"],
                "role": "roles/storage.objectCreator"
            },
            {
                # Grant viewer access to LOG_READER_GROUP:
                "members": ["group:{}".format(LOG_READER_GROUP)],
                "role": "roles/storage.objectViewer"
            }
        ]
    }

    save_JSON(iam_binding, 'tmp_iam_binding.json')
    run_command('gsutil iam set tmp_iam_binding.json gs://{}'.format(LOGS_BUCKET_ID) )

    # When done, remove the temp file.
    run_command('rm tmp_iam_binding.json')


def __set_log_life_cycle():
    """
    Creates a temp JSON file to define Time to Live (TTL) policy for the logs
    and uses that to set the lifecycle for the log files.

    :return: None
    """

    iam_binding = {
        "lifecycle": {
            "rule": [
                {
                    "action": {"type": "Delete"},
                    "condition": {"age": LOGS_TTL, "isLive": True}
                }
            ]
        }
    }

    save_JSON(iam_binding, 'tmp_ttl.json')

    # Use the temp json file to set TTL policy for the logs bucket
    run_command( 'gsutil lifecycle set tmp_ttl.json gs://{}'.format(LOGS_BUCKET_ID) )

    # When done, remove the temp file.
    run_command('rm tmp_ttl.json')


def __set_data_bucket_access():
    """
    Creates a temp json file to define IAM roles according to best practices
    and uses the JSON file to set the access rights against the data bucket.
    Note: For details refer to https://cloud.google.com/storage/docs/access-control/iam-roles

    :return: None
    """

    iam_binding = {
        "bindings": [
            {
                "members": [
                    "group:{}".format(OWNERS_GROUP)
                ],
                "role": "roles/storage.admin"
            },
            {
                "members": [
                    "group:{}".format(DATA_READER_GROUP)
                ],
                "role": "roles/storage.objectViewer"
            },
            {
                "members": [
                    "group:{}".format(DATA_CREATOR_GROUP)
                ],
                "role": "roles/storage.objectAdmin"
            }
        ]
    }

    save_JSON(iam_binding, 'tmp_iam_binding.json')

    # Use the temp json file to overwrite existing legacy policies with above-defined roles.
    run_command('gsutil iam set tmp_iam_binding.json gs://{}'.format(DATA_BUCKET_ID))

    # When done, remove the temp file.
    run_command('rm tmp_iam_binding.json')
