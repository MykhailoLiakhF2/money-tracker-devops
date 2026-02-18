// =============================================================================
// buildKaniko — Build & push Docker image via Kaniko (no Docker daemon needed)
// =============================================================================
// Usage in Jenkinsfile:
//   buildKaniko(
//     containerName: 'kaniko-backend',
//     image:         "${REGISTRY}/money-talks-backend",
//     tag:           GIT_COMMIT,
//     dockerfile:    'backend/Dockerfile',
//     context:       'backend'
//   )
// =============================================================================

def call(Map config) {
    // -------------------------------------------------------------------------
    // 1. Validate required parameters
    //    Groovy Maps return null for missing keys — we fail fast if something
    //    is missing rather than getting a cryptic Kaniko error later.
    // -------------------------------------------------------------------------
    def required = ['containerName', 'image', 'tag', 'dockerfile', 'context']
    required.each { param ->
        if (!config[param]) {
            error "buildKaniko: missing required parameter '${param}'"
        }
    }

    // -------------------------------------------------------------------------
    // 2. Extract parameters with defaults (Elvis operator ?:)
    //    config.cache ?: true  → if config.cache is null/false → use true
    // -------------------------------------------------------------------------
    def containerName = config.containerName
    def image         = config.image
    def tag           = config.tag
    def dockerfile    = config.dockerfile
    def context       = config.context
    def useCache      = config.cache ?: true          // default: caching ON
    def extraTags     = config.extraTags ?: ['latest'] // default: also tag as 'latest'

    // -------------------------------------------------------------------------
    // 3. Build destination flags
    //    Primary: image:tag (e.g. registry/backend:abc1234)
    //    Extra:   image:latest (or whatever extraTags contains)
    // -------------------------------------------------------------------------
    def destinations = "--destination=${image}:${tag}"
    extraTags.each { extraTag ->
        destinations += " --destination=${image}:${extraTag}"
    }

    // -------------------------------------------------------------------------
    // 4. Cache flags (only if caching enabled)
    //    Cache repo = image name + "-cache" suffix
    //    This stores layer cache in Artifact Registry for faster rebuilds
    // -------------------------------------------------------------------------
    def cacheFlags = ''
    if (useCache) {
        cacheFlags = "--cache=true --cache-repo=${image}-cache"
    }

    // -------------------------------------------------------------------------
    // 5. Execute Kaniko inside the named container
    //    container() — Jenkins K8s plugin step: runs commands in specific
    //    container of the pod (not the default jnlp container)
    //
    //    WORKSPACE — Jenkins built-in env var, path to checked-out code
    // -------------------------------------------------------------------------
    container(containerName) {
        sh """
            /kaniko/executor \
                --dockerfile=${dockerfile} \
                --context=dir://\${WORKSPACE}/${context} \
                ${destinations} \
                ${cacheFlags} \
                --snapshot-mode=redo \
                --compressed-caching=false
        """
    }
}

// REQUIRED for 'load' — returns this Script object so Jenkinsfile can call()
return this
