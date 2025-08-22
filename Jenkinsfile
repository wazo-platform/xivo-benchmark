def VENV = 'wazo-benchmark-venv'

pipeline {
  agent {
    label 'built-in'
  }
  environment {
    MAIL_RECIPIENTS = 'dev+tests-reports@wazo.community'
  }

  options {
    disableConcurrentBuilds()
    timeout(time: 10, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }
  stages {
    stage ("Benchmark"){
      steps {
        sh """
          set -xe
          python3.9 -m venv --clear $VENV
          . $VENV/bin/activate
          pip install wheel

          pip install -r requirements.txt

          fab -H root@wazo-benchmark.lan.wazo.io reset-server
          pytest
        """
      }
    }
  }
  post {
    failure {
      emailext to: "${MAIL_RECIPIENTS}", subject: '${DEFAULT_SUBJECT}', body: '${DEFAULT_CONTENT}'
    }
    fixed {
      emailext to: "${MAIL_RECIPIENTS}", subject: '${DEFAULT_SUBJECT}', body: '${DEFAULT_CONTENT}'
    }
  }
}
