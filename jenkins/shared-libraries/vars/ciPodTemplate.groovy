// =============================================================================
// ciPodTemplate — Generate Kubernetes pod YAML for CI agent
// =============================================================================
// Usage in Jenkinsfile:
//   agent {
//     kubernetes {
//       yaml ciPodTemplate(
//         gcpSecretName: 'jenkins-gcp-sa',
//         containers: ['python', 'kaniko-backend', 'kaniko-frontend', 'tools']
//       )
//     }
//   }
//
// WHY this exists:
//   Pod template is ~60 lines of YAML that's identical across pipelines.
//   Extracting it means: one place to tune resource requests, add sidecars,
//   change base images, or add security contexts (Phase 4).
//   In production systems (hundreds of services), this is critical — platform team
//   controls pod templates centrally, service teams just reference them.
// =============================================================================

def call(Map config = [:]) {
    // -------------------------------------------------------------------------
    // 1. Parameters with defaults
    // -------------------------------------------------------------------------
    def gcpSecretName = config.gcpSecretName ?: 'jenkins-gcp-sa'
    def pythonImage   = config.pythonImage ?: 'python:3.12-slim'
    def kanikoImage   = config.kanikoImage ?: 'gcr.io/kaniko-project/executor:debug'
    def toolsImage    = config.toolsImage ?: 'alpine/k8s:1.32.0'

    // -------------------------------------------------------------------------
    // 2. Which containers to include
    //    Default: all four. But a pipeline that only runs tests could pass
    //    containers: ['python'] to skip Kaniko entirely (saves resources).
    //
    //    .contains() — Java List method, returns boolean
    // -------------------------------------------------------------------------
    def containers = config.containers ?: ['python', 'kaniko-backend', 'kaniko-frontend', 'tools']

    // -------------------------------------------------------------------------
    // 3. Build YAML string
    //    Triple-quoted GString (""") — multi-line string with interpolation
    //    We conditionally include container blocks using helper methods below
    // -------------------------------------------------------------------------
    def yaml = """
        apiVersion: v1
        kind: Pod
        metadata:
          labels:
            app: money-tracker-ci
        spec:
          serviceAccountName: jenkins
          containers:
${containerPython(pythonImage, containers)}${containerKaniko('kaniko-backend', kanikoImage, containers)}${containerKaniko('kaniko-frontend', kanikoImage, containers)}${containerTools(toolsImage, containers)}
          volumes:
          - name: gcp-sa-key
            secret:
              secretName: ${gcpSecretName}
    """

    // -------------------------------------------------------------------------
    // 4. Return the YAML string
    //    stripIndent() — Groovy method that removes common leading whitespace
    //    .trim() — remove trailing newlines
    // -------------------------------------------------------------------------
    return yaml.stripIndent().trim()
}

// =============================================================================
// Private helper methods
// Each returns a YAML snippet or empty string if container not requested.
// Keeping them separate makes it easy to modify one container type
// without touching others.
// =============================================================================

/**
 * Python container for running tests
 */
private String containerPython(String image, List containers) {
    if (!containers.contains('python')) return ''
    return """
          - name: python
            image: ${image}
            command: ['sleep']
            args: ['3600']
            resources:
              requests:
                cpu: 50m
                memory: 128Mi
              limits:
                cpu: 500m
                memory: 512Mi
"""
}

/**
 * Kaniko container for building & pushing Docker images
 * Used for both backend and frontend — name parameter differentiates them
 */
private String containerKaniko(String name, String image, List containers) {
    if (!containers.contains(name)) return ''
    // Backend gets more resources (larger image, more dependencies)
    def memRequest = (name == 'kaniko-backend') ? '256Mi' : '128Mi'
    def memLimit   = (name == 'kaniko-backend') ? '1Gi' : '512Mi'
    def cpuLimit   = (name == 'kaniko-backend') ? '1' : '500m'

    return """
          - name: ${name}
            image: ${image}
            command: ['/busybox/sleep']
            args: ['3600']
            env:
            - name: GOOGLE_APPLICATION_CREDENTIALS
              value: /secret/key.json
            resources:
              requests:
                cpu: 50m
                memory: ${memRequest}
              limits:
                cpu: '${cpuLimit}'
                memory: ${memLimit}
            volumeMounts:
            - name: gcp-sa-key
              mountPath: /secret
              readOnly: true
"""
}

/**
 * Tools container (alpine/k8s) for kustomize, kubectl, git operations
 */
private String containerTools(String image, List containers) {
    if (!containers.contains('tools')) return ''
    return """
          - name: tools
            image: ${image}
            command: ['sleep']
            args: ['3600']
            resources:
              requests:
                cpu: 50m
                memory: 64Mi
              limits:
                cpu: 200m
                memory: 128Mi
"""
}

// REQUIRED for 'load' — returns this Script object so Jenkinsfile can call()
return this
