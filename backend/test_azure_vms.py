#!/usr/bin/env python3
"""
Test script to verify Azure VM listing works with Service Principal credentials
"""
import asyncio
from app.core.database import get_db
from app.models.cloud_account import CloudAccount
from app.core.security import credential_encryption
import json
from azure.identity import ClientSecretCredential
from azure.mgmt.compute import ComputeManagementClient

async def test_list_vms():
    """Test listing VMs from Azure"""
    from sqlalchemy import select

    # Get database session
    async for db in get_db():
        # Get Azure account
        result = await db.execute(
            select(CloudAccount).where(CloudAccount.provider == "azure").limit(1)
        )
        account = result.scalar_one_or_none()

        if not account:
            print("❌ No Azure account found in database")
            return

        # Decrypt credentials
        credentials_json = credential_encryption.decrypt(account.credentials_encrypted)
        credentials = json.loads(credentials_json)

        tenant_id = credentials.get("azure_tenant_id")
        client_id = credentials.get("azure_client_id")
        client_secret = credentials.get("azure_client_secret")
        subscription_id = credentials.get("azure_subscription_id")

        print(f"✅ Account found: {account.account_name}")
        print(f"   Tenant ID: {tenant_id}")
        print(f"   Client ID: {client_id}")
        print(f"   Subscription ID: {subscription_id}")
        print()

        # Create Azure credential
        print("🔐 Authenticating with Azure...")
        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Create Compute Management Client
        print("📡 Creating Compute Management Client...")
        compute_client = ComputeManagementClient(credential, subscription_id)

        # List all VMs
        print("🔍 Listing all VMs in subscription...")
        vms_list = list(compute_client.virtual_machines.list_all())

        print(f"\n📊 Total VMs found: {len(vms_list)}")
        print()

        if len(vms_list) == 0:
            print("❌ No VMs found! This is the problem.")
            print("   Trying alternative methods...")

            # Try listing by resource group
            print("\n🔍 Trying to list VMs by resource group 'CloudWaste-Tests'...")
            try:
                rg_vms = list(compute_client.virtual_machines.list("CloudWaste-Tests"))
                print(f"   VMs in CloudWaste-Tests: {len(rg_vms)}")
                for vm in rg_vms:
                    print(f"   - {vm.name} (location: {vm.location})")
            except Exception as e:
                print(f"   ❌ Error: {e}")

            # Try listing by resource group (case insensitive)
            print("\n🔍 Trying to list VMs by resource group 'CLOUDWASTE-TESTS' (uppercase)...")
            try:
                rg_vms = list(compute_client.virtual_machines.list("CLOUDWASTE-TESTS"))
                print(f"   VMs in CLOUDWASTE-TESTS: {len(rg_vms)}")
                for vm in rg_vms:
                    print(f"   - {vm.name} (location: {vm.location})")
            except Exception as e:
                print(f"   ❌ Error: {e}")
        else:
            print("✅ VMs found successfully!")
            for vm in vms_list:
                print(f"\n   VM: {vm.name}")
                print(f"   - Location: {vm.location}")
                print(f"   - Resource Group: {vm.id.split('/')[4]}")
                print(f"   - VM Size: {vm.hardware_profile.vm_size}")

        break

if __name__ == "__main__":
    asyncio.run(test_list_vms())
