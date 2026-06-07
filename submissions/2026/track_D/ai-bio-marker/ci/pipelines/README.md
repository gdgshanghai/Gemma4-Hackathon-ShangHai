# CI/CD Pipeline — Tekton / GitHub Actions placeholder.
#
# Pipeline stages:
#   1. Lint (golangci-lint, pylint, buf lint)
#   2. Test (unit + integration)
#   3. Build (OCI images — podman/docker)
#   4. Scan (Trivy / Grype vulnerability + SBOM)
#   5. Sign (cosign)
#   6. Render Kustomize manifests
#   7. Push images + manifests to registry
#
# Replace with actual pipeline definition when CI system is chosen.
