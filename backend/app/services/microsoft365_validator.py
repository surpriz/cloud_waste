"""Microsoft 365 credentials validation service."""

from typing import Any

from azure.core.exceptions import ClientAuthenticationError, HttpResponseError
from azure.identity import ClientSecretCredential
import httpx

from app.schemas.cloud_account import Microsoft365Credentials


class Microsoft365ValidationError(Exception):
    """Microsoft 365 credentials validation error."""

    pass


async def validate_microsoft365_credentials(credentials: Microsoft365Credentials) -> dict[str, Any]:
    """
    Validate Microsoft 365 App Registration credentials and verify Graph API access.

    Args:
        credentials: Microsoft365Credentials with tenant_id, client_id, client_secret

    Returns:
        Dict with organization info:
        {
            "tenant_id": "...",
            "organization_name": "...",
            "verified_domains": [...]
        }

    Raises:
        Microsoft365ValidationError: If credentials are invalid or Graph API inaccessible
    """
    try:
        # Create Azure credential object (same as Azure, but for Graph API)
        credential = ClientSecretCredential(
            tenant_id=credentials.tenant_id,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
        )

        # Get access token for Microsoft Graph
        token = credential.get_token("https://graph.microsoft.com/.default")
        access_token = token.token

        # Test Graph API access by fetching organization info
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://graph.microsoft.com/v1.0/organization",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )

            if response.status_code == 403:
                raise Microsoft365ValidationError(
                    "Access denied: App Registration does not have required Microsoft Graph permissions. "
                    "Ensure 'Files.Read.All', 'Sites.Read.All', and 'User.Read.All' permissions are granted with admin consent."
                )

            response.raise_for_status()
            data = response.json()

            if "value" not in data or len(data["value"]) == 0:
                raise Microsoft365ValidationError(
                    "No organization data returned from Microsoft Graph API. "
                    "Verify App Registration has correct tenant_id."
                )

            org = data["value"][0]

            return {
                "tenant_id": org.get("id", credentials.tenant_id),
                "organization_name": org.get("displayName", "Unknown"),
                "verified_domains": [
                    d["name"] for d in org.get("verifiedDomains", [])
                ],
            }

    except ClientAuthenticationError as e:
        raise Microsoft365ValidationError(
            f"Authentication failed: Invalid App Registration credentials. "
            f"Please verify tenant_id, client_id, and client_secret. Error: {str(e)}"
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise Microsoft365ValidationError(
                "Unauthorized: Invalid App Registration credentials. "
                "Please verify tenant_id, client_id, and client_secret are correct."
            )
        elif e.response.status_code == 403:
            raise Microsoft365ValidationError(
                "Access denied: App Registration does not have required Microsoft Graph permissions. "
                "Ensure 'Files.Read.All', 'Sites.Read.All', and 'User.Read.All' permissions are granted with admin consent."
            )
        elif e.response.status_code == 404:
            raise Microsoft365ValidationError(
                f"Organization not found for tenant {credentials.tenant_id}. "
                f"Please verify the tenant ID is correct."
            )
        else:
            raise Microsoft365ValidationError(
                f"Microsoft Graph API error (status {e.response.status_code}): {str(e)}"
            )
    except Exception as e:
        raise Microsoft365ValidationError(
            f"Unexpected error while validating Microsoft 365 credentials: {str(e)}"
        )


async def check_microsoft365_permissions(
    credentials: Microsoft365Credentials,
) -> dict[str, Any]:
    """
    Check if Microsoft 365 App Registration has required Graph API permissions.

    Verifies that the App Registration can access:
    - Files.Read.All (SharePoint/OneDrive files)
    - Sites.Read.All (SharePoint sites)
    - User.Read.All (User accounts for OneDrive)

    Args:
        credentials: Microsoft365Credentials

    Returns:
        Dict with permission check results:
        {
            "has_files_read_all": True/False,
            "has_sites_read_all": True/False,
            "has_user_read_all": True/False,
            "missing_permissions": [...],
            "all_permissions_granted": True/False
        }

    Raises:
        Microsoft365ValidationError: If permission check fails
    """
    try:
        # Create credential
        credential = ClientSecretCredential(
            tenant_id=credentials.tenant_id,
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
        )

        # Get access token
        token = credential.get_token("https://graph.microsoft.com/.default")
        access_token = token.token

        # Test permissions by attempting to call specific endpoints
        permissions_result = {
            "has_files_read_all": False,
            "has_sites_read_all": False,
            "has_user_read_all": False,
            "missing_permissions": [],
            "all_permissions_granted": False,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            }

            # Test Files.Read.All (try to list drives)
            try:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/me/drive",
                    headers=headers,
                )
                if response.status_code == 200:
                    permissions_result["has_files_read_all"] = True
            except Exception:
                permissions_result["missing_permissions"].append("Files.Read.All")

            # Test Sites.Read.All (try to list sites)
            try:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/sites?search=*",
                    headers=headers,
                )
                if response.status_code == 200:
                    permissions_result["has_sites_read_all"] = True
            except Exception:
                permissions_result["missing_permissions"].append("Sites.Read.All")

            # Test User.Read.All (try to list users)
            try:
                response = await client.get(
                    "https://graph.microsoft.com/v1.0/users?$top=1",
                    headers=headers,
                )
                if response.status_code == 200:
                    permissions_result["has_user_read_all"] = True
            except Exception:
                permissions_result["missing_permissions"].append("User.Read.All")

        # Check if all required permissions are granted
        permissions_result["all_permissions_granted"] = (
            permissions_result["has_files_read_all"]
            and permissions_result["has_sites_read_all"]
            and permissions_result["has_user_read_all"]
        )

        return permissions_result

    except Exception as e:
        raise Microsoft365ValidationError(
            f"Error checking Microsoft 365 permissions: {str(e)}"
        )
