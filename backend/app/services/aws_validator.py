"""AWS credentials validation service."""

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.schemas.cloud_account import AWSCredentials


class AWSValidationError(Exception):
    """AWS validation error."""

    pass


async def validate_aws_credentials(credentials: AWSCredentials) -> dict[str, str]:
    """
    Validate AWS credentials by attempting to connect and get caller identity.

    This function tests if the credentials are valid and have at minimum
    read-only permissions. It uses STS GetCallerIdentity which is a safe,
    read-only operation.

    Args:
        credentials: AWS credentials to validate

    Returns:
        Dictionary with account info (account_id, arn, user_id)

    Raises:
        AWSValidationError: If credentials are invalid or connection fails
    """
    try:
        # Create STS client with provided credentials
        sts_client = boto3.client(
            "sts",
            aws_access_key_id=credentials.access_key_id,
            aws_secret_access_key=credentials.secret_access_key,
            region_name=credentials.region,
        )

        # Get caller identity (read-only operation, no permissions needed)
        response = sts_client.get_caller_identity()

        return {
            "account_id": response["Account"],
            "arn": response["Arn"],
            "user_id": response["UserId"],
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_message = e.response["Error"]["Message"]

        if error_code == "InvalidClientTokenId":
            raise AWSValidationError("Invalid AWS Access Key ID. Please check your credentials.")
        elif error_code == "SignatureDoesNotMatch":
            raise AWSValidationError(
                "Invalid AWS Secret Access Key. Please check your credentials."
            )
        elif error_code == "AccessDenied":
            raise AWSValidationError(
                "Access denied. Your credentials may not have the necessary permissions."
            )
        else:
            raise AWSValidationError(f"AWS Error ({error_code}): {error_message}")

    except BotoCoreError as e:
        raise AWSValidationError(f"AWS connection error: {str(e)}")

    except Exception as e:
        raise AWSValidationError(f"Unexpected error validating AWS credentials: {str(e)}")


async def check_aws_read_permissions(credentials: AWSCredentials) -> dict[str, bool]:
    """
    Check if AWS credentials have the required read-only permissions.

    Tests specific permissions required for CutCosts scanning:
    - EC2 Describe operations
    - RDS Describe operations
    - S3 List operations
    - ELB Describe operations
    - CloudWatch operations

    Args:
        credentials: AWS credentials to check

    Returns:
        Dictionary with permission check results for each service

    Raises:
        AWSValidationError: If unable to check permissions
    """
    permissions = {
        "ec2": False,
        "rds": False,
        "s3": False,
        "elb": False,
        "cloudwatch": False,
    }

    try:
        # Test EC2 Describe permissions
        try:
            ec2_client = boto3.client(
                "ec2",
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                region_name=credentials.region,
            )
            # Try to describe instances (read-only, returns empty if no instances)
            ec2_client.describe_instances(MaxResults=5)
            permissions["ec2"] = True
        except ClientError:
            pass  # Permission denied or other error

        # Test RDS Describe permissions
        try:
            rds_client = boto3.client(
                "rds",
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                region_name=credentials.region,
            )
            rds_client.describe_db_instances(MaxRecords=5)
            permissions["rds"] = True
        except ClientError:
            pass

        # Test S3 List permissions
        try:
            s3_client = boto3.client(
                "s3",
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                region_name=credentials.region,
            )
            s3_client.list_buckets()
            permissions["s3"] = True
        except ClientError:
            pass

        # Test ELB Describe permissions
        try:
            elb_client = boto3.client(
                "elbv2",
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                region_name=credentials.region,
            )
            elb_client.describe_load_balancers(PageSize=5)
            permissions["elb"] = True
        except ClientError:
            pass

        # Test CloudWatch permissions
        try:
            cw_client = boto3.client(
                "cloudwatch",
                aws_access_key_id=credentials.access_key_id,
                aws_secret_access_key=credentials.secret_access_key,
                region_name=credentials.region,
            )
            cw_client.list_metrics(MaxRecords=5)
            permissions["cloudwatch"] = True
        except ClientError:
            pass

        return permissions

    except Exception as e:
        raise AWSValidationError(f"Error checking AWS permissions: {str(e)}")
