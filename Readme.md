# AAP CAC Sample

Populates AAP with the following API resources. 

  Common resources (orgs, teams, users, credential types) are applied once regardless of environment. 
  Environment-specific resources (credentials, projects, inventories, job templates, workflows) change based on -e env=dev|prod

aap-cac/
  ├── ansible.cfg
  ├── collections/requirements.yml       
  ├── playbooks/
  │   └── configure-aap.yaml             
  ├── vars/
  │   ├── auth.yaml                      
  │   ├── common/                        
  │   │   ├── organizations.yaml         
  │   │   ├── teams.yaml                 
  │   │   ├── users.yaml                 
  │   │   └── credential_types.yaml      
  │   ├── dev/                           
  │   │   ├── credentials.yaml           
  │   │   ├── projects.yaml              
  │   │   ├── inventories.yaml           
  │   │   └── job_templates.yaml         
  │   └── prod/                          
  │       ├── credentials.yaml           
  │       ├── projects.yaml              
  │       ├── inventories.yaml           
  │       └── job_templates.yaml         