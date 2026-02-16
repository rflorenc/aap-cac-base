#!/usr/bin/env python3
"""
Populate AWX with Sample Assets for Migration Testing

This script connects to an AWX instance via the /api/v2/ API and creates
a realistic set of objects to use as migration source data:
- Organizations
- Teams (by IT department)
- Users (assigned to teams and organizations)
- Credential Types (custom)
- Credentials (Machine, SCM, Vault)
- Projects (Git-backed)
- Inventories
- Hosts and Groups
- Job Templates
- Workflow Job Templates (with nodes)
- Role-based access (team permissions on objects)

Designed to run against AWX (awx.lab.local) using the direct /api/v2/ API.
Objects are created in dependency order so references resolve correctly.

Usage:
    python3 populate_awx_assets.py

    Override defaults with environment variables:
        AWX_HOST=https://awx.lab.local
        AWX_USERNAME=admin
        AWX_PASSWORD=password
"""
import os
import sys
import time
import requests
import json
import urllib3
from typing import Optional, Dict, Any, List

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
# Sample data definitions – edit these to change what gets created
# ---------------------------------------------------------------------------

ORGANIZATIONS = [
    {
        "name": "MigrateMe-Corp",
        "description": "Primary organization for migration testing",
    },
    {
        "name": "MigrateMe-Ops",
        "description": "Operations team organization",
    },
]

TEAMS = [
    # -- MigrateMe-Corp departments --
    {
        "name": "DevOps",
        "description": "CI/CD pipelines and deployment automation",
        "organization": "MigrateMe-Corp",
    },
    {
        "name": "DBA",
        "description": "Database administration and operations",
        "organization": "MigrateMe-Corp",
    },
    {
        "name": "Security",
        "description": "Security auditing and compliance",
        "organization": "MigrateMe-Corp",
    },
    {
        "name": "App Development",
        "description": "Application developers",
        "organization": "MigrateMe-Corp",
    },
    # -- MigrateMe-Ops departments --
    {
        "name": "Network Operations",
        "description": "Network infrastructure management",
        "organization": "MigrateMe-Ops",
    },
    {
        "name": "Infrastructure",
        "description": "Server and platform infrastructure",
        "organization": "MigrateMe-Ops",
    },
]

USERS = [
    # DevOps
    {
        "username": "jsmith",
        "first_name": "John",
        "last_name": "Smith",
        "email": "jsmith@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["DevOps"],
    },
    {
        "username": "tchen",
        "first_name": "Tom",
        "last_name": "Chen",
        "email": "tchen@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["DevOps"],
    },
    # DBA
    {
        "username": "jdoe",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jdoe@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["DBA"],
    },
    {
        "username": "nmiller",
        "first_name": "Nancy",
        "last_name": "Miller",
        "email": "nmiller@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["DBA"],
    },
    # Security
    {
        "username": "mbrown",
        "first_name": "Mike",
        "last_name": "Brown",
        "email": "mbrown@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["Security"],
    },
    {
        "username": "lpatel",
        "first_name": "Lisa",
        "last_name": "Patel",
        "email": "lpatel@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["Security"],
    },
    # App Development
    {
        "username": "agarcia",
        "first_name": "Ana",
        "last_name": "Garcia",
        "email": "agarcia@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["App Development"],
    },
    {
        "username": "dwang",
        "first_name": "David",
        "last_name": "Wang",
        "email": "dwang@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Corp",
        "teams": ["App Development"],
    },
    # Network Operations
    {
        "username": "swilson",
        "first_name": "Sarah",
        "last_name": "Wilson",
        "email": "swilson@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Ops",
        "teams": ["Network Operations"],
    },
    # Infrastructure
    {
        "username": "rkumar",
        "first_name": "Raj",
        "last_name": "Kumar",
        "email": "rkumar@migrateme.local",
        "password": "ChangeMe123!",
        "organization": "MigrateMe-Ops",
        "teams": ["Infrastructure"],
    },
]

