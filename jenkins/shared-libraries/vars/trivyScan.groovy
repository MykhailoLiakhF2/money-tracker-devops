// =============================================================================
// trivyScan.groovy — Trivy vulnerability scanner (shared library)
// =============================================================================
// Scans Docker images for CRITICAL CVEs before deployment.
// If a CRITICAL vulnerability is found → build fails → ArgoCD never sees
// the new image tag → production stays safe.
//
// INTERVIEW NOTE:
//   This is "shift-left security" — catching vulnerabilities in CI, not prod.
//   High-security systems use similar gates: no image reaches production without passing
//   a vulnerability scan. Trivy is open-source (Aqua Security) and scans
//   OS packages + language dependencies (pip, npm, go modules).
//
// Usage in Jenkinsfile:
//   trivyScan(
//       containerName: 'trivy',
//       images: [
//           "registry/backend:tag",
//           "registry/frontend:tag"
//       ],
//       severity: 'CRITICAL'    // optional, default: CRITICAL
//   )
// =============================================================================

def call(Map config = [:]) {
    def containerName = config.containerName ?: 'trivy'
    def images = config.images ?: []
    def severity = config.severity ?: 'CRITICAL'

    if (!images) {
        error "trivyScan: 'images' list is required"
    }

    container(containerName) {
        for (img in images) {
            echo "🔍 Scanning ${img} for ${severity} vulnerabilities..."
            // --exit-code 1 = fail if vulnerabilities found at given severity
            // --no-progress = cleaner CI logs
            // --severity = filter level (CRITICAL, HIGH, MEDIUM, LOW)
            sh """
                trivy image \
                    --exit-code 1 \
                    --no-progress \
                    --severity ${severity} \
                    ${img}
            """
            echo "✅ ${img} — passed security scan"
        }
    }
}

// REQUIRED for 'load' — returns this Script object so Jenkinsfile can call()
return this
