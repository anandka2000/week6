podTemplate(yaml: '''
    apiVersion: v1
    kind: Pod
    spec:
      containers:
      - name: gradle
        image: gradle:6.3-jdk14
        command:
        - sleep
        args:
        - 99d
        volumeMounts:
        - name: shared-storage
          mountPath: /mnt        
      - name: kaniko
        image: gcr.io/kaniko-project/executor:debug
        command:
        - sleep
        args:
        - 9999999
        volumeMounts:
        - name: shared-storage
          mountPath: /mnt
        - name: kaniko-secret
          mountPath: /kaniko/.docker
      restartPolicy: Never
      volumes:
      - name: shared-storage
        persistentVolumeClaim:
          claimName: jenkins-pv-claim
      - name: kaniko-secret
        secret:
            secretName: dockercred
            items:
            - key: .dockerconfigjson
              path: config.json
''') {
  node(POD_LABEL) {

    stage('Build a gradle project') {
       echo "I am the ${env.BRANCH_NAME} branch"
       
        try {
          git 'https://github.com/anandka2000/week6.git'
          container('gradle') {

            stage('Build code') {
              sh '''
                  cd sample1
                  chmod +x gradlew
                  ./gradlew build
                  mv ./build/libs/calculator-0.0.1-SNAPSHOT.jar /mnt
              '''
            } // stage build

            // Run codecoverage test only on master
            stage("Code coverage") {
                if (env.BRANCH_NAME == "master") {
                    echo "Running code coverage"
                    sh '''
                        pwd
                        cd sample1
                        ./gradlew jacocoTestCoverageVerification
                        ./gradlew jacocoTestReport
                    '''
                }
            } // stage codecoverage

            // Run checkstyle test on master and feature
            stage("Checkstyle test") {
                if (env.BRANCH_NAME == "master" || env.BRANCH_NAME == "feature") {
                    echo "Running checkstyle tests"
                    sh '''
                        cd sample1
                        chmod +x gradlew
                        ./gradlew checkstyleMain
                    '''
                }
            } // stage checkstyle
          } // container gradle
        } catch (Exception E) {
            echo "Build failed"
            error ('Abortin as build failed')
        } // exception
    } // Stage Build


    stage('Build Java Image') {
      container('kaniko') {
        stage('Build docker image') {
          sh '''
              echo 'FROM openjdk:8-jre' > Dockerfile
              echo 'COPY ./calculator-0.0.1-SNAPSHOT.jar app.jar' >> Dockerfile
              echo 'ENTRYPOINT ["java", "-jar", "app.jar"]' >> Dockerfile
              mv /mnt/calculator-0.0.1-SNAPSHOT.jar .
              /kaniko/executor --context `pwd` --destination anandka2000/hello-kaniko:1.0
          '''
        } // stage build docker
      } // container kaniko
    } // Stage Build Java Image
  } // NODE label
}
