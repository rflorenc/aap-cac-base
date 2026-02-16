#!/usr/bin/env python3
"""
Download Ansible Automation Platform API Assets

This script connects to an AAP (Ansible Automation Platform) instance via the
Gateway API and downloads workflow job templates along with all their dependencies:
- Workflow Job Templates (workflows, nodes, surveys)
- Job Templates (templates, surveys, schedules)
- Projects (source control repositories)
- Inventories (inventory sources, groups, hosts)
- Credentials (metadata only, no secrets)
- Execution Environments
- Organizations
"""
import requests
import json
import urllib3
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Optional

# Disable SSL warnings for sandbox environment
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
AAP_HOST = ""
API_BASE = f"{AAP_HOST}/api/controller/v2"
USERNAME = ""
PASSWORD = ""
OUTPUT_DIR = Path(__file__).parent / "aap_assets"


class AAPAssetDownloader:
    """Download and manage AAP assets with dependency tracking"""

    def __init__(self, session, output_dir: Path):
        self.session = session
        self.output_dir = output_dir

        # Track downloaded assets to avoid duplicates
        self.downloaded: Dict[str, Set[int]] = defaultdict(set)

        # Statistics
        self.stats = defaultdict(int)

        # Create output directories
        self.dirs = {
            'workflows': output_dir / 'workflow_job_templates',
            'job_templates': output_dir / 'job_templates',
            'projects': output_dir / 'projects',
            'inventories': output_dir / 'inventories',
            'credentials': output_dir / 'credentials',
            'execution_environments': output_dir / 'execution_environments',
            'organizations': output_dir / 'organizations',
        }

        for dir_path in self.dirs.values():
            dir_path.mkdir(parents=True, exist_ok=True)

    def fetch_api(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Fetch data from AAP API"""
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params, verify=False)
        response.raise_for_status()
        return response.json()

    def fetch_api_url(self, url: str) -> dict:
        """Fetch data from full AAP API URL"""
        if not url.startswith('http'):
            url = f"{AAP_HOST}{url}"
        response = self.session.get(url, verify=False)
        response.raise_for_status()
        return response.json()

    def save_json(self, data: dict, filepath: Path):
        """Save data as JSON"""
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def safe_filename(self, name: str, asset_id: int) -> str:
        """Create safe filename from asset name"""
        safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in name)
        return f"{asset_id:03d}_{safe_name}"

    def download_workflow_job_templates(self) -> List[dict]:
        """Download all workflow job templates"""
        print("\n📋 Downloading Workflow Job Templates...")

        workflows = self.fetch_api('workflow_job_templates/')
        workflow_list = workflows.get('results', [])
        self.stats['workflow_job_templates'] = len(workflow_list)

        print(f"   Found {len(workflow_list)} workflow(s)")

        # Save master list
        self.save_json(workflows, self.dirs['workflows'] / '_all_workflows.json')

        for wf in workflow_list:
            wf_id = wf['id']
            if wf_id in self.downloaded['workflows']:
                continue

            print(f"   📦 {wf['name']} (ID: {wf_id})")

            # Fetch detailed workflow data
            wf_detail = self.fetch_api(f"workflow_job_templates/{wf_id}/")
            nodes = self.fetch_api(f"workflow_job_templates/{wf_id}/workflow_nodes/")

            # Try to fetch survey
            survey = None
            try:
                survey = self.fetch_api(f"workflow_job_templates/{wf_id}/survey_spec/")
            except:
                pass

            # Save workflow data
            base_name = self.safe_filename(wf['name'], wf_id)
            self.save_json(wf_detail, self.dirs['workflows'] / f"{base_name}_details.json")
            self.save_json(nodes, self.dirs['workflows'] / f"{base_name}_nodes.json")
            if survey:
                self.save_json(survey, self.dirs['workflows'] / f"{base_name}_survey.json")

            self.downloaded['workflows'].add(wf_id)

            # Extract dependencies from workflow nodes
            for node in nodes.get('results', []):
                ujt = node.get('unified_job_template')
                if ujt:
                    # This could be a job_template, project, inventory_update, etc.
                    related_url = node.get('related', {}).get('unified_job_template')
                    if related_url and 'job_templates' in related_url:
                        # Extract job template ID from URL
                        jt_id = int(related_url.rstrip('/').split('/')[-1])
                        self.download_job_template(jt_id)

        return workflow_list

    def download_job_template(self, jt_id: int):
        """Download a specific job template and its dependencies"""
        if jt_id in self.downloaded['job_templates']:
            return

        try:
            print(f"      🔧 Downloading Job Template ID: {jt_id}")

            jt_detail = self.fetch_api(f"job_templates/{jt_id}/")
            self.stats['job_templates'] += 1

            # Save job template
            base_name = self.safe_filename(jt_detail['name'], jt_id)
            self.save_json(jt_detail, self.dirs['job_templates'] / f"{base_name}_details.json")

            # Try to fetch survey
            try:
                survey = self.fetch_api(f"job_templates/{jt_id}/survey_spec/")
                if survey:
                    self.save_json(survey, self.dirs['job_templates'] / f"{base_name}_survey.json")
            except:
                pass

            self.downloaded['job_templates'].add(jt_id)

            # Download dependencies
            if jt_detail.get('project'):
                self.download_project(jt_detail['project'])

            if jt_detail.get('inventory'):
                self.download_inventory(jt_detail['inventory'])

            if jt_detail.get('execution_environment'):
                self.download_execution_environment(jt_detail['execution_environment'])

            # Download credentials (metadata only)
            summary_fields = jt_detail.get('summary_fields', {})
            if summary_fields.get('credentials'):
                for cred in summary_fields['credentials']:
                    self.download_credential(cred['id'])

        except Exception as e:
            print(f"         ⚠️  Could not download Job Template {jt_id}: {e}")

    def download_project(self, project_id: int):
        """Download a project"""
        if project_id in self.downloaded['projects']:
            return

        try:
            print(f"         📂 Downloading Project ID: {project_id}")

            project = self.fetch_api(f"projects/{project_id}/")
            self.stats['projects'] += 1

            base_name = self.safe_filename(project['name'], project_id)
            self.save_json(project, self.dirs['projects'] / f"{base_name}.json")

            self.downloaded['projects'].add(project_id)

            # Download organization if present
            if project.get('organization'):
                self.download_organization(project['organization'])

            # Download SCM credential if present
            summary_fields = project.get('summary_fields', {})
            if summary_fields.get('credential'):
                self.download_credential(summary_fields['credential']['id'])

        except Exception as e:
            print(f"            ⚠️  Could not download Project {project_id}: {e}")

    def download_inventory(self, inventory_id: int):
        """Download an inventory"""
        if inventory_id in self.downloaded['inventories']:
            return

        try:
            print(f"         📊 Downloading Inventory ID: {inventory_id}")

            inventory = self.fetch_api(f"inventories/{inventory_id}/")
            self.stats['inventories'] += 1

            base_name = self.safe_filename(inventory['name'], inventory_id)
            self.save_json(inventory, self.dirs['inventories'] / f"{base_name}.json")

            # Try to download inventory sources
            try:
                sources = self.fetch_api(f"inventories/{inventory_id}/inventory_sources/")
                if sources.get('results'):
                    self.save_json(sources, self.dirs['inventories'] / f"{base_name}_sources.json")
            except:
                pass

            self.downloaded['inventories'].add(inventory_id)

            # Download organization if present
            if inventory.get('organization'):
                self.download_organization(inventory['organization'])

        except Exception as e:
            print(f"            ⚠️  Could not download Inventory {inventory_id}: {e}")

    def download_credential(self, cred_id: int):
        """Download credential metadata (no secrets)"""
        if cred_id in self.downloaded['credentials']:
            return

        try:
            credential = self.fetch_api(f"credentials/{cred_id}/")
            self.stats['credentials'] += 1

            # Remove any sensitive data (should already be masked by API)
            if 'inputs' in credential:
                credential['inputs'] = {'_note': 'Sensitive data removed'}

            base_name = self.safe_filename(credential['name'], cred_id)
            self.save_json(credential, self.dirs['credentials'] / f"{base_name}.json")

            self.downloaded['credentials'].add(cred_id)

            # Download organization if present
            if credential.get('organization'):
                self.download_organization(credential['organization'])

        except Exception as e:
            print(f"            ⚠️  Could not download Credential {cred_id}: {e}")

    def download_execution_environment(self, ee_id: int):
        """Download execution environment"""
        if ee_id in self.downloaded['execution_environments']:
            return

        try:
            ee = self.fetch_api(f"execution_environments/{ee_id}/")
            self.stats['execution_environments'] += 1

            base_name = self.safe_filename(ee['name'], ee_id)
            self.save_json(ee, self.dirs['execution_environments'] / f"{base_name}.json")

            self.downloaded['execution_environments'].add(ee_id)

            # Download organization if present
            if ee.get('organization'):
                self.download_organization(ee['organization'])

        except Exception as e:
            print(f"            ⚠️  Could not download Execution Environment {ee_id}: {e}")

    def download_organization(self, org_id: int):
        """Download organization"""
        if org_id in self.downloaded['organizations']:
            return

        try:
            org = self.fetch_api(f"organizations/{org_id}/")
            self.stats['organizations'] += 1

            base_name = self.safe_filename(org['name'], org_id)
            self.save_json(org, self.dirs['organizations'] / f"{base_name}.json")

            self.downloaded['organizations'].add(org_id)

        except Exception as e:
            print(f"            ⚠️  Could not download Organization {org_id}: {e}")

    def print_summary(self):
        """Print download summary"""
        print("\n" + "="*60)
        print("📊 Download Summary")
        print("="*60)

        for asset_type, count in self.stats.items():
            print(f"   • {asset_type.replace('_', ' ').title()}: {count}")

        print(f"\n📁 Output Directory: {self.output_dir}")
        print(f"   Total files: {sum(1 for _ in self.output_dir.rglob('*.json'))}")
        print("="*60)


def main():
    """Main execution function"""
    print("="*60)
    print("🚀 AAP Asset Downloader")
    print("="*60)
    print(f"🔗 Host: {AAP_HOST}")
    print(f"📥 API: {API_BASE}")
    print(f"📁 Output: {OUTPUT_DIR}")
    print("="*60)

    # Create session with authentication
    session = requests.Session()
    session.auth = (USERNAME, PASSWORD)
    session.headers.update({
        "Content-Type": "application/json",
    })

    try:
        # Initialize downloader
        downloader = AAPAssetDownloader(session, OUTPUT_DIR)

        # Download workflow templates and all dependencies
        downloader.download_workflow_job_templates()

        # Print summary
        downloader.print_summary()

        return 0

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error connecting to AAP: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit(main())
