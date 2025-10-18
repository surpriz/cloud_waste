"""Script to insert detection_rules properly via SQLAlchemy."""
import asyncio
import uuid
from app.core.database import AsyncSessionLocal
from app.crud import detection_rule as detection_rule_crud

async def main():
    async with AsyncSessionLocal() as db:
        user_id = uuid.UUID("c50adeba-3f7b-4a1f-9730-af54f154fe08")

        # Insert disk_snapshot_redundant rule
        rule = await detection_rule_crud.create_or_update_rule(
            db=db,
            user_id=user_id,
            resource_type="disk_snapshot_redundant",
            rules={
                "enabled": True,
                "min_age_days": 0,
                "max_snapshots_per_disk": 3
            }
        )

        print(f"✅ Inserted rule: {rule.resource_type} with rules: {rule.rules}")

if __name__ == "__main__":
    asyncio.run(main())
