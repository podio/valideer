#!/usr/bin/env groovy
applicationName = "valideer";
securityScanOnly = true;

def template
node ('aws-linuxdocker-test') {
    checkout scm
    dir("jenkins-template") {
        checkout([$class: 'GitSCM',branches: [[name:'main']],extensions:[],userRemoteConfigs: [[credentialsId: 'gh-podio-app', url: 'https://github.com/podio/jenkins-template-repo.git']]])
    }
    def rootDir = pwd()
    template = load "${rootDir}/jenkins-template/Jenkinsfile"
}

template()