# Role assignments: grant teams specific permissions on objects.
# object_type must match an AWX API endpoint (job_templates, inventories, projects, etc.)
# role_field is the key in summary_fields.object_roles (e.g. "execute_role", "read_role",
# "admin_role", "use_role", "update_role", "adhoc_role")
TEAM_ROLES = [
    # DevOps team: admin on deploy templates, execute on DB backup, use credentials & inventories
    {"team": "DevOps", "object_type": "job_templates", "object_name": "MigrateMe - Deploy App (Dev)", "role_field": "admin_role"},
    {"team": "DevOps", "object_type": "job_templates", "object_name": "MigrateMe - Deploy App (Prod)", "role_field": "execute_role"},
    {"team": "DevOps", "object_type": "job_templates", "object_name": "MigrateMe - DB Backup", "role_field": "execute_role"},
    {"team": "DevOps", "object_type": "inventories", "object_name": "MigrateMe Dev Inventory", "role_field": "use_role"},
    {"team": "DevOps", "object_type": "inventories", "object_name": "MigrateMe Prod Inventory", "role_field": "use_role"},
    {"team": "DevOps", "object_type": "projects", "object_name": "MigrateMe Sample Playbooks", "role_field": "use_role"},
    {"team": "DevOps", "object_type": "credentials", "object_name": "MigrateMe Machine Credential", "role_field": "use_role"},
    # DBA team: admin on DB backup, read on prod inventory
    {"team": "DBA", "object_type": "job_templates", "object_name": "MigrateMe - DB Backup", "role_field": "admin_role"},
    {"team": "DBA", "object_type": "inventories", "object_name": "MigrateMe Prod Inventory", "role_field": "use_role"},
    {"team": "DBA", "object_type": "credentials", "object_name": "MigrateMe Machine Credential", "role_field": "use_role"},
    # Security team: read-only across everything in Corp
    {"team": "Security", "object_type": "job_templates", "object_name": "MigrateMe - Hello World", "role_field": "read_role"},
    {"team": "Security", "object_type": "job_templates", "object_name": "MigrateMe - Deploy App (Dev)", "role_field": "read_role"},
    {"team": "Security", "object_type": "job_templates", "object_name": "MigrateMe - Deploy App (Prod)", "role_field": "read_role"},
    {"team": "Security", "object_type": "job_templates", "object_name": "MigrateMe - DB Backup", "role_field": "read_role"},
    {"team": "Security", "object_type": "inventories", "object_name": "MigrateMe Dev Inventory", "role_field": "read_role"},
    {"team": "Security", "object_type": "inventories", "object_name": "MigrateMe Prod Inventory", "role_field": "read_role"},
    {"team": "Security", "object_type": "projects", "object_name": "MigrateMe Sample Playbooks", "role_field": "read_role"},
    # App Development: execute hello world and dev deploy, use dev inventory
    {"team": "App Development", "object_type": "job_templates", "object_name": "MigrateMe - Hello World", "role_field": "execute_role"},
    {"team": "App Development", "object_type": "job_templates", "object_name": "MigrateMe - Deploy App (Dev)", "role_field": "execute_role"},
    {"team": "App Development", "object_type": "inventories", "object_name": "MigrateMe Dev Inventory", "role_field": "use_role"},
    {"team": "App Development", "object_type": "projects", "object_name": "MigrateMe Sample Playbooks", "role_field": "use_role"},
    # Network Operations: admin on network audit, use network inventory
    {"team": "Network Operations", "object_type": "job_templates", "object_name": "Ops - Network Audit", "role_field": "admin_role"},
    {"team": "Network Operations", "object_type": "inventories", "object_name": "Ops Network Inventory", "role_field": "admin_role"},
    {"team": "Network Operations", "object_type": "projects", "object_name": "Ops Automation Playbooks", "role_field": "use_role"},
    {"team": "Network Operations", "object_type": "credentials", "object_name": "Ops Machine Credential", "role_field": "use_role"},
    # Infrastructure: read on network objects, use Ops credential
    {"team": "Infrastructure", "object_type": "job_templates", "object_name": "Ops - Network Audit", "role_field": "execute_role"},
    {"team": "Infrastructure", "object_type": "inventories", "object_name": "Ops Network Inventory", "role_field": "use_role"},
    {"team": "Infrastructure", "object_type": "credentials", "object_name": "Ops Machine Credential", "role_field": "use_role"},
]

CUSTOM_CREDENTIAL_TYPES = [
    {
        "name": "API Token",
        "description": "Custom credential type for REST API tokens",
        "kind": "cloud",
        "inputs": {
            "fields": [
                {"id": "api_url", "label": "API URL", "type": "string"},
                {"id": "api_token", "label": "API Token", "type": "string", "secret": True},
            ],
            "required": ["api_url", "api_token"],
        },
        "injectors": {
            "extra_vars": {
                "api_url": "{{ api_url }}",
                "api_token": "{{ api_token }}",
            }
        },
    },
]

