"""Azure credentials validation service."""

from typing import Any

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient, SubscriptionClient

from app.schemas.cloud_account import AzureCredentials


class AzureValidationError(Exception):
    """Azure credentials validation error."""

    pass


async def validate_azure_credentials(credentials: AzureCredentials) -> dict[str, Any]:
    """
    Validate Azure Service Principal credentials and verify subscription access.

    Args:
        credentials: AzureCredentials with tenant_id, client_id, client_secret, subscription_id

    Returns:
        Dict with subscription info:
        {
            "subscription_id": "...",
            "subscription_name": "...",
            "tenant_id": "...",
            "state": "Enabled"
        }

    Raises:
        AzureValidationError: If credentials are invalid or subscription inaccessible
    """
    try:
        # Create Azure credential object
        credential = ClientSecretCredential(
            tenant_id=credentials.tenant_id,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
        )

        # Validate by trying to get subscription info
        subscription_client = SubscriptionClient(credential)

        # Get subscription details
        subscription = subscription_client.subscriptions.get(
            credentials.subscription_id
        )

        return {
            "subscription_id": subscription.subscription_id,
            "subscription_name": subscription.display_name,
            "tenant_id": subscription.tenant_id,
            "state": subscription.state,
        }

    except ClientAuthenticationError as e:
        raise AzureValidationError(
            f"Authentication failed: Invalid Service Principal credentials. "
            f"Please verify tenant_id, client_id, and client_secret. Error: {str(e)}"
        )
    except HttpResponseError as e:
        if e.status_code == 403:
            raise AzureValidationError(
                f"Access denied: Service Principal does not have permission to access subscription "
                f"{credentials.subscription_id}. Ensure 'Reader' role is assigned."
            )
        elif e.status_code == 404:
            raise AzureValidationError(
                f"Subscription not found: {credentials.subscription_id}. "
                f"Please verify the subscription ID is correct."
            )
        else:
            raise AzureValidationError(
                f"Azure API error (status {e.status_code}): {str(e)}"
            )
    except Exception as e:
        raise AzureValidationError(
            f"Unexpected error while validating Azure credentials: {str(e)}"
        )


async def check_azure_read_permissions(
    credentials: AzureCredentials,
) -> dict[str, Any]:
    """
    Check if Azure Service Principal has read-only permissions.

    Verifies that the Service Principal can list resources (Reader role).

    Args:
        credentials: AzureCredentials

    Returns:
        Dict with permission check results:
        {
            "has_reader_access": True,
            "can_list_resource_groups": True,
            "can_list_resources": True
        }

    Raises:
        AzureValidationError: If permission check fails
    """
    try:
        credential = ClientSecretCredential(
            tenant_id=credentials.tenant_id,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
        )

        # Try to list resource groups (requires Reader role)
        resource_client = ResourceManagementClient(
            credential=credential,
            subscription_id=credentials.subscription_id,
        )

        # Test: List resource groups
        can_list_resource_groups = False
        try:
            list(resource_client.resource_groups.list())
            can_list_resource_groups = True
        except HttpResponseError:
            pass

        # Test: List resources
        can_list_resources = False
        try:
            list(resource_client.resources.list())
            can_list_resources = True
        except HttpResponseError:
            pass

        has_reader_access = can_list_resource_groups and can_list_resources

        return {
            "has_reader_access": has_reader_access,
            "can_list_resource_groups": can_list_resource_groups,
            "can_list_resources": can_list_resources,
        }

    except Exception as e:
        raise AzureValidationError(
            f"Error checking Azure permissions: {str(e)}"
        )
