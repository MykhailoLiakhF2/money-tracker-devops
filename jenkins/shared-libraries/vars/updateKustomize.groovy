// =============================================================================
// updateKustomize — Update image tags + commit & push (GitOps)
// =============================================================================
// Usage in Jenkinsfile:
//   updateKustomize(
//     overlay:       'k8s/overlays/prod',
//     images:        [
//       'BACKEND_IMAGE':  "${REGISTRY}/money-talks-backend:${GIT_COMMIT}",
//       'FRONTEND_IMAGE': "${REGISTRY}/money-talks-frontend:${GIT_COMMIT}"
//     ],
//     credentialsId: 'github-pat',
//     repoUrl:       'https://github.com/YOUR_GITHUB_USERNAME/money-tracker-app.git'
//   )
//
// WHY this exists:
//   Jenkins (CI) builds images. ArgoCD (CD) watches Git for changes.
//   This function is the BRIDGE: it updates image tags in kustomization.yaml
//   and pushes the change to Git. ArgoCD detects the new commit → syncs.
//
//   This pattern is called "image tag promotion via Git commit".
//   Without the push, changes die with the ephemeral pod agent.
//
// INTERVIEW NOTE:
//   "[skip ci]" in the commit message prevents infinite loops:
//   push → webhook → Jenkins build → push → webhook → ... forever
//   Jenkins checks for this marker and skips the build if found.
// =============================================================================

def call(Map config) {
    // -------------------------------------------------------------------------
    // 1. Validate required parameters
    // -------------------------------------------------------------------------
    if (!config.overlay) {
        error "updateKustomize: missing 'overlay' (e.g. 'k8s/overlays/prod')"
    }
    if (!config.images || config.images.isEmpty()) {
        error "updateKustomize: 'images' map is required and cannot be empty"
    }
    if (!config.credentialsId) {
        error "updateKustomize: missing 'credentialsId' for git push"
    }
    if (!config.repoUrl) {
        error "updateKustomize: missing 'repoUrl' for git push"
    }

    // -------------------------------------------------------------------------
    // 2. Extract parameters
    // -------------------------------------------------------------------------
    def overlay       = config.overlay
    def images        = config.images
    def containerName = config.container ?: 'tools'
    def credentialsId = config.credentialsId
    def repoUrl       = config.repoUrl
    def branch        = config.branch ?: 'main'  // Default: main (backward compatible)

    // -------------------------------------------------------------------------
    // 3. Build kustomize image arguments
    //    Example result:
    //    "BACKEND_IMAGE=registry/backend:abc123 FRONTEND_IMAGE=registry/frontend:abc123"
    // -------------------------------------------------------------------------
    def imageArgs = images.collect { placeholder, fullImage ->
        "${placeholder}=${fullImage}"
    }.join(' ')

    // -------------------------------------------------------------------------
    // 4. Update kustomization.yaml + git commit + push
    //
    //    withCredentials injects:
    //      GIT_USERNAME = GitHub username
    //      GIT_PASSWORD = GitHub PAT (the actual token)
    //
    //    git diff --cached --quiet:
    //      Exit code 0 = nothing changed (idempotent — same image tag)
    //      Exit code 1 = there are staged changes → proceed with commit
    //
    //    The push URL embeds credentials:
    //      https://username:token@github.com/user/repo.git
    //      This avoids interactive auth prompts in headless CI environments.
    //
    //    SECURITY: credentials are masked in Jenkins logs automatically
    //    because withCredentials marks them as sensitive.
    // -------------------------------------------------------------------------
    container(containerName) {
        withCredentials([usernamePassword(
            credentialsId: credentialsId,
            usernameVariable: 'GIT_USERNAME',
            passwordVariable: 'GIT_PASSWORD'
        )]) {
            sh """
                set -e

                # --- Step 1: Update image tags ---
                cd ${overlay}
                kustomize edit set image ${imageArgs}
                echo "=== Updated kustomization.yaml ==="
                cat kustomization.yaml

                # --- Step 2: Configure git identity ---
                # safe.directory: Git 2.35.2+ blocks operations in directories
                # owned by a different user. The jnlp container clones as one
                # UID, but the tools container runs as another. This is expected
                # in multi-container pod agents — not a security risk here.
                cd \${WORKSPACE}
                git config --global --add safe.directory \${WORKSPACE}
                git config user.name "Jenkins CI"
                git config user.email "jenkins@your-domain.com"

                # --- Step 3: Stage the change ---
                git add ${overlay}/kustomization.yaml

                # --- Step 4: Commit only if something changed ---
                if git diff --cached --quiet; then
                    echo "No changes to commit — image tags already up to date"
                else
                    git commit -m "ci: update image tags to \$(echo ${imageArgs} | head -1 | sed 's/.*://') [skip ci]"

                    # --- Step 5: Push to GitHub ---
                    git push https://\${GIT_USERNAME}:\${GIT_PASSWORD}@github.com/YOUR_GITHUB_USERNAME/money-tracker-app.git HEAD:${branch}
                    echo "✅ Pushed updated tags to GitHub"
                fi
            """
        }
    }
}

// REQUIRED for 'load' — returns this Script object so Jenkinsfile can call()
return this