CREDENTIALS = [
    {
        "name": "MigrateMe Machine Credential",
        "description": "SSH credential for Linux hosts",
        "organization": "MigrateMe-Corp",
        "credential_type": "Machine",
        "inputs": {
            "username": "ansible",
            "password": "ansible123",
            "become_method": "sudo",
            "become_username": "root",
        },
    },
    {
        "name": "MigrateMe SCM Credential",
        "description": "Git credential for project sync",
        "organization": "MigrateMe-Corp",
        "credential_type": "Source Control",
        "inputs": {
            "username": "git-user",
            "password": "git-token-placeholder",
        },
    },
    {
        "name": "MigrateMe Vault Credential",
        "description": "Ansible Vault password",
        "organization": "MigrateMe-Corp",
        "credential_type": "Vault",
        "inputs": {
            "vault_password": "vault-secret-123",
        },
    },
    {
        "name": "Ops Machine Credential",
        "description": "SSH credential for operations hosts",
        "organization": "MigrateMe-Ops",
        "credential_type": "Machine",
        "inputs": {
            "username": "ops-user",
            "password": "ops-pass-123",
            "become_method": "sudo",
            "become_username": "root",
        },
    },
    {
        "name": "MigrateMe API Token",
        "description": "Sample custom credential",
        "organization": "MigrateMe-Corp",
        "credential_type": "API Token",  # custom type
        "inputs": {
            "api_url": "https://api.example.com/v1",
            "api_token": "sample-token-abc123",
        },
    },
]

PROJECTS = [
    {
        "name": "MigrateMe Sample Playbooks",
        "description": "Public sample playbooks for migration testing",
        "organization": "MigrateMe-Corp",
        "scm_type": "git",
        "scm_url": "https://github.com/ansible/ansible-tower-samples.git",
        "scm_branch": "master",
        "scm_update_on_launch": False,
    },
    {
        "name": "Ops Automation Playbooks",
        "description": "Operational automation playbooks",
        "organization": "MigrateMe-Ops",
        "scm_type": "git",
        "scm_url": "https://github.com/ansible/ansible-examples.git",
        "scm_branch": "master",
        "scm_update_on_launch": False,
    },
]

INVENTORIES = [
    {
        "name": "MigrateMe Dev Inventory",
        "description": "Development environment hosts",
        "organization": "MigrateMe-Corp",
        "hosts": [
            {"name": "dev-web-01.lab.local", "variables": {"http_port": 8080, "env": "dev"}},
            {"name": "dev-web-02.lab.local", "variables": {"http_port": 8080, "env": "dev"}},
            {"name": "dev-db-01.lab.local", "variables": {"db_port": 5432, "env": "dev"}},
        ],
        "groups": [
            {
                "name": "webservers",
                "description": "Web server group",
                "variables": {"nginx_version": "1.24"},
                "hosts": ["dev-web-01.lab.local", "dev-web-02.lab.local"],
            },
            {
                "name": "databases",
                "description": "Database server group",
                "variables": {"postgres_version": "15"},
                "hosts": ["dev-db-01.lab.local"],
            },
        ],
    },
    {
        "name": "MigrateMe Prod Inventory",
        "description": "Production environment hosts",
        "organization": "MigrateMe-Corp",
        "hosts": [
            {"name": "prod-web-01.lab.local", "variables": {"http_port": 80, "env": "prod"}},
            {"name": "prod-web-02.lab.local", "variables": {"http_port": 80, "env": "prod"}},
            {"name": "prod-web-03.lab.local", "variables": {"http_port": 80, "env": "prod"}},
            {"name": "prod-db-01.lab.local", "variables": {"db_port": 5432, "env": "prod"}},
            {"name": "prod-db-02.lab.local", "variables": {"db_port": 5432, "env": "prod"}},
        ],
        "groups": [
            {
                "name": "webservers",
                "description": "Production web servers",
                "variables": {"nginx_version": "1.24"},
                "hosts": [
                    "prod-web-01.lab.local",
                    "prod-web-02.lab.local",
                    "prod-web-03.lab.local",
                ],
            },
            {
                "name": "databases",
                "description": "Production database servers",
                "variables": {"postgres_version": "15"},
                "hosts": ["prod-db-01.lab.local", "prod-db-02.lab.local"],
            },
        ],
    },
    {
        "name": "Ops Network Inventory",
        "description": "Network infrastructure hosts",
        "organization": "MigrateMe-Ops",
        "hosts": [
            {"name": "switch-core-01.lab.local", "variables": {"device_type": "switch"}},
            {"name": "router-gw-01.lab.local", "variables": {"device_type": "router"}},
            {"name": "fw-perimeter-01.lab.local", "variables": {"device_type": "firewall"}},
        ],
        "groups": [
            {
                "name": "network_devices",
                "description": "All network devices",
                "hosts": [
                    "switch-core-01.lab.local",
                    "router-gw-01.lab.local",
                    "fw-perimeter-01.lab.local",
                ],
            },
        ],
    },
]

