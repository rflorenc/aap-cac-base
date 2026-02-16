#!/usr/bin/env python3
"""
Cleanup AAP API Assets

This script queries an AAP 2.5+ instance via the Controller API and deletes
all non-default objects in reverse dependency order.

Default/system-managed objects (Default org, Demo Inventory, Demo Project,
Demo Credential, system EEs) are never deleted.

Deletion order (reverse of dependency):
  1. Workflow Job Templates
  2. Job Templates
  3. Inventories (cascades hosts, groups, sources)
  4. Projects
  5. Credentials
  6. Execution Environments
  7. Organizations

Usage:
    python3 cleanup_aap_api_assets.py

    Override defaults with environment variables:
        AAP_HOST=https://aap.lab.local
        AAP_USERNAME=admin
        AAP_PASSWORD=redhat123
"""
import os
import sys
import requests
import urllib3
from typing import Optional, List

# Disable SSL warnings for lab environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------------------------------------------------------------------------
# Configuration – override via environment variables
# ---------------------------------------------------------------------------
AAP_HOST = os.environ.get("AAP_HOST", "https://aap.lab.local")
API_BASE = f"{AAP_HOST}/api/controller/v2"
USERNAME = os.environ.get("AAP_USERNAME", "admin")
PASSWORD = os.environ.get("AAP_PASSWORD", "redhat123")

# ---------------------------------------------------------------------------
# Default / system-managed objects to NEVER delete
# ---------------------------------------------------------------------------
SKIP_ORGS = {"Default"}
SKIP_PROJECTS = {"Demo Project"}
SKIP_INVENTORIES = {"Demo Inventory"}
SKIP_CREDENTIALS = {"Demo Credential"}
SKIP_EES = {
    "Control Plane Execution Environment",
    "Default execution environment",
    "Ansible Engine 2.9 Execution Environment",
    "Minimal execution environment",
}


class AAPCleaner:
    """Delete AAP objects via the /api/controller/v2/ REST API."""

    def __init__(self, session: requests.Session):
        self.session = session
        self.deleted = 0
        self.skipped = 0
        self.failed = 0

    def _get_all(self, endpoint: str, params: Optional[dict] = None) -> List[dict]:
        """Fetch all pages from a paginated API endpoint."""
        results = []
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        while url:
            resp = self.session.get(url, params=params, verify=False)
            resp.raise_for_status()
            data = resp.json()
            results.extend(data.get("results", []))
            url = data.get("next")
            params = None  # next URL already includes params
        return results

    def _delete(self, endpoint: str) -> bool:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.delete(url, verify=False)
        if resp.status_code in (204, 202):
            return True
        elif resp.status_code == 404:
            return False
        resp.raise_for_status()
        return True

    def _delete_object(self, endpoint: str, obj_id: int, name: str) -> bool:
        print(f"   -> {name} (id={obj_id})")
        try:
            if self._delete(f"{endpoint}{obj_id}/"):
                print(f"      deleted")
                self.deleted += 1
                return True
            else:
                print(f"      not found, skipping")
                self.skipped += 1
                return False
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            print(f"      FAILED (HTTP {status})")
            self.failed += 1
            return False

    def delete_all_non_default(self):
        """Query the API and delete all non-default objects."""
        order = [
            ("Workflow Job Templates", "workflow_job_templates/", set()),
            ("Job Templates",          "job_templates/",          set()),
            ("Inventories",            "inventories/",            SKIP_INVENTORIES),
            ("Projects",               "projects/",               SKIP_PROJECTS),
            ("Credentials",            "credentials/",            SKIP_CREDENTIALS),
            ("Execution Environments", "execution_environments/", SKIP_EES),
            ("Organizations",          "organizations/",          SKIP_ORGS),
        ]

        for step, (label, endpoint, skip_names) in enumerate(order, 1):
            print(f"\n[{step}/{len(order)}] Deleting {label}...")
            try:
                objects = self._get_all(endpoint)
            except requests.exceptions.HTTPError as e:
                print(f"   ERROR fetching list: {e}")
                continue

            if not objects:
                print("   (none found)")
                continue

            for obj in objects:
                name = obj.get("name", f"id={obj['id']}")
                if name in skip_names:
                    print(f"   -> {name} (id={obj['id']})  [DEFAULT — skipping]")
                    self.skipped += 1
                    continue
                if obj.get("managed"):
                    print(f"   -> {name} (id={obj['id']})  [MANAGED — skipping]")
                    self.skipped += 1
                    continue
                self._delete_object(endpoint, obj["id"], name)

    def print_summary(self):
        print("\n" + "=" * 60)
        print(" Cleanup Summary")
        print("=" * 60)
        print(f"   {'Deleted':.<40} {self.deleted}")
        print(f"   {'Skipped (default/not found)':.<40} {self.skipped}")
        print(f"   {'Failed':.<40} {self.failed}")
        print("=" * 60)


# ======================================================================
# Main
# ======================================================================

def main() -> int:
    print("=" * 60)
    print(" AAP Asset Cleanup")
    print("=" * 60)
    print(f" Host:  {AAP_HOST}")
    print(f" API:   {API_BASE}")
    print(f" User:  {USERNAME}")
    print("=" * 60)

    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    session.headers.update({"Content-Type": "application/json"})

    # Quick connectivity check
    try:
        resp = session.get(f"{API_BASE}/ping/", verify=False)
        resp.raise_for_status()
        print("\nConnected to AAP successfully.\n")
    except requests.exceptions.ConnectionError:
        print(f"\nERROR: Cannot connect to {AAP_HOST}")
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"\nERROR: AAP returned {e.response.status_code}")
        return 1

    cleaner = AAPCleaner(session)

    try:
        cleaner.delete_all_non_default()
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
