FROM registry.redhat.io/ansible-automation-platform-26/ee-supported-rhel9:latest

USER root

# Copy ansible.cfg for Automation Hub + Galaxy access during build
COPY ansible.cfg /etc/ansible/ansible.cfg

# Install extra collections not in the supported EE
COPY requirements.yml /tmp/requirements.yml
RUN ANSIBLE_GALAXY_DISABLE_GPG_VERIFY=1 \
    ansible-galaxy collection install -r /tmp/requirements.yml \
      --collections-path /usr/share/ansible/collections && \
    rm -f /tmp/requirements.yml

# Clean up ansible.cfg (contains tokens)
RUN rm -f /etc/ansible/ansible.cfg

USER 1000
