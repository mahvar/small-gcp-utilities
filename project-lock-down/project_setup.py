from utils import *
from parameters import *

import bucket_setup
import audit_monitoring_setup
import yaml


def create_project():
    """
    Creates a gcloud config (optional), creates a project mapped to the billing account
    and organization and sets the project as the default in the gcloud config.

    :return: None
    """

    # First create a gcloud config and set the account (optional):
    run_command('gcloud config configurations create {} --activate'.format(CONFIG_NAME), 'already exists')
    run_command('gcloud config set account {}'.format(ACCOUNT))

    # Then create the project:
    # Note: You must set up your project against an organization.
    run_command('gcloud projects create --organization={} {}'.format(ORGANIZATION_ID, PROJECT_ID), 'try an alternative ID')
    run_command('gcloud projects describe {}'.format(PROJECT_ID))

    # Set the appropriate billing account for this project:
    run_command('gcloud beta billing projects link --billing-account {} {}'
                .format(BILLING_ACCOUNT, PROJECT_ID))

    # Finally set the project as your default (optional):
    run_command('gcloud config set project {}'.format(PROJECT_ID))
    run_command('gcloud config configurations list')


def set_project_access():
    """
    Adjusts project rights by making OWNERS_GROUP an owner of the project.
    It removes direct ACCOUNT rights against the project.

    Note: Ensure ACCOUNT is a member (directly or indirectly) of OWNERS_GROUP
    before running this step!!!

    :return: None
    """

    # Add a policy binding to make OWNERS_GROUP an owner of the project:
    run_command('gcloud projects add-iam-policy-binding {} --member="group:{}" --role="roles/owner"'
        .format(PROJECT_ID,OWNERS_GROUP))

    # Ensure the only policy binding is the one defined above; remove everything else!
    policies = yaml.load(run_command('gcloud projects get-iam-policy {}'.format(PROJECT_ID)))

    for binding in policies['bindings']:
        members = binding['members']
        for member in members:
            if binding['role'] != "roles/owner" or member != 'group:{}'.format(OWNERS_GROUP):
                run_command('gcloud projects remove-iam-policy-binding {} --member="{}" --role="{}"'
                            .format(PROJECT_ID, member, binding['role']))


def main():
    """
    This is the main function which:
     1) creates the project and adjusts its IAM policies according to best practices.
     2) creates the data bucket and a secondary bucket for storing audit logs.
     3) sets permissions to those buckets according to best practices.
     4) turns on access logs and creates metrics that count "offensive" actions based on audit logs.
     5) uses those metrics to define alerts that fire off notifications when "offensive" actions are detected.
     6) define BigQuery queries that can retrieve the history of "offensive" actions.

    Note: This script assumes ACCOUNT is already authenticated with Google Cloud SDK.
    If that is not the case, run "gcloud auth login" before starting!!!
    """
    try:
        # Step 1: Create the project:
        create_project()

        # Step 2: Adjust project rights
        set_project_access()

        # Step 3: Create GCS bucket for logs
        bucket_setup.create_logs_bucket()

        # Step 4: Create GCS bucket for ingested data
        bucket_setup.create_data_bucket()

        # Step 5: Enable auditing and monitoring for the project
        audit_monitoring_setup.enable_audit_monitoring()

    except Exception as e:
        print('Execution interrupted with message: "{}"'.format(e.message))
    else:
        print('Finished the script successfully!')

if __name__ == '__main__':
    main()