pipeline {
    agent any   // Jenkins je node e run korche (Windows machine)

    stages {
        stage('Checkout') {
            steps {
                // GitHub theke code ane
                git branch: 'main', url: 'https://github.com/Manir96/Django-Shoppingo-Ecom.git'
            }
        }

        stage('Create venv & Install deps') {
            steps {
                bat '''
                cd my_ecom

                if not exist venv (
                    python -m venv venv
                )

                call venv\\Scripts\\activate.bat
                pip install --upgrade pip
                pip install -r requirements.txt
                '''
            }
        }

        stage('Django check') {
            steps {
                bat '''
                cd my_ecom
                call venv\\Scripts\\activate.bat
                python manage.py check
                '''
            }
        }

        stage('Run tests') {
            steps {
                bat '''
                cd my_ecom
                call venv\\Scripts\\activate.bat
                python manage.py test
                '''
            }
        }

        stage('Deploy (later)') {
            when {
                expression { return false } // pore true korbo, ekhono off
            }
            steps {
                echo 'Ei stage e pore deploy script boshabo (ssh / server restart etc.)'
            }
        }
    }

    post {
        success {
            echo '✅ Jenkins CI SUCCESS (Shoppingo Ecom on Windows)!'
        }
        failure {
            echo '❌ Build failed. Console output e error dekhun.'
        }
    }
}
