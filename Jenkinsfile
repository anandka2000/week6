// week5 example uses Jenkin's "scripted" syntax, as opposed to its "declarative" syntax
// see: https://www.jenkins.io/doc/book/pipeline/syntax/#scripted-pipeline

// Defines a Kubernetes pod template that can be used to create nodes.

podTemplate(containers: [
    podRetention: onFailure
    containerTemplate(
        name: 'gradle',
        image: 'gradle:6.3-jdk14',
        command: 'sleep',
        args: '30d'
        ),
    ]) {

    node(POD_LABEL) {
        stage('Run pipeline against a gradle project') {

            // "container" Selects a container of the agent pod so that 
            // all shell steps are executed in that container.
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
                     if (env.BRANCH_NAME == "feature") {
                         sh 'printenv'
                         echo "I am the ${env.BRANCH_NAME} branch"
                         echo "Running code coverage"
                         try {
				sh '''
				    pwd
				    cd sample1
				    ./gradlew jacocoTestCoverageVerification
				    ./gradlew jacocoTestReport
				'''
			 } catch (Exception E) {
				echo 'Failure detected'
			 }

			 // from the HTML publisher plugin
			 // https://www.jenkins.io/doc/pipeline/steps/htmlpublisher/
			 publishHTML (target: [
				reportDir: 'sample1/build/reports/tests/test',
				reportFiles: 'index.html',
				reportName: "JaCoCo Report"
                    	 ])                       
		    }
                }

                stage("checkstyle test") {
                    sh '''
                    cd sample1
                    chmod +x gradlew
                    ./gradlew checkstyleMain
                    '''


                    // from the HTML publisher plugin
                    // https://www.jenkins.io/doc/pipeline/steps/htmlpublisher/
                    publishHTML (target: [
                        reportDir: 'sample1/build/reports/checkstyle',
                        reportFiles: 'main.html',
                        reportName: "Checkstyle report"
                    ])                       
		
		}
           }
        }
    }
}
