#!/usr/bin/env bash
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: ${0} <image:tag> [registry]"
  echo "  Example: ${0} ee-migration:v1"
  echo "  Example: ${0} ee-migration:v1 quay.io/myorg"
  exit 1
fi

IMAGE_TAG="${1}"
REGISTRY="${2:-}"

# Verify ansible.cfg exists (needed to pull collections from Automation Hub)
if [ ! -f ansible.cfg ]; then
  echo "ERROR: ansible.cfg not found."
  echo "Copy ansible.cfg.example to ansible.cfg and configure your Automation Hub token."
  exit 1
fi

echo "Building Execution Environment: ${IMAGE_TAG}"
docker build -t "${IMAGE_TAG}" .

if [ -n "${REGISTRY}" ]; then
  FULL_IMAGE="${REGISTRY}/${IMAGE_TAG}"
  echo "Tagging as ${FULL_IMAGE}"
  docker tag "${IMAGE_TAG}" "${FULL_IMAGE}"
  echo "Pushing ${FULL_IMAGE}"
  docker push "${FULL_IMAGE}"
fi

echo "Done. Image available locally as: ${IMAGE_TAG}"
