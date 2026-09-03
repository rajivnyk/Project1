pipeline {
    agent any
    stages {

        stage('Build Docker Image') {
            steps {
                dir('Project1') {
                    sh 'docker build -t rajiv69/flask-app:latest .'
                }
            }
        }
        stage('Test') {
            steps {
                dir('Project1') {
                    sh '''#!/bin/bash
                        set +e
                        
                        # Cleanup any stuck containers from previous aborted builds
                        docker rm -f test-mysql || true
                        docker network rm test-net || true
                        
                        docker network create test-net
                        
                        # Start a temporary MySQL database for testing
                        docker run -d --name test-mysql --network test-net \\
                          -e MYSQL_ROOT_PASSWORD=mysql@rajiv \\
                          -e MYSQL_DATABASE=travel_test \\
                          mysql:8.4
                          
                        echo "Waiting for MySQL to fully initialize..."
                        sleep 35
                        
                        # Run pytest inside the app container, connecting to the test DB
                        docker run --rm --network test-net \\
                          -e DB_HOST=test-mysql \\
                          -e DB_PASSWORD=mysql@rajiv \\
                          -e DB_USER=root \\
                          -e DB_NAME=travel_test \\
                          rajiv69/flask-app:latest pytest
                          
                        TEST_EXIT_CODE=$?
                        
                        # Cleanup
                        docker rm -f test-mysql
                        docker network rm test-net
                        
                        exit $TEST_EXIT_CODE
                    '''
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
