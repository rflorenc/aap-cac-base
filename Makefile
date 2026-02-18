AUTH_FILE   ?= vars/auth.yaml
VAULT_FILE  ?= .vault-password

VAULT_FILES = vars/auth.yaml vars/dev/credentials.yaml vars/dev/ssh_keys.yaml vars/prod/credentials.yaml

.PHONY: configure-dev configure-prod teardown-dev teardown-prod clean-aap encrypt decrypt

configure-dev:
	ansible-playbook playbooks/configure-aap-controller.yaml \
	  -e @$(AUTH_FILE) -e env=dev --vault-password-file $(VAULT_FILE)

configure-prod:
	ansible-playbook playbooks/configure-aap-controller.yaml \
	  -e @$(AUTH_FILE) -e env=prod --vault-password-file $(VAULT_FILE)

teardown-dev:
	ansible-playbook playbooks/teardown-aap-controller.yaml \
	  -e @$(AUTH_FILE) -e env=dev --vault-password-file $(VAULT_FILE)

teardown-prod:
	ansible-playbook playbooks/teardown-aap-controller.yaml \
	  -e @$(AUTH_FILE) -e env=prod --vault-password-file $(VAULT_FILE)

clean-aap:
	python3 scripts/cleanup_aap_api_assets.py

encrypt:
	@for f in $(VAULT_FILES); do \
	  if head -1 "$$f" | grep -q '^\$$ANSIBLE_VAULT'; then \
	    echo "$$f already encrypted, skipping"; \
	  else \
	    ansible-vault encrypt "$$f" --vault-password-file $(VAULT_FILE) && echo "$$f encrypted"; \
	  fi; \
	done

decrypt:
	@for f in $(VAULT_FILES); do \
	  if head -1 "$$f" | grep -q '^\$$ANSIBLE_VAULT'; then \
	    ansible-vault decrypt "$$f" --vault-password-file $(VAULT_FILE) && echo "$$f decrypted"; \
	  else \
	    echo "$$f not encrypted, skipping"; \
	  fi; \
	done
