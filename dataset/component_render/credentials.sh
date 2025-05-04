echo "Update credential"
AUDIENCE="aws-non-falcon"
ROLE_ARN="arn:aws:iam::226332508888:role/bedrock-access-gcp"
# Fetch JWT token
jwt_token=$(curl -sH "Metadata-Flavor: Google" "http://metadata/computeMetadata/v1/instance/service-accounts/default/identity?audience=${AUDIENCE}&format=full&licenses=FALSE")
# Extract JWT payload and decode it
# JWT tokens are Base64 URL encoded, so we need to replace '-' with '+' and '_' with '/'
jwt_payload=$(echo "$jwt_token" | awk -F '.' '{print $2}' | tr '_-' '/+' | base64 -d 2>/dev/null)
# Extract the 'sub' claim from the decoded JSON
jwt_sub=$(echo "$jwt_payload" | jq -r '.sub')
# Assume role with web identity
CREDENTIALS=$(aws sts assume-role-with-web-identity --role-arn $ROLE_ARN --role-session-name $jwt_sub --web-identity-token $jwt_token --duration-seconds 43200)
# Extract credentials from the response
AWS_ACCESS_KEY_ID=$(echo $CREDENTIALS | jq -r '.Credentials.AccessKeyId')
AWS_SECRET_ACCESS_KEY=$(echo $CREDENTIALS | jq -r '.Credentials.SecretAccessKey')
AWS_SESSION_TOKEN=$(echo $CREDENTIALS | jq -r '.Credentials.SessionToken')
# Configure AWS CLI
aws configure set aws_access_key_id $AWS_ACCESS_KEY_ID
aws configure set aws_secret_access_key $AWS_SECRET_ACCESS_KEY
aws configure set aws_session_token $AWS_SESSION_TOKEN
echo "AWS Credentials have been exported to the pod - valid for 12 hrs"