# Artifact signing configuration — placeholder.
#
# Tool: cosign (Sigstore).
#
# Policy:
#   - Sign every OCI image with the CI key pair.
#   - Verify signatures via OKD admission policy before deployment.
#   - Reject unsigned images at the cluster boundary.
#
# Key management: CI key stored in cluster secret store; never in Git.