JOB_TEMPLATES = [
    {
        "name": "MigrateMe - Hello World",
        "description": "Simple hello world playbook for testing",
        "organization": "MigrateMe-Corp",
        "project": "MigrateMe Sample Playbooks",
        "inventory": "MigrateMe Dev Inventory",
        "playbook": "hello_world.yml",
        "credentials": ["MigrateMe Machine Credential"],
        "verbosity": 0,
        "ask_variables_on_launch": False,
    },
    {
        "name": "MigrateMe - Deploy App (Dev)",
        "description": "Deploy application to development environment",
        "organization": "MigrateMe-Corp",
        "project": "MigrateMe Sample Playbooks",
        "inventory": "MigrateMe Dev Inventory",
        "playbook": "hello_world.yml",
        "credentials": ["MigrateMe Machine Credential"],
        "verbosity": 1,
        "ask_variables_on_launch": True,
        "extra_vars": json.dumps({"app_version": "latest", "rolling_update": True}),
        "job_tags": "deploy,verify",
    },
    {
        "name": "MigrateMe - Deploy App (Prod)",
        "description": "Deploy application to production environment",
        "organization": "MigrateMe-Corp",
        "project": "MigrateMe Sample Playbooks",
        "inventory": "MigrateMe Prod Inventory",
        "playbook": "hello_world.yml",
        "credentials": ["MigrateMe Machine Credential", "MigrateMe Vault Credential"],
        "verbosity": 0,
        "ask_variables_on_launch": True,
        "extra_vars": json.dumps({"app_version": "stable", "rolling_update": True}),
        "limit": "webservers",
    },
    {
        "name": "MigrateMe - DB Backup",
        "description": "Backup databases",
        "organization": "MigrateMe-Corp",
        "project": "MigrateMe Sample Playbooks",
        "inventory": "MigrateMe Prod Inventory",
        "playbook": "hello_world.yml",
        "credentials": ["MigrateMe Machine Credential"],
        "verbosity": 0,
        "limit": "databases",
    },
    {
        "name": "Ops - Network Audit",
        "description": "Run network compliance audit",
        "organization": "MigrateMe-Ops",
        "project": "Ops Automation Playbooks",
        "inventory": "Ops Network Inventory",
        "playbook": "lamp_simple/site.yml",
        "credentials": ["Ops Machine Credential"],
        "verbosity": 2,
    },
]

WORKFLOW_JOB_TEMPLATES = [
    {
        "name": "MigrateMe - Full Deploy Pipeline",
        "description": "End-to-end deployment: backup -> deploy dev -> deploy prod",
        "organization": "MigrateMe-Corp",
        "nodes": [
            {
                "identifier": "backup_db",
                "job_template": "MigrateMe - DB Backup",
                "success_nodes": ["deploy_dev"],
                "failure_nodes": [],
                "always_nodes": [],
            },
            {
                "identifier": "deploy_dev",
                "job_template": "MigrateMe - Deploy App (Dev)",
                "success_nodes": ["deploy_prod"],
                "failure_nodes": [],
                "always_nodes": [],
            },
            {
                "identifier": "deploy_prod",
                "job_template": "MigrateMe - Deploy App (Prod)",
                "success_nodes": [],
                "failure_nodes": [],
                "always_nodes": [],
            },
        ],
    },
]


