#!/usr/bin/env python3
"""
Cleanup AWX Sample Assets

This script deletes all objects created by 0_populate_awx_assets.py.
It uses the same data definitions to identify what to remove, and deletes
in reverse dependency order so references are removed before the objects
they depend on.

Deletion order (reverse of creation):
1. Workflow Job Templates
2. Job Templates
3. Inventories (cascades hosts and groups)
4. Projects
5. Credentials
6. Custom Credential Types
7. Users
8. Teams
9. Organizations

Default objects (Demo Inventory, Demo Project, etc.) are NOT deleted.

Usage:
    python3 0_cleanup_awx_assets.py

    Override defaults with environment variables:
        AWX_HOST=https://awx.lab.local
        AWX_USERNAME=admin
        AWX_PASSWORD=password
"""
import os
import sys
import requests
import urllib3
from typing import Optional, Dict, List

# Disable SSL warnings for lab environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuration – override via environment variables
# ---------------------------------------------------------------------------
AWX_HOST = os.environ.get("AWX_HOST", "http://awx.lab.local:32000")
API_BASE = f"{AWX_HOST}/api/v2"
USERNAME = os.environ.get("AWX_USERNAME", "admin")
PASSWORD = os.environ.get("AWX_PASSWORD", "changeme")

# ---------------------------------------------------------------------------
# Names to delete — must match what 0_populate_awx_assets.py creates
# ---------------------------------------------------------------------------

ORGANIZATION_NAMES = ["MigrateMe-Corp", "MigrateMe-Ops"]

TEAM_NAMES = ["DevOps", "DBA", "Security", "App Development", "Network Operations", "Infrastructure"]

USER_NAMES = ["jsmith", "tchen", "jdoe", "nmiller", "mbrown", "lpatel", "agarcia", "dwang", "swilson", "rkumar"]

CUSTOM_CREDENTIAL_TYPE_NAMES = ["API Token"]

CREDENTIAL_NAMES = [
    "MigrateMe Machine Credential",
    "MigrateMe SCM Credential",
    "MigrateMe Vault Credential",
    "Ops Machine Credential",
    "MigrateMe API Token",
]

PROJECT_NAMES = ["MigrateMe Sample Playbooks", "Ops Automation Playbooks"]

INVENTORY_NAMES = ["MigrateMe Dev Inventory", "MigrateMe Prod Inventory", "Ops Network Inventory"]

JOB_TEMPLATE_NAMES = [
    "MigrateMe - Hello World",
    "MigrateMe - Deploy App (Dev)",
    "MigrateMe - Deploy App (Prod)",
    "MigrateMe - DB Backup",
    "Ops - Network Audit",
]

WORKFLOW_JOB_TEMPLATE_NAMES = ["MigrateMe - Full Deploy Pipeline"]


class AWXCleaner:
    """Delete AWX objects via the /api/v2/ REST API."""

    def __init__(self, session: requests.Session):
        self.session = session
        self.deleted = 0
        self.skipped = 0
        self.failed = 0

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, verify=False)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, endpoint: str) -> bool:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.delete(url, verify=False)
        if resp.status_code in (204, 202):
            return True
        elif resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def _find_by_name(self, endpoint: str, name: str) -> Optional[dict]:
        data = self._get(endpoint, params={"name": name})
        results = data.get("results", [])
        return results[0] if results else None

    def _find_by_username(self, endpoint: str, username: str) -> Optional[dict]:
        data = self._get(endpoint, params={"username": username})
        results = data.get("results", [])
        return results[0] if results else None

    def _delete_by_name(self, endpoint: str, name: str) -> bool:
        obj = self._find_by_name(endpoint, name)
        if not obj:
            print(f"      (not found, skipping)")
            self.skipped += 1
            return False
        obj_id = obj["id"]
        if self._delete(f"{endpoint}{obj_id}/"):
            print(f"      deleted (id={obj_id})")
            self.deleted += 1
            return True
        else:
            print(f"      failed to delete (id={obj_id})")
            self.failed += 1
            return False

    def delete_workflow_job_templates(self, names: List[str]):
        print("\n[1/9] Deleting Workflow Job Templates...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("workflow_job_templates/", name)

    def delete_job_templates(self, names: List[str]):
        print("\n[2/9] Deleting Job Templates...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("job_templates/", name)

    def delete_inventories(self, names: List[str]):
        print("\n[3/9] Deleting Inventories (cascades hosts and groups)...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("inventories/", name)

    def delete_projects(self, names: List[str]):
        print("\n[4/9] Deleting Projects...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("projects/", name)

    def delete_credentials(self, names: List[str]):
        print("\n[5/9] Deleting Credentials...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("credentials/", name)

    def delete_credential_types(self, names: List[str]):
        print("\n[6/9] Deleting Custom Credential Types...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("credential_types/", name)

    def delete_users(self, usernames: List[str]):
        print("\n[7/9] Deleting Users...")
        for username in usernames:
            print(f"   -> {username}")
            user = self._find_by_username("users/", username)
            if not user:
                print(f"      (not found, skipping)")
                self.skipped += 1
                continue
            user_id = user["id"]
            if self._delete(f"users/{user_id}/"):
                print(f"      deleted (id={user_id})")
                self.deleted += 1
            else:
                print(f"      failed to delete (id={user_id})")
                self.failed += 1

    def delete_teams(self, names: List[str]):
        print("\n[8/9] Deleting Teams...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("teams/", name)

    def delete_organizations(self, names: List[str]):
        print("\n[9/9] Deleting Organizations...")
        for name in names:
            print(f"   -> {name}")
            self._delete_by_name("organizations/", name)

    def print_summary(self):
        print("\n" + "=" * 60)
        print(" Cleanup Summary")
        print("=" * 60)
        print(f"   {'Deleted':.<40} {self.deleted}")
        print(f"   {'Skipped (not found)':.<40} {self.skipped}")
        print(f"   {'Failed':.<40} {self.failed}")
        print("=" * 60)


# ======================================================================
# Main
# ======================================================================

def main() -> int:
    print("=" * 60)
    print(" AWX Asset Cleanup")
    print("=" * 60)
    print(f" Host: {AWX_HOST}")
    print(f" API:  {API_BASE}")
    print(f" User: {USERNAME}")
    print("=" * 60)

    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    session.headers.update({"Content-Type": "application/json"})

    # Quick connectivity check
    try:
        resp = session.get(f"{API_BASE}/ping/", verify=False)
        resp.raise_for_status()
        print("\nConnected to AWX successfully.\n")
    except requests.exceptions.ConnectionError:
        print(f"\nERROR: Cannot connect to {AWX_HOST}")
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"\nERROR: AWX returned {e.response.status_code}")
        return 1

    cleaner = AWXCleaner(session)

    try:
        # Delete in reverse dependency order
        cleaner.delete_workflow_job_templates(WORKFLOW_JOB_TEMPLATE_NAMES)
        cleaner.delete_job_templates(JOB_TEMPLATE_NAMES)
        cleaner.delete_inventories(INVENTORY_NAMES)
        cleaner.delete_projects(PROJECT_NAMES)
        cleaner.delete_credentials(CREDENTIAL_NAMES)
        cleaner.delete_credential_types(CUSTOM_CREDENTIAL_TYPE_NAMES)
        cleaner.delete_users(USER_NAMES)
        cleaner.delete_teams(TEAM_NAMES)
        cleaner.delete_organizations(ORGANIZATION_NAMES)

        print("\nDone!")
        cleaner.print_summary()
        return 0

    except requests.exceptions.HTTPError as e:
        print(f"\nERROR: API request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"       Response: {e.response.text[:500]}")
        return 1
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
