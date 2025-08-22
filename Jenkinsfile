def VENV = 'wazo-benchmark-venv'

pipeline {
  agent {
    label 'built-in'
  }

    stages {
      stage ("Benchmark"){
        steps {
          sh """
            set -xe
            python3.9 -m venv --clear $VENV
            source $VENV/bin/activate
            pip install wheel

            pip install -r requirements.txt

            fab -H root@wazo-benchmark.lan.wazo.io reset-server
            pytest
          """
      }
    }
  }
}
