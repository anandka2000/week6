podTemplate(containers: [
    containerTemplate(
        name: 'gradle',
        image: 'gradle:6.3-jdk14',
        command: 'sleep',
        args: '30d'
        ),
    ]) {

    node(POD_LABEL) {
        stage('Run pipeline against a gradle project') {
            container('gradle') {
                stage('Build a gradle project') {
                    echo "I am the ${env.BRANCH_NAME} branch"
                    git 'https://github.com/anandka2000/week6.git'
                    sh '''
                    cd sample1
                    chmod +x gradlew
                    ./gradlew test
                    '''
                }
                stage("Code coverage") {
                     if (env.BRANCH_NAME == "master") {
                         sh 'printenv'
                         echo "I am the ${env.BRANCH_NAME} branch"
                         echo "Running code coverage"
			sh '''
		            pwd
			    cd sample1
			    ./gradlew jacocoTestCoverageVerification
			    ./gradlew jacocoTestReport
			'''              
		    }
                }

                stage("checkstyle test") {
                    sh '''
                    cd sample1
                    chmod +x gradlew
                    ./gradlew checkstyleMain
                    '''                   
		}
           }
        }
    }
}
