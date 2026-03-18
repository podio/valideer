pipeline {
    agent { label 'azure-linux-ubuntu-18' }
    options {
        skipStagesAfterUnstable()
        disableConcurrentBuilds()
    }
    stages {
        stage("Clone Git Repo") {
            steps {
                cleanWs()
                script {
                    def branchName = env.CHANGE_BRANCH ?: env.BRANCH_NAME
                    env.branchName = branchName
                    echo "Using branch/commit: ${env.BRANCH_NAME}"
                }
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "refs/heads/${env.branchName}"]],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [
                        [$class: 'RelativeTargetDirectory', relativeTargetDir: 'valideer'],
                        [$class: 'CloneOption', shallow: false, noTags: false]
                    ],
                    submoduleCfg: [],
                    userRemoteConfigs: [[credentialsId: 'github-app-podio-jm', url: 'https://github.com/podio/valideer.git']]
                ])
            }
        }

        stage('Polaris') {
            environment {
                BRIDGE_POLARIS_SERVERURL = "https://polaris.blackduck.com"
                BRIDGE_POLARIS_ACCESSTOKEN = credentials('blackduck-api-token')
                BRIDGE_POLARIS_APPLICATION_NAME = "Podio-Podio"
                BRIDGE_POLARIS_PROJECT_NAME = "valideer"
                BRIDGE_POLARIS_BRANCH_NAME = "${env.branchName}"
                BRIDGE_POLARIS_ASSESSMENT_TYPES = "SAST"
            }
            steps {
                dir('valideer') {
                    script {
                        status = sh returnStatus: true, script: '''
                            bridge-cli --stage polaris
                        '''
                        if (status == 8) {
                            unstable 'Policy violation'
                        } else if (status != 0) {
                            error 'Bridge CLI failure'
                        }
                    }
                }
            }
        }

        stage('BlackDuckSCA') {
            environment {
                BRIDGE_BLACKDUCKSCA_URL = "https://progresssoftware.app.blackduck.com"
                BRIDGE_BLACKDUCKSCA_TOKEN = credentials('blackduck-sca-token')
                BRIDGE_BLACKDUCKSCA_SCAN_FAILURE_SEVERITIES = "CRITICAL"
                BRIDGE_BLACKDUCKSCA_SCAN_FULL = "true"
                BRIDGE_DETECT_ARGS = "--detect.project.name=DX-Podio-valideer --detect.project.version.name=${env.branchName} --detect.project.version.update=true --detect.project.version.distribution=SAAS --detect.project.group.name=Podio-Podio --detect.accuracy.required=NONE"
            }
            steps {
                dir('valideer') {
                    script {
                        status = sh returnStatus: true, script: '''
                            bridge-cli --stage blackducksca
                        '''
                        if (status != 0) {
                            error 'BlackDuck SCA Scan failed'
                        }
                    }
                }
            }
        }

        stage('TruffleHog Scan') {
            steps {
                script {
                    def scanOutput = 'trufflehog_output.json'
                    def repoPath = "${env.WORKSPACE}/valideer"

                    echo "🔍 Running TruffleHog Git scan on repo path: ${repoPath}, branch: ${env.branchName}"

                    def scanExitCode = sh(returnStatus: true, script: """
                        docker run --rm -v "${repoPath}:/usr/src" \
                          artifacts.progress.com/ci-local-docker/trufflesecurity/trufflehog:3.88.29-amd64 \
                          git file:/usr/src \
                          --branch="${env.branchName}" \
                          --results=verified,unknown \
                          --force-skip-binaries \
                          --force-skip-archives \
                          --json \
                          --no-update \
                          > "${scanOutput}"

                        echo "📄 TruffleHog scan completed. Output saved to ${scanOutput}"
                        if grep -q '"SourceMetadata"' "${scanOutput}"; then
                            echo "❌ TruffleHog found potential secrets!"
                            cat "${scanOutput}"
                            exit 1
                        else
                            echo "✅ No secrets found."
                        fi
                    """)

                    if (scanExitCode != 0) {
                        error("❌ TruffleHog scan failed, potential secrets detected in the repository.")
                    }
                }
            }
            post {
                always {
                    archiveArtifacts artifacts: 'trufflehog_output.json', fingerprint: true, allowEmptyArchive: true
                }
                success {
                    echo "✅ TruffleHog scan passed - No secrets detected."
                }
            }
        }
    }
}
