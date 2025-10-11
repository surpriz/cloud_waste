"""Debug script to decrypt and inspect Azure credentials."""
import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add app to path
sys.path.insert(0, '/Users/jerome_laval/Desktop/CloudWaste/backend')

from app.core.config import settings
from app.core.security import credential_encryption
from app.models.cloud_account import CloudAccount


async def inspect_credentials():
    """Inspect the encrypted credentials for the Azure account."""
    # Create async engine
    engine = create_async_engine(str(settings.DATABASE_URL), echo=False)
    AsyncSessionLocal = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with AsyncSessionLocal() as db:
        # Query the Azure account
        result = await db.execute(
            select(CloudAccount).where(
                CloudAccount.id == "ad372698-c901-4527-87d7-9920c3c21873"
            )
        )
        account = result.scalar_one_or_none()

        if not account:
            print("❌ Account not found!")
            return

        print(f"✅ Account found:")
        print(f"   ID: {account.id}")
        print(f"   Provider: {account.provider}")
        print(f"   Account Name: {account.account_name}")
        print(f"   Account Identifier: {account.account_identifier}")
        print(f"   Created At: {account.created_at}")
        print(f"\n📦 Encrypted credentials length: {len(account.credentials_encrypted)} bytes")
        print(f"   Raw (first 50 chars): {account.credentials_encrypted[:50]}")

        # Decrypt credentials
        try:
            decrypted_json = credential_encryption.decrypt(account.credentials_encrypted)
            print(f"\n🔓 Decrypted credentials JSON:")
            print(f"   {decrypted_json}")

            import json
            credentials_dict = json.loads(decrypted_json)
            print(f"\n📋 Parsed credentials dictionary:")
            print(f"   Keys: {list(credentials_dict.keys())}")
            for key, value in credentials_dict.items():
                if isinstance(value, str) and len(value) > 20:
                    print(f"   {key}: {value[:20]}... (length: {len(value)})")
                else:
                    print(f"   {key}: {value}")

        except Exception as e:
            print(f"\n❌ Error decrypting credentials: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(inspect_credentials())
