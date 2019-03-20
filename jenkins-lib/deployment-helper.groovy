def generate_add_user_script() {
    stage('generate_add_user_script') {
        script {
          sh '''#!/bin/sh
              my_UID=$(id -u)
              my_GID=$(id -g)
              my_NAME=$(whoami)
              cat <<EOF > generate_add_user_script.sh
              #!/bin/sh
              if [ -f "/etc/alpine-release" ]; then
              	addgroup -g $my_GID $my_NAME
              	adduser -u $my_UID -g $my_GID -D -S $my_NAME
              else
              	groupadd -g $my_GID $my_NAME
              	useradd -u $my_UID -g $my_GID $my_NAME
              fi

              mkdir -p /home/$my_NAME >/dev/null 2>&1
              chown -R $my_NAME:$my_GID /home/$my_NAME
              # $WORKSPACE
          '''
          sh 'chmod +x generate_add_user_script.sh'
        }//script
    }//stage
}

def generate_aws_environment() {
    stage('generate_aws_environment') {
      withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', accessKeyVariable: 'AWS_ACCESS_KEY_ID', credentialsId: "$PROFILE", secretKeyVariable: 'AWS_SECRET_ACCESS_KEY']]) {
        withCredentials([string(credentialsId: 'GITHUB_TOKEN', variable: 'GITHUB_TOKEN')]) {
          withCredentials([string(credentialsId: 'ANSIBLE_VAULT_FILE_ACT2', variable: 'VAULT')]) {
            sh '''cat <<EOF > generate_aws_environment.sh
#!/bin/sh -e
mkdir -p ~/.aws

printf "[$PROFILE]\\n
output=json\\n
region=ap-southeast-2" > ~/.aws/config

printf "[$PROFILE]\\n
aws_access_key_id = ${AWS_ACCESS_KEY_ID}\\n
aws_secret_access_key = ${AWS_SECRET_ACCESS_KEY}" > ~/.aws/credentials

mkdir -p ~/.ansible/vault/password
echo "$VAULT" > ~/.ansible/vault/password/act2-infrastructure
chmod 0600 ~/.ansible/vault/password/act2-infrastructure

sed -i "s|git+ssh://git|https://${GITHUB_TOKEN}|g" requirements.yml
./ansible-common/update-galaxy.py
git reset --hard
'''
          sh 'chmod +x generate_aws_environment.sh'
          }//withCred vault
        }//withCred github
      }//withCred AWS
    }//stage
}

def run_build_script() {
    stage('run_build_script') {
        script {
            docker.image('xvtsolutions/python3-aws-ansible:2.7.9').withRun('-u root --volumes-from xvt_jenkins --net=container:xvt') { c->
                if (fileExists 'generate_add_user_script.sh') {
                    sh "docker exec --workdir ${WORKSPACE} ${c.id} bash ./generate_add_user_script.sh"
                } 
                else {
                    echo 'generate_add_user_script.sh does not exist - skipping'
                }
                if (fileExists 'generate_aws_environment.sh') {
                    sh "docker exec --user jenkins --workdir ${WORKSPACE} ${c.id} ./generate_aws_environment.sh"
                }
                else {
                    echo 'generate_aws_environment.sh does not exist - skipping'
                }
                if (fileExists 'build.sh') {
                    sh "docker exec --user jenkins --workdir ${WORKSPACE} ${c.id} ./build.sh"
                }
                else {
                    echo 'build.sh does not exist - skipping'
                }
                sh 'rm -rf build.sh add-user.sh ~/.aws ~/.ansible ubuntu || true'
            }//docker env
        }//script
    }//stage
}

def load_upstream_build_data() {
    stage('load_upstream_build_data') {
        script {
            if (env.UPSTREAM_BUILD_NUMBER == 'LAST_SAVED_BUILD') {
              copyArtifacts filter: 'artifact_data.yml', fingerprintArtifacts: true, flatten: true, projectName: "${UPSTREAM_JOB_NAME}", selector: latestSavedBuild()
            }
            else if (env.UPSTREAM_BUILD_NUMBER == 'LAST_SUCCESS_BUILD')  {
                copyArtifacts filter: 'artifact_data.yml', fingerprintArtifacts: true, flatten: true, projectName: "${UPSTREAM_JOB_NAME}", selector: lastSuccessful()
            }
            else {
              copyArtifacts filter: 'artifact_data.yml', fingerprintArtifacts: true, flatten: true, projectName: "${UPSTREAM_JOB_NAME}", selector: specific("${UPSTREAM_BUILD_NUMBER}")
            }//If
            // Parsing artifact data
            ARTIFACT_DATA = readYaml(file: 'artifact_data.yml')
            if (ARTIFACT_DATA.artifact_filename) env.ARTIFACT_FILENAME = ARTIFACT_DATA.artifact_filename
            if (ARTIFACT_DATA.artifact_revision) env.ARTIFACT_REVISION = ARTIFACT_DATA.artifact_revision
            if (ARTIFACT_DATA.build_number) env.UPSTREAM_BUILD_NUMBER = ARTIFACT_DATA.build_number
            if (ARTIFACT_DATA.branch_name) env.UPSTREAM_BRANCH_NAME = ARTIFACT_DATA.branch_name
            if (ARTIFACT_DATA.upstream_build_url) env.UPSTREAM_BUILD_URL = ARTIFACT_DATA.upstream_build_url
            if (ARTIFACT_DATA.upstream_job_name) env.UPSTREAM_JOB_NAME = ARTIFACT_DATA.upstream_job_name
        }//script
    }//stage
}

return this
