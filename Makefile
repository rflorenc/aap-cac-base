EE_IMAGE    ?= ee-cac:v1
CONTAINER   ?= docker
AUTH_FILE   ?= vars/auth.yaml
VAULT_FILE  ?= .vault-password

# Proxy settings (optional) — set here or pass via command line:
#   make run-dev HTTP_PROXY=http://proxy.corp:8080
HTTP_PROXY  ?=
HTTPS_PROXY ?=
NO_PROXY    ?=

VAULT_FILES = vars/auth.yaml vars/dev/credentials.yaml vars/prod/credentials.yaml

# Build --senv flags only for non-empty proxy vars
PROXY_FLAGS := $(if $(HTTP_PROXY),--senv HTTP_PROXY=$(HTTP_PROXY)) \
               $(if $(HTTPS_PROXY),--senv HTTPS_PROXY=$(HTTPS_PROXY)) \
               $(if $(NO_PROXY),--senv NO_PROXY=$(NO_PROXY))

.PHONY: build-ee run-dev run-prod clean-aap encrypt decrypt

configure-cac:
	ansible-playbook playbooks/configure-aap-controller.yaml -e @vars/auth.yaml -e env=dev --vault-password-file .vault-password

build-ee:
	cd ee && \
	  HTTP_PROXY=$(HTTP_PROXY) HTTPS_PROXY=$(HTTPS_PROXY) NO_PROXY=$(NO_PROXY) \
	  ./build-ee.sh $(EE_IMAGE)

run-dev:
	ansible-navigator run playbooks/configure-aap.yaml \
	  -i localhost, -m stdout \
	  --eei $(EE_IMAGE) \
	  --eev "$$(pwd):/project" \
	  --co="--network=host" \
	  --ce $(CONTAINER) \
	  -e @$(AUTH_FILE) \
	  -e env=dev \
	  --vault-password-file $(VAULT_FILE) \
	  $(PROXY_FLAGS)

run-prod:
	ansible-navigator run playbooks/configure-aap.yaml \
	  -i localhost, -m stdout \
	  --eei $(EE_IMAGE) \
	  --eev "$$(pwd):/project" \
	  --co="--network=host" \
	  --ce $(CONTAINER) \
	  -e @$(AUTH_FILE) \
	  -e env=prod \
	  --vault-password-file $(VAULT_FILE) \
	  $(PROXY_FLAGS)

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
