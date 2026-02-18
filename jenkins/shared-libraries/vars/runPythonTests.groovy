// =============================================================================
// runPythonTests — Install dependencies and run pytest in a container
// =============================================================================
// Usage in Jenkinsfile:
//   runPythonTests(
//     directory:    'backend',
//     requirements: 'requirements.txt',   // optional, default
//     testDir:      'tests/',             // optional, default
//     container:    'python'              // optional, default
//   )
// =============================================================================

def call(Map config = [:]) {
    // -------------------------------------------------------------------------
    // 1. Parameters with defaults
    //    config = [:]  → empty Map as default, so calling runPythonTests()
    //    with no args still works (all defaults kick in)
    // -------------------------------------------------------------------------
    def dir          = config.directory ?: 'backend'
    def requirements = config.requirements ?: 'requirements.txt'
    def testDir      = config.testDir ?: 'tests/'
    def containerName = config.container ?: 'python'
    def extraArgs    = config.extraArgs ?: ''  // e.g. '--cov=app --cov-report=html'

    // -------------------------------------------------------------------------
    // 2. Run inside the python container
    //    -q flag on pip: quiet output (less noise in Jenkins console)
    //    -v flag on pytest: verbose test names (useful for debugging)
    //    --tb=short: shorter tracebacks (enough to find the problem)
    // -------------------------------------------------------------------------
    container(containerName) {
        sh """
            cd ${dir}
            pip install --no-cache-dir -r ${requirements} -q
            python -m pytest ${testDir} -v --tb=short ${extraArgs}
        """
    }
}

// REQUIRED for 'load' — returns this Script object so Jenkinsfile can call()
return this
