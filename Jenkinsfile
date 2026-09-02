pipeline {
    agent any
    stages {
        stage('Checkout') {
            steps { 
                checkout scm
            }
        }
        stage('Install Dependencies') {
            steps {
                dir('Project1') {
                    sh 'pip install -r requirements.txt'
                }
            }
        }
        stage('Test') {
            steps {
                dir('Project1') {
                    sh 'pytest'
                }
            }
        }
        stage('Build Docker Image') {
            steps {
                dir('Project1') {
                    sh 'docker build -t rajiv69/flask-app:latest .'
                }
            }
        }  
        stage('Push to Docker Hub') {
            steps {
                withCredentials([
                    usernamePassword(
                        credentialsId: 'dockerhub-cred',
                        usernameVariable: 'DOCKER_USER',
                        passwordVariable: 'DOCKER_PASS'
                    )
                ]) {
                    sh '''
                        echo "$DOCKER_PASS" | docker login -u "$DOCKER_USER" --password-stdin
                        docker push rajiv69/flask-app:latest
                    '''
                }
            }
        }
    }
}