class AWXPopulator:
    """Create AWX objects via the /api/v2/ REST API."""

    def __init__(self, session: requests.Session):
        self.session = session
        # Caches: name -> id
        self.org_ids: Dict[str, int] = {}
        self.cred_type_ids: Dict[str, int] = {}
        self.cred_ids: Dict[str, int] = {}
        self.project_ids: Dict[str, int] = {}
        self.inventory_ids: Dict[str, int] = {}
        self.host_ids: Dict[str, int] = {}      # "inv_name/host_name" -> id
        self.group_ids: Dict[str, int] = {}      # "inv_name/group_name" -> id
        self.team_ids: Dict[str, int] = {}   # "org/team" -> id
        self.user_ids: Dict[str, int] = {}   # username -> id
        self.jt_ids: Dict[str, int] = {}
        self.wfjt_ids: Dict[str, int] = {}
        self.stats: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    def _get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.get(url, params=params, verify=False)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.post(url, json=payload, verify=False)
        if resp.status_code == 400:
            print(f"         400 response: {resp.text}")
        resp.raise_for_status()
        return resp.json()

    def _post_no_body(self, endpoint: str, payload: dict) -> Optional[dict]:
        """POST that may return 204 No Content."""
        url = f"{API_BASE}/{endpoint.lstrip('/')}"
        resp = self.session.post(url, json=payload, verify=False)
        if resp.status_code == 400:
            print(f"         400 response: {resp.text}")
        resp.raise_for_status()
        if resp.status_code == 204 or not resp.text:
            return None
        return resp.json()

    def _find_by_name(self, endpoint: str, name: str) -> Optional[dict]:
        """Look up an existing object by name."""
        data = self._get(endpoint, params={"name": name})
        results = data.get("results", [])
        return results[0] if results else None

    def _ensure(self, endpoint: str, name: str, payload: dict) -> dict:
        """Create if missing, otherwise return existing object."""
        existing = self._find_by_name(endpoint, name)
        if existing:
            print(f"         (already exists, id={existing['id']})")
            return existing
        return self._post(endpoint, payload)

    # ------------------------------------------------------------------
    # Object creators – called in dependency order
    # ------------------------------------------------------------------

    def create_organizations(self, orgs: List[dict]):
        print("\n[1/10] Creating Organizations...")
        for org in orgs:
            name = org["name"]
            print(f"   -> {name}")
            result = self._ensure("organizations/", name, org)
            self.org_ids[name] = result["id"]
        self.stats["organizations"] = len(orgs)

    def _find_by_username(self, username: str) -> Optional[dict]:
        """Look up a user by username."""
        data = self._get("users/", params={"username": username})
        results = data.get("results", [])
        return results[0] if results else None

    def create_teams(self, teams: List[dict]):
        print("\n[2/10] Creating Teams...")
        for team in teams:
            name = team["name"]
            org_name = team["organization"]
            cache_key = f"{org_name}/{name}"
            print(f"   -> {name} (org: {org_name})")

            payload = {
                "name": name,
                "description": team.get("description", ""),
                "organization": self.org_ids[org_name],
            }
            result = self._ensure("teams/", name, payload)
            self.team_ids[cache_key] = result["id"]
        self.stats["teams"] = len(teams)

    def create_users(self, users: List[dict]):
        print("\n[3/10] Creating Users...")
        for user in users:
            username = user["username"]
            org_name = user["organization"]
            print(f"   -> {username} ({user['first_name']} {user['last_name']}, org: {org_name})")

            existing = self._find_by_username(username)
            if existing:
                print(f"         (already exists, id={existing['id']})")
                user_id = existing["id"]
            else:
                payload = {
                    "username": username,
                    "first_name": user["first_name"],
                    "last_name": user["last_name"],
                    "email": user["email"],
                    "password": user["password"],
                    "is_superuser": False,
                }
                result = self._post("users/", payload)
                user_id = result["id"]

            self.user_ids[username] = user_id

            # Associate user with organization (member role)
            org_id = self.org_ids[org_name]
            try:
                self._post_no_body(f"organizations/{org_id}/users/", {"id": user_id})
            except requests.exceptions.HTTPError:
                pass  # already a member

            # Associate user with teams
            for team_name in user.get("teams", []):
                cache_key = f"{org_name}/{team_name}"
                team_id = self.team_ids.get(cache_key)
                if team_id:
                    try:
                        self._post_no_body(f"teams/{team_id}/users/", {"id": user_id})
                    except requests.exceptions.HTTPError:
                        pass  # already a member

        self.stats["users"] = len(users)

    def assign_team_roles(self, role_assignments: List[dict]):
        """Grant teams specific roles on AWX objects (RBAC)."""
        print("\n[10/10] Assigning Team Roles (RBAC)...")

        # Map object_type -> name cache
        object_caches = {
            "job_templates": self.jt_ids,
            "workflow_job_templates": self.wfjt_ids,
            "inventories": self.inventory_ids,
            "projects": self.project_ids,
            "credentials": self.cred_ids,
        }

        assigned = 0
        for ra in role_assignments:
            team_name = ra["team"]
            obj_type = ra["object_type"]
            obj_name = ra["object_name"]
            role_field = ra["role_field"]

            cache = object_caches.get(obj_type, {})
            obj_id = cache.get(obj_name)
            if not obj_id:
                print(f"   WARNING: {obj_type} '{obj_name}' not found, skipping")
                continue

            # Look up the team id — try both orgs
            team_id = None
            for key, tid in self.team_ids.items():
                if key.endswith(f"/{team_name}"):
                    team_id = tid
                    break
            if not team_id:
                print(f"   WARNING: team '{team_name}' not found, skipping")
                continue

            # Get the object to find its role IDs from summary_fields.object_roles
            obj_detail = self._get(f"{obj_type}/{obj_id}/")
            object_roles = obj_detail.get("summary_fields", {}).get("object_roles", {})
            role_info = object_roles.get(role_field)
            if not role_info:
                print(f"   WARNING: role '{role_field}' not found on {obj_type} '{obj_name}'")
                continue

            role_id = role_info["id"]
            role_label = role_info.get("name", role_field)
            print(f"   -> {team_name:.<22} {role_label:.<16} on {obj_name}")

            try:
                self._post_no_body(f"roles/{role_id}/teams/", {"id": team_id})
                assigned += 1
            except requests.exceptions.HTTPError:
                pass  # already assigned

        self.stats["role_assignments"] = assigned

    def create_credential_types(self, cred_types: List[dict]):
        print("\n[4/10] Creating Custom Credential Types...")
        if not cred_types:
            print("   (none defined)")
            return
        for ct in cred_types:
            name = ct["name"]
            print(f"   -> {name}")
            result = self._ensure("credential_types/", name, ct)
            self.cred_type_ids[name] = result["id"]
        self.stats["credential_types"] = len(cred_types)

    def _resolve_credential_type_id(self, type_name: str) -> int:
        """Resolve a credential type name to its ID (built-in or custom)."""
        # Check custom types first
        if type_name in self.cred_type_ids:
            return self.cred_type_ids[type_name]

        # Search built-in types
        existing = self._find_by_name("credential_types/", type_name)
        if existing:
            self.cred_type_ids[type_name] = existing["id"]
            return existing["id"]

        raise ValueError(f"Credential type '{type_name}' not found")

    def create_credentials(self, credentials: List[dict]):
        print("\n[5/10] Creating Credentials...")
        for cred in credentials:
            name = cred["name"]
            org_name = cred["organization"]
            type_name = cred["credential_type"]
            print(f"   -> {name} (type: {type_name}, org: {org_name})")

            payload = {
                "name": name,
                "description": cred.get("description", ""),
                "organization": self.org_ids[org_name],
                "credential_type": self._resolve_credential_type_id(type_name),
                "inputs": cred.get("inputs", {}),
            }
            result = self._ensure("credentials/", name, payload)
            self.cred_ids[name] = result["id"]
        self.stats["credentials"] = len(credentials)

    def create_projects(self, projects: List[dict]):
        print("\n[6/10] Creating Projects...")
        for proj in projects:
            name = proj["name"]
            org_name = proj["organization"]
            print(f"   -> {name} (org: {org_name})")

            payload = {
                "name": name,
                "description": proj.get("description", ""),
                "organization": self.org_ids[org_name],
                "scm_type": proj.get("scm_type", "git"),
                "scm_url": proj["scm_url"],
                "scm_branch": proj.get("scm_branch", "main"),
                "scm_update_on_launch": proj.get("scm_update_on_launch", False),
            }
            # Attach SCM credential if specified
            if proj.get("credential"):
                payload["credential"] = self.cred_ids[proj["credential"]]

            result = self._ensure("projects/", name, payload)
            self.project_ids[name] = result["id"]
        self.stats["projects"] = len(projects)

        # Wait for project sync to finish so playbook lists are available
        self._wait_for_project_syncs()

    def _wait_for_project_syncs(self, timeout: int = 120):
        """Wait until every project reaches 'successful' or 'failed' status."""
        print("   Waiting for project sync...")
        deadline = time.time() + timeout
        pending = set(self.project_ids.values())

        while pending and time.time() < deadline:
            still_pending = set()
            for pid in pending:
                proj = self._get(f"projects/{pid}/")
                status = proj.get("status", "unknown")
                if status in ("pending", "waiting", "running", "new"):
                    still_pending.add(pid)
                elif status == "successful":
                    print(f"      Project {proj['name']} synced OK")
                else:
                    print(f"      Project {proj['name']} sync status: {status}")
            pending = still_pending
            if pending:
                time.sleep(3)

        if pending:
            print(f"   WARNING: {len(pending)} project(s) did not finish syncing within {timeout}s")

    def create_inventories(self, inventories: List[dict]):
        print("\n[7/10] Creating Inventories...")
        for inv in inventories:
            name = inv["name"]
            org_name = inv["organization"]
            print(f"   -> {name} (org: {org_name})")

            payload = {
                "name": name,
                "description": inv.get("description", ""),
                "organization": self.org_ids[org_name],
            }
            if inv.get("variables"):
                payload["variables"] = json.dumps(inv["variables"])

            result = self._ensure("inventories/", name, payload)
            inv_id = result["id"]
            self.inventory_ids[name] = inv_id

            # Create hosts
            for host_def in inv.get("hosts", []):
                self._create_host(inv_id, name, host_def)

            # Create groups and assign hosts
            for group_def in inv.get("groups", []):
                self._create_group(inv_id, name, group_def)

        self.stats["inventories"] = len(inventories)

    def _create_host(self, inv_id: int, inv_name: str, host_def: dict):
        host_name = host_def["name"]
        cache_key = f"{inv_name}/{host_name}"
        print(f"      host: {host_name}")

        payload: Dict[str, Any] = {"name": host_name}
        if host_def.get("variables"):
            payload["variables"] = json.dumps(host_def["variables"])

        result = self._ensure(f"inventories/{inv_id}/hosts/", host_name, payload)
        self.host_ids[cache_key] = result["id"]
        self.stats["hosts"] = self.stats.get("hosts", 0) + 1

    def _create_group(self, inv_id: int, inv_name: str, group_def: dict):
        group_name = group_def["name"]
        cache_key = f"{inv_name}/{group_name}"
        print(f"      group: {group_name}")

        payload: Dict[str, Any] = {
            "name": group_name,
            "description": group_def.get("description", ""),
        }
        if group_def.get("variables"):
            payload["variables"] = json.dumps(group_def["variables"])

        result = self._ensure(f"inventories/{inv_id}/groups/", group_name, payload)
        group_id = result["id"]
        self.group_ids[cache_key] = group_id
        self.stats["groups"] = self.stats.get("groups", 0) + 1

        # Associate hosts to the group
        for host_name in group_def.get("hosts", []):
            host_cache_key = f"{inv_name}/{host_name}"
            host_id = self.host_ids.get(host_cache_key)
            if host_id:
                self._post_no_body(
                    f"groups/{group_id}/hosts/",
                    {"id": host_id},
                )

    def create_job_templates(self, templates: List[dict]):
        print("\n[8/10] Creating Job Templates...")
        for jt in templates:
            name = jt["name"]
            project_name = jt["project"]
            inv_name = jt["inventory"]
            print(f"   -> {name}")

            payload: Dict[str, Any] = {
                "name": name,
                "description": jt.get("description", ""),
                "job_type": "run",
                "project": self.project_ids[project_name],
                "inventory": self.inventory_ids[inv_name],
                "playbook": jt["playbook"],
                "verbosity": jt.get("verbosity", 0),
                "ask_variables_on_launch": jt.get("ask_variables_on_launch", False),
            }
            if jt.get("extra_vars"):
                payload["extra_vars"] = jt["extra_vars"]
            if jt.get("limit"):
                payload["limit"] = jt["limit"]
            if jt.get("job_tags"):
                payload["job_tags"] = jt["job_tags"]

            result = self._ensure("job_templates/", name, payload)
            jt_id = result["id"]
            self.jt_ids[name] = jt_id

            # Associate credentials
            for cred_name in jt.get("credentials", []):
                cred_id = self.cred_ids.get(cred_name)
                if cred_id:
                    try:
                        self._post_no_body(
                            f"job_templates/{jt_id}/credentials/",
                            {"id": cred_id},
                        )
                    except requests.exceptions.HTTPError:
                        pass  # already associated

        self.stats["job_templates"] = len(templates)

    def create_workflow_job_templates(self, workflows: List[dict]):
        print("\n[9/10] Creating Workflow Job Templates...")
        for wf in workflows:
            name = wf["name"]
            org_name = wf["organization"]
            print(f"   -> {name}")

            payload = {
                "name": name,
                "description": wf.get("description", ""),
                "organization": self.org_ids[org_name],
            }
            result = self._ensure("workflow_job_templates/", name, payload)
            wfjt_id = result["id"]
            self.wfjt_ids[name] = wfjt_id

            # Create workflow nodes
            node_id_map: Dict[str, int] = {}  # identifier -> AWX node id

            # First pass: create all nodes
            for node_def in wf.get("nodes", []):
                identifier = node_def["identifier"]
                jt_name = node_def["job_template"]
                jt_id = self.jt_ids.get(jt_name)
                if not jt_id:
                    print(f"      WARNING: job template '{jt_name}' not found, skipping node")
                    continue

                node_payload = {"unified_job_template": jt_id}
                # Check if node already exists (by unified_job_template)
                existing_nodes = self._get(
                    f"workflow_job_templates/{wfjt_id}/workflow_nodes/"
                )
                existing_node = None
                for en in existing_nodes.get("results", []):
                    if en.get("unified_job_template") == jt_id:
                        existing_node = en
                        break

                if existing_node:
                    print(f"      node: {identifier} (already exists, id={existing_node['id']})")
                    node_id_map[identifier] = existing_node["id"]
                else:
                    print(f"      node: {identifier} -> {jt_name}")
                    node_result = self._post(
                        f"workflow_job_templates/{wfjt_id}/workflow_nodes/",
                        node_payload,
                    )
                    node_id_map[identifier] = node_result["id"]

            # Second pass: wire up edges (success/failure/always)
            for node_def in wf.get("nodes", []):
                identifier = node_def["identifier"]
                source_node_id = node_id_map.get(identifier)
                if not source_node_id:
                    continue

                for edge_type in ("success_nodes", "failure_nodes", "always_nodes"):
                    for target_identifier in node_def.get(edge_type, []):
                        target_node_id = node_id_map.get(target_identifier)
                        if target_node_id:
                            try:
                                self._post_no_body(
                                    f"workflow_job_template_nodes/{source_node_id}/{edge_type}/",
                                    {"id": target_node_id},
                                )
                            except requests.exceptions.HTTPError:
                                pass  # edge already exists

        self.stats["workflow_job_templates"] = len(workflows)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def print_summary(self):
        print("\n" + "=" * 60)
        print(" Populate Summary")
        print("=" * 60)
        for asset_type, count in sorted(self.stats.items()):
            print(f"   {asset_type.replace('_', ' ').title():.<40} {count}")
        print("=" * 60)


# ======================================================================
# Main
# ======================================================================

def main() -> int:
    print("=" * 60)
    print(" AWX Asset Populator")
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
        print("Make sure the AWX host is reachable and the URL is correct.")
        return 1
    except requests.exceptions.HTTPError as e:
        print(f"\nERROR: AWX returned {e.response.status_code}")
        print("Check your credentials.")
        return 1

    populator = AWXPopulator(session)

    try:
        populator.create_organizations(ORGANIZATIONS)
        populator.create_teams(TEAMS)
        populator.create_users(USERS)
        populator.create_credential_types(CUSTOM_CREDENTIAL_TYPES)
        populator.create_credentials(CREDENTIALS)
        populator.create_projects(PROJECTS)
        populator.create_inventories(INVENTORIES)
        populator.create_job_templates(JOB_TEMPLATES)
        populator.create_workflow_job_templates(WORKFLOW_JOB_TEMPLATES)
        populator.assign_team_roles(TEAM_ROLES)

        print("\nDone!")
        populator.print_summary()
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
