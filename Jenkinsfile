// =============================================================================
// Money Tracker — Jenkins CI Pipeline (Shared Libraries)
// =============================================================================
// This Jenkinsfile uses shared library functions from jenkins/shared-libraries/
// loaded via Groovy 'load' step (monorepo pattern).
//
// PRODUCTION NOTE:
//   In production systems, shared libraries live in a SEPARATE Git repo and are
//   configured as Global Libraries in JCasC. The Jenkinsfile would then use:
//     @Library('enterprise-ci-lib') _
//   and all vars/* functions become available without 'load'.
//   We use 'load' here because our library is in the same repo.
// =============================================================================

// -- Constants --
def REGISTRY       = 'REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REGISTRY'
def BACKEND_IMAGE  = 'money-talks-backend'
def FRONTEND_IMAGE = 'money-talks-frontend'
def REPO_URL       = 'https://github.com/YOUR_GITHUB_USERNAME/money-tracker-devops.git'
def GIT_COMMIT     = ''

// -- Shared library references (populated after checkout) --
def buildKaniko
def runPythonTests
def updateKustomize
def trivyScan

pipeline {
    agent {
        kubernetes {
            // -----------------------------------------------------------------
            // Pod template stays inline because agent{} is evaluated BEFORE
            // any stage runs — we can't 'load' a library function yet.
            // With @Library (production), ciPodTemplate() would work here.
            // -----------------------------------------------------------------
            yaml """
                apiVersion: v1
                kind: Pod
                metadata:
                  labels:
                    app: money-tracker-ci
                spec:
                  serviceAccountName: jenkins
                  containers:
                  - name: python
                    image: python:3.12-slim
                    command: ['sleep']
                    args: ['3600']
                    resources:
                      requests:
                        cpu: 10m
                        memory: 128Mi
                      limits:
                        cpu: 500m
                        memory: 512Mi
                  - name: kaniko-backend
                    image: gcr.io/kaniko-project/executor:debug
                    command: ['/busybox/sleep']
                    args: ['3600']
                    env:
                    - name: GOOGLE_APPLICATION_CREDENTIALS
                      value: /secret/key.json
                    resources:
                      requests:
                        cpu: 10m
                        memory: 256Mi
                      limits:
                        cpu: '1'
                        memory: 1Gi
                    volumeMounts:
                    - name: gcp-sa-key
                      mountPath: /secret
                      readOnly: true
                  - name: kaniko-frontend
                    image: gcr.io/kaniko-project/executor:debug
                    command: ['/busybox/sleep']
                    args: ['3600']
                    env:
                    - name: GOOGLE_APPLICATION_CREDENTIALS
                      value: /secret/key.json
                    resources:
                      requests:
                        cpu: 10m
                        memory: 128Mi
                      limits:
                        cpu: 500m
                        memory: 512Mi
                    volumeMounts:
                    - name: gcp-sa-key
                      mountPath: /secret
                      readOnly: true
                  - name: trivy
                    image: aquasec/trivy:latest
                    command: ['sleep']
                    args: ['3600']
                    env:
                    - name: GOOGLE_APPLICATION_CREDENTIALS
                      value: /secret/key.json
                    resources:
                      requests:
                        cpu: 10m
                        memory: 128Mi
                      limits:
                        cpu: 500m
                        memory: 512Mi
                    volumeMounts:
                    - name: gcp-sa-key
                      mountPath: /secret
                      readOnly: true
                  - name: tools
                    image: alpine/k8s:1.32.0
                    command: ['sleep']
                    args: ['3600']
                    resources:
                      requests:
                        cpu: 10m
                        memory: 64Mi
                      limits:
                        cpu: 200m
                        memory: 128Mi
                  volumes:
                  - name: gcp-sa-key
                    secret:
                      secretName: jenkins-gcp-sa
            """
        }
    }

    options {
        timeout(time: 15, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '5'))
    }

    triggers {
        // =====================================================================
        // Automatically run pipeline when GitHub sends a webhook (push event).
        // Jenkins exposes /github-webhook/ endpoint — GitHub POSTs to it.
        // Without this, you'd have to click "Build Now" manually every time.
        //
        // Alternative: pollSCM('H/5 * * * *') — polls every 5 min (wasteful).
        // Webhook = instant + no unnecessary polling. Always prefer webhooks.
        // =====================================================================
        githubPush()
    }

    stages {

        // =====================================================================
        // Stage 0: Skip CI check
        // =====================================================================
        stage('Skip CI Check') {
            steps {
                script {
                    def commitMsg = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    if (commitMsg.contains('[skip ci]')) {
                        currentBuild.description = 'Skipped: [skip ci]'
                        currentBuild.result = 'NOT_BUILT'
                        env.SKIP_CI = 'true'
                        echo "Commit message contains [skip ci] — skipping all stages."
                        return
                    }

                    def changedFiles = sh(
                        script: 'git diff --name-only HEAD~1 HEAD || echo "FIRST_COMMIT"',
                        returnStdout: true
                    ).trim()

                    echo "Changed files:\n${changedFiles}"

                    if (changedFiles == 'FIRST_COMMIT') {
                        echo "First commit — running full build."
                        return
                    }

                    def appPaths = ['backend/', 'frontend/', 'Jenkinsfile', 'jenkins/']
                    def hasAppChanges = changedFiles.split('\n').any { file ->
                        appPaths.any { path -> file.startsWith(path) }
                    }

                    if (!hasAppChanges) {
                        currentBuild.description = 'Skipped: no app changes'
                        currentBuild.result = 'NOT_BUILT'
                        env.SKIP_CI = 'true'
                        echo "Only infra/docs files changed — skipping build."
                    }
                }
            }
        }

        // =====================================================================
        // Stage 1: Checkout + Load Libraries
        // =====================================================================
        stage('Checkout') {
            when { expression { env.SKIP_CI != 'true' } }
            steps {
                checkout scm
                script {
                    GIT_COMMIT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    echo "Building commit: ${GIT_COMMIT}"
                    currentBuild.description = "commit: ${GIT_COMMIT}"

                    buildKaniko     = load 'jenkins/shared-libraries/vars/buildKaniko.groovy'
                    runPythonTests  = load 'jenkins/shared-libraries/vars/runPythonTests.groovy'
                    updateKustomize = load 'jenkins/shared-libraries/vars/updateKustomize.groovy'
                    trivyScan       = load 'jenkins/shared-libraries/vars/trivyScan.groovy'
                    echo "Shared libraries loaded ✓"
                }
            }
        }

        // =====================================================================
        // Stage 2: Test backend
        // =====================================================================
        stage('Test') {
            when { expression { env.SKIP_CI != 'true' } }
            steps {
                script {
                    runPythonTests()
                }
            }
        }

        // =====================================================================
        // Stage 3: Build & Push images (parallel)
        // =====================================================================
        stage('Build & Push Images') {
            when { expression { env.SKIP_CI != 'true' } }
            parallel {
                stage('Backend Image') {
                    steps {
                        script {
                            buildKaniko(
                                containerName: 'kaniko-backend',
                                image:         "${REGISTRY}/${BACKEND_IMAGE}",
                                tag:           GIT_COMMIT,
                                dockerfile:    'backend/Dockerfile',
                                context:       'backend'
                            )
                        }
                    }
                }
                stage('Frontend Image') {
                    steps {
                        script {
                            buildKaniko(
                                containerName: 'kaniko-frontend',
                                image:         "${REGISTRY}/${FRONTEND_IMAGE}",
                                tag:           GIT_COMMIT,
                                dockerfile:    'frontend/Dockerfile',
                                context:       'frontend'
                            )
                        }
                    }
                }
            }
        }

        // =====================================================================
        // Stage 4: Security Scan (Trivy)
        // =====================================================================
        // INTERVIEW NOTE:
        //   This is "shift-left security" — scanning AFTER build but BEFORE
        //   deploy. If CRITICAL CVEs found → build fails → ArgoCD never
        //   sees the new tag → production is protected.
        //
        //   Pipeline order: Test → Build → **Security Scan** → Deploy
        //   The scan runs on already-pushed images (Trivy pulls from registry).
        // =====================================================================
        stage('Security Scan') {
            when { expression { env.SKIP_CI != 'true' } }
            steps {
                script {
                    // Reload after parallel stage — CPS loses local variable
                    // references after parallel block serialization/deserialization.
                    // Production fix: @Library('shared-lib') _ avoids this entirely.
                    def trivyScanReloaded = load 'jenkins/shared-libraries/vars/trivyScan.groovy'
                    trivyScanReloaded(
                        containerName: 'trivy',
                        images: [
                            "${REGISTRY}/${BACKEND_IMAGE}:${GIT_COMMIT}",
                            "${REGISTRY}/${FRONTEND_IMAGE}:${GIT_COMMIT}"
                        ],
                        severity: 'CRITICAL'
                    )
                }
            }
        }

        // =====================================================================
        // Stage 5a: Deploy to Dev (dev branch only)
        // =====================================================================
        // MULTI-ENV: dev branch → updates dev overlay → ArgoCD auto-syncs
        // to money-talks-dev namespace. Allows testing before prod.
        // =====================================================================
        stage('Deploy to Dev') {
            when {
                allOf {
                    expression { env.SKIP_CI != 'true' }
                    expression { env.BRANCH_NAME == 'dev' }
                }
            }
            steps {
                script {
                    // Reload after parallel stage (CPS serialization workaround)
                    def updateKustomizeReloaded = load 'jenkins/shared-libraries/vars/updateKustomize.groovy'
                    updateKustomizeReloaded(
                        overlay:       'k8s/overlays/dev',
                        branch:        'dev',
                        images: [
                            'BACKEND_IMAGE':  "${REGISTRY}/${BACKEND_IMAGE}:${GIT_COMMIT}",
                            'FRONTEND_IMAGE': "${REGISTRY}/${FRONTEND_IMAGE}:${GIT_COMMIT}"
                        ],
                        credentialsId: 'github-pat',
                        repoUrl:       REPO_URL
                    )
                }
            }
        }

        // =====================================================================
        // Stage 5b: Deploy to Prod (main branch only)
        // =====================================================================
        // MULTI-ENV: main branch → updates prod overlay → ArgoCD waits for
        // manual sync before deploying to money-talks-prod namespace.
        // =====================================================================
        stage('Deploy to Prod') {
            when {
                allOf {
                    expression { env.SKIP_CI != 'true' }
                    expression { env.BRANCH_NAME == 'main' }
                }
            }
            steps {
                script {
                    def updateKustomizeReloaded = load 'jenkins/shared-libraries/vars/updateKustomize.groovy'
                    updateKustomizeReloaded(
                        overlay:       'k8s/overlays/prod',
                        branch:        'main',
                        images: [
                            'BACKEND_IMAGE':  "${REGISTRY}/${BACKEND_IMAGE}:${GIT_COMMIT}",
                            'FRONTEND_IMAGE': "${REGISTRY}/${FRONTEND_IMAGE}:${GIT_COMMIT}"
                        ],
                        credentialsId: 'github-pat',
                        repoUrl:       REPO_URL
                    )
                }
            }
        }
    }

    // =========================================================================
    // Post-build actions
    // =========================================================================
    post {
        success {
            echo """
                ✅ Build SUCCESS
                Commit: ${GIT_COMMIT}
                Backend:  ${REGISTRY}/${BACKEND_IMAGE}:${GIT_COMMIT}
                Frontend: ${REGISTRY}/${FRONTEND_IMAGE}:${GIT_COMMIT}
            """
        }
        failure {
            echo '❌ Build FAILED — check stage logs above'
        }
        always {
            echo 'Pipeline finished. Agent pod will be destroyed.'
        }
    }
}
