# MedRAG AWS EC2 CI/CD Runbook

This is the tested, CLI-first runbook for the full MedRAG production lifecycle on AWS:

1. prepare local AWS and GitHub access
2. create or update the production stack
3. wire GitHub Actions and runtime secrets
4. deploy through CI/CD
5. test the live system
6. destroy everything completely

This guide matches the production assets already in this repo:

- [infra/cloudformation/medrag-prod.yml](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/infra/cloudformation/medrag-prod.yml)
- [.github/workflows/infrastructure.yml](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/.github/workflows/infrastructure.yml)
- [.github/workflows/deploy-prod.yml](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/.github/workflows/deploy-prod.yml)
- [.github/workflows/destroy-prod.yml](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/.github/workflows/destroy-prod.yml)
- [docker-compose.prod.yml](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/docker-compose.prod.yml)
- [scripts/bootstrap-ec2.sh](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/scripts/bootstrap-ec2.sh)
- [scripts/deploy-prod.sh](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/scripts/deploy-prod.sh)
- [scripts/destroy-prod.sh](/Users/yashpatil/Developer/AI/Evolvue/MedRAG/scripts/destroy-prod.sh)

## 1. Lessons baked into this runbook

These are the exact issues we hit during the real rollout, and this runbook now accounts for them:

- Always verify AWS CLI auth with `aws sts get-caller-identity` before doing anything. We hit invalid and expired credentials early.
- Set `AWS_PAGER=""` up front. AWS CLI paging made VPC and subnet output awkward.
- Amazon Linux 2023 does not provide `docker-compose-plugin` through `dnf`. The working bootstrap installs `docker` from `dnf` and installs Docker Compose as a standalone CLI plugin binary.
- An EC2 instance being `Online` in SSM does not mean Docker is installed correctly. Verify `docker --version` and `docker compose version` before the first deploy.
- `AWS_ROLE_ARN` and `AWS_BOOTSTRAP_ROLE_ARN` must never be the same.
  - `AWS_ROLE_ARN` is the stack-managed deploy role created by CloudFormation.
  - `AWS_BOOTSTRAP_ROLE_ARN` must be an external bootstrap/admin role not created by the stack.
- If destroy partially deletes resources and then fails, rerunning destroy from stable local admin credentials usually finishes the cleanup cleanly.

## 2. Tooling and access you need

Install these CLIs on your machine:

- AWS CLI v2
- GitHub CLI `gh`
- `jq`
- `git`
- `curl`

You also need:

- local AWS credentials with permission to create IAM, EC2, S3, ECR, Secrets Manager, and CloudFormation resources
- admin access to the GitHub repository
- one `OPENAI_API_KEY`
- one `LLAMA_CLOUD_API_KEY`

Important distinction:

- runtime secrets for the deployed app live in AWS Secrets Manager
- the current `Evaluation` GitHub workflow still uses GitHub repository secrets

## 3. Recommended operating model

The safest working model is:

- use local AWS CLI admin credentials for infrastructure create, update, and destroy
- use GitHub Actions for evaluation and application deploys

If you want the `Infrastructure` and `Destroy Production` GitHub workflows too, create an external GitHub OIDC bootstrap role and store it as `AWS_BOOTSTRAP_ROLE_ARN`.

Important safety rule:

- `AWS_BOOTSTRAP_ROLE_ARN` must be external to the `medrag-prod` CloudFormation stack
- `AWS_ROLE_ARN` is the stack-managed deploy role output by the stack
- never set `AWS_BOOTSTRAP_ROLE_ARN` equal to `AWS_ROLE_ARN`

## 4. Shell preflight

Run this before the AWS steps:

```bash
export AWS_PAGER=""
export AWS_REGION="us-east-1"
export AWS_DEFAULT_REGION="${AWS_REGION}"
export ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
```

Verify AWS CLI credentials:

```bash
aws sts get-caller-identity
aws configure list
env | grep '^AWS_'
```

If `aws sts get-caller-identity` fails, stop and fix credentials first.

Verify GitHub CLI:

```bash
gh auth status
```

## 5. Set your shell variables

Use this repo’s production values:

```bash
export STACK_NAME="medrag-prod"
export PROJECT_SLUG="medrag-prod"
export GITHUB_OWNER="yashprogrammer"
export GITHUB_REPO="MedRAG_live"
export GH_REPO="${GITHUB_OWNER}/${GITHUB_REPO}"
export INSTANCE_TYPE="t3.large"
export SECRET_NAME="medrag/prod/app"

export OPENAI_API_KEY=""
export LLAMA_CLOUD_API_KEY=""
```

If you already know the target VPC and subnet:

```bash
export VPC_ID="vpc-xxxxxxxx"
export SUBNET_ID="subnet-xxxxxxxx"
```

## 6. Discover the VPC and subnet

List VPCs:

```bash
aws ec2 describe-vpcs \
  --region "${AWS_REGION}" \
  --query 'Vpcs[].{Id:VpcId,Cidr:CidrBlock,Default:IsDefault,Name:Tags[?Key==`Name`]|[0].Value}' \
  --output table
```

List subnets:

```bash
aws ec2 describe-subnets \
  --region "${AWS_REGION}" \
  --query 'Subnets[].{Id:SubnetId,Vpc:VpcId,AZ:AvailabilityZone,Cidr:CidrBlock,PublicIpOnLaunch:MapPublicIpOnLaunch,Name:Tags[?Key==`Name`]|[0].Value}' \
  --output table
```

Pick:

- one `VPC_ID`
- one `SUBNET_ID` in that same VPC
- a subnet where `PublicIpOnLaunch` is `true`

Then export them:

```bash
export VPC_ID="vpc-06139884a295f5082"
export SUBNET_ID="subnet-0505f642ae30fb647"
```

## 7. Optional: create an external GitHub bootstrap role with AWS CLI

You only need this if you want to use the `Infrastructure` or `Destroy Production` GitHub workflows.

For the fastest working path, create a separate GitHub OIDC role outside the stack and attach `AdministratorAccess`. You can tighten this later.

First set a role name:

```bash
export ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export BOOTSTRAP_ROLE_NAME="medrag-github-bootstrap"
```

Find or create the GitHub OIDC provider:

```bash
export EXISTING_GITHUB_OIDC_PROVIDER_ARN="$(
  aws iam list-open-id-connect-providers \
    --query "OpenIDConnectProviderList[?contains(Arn, 'token.actions.githubusercontent.com')].Arn | [0]" \
    --output text
)"

if [[ -z "${EXISTING_GITHUB_OIDC_PROVIDER_ARN}" || "${EXISTING_GITHUB_OIDC_PROVIDER_ARN}" == "None" ]]; then
  export EXISTING_GITHUB_OIDC_PROVIDER_ARN="$(
    aws iam create-open-id-connect-provider \
      --url https://token.actions.githubusercontent.com \
      --client-id-list sts.amazonaws.com \
      --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
      --query OpenIDConnectProviderArn \
      --output text
  )"
fi
```

Create the trust policy:

```bash
cat > /tmp/medrag-bootstrap-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "${EXISTING_GITHUB_OIDC_PROVIDER_ARN}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:${GITHUB_OWNER}/${GITHUB_REPO}:ref:refs/heads/main"
        }
      }
    }
  ]
}
EOF
```

Create the role if it does not already exist:

```bash
if ! aws iam get-role --role-name "${BOOTSTRAP_ROLE_NAME}" >/dev/null 2>&1; then
  aws iam create-role \
    --role-name "${BOOTSTRAP_ROLE_NAME}" \
    --assume-role-policy-document file:///tmp/medrag-bootstrap-trust-policy.json

  aws iam attach-role-policy \
    --role-name "${BOOTSTRAP_ROLE_NAME}" \
    --policy-arn arn:aws:iam::aws:policy/AdministratorAccess
fi

export AWS_BOOTSTRAP_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${BOOTSTRAP_ROLE_NAME}"
```

If you do not want to create this role, skip this section and use local AWS CLI admin credentials for infrastructure and destroy.

## 8. Validate and deploy the production stack with AWS CLI

Validate the template:

```bash
aws cloudformation validate-template \
  --region "${AWS_REGION}" \
  --template-body file://infra/cloudformation/medrag-prod.yml >/dev/null
```

If you created or already have an external GitHub OIDC provider ARN, include it. Otherwise leave it empty.

```bash
EXTRA_STACK_PARAMS=()
if [[ -n "${EXISTING_GITHUB_OIDC_PROVIDER_ARN:-}" && "${EXISTING_GITHUB_OIDC_PROVIDER_ARN}" != "None" ]]; then
  EXTRA_STACK_PARAMS+=("ExistingGitHubOidcProviderArn=${EXISTING_GITHUB_OIDC_PROVIDER_ARN}")
fi

aws cloudformation deploy \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --template-file infra/cloudformation/medrag-prod.yml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectSlug="${PROJECT_SLUG}" \
    VpcId="${VPC_ID}" \
    SubnetId="${SUBNET_ID}" \
    InstanceType="${INSTANCE_TYPE}" \
    GitHubOwner="${GITHUB_OWNER}" \
    GitHubRepository="${GITHUB_REPO}" \
    GitHubBranch="main" \
    SecretName="${SECRET_NAME}" \
    "${EXTRA_STACK_PARAMS[@]}"
```

Enable termination protection:

```bash
aws cloudformation update-termination-protection \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --enable-termination-protection
```

## 9. Capture the stack outputs

```bash
STACK_OUTPUTS="$(aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}" \
  --query 'Stacks[0].Outputs' \
  --output json)"

export AWS_ROLE_ARN="$(printf '%s' "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="GitHubActionsRoleArn").OutputValue')"
export INSTANCE_ID="$(printf '%s' "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="InstanceId").OutputValue')"
export ELASTIC_IP="$(printf '%s' "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="ElasticIp").OutputValue')"
export ECR_REPOSITORY_URI="$(printf '%s' "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="EcrRepositoryUri").OutputValue')"
export DEPLOY_BUCKET_NAME="$(printf '%s' "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="DeployBucketName").OutputValue')"
export SECRET_ARN="$(printf '%s' "${STACK_OUTPUTS}" | jq -r '.[] | select(.OutputKey=="SecretArn").OutputValue')"

printf '%s\n' "${STACK_OUTPUTS}" | jq -r '.[] | "\(.OutputKey)=\(.OutputValue)"'
```

At this point:

- `AWS_ROLE_ARN` is the stack-managed deploy role for `deploy-prod.yml`
- `AWS_BOOTSTRAP_ROLE_ARN`, if you created it, remains the external role for infrastructure and destroy

## 10. Configure GitHub Actions with GitHub CLI

Authenticate GitHub CLI if needed:

```bash
gh auth login
gh auth status
```

### 10.1 Required repository variables for deploy

```bash
gh variable set AWS_REGION --repo "${GH_REPO}" --body "${AWS_REGION}"
gh variable set AWS_ROLE_ARN --repo "${GH_REPO}" --body "${AWS_ROLE_ARN}"
gh variable set PROD_STACK_NAME --repo "${GH_REPO}" --body "${STACK_NAME}"
```

### 10.2 Optional repository variables for infrastructure and destroy workflows

Only set these if you created an external bootstrap role:

```bash
gh variable set AWS_BOOTSTRAP_ROLE_ARN --repo "${GH_REPO}" --body "${AWS_BOOTSTRAP_ROLE_ARN}"
gh variable set PROD_VPC_ID --repo "${GH_REPO}" --body "${VPC_ID}"
gh variable set PROD_SUBNET_ID --repo "${GH_REPO}" --body "${SUBNET_ID}"
gh variable set PROD_INSTANCE_TYPE --repo "${GH_REPO}" --body "${INSTANCE_TYPE}"
gh variable set PROD_SECRET_NAME --repo "${GH_REPO}" --body "${SECRET_NAME}"
gh variable set EXISTING_GITHUB_OIDC_PROVIDER_ARN --repo "${GH_REPO}" --body "${EXISTING_GITHUB_OIDC_PROVIDER_ARN:-}"
```

### 10.3 GitHub repository secrets for the Evaluation workflow

```bash
printf '%s' "${OPENAI_API_KEY}" | gh secret set OPENAI_API_KEY --repo "${GH_REPO}"
printf '%s' "${LLAMA_CLOUD_API_KEY}" | gh secret set LLAMA_CLOUD_API_KEY --repo "${GH_REPO}"
```

## 11. Put the runtime secrets into AWS Secrets Manager

```bash
aws secretsmanager put-secret-value \
  --region "${AWS_REGION}" \
  --secret-id "${SECRET_NAME}" \
  --secret-string "$(jq -nc \
    --arg openai "${OPENAI_API_KEY}" \
    --arg llama "${LLAMA_CLOUD_API_KEY}" \
    '{OPENAI_API_KEY: $openai, LLAMA_CLOUD_API_KEY: $llama}')"
```

Verify:

```bash
aws secretsmanager describe-secret \
  --region "${AWS_REGION}" \
  --secret-id "${SECRET_NAME}" \
  --query '{Name:Name,ARN:ARN}' \
  --output table
```

## 12. Verify EC2 bootstrap before the first deploy

First verify SSM sees the instance:

```bash
aws ssm describe-instance-information \
  --region "${AWS_REGION}" \
  --query "InstanceInformationList[?InstanceId=='${INSTANCE_ID}'].[InstanceId,PingStatus,PlatformName,AgentVersion]" \
  --output table
```

You want `PingStatus` to be `Online`.

Then explicitly verify Docker and Compose:

```bash
COMMAND_ID="$(aws ssm send-command \
  --region "${AWS_REGION}" \
  --instance-ids "${INSTANCE_ID}" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=[
    "docker --version",
    "docker compose version",
    "docker-compose --version"
  ]' \
  --query 'Command.CommandId' \
  --output text)"

aws ssm get-command-invocation \
  --region "${AWS_REGION}" \
  --command-id "${COMMAND_ID}" \
  --instance-id "${INSTANCE_ID}" \
  --output json
```

Do not skip this check. We had an instance that was `Online` in SSM but still missing Docker because cloud-init had failed.

## 13. If Docker or Compose is missing, repair the instance

The known Amazon Linux 2023 fix is:

- install `docker` from `dnf`
- install Docker Compose manually as a CLI plugin binary
- do not rely on `dnf install docker-compose-plugin`

Use this SSM repair command:

```bash
REPAIR_COMMAND_ID="$(aws ssm send-command \
  --region "${AWS_REGION}" \
  --instance-ids "${INSTANCE_ID}" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=[
    "set -euo pipefail",
    "sudo dnf update -y",
    "sudo dnf install -y docker jq tar gzip unzip awscli",
    "sudo install -d -m 0755 /usr/local/libexec/docker/cli-plugins",
    "sudo curl -fsSL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 -o /usr/local/libexec/docker/cli-plugins/docker-compose",
    "sudo chmod 0755 /usr/local/libexec/docker/cli-plugins/docker-compose",
    "sudo ln -sfn /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose",
    "sudo systemctl enable --now docker",
    "sudo systemctl enable --now amazon-ssm-agent || true",
    "docker --version",
    "docker compose version",
    "docker-compose --version"
  ]' \
  --query 'Command.CommandId' \
  --output text)"

aws ssm get-command-invocation \
  --region "${AWS_REGION}" \
  --command-id "${REPAIR_COMMAND_ID}" \
  --instance-id "${INSTANCE_ID}" \
  --output json
```

If you want to inspect bootstrap failure logs:

```bash
aws ssm start-session \
  --region "${AWS_REGION}" \
  --target "${INSTANCE_ID}"
```

Then on the instance:

```bash
sudo journalctl -u cloud-final --no-pager -n 200
sudo tail -n 200 /var/log/cloud-init-output.log
```

## 14. Trigger the first deploy

The application deploy flow is:

1. push to `main`
2. `Evaluation` runs
3. if `Evaluation` succeeds, `Deploy Production` runs automatically

To trigger a deploy without changing code:

```bash
git checkout main
git pull origin main
git commit --allow-empty -m "Trigger production deploy"
git push origin main
```

## 15. Watch the GitHub Actions runs

Watch the `Evaluation` workflow:

```bash
gh run list --repo "${GH_REPO}" --workflow eval.yml --limit 5

EVAL_RUN_ID="$(gh run list \
  --repo "${GH_REPO}" \
  --workflow eval.yml \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')"

gh run watch "${EVAL_RUN_ID}" --repo "${GH_REPO}"
```

Then watch the deploy workflow:

```bash
DEPLOY_RUN_ID=""
until [ -n "${DEPLOY_RUN_ID}" ] && [ "${DEPLOY_RUN_ID}" != "null" ]; do
  DEPLOY_RUN_ID="$(gh run list \
    --repo "${GH_REPO}" \
    --workflow deploy-prod.yml \
    --limit 1 \
    --json databaseId \
    --jq '.[0].databaseId')"
  sleep 10
done

gh run watch "${DEPLOY_RUN_ID}" --repo "${GH_REPO}"
```

If a workflow fails:

```bash
gh run view "${EVAL_RUN_ID}" --repo "${GH_REPO}" --log
gh run view "${DEPLOY_RUN_ID}" --repo "${GH_REPO}" --log
```

## 16. Test the live deployment

### 16.1 Public checks

```bash
curl -I "http://${ELASTIC_IP}/"
curl "http://${ELASTIC_IP}/healthz"
```

Expected result:

- `http://${ELASTIC_IP}/` returns the Streamlit app
- `http://${ELASTIC_IP}/healthz` returns the MedRAG health payload

### 16.2 Remote runtime checks through SSM

```bash
COMMAND_ID="$(aws ssm send-command \
  --region "${AWS_REGION}" \
  --instance-ids "${INSTANCE_ID}" \
  --document-name AWS-RunShellScript \
  --parameters 'commands=[
    "curl -fsS http://127.0.0.1:8000/health",
    "sudo docker compose --env-file /opt/medrag/runtime/app.env -f /opt/medrag/app/current/docker-compose.prod.yml ps"
  ]' \
  --query 'Command.CommandId' \
  --output text)"

aws ssm get-command-invocation \
  --region "${AWS_REGION}" \
  --command-id "${COMMAND_ID}" \
  --instance-id "${INSTANCE_ID}" \
  --output json
```

### 16.3 Interactive SSM session if needed

```bash
aws ssm start-session \
  --region "${AWS_REGION}" \
  --target "${INSTANCE_ID}"
```

Then on the instance:

```bash
cd /opt/medrag/app/current
sudo docker compose --env-file /opt/medrag/runtime/app.env -f docker-compose.prod.yml ps
sudo docker compose --env-file /opt/medrag/runtime/app.env -f docker-compose.prod.yml logs --tail=200
```

## 17. Normal redeploy flow

After the first deployment:

1. merge to `main`
2. `Evaluation` runs
3. `Deploy Production` runs automatically if evaluation is green

Useful commands:

```bash
gh run list --repo "${GH_REPO}" --workflow eval.yml --limit 5
gh run list --repo "${GH_REPO}" --workflow deploy-prod.yml --limit 5
```

## 18. Optional: run infrastructure from GitHub Actions

Only do this if `AWS_BOOTSTRAP_ROLE_ARN` is set to an external bootstrap/admin role.

```bash
gh workflow run infrastructure.yml --repo "${GH_REPO}"

INFRA_RUN_ID="$(gh run list \
  --repo "${GH_REPO}" \
  --workflow infrastructure.yml \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')"

gh run watch "${INFRA_RUN_ID}" --repo "${GH_REPO}"
```

## 19. Destroy everything completely

### 19.1 Preferred destroy path: local AWS CLI admin credentials

This is the safest path and the one that recovered the real failed destroy cleanly:

```bash
bash scripts/destroy-prod.sh \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --confirm DESTROY_MEDRAG_PROD
```

Notes:

- if the script prints `InvalidInstanceId` during the SSM teardown step, that is usually harmless and means the EC2 instance was already terminated
- if the stack was partially deleted earlier, rerunning this script from stable local admin credentials usually completes the cleanup

### 19.2 Optional destroy path: GitHub workflow

Use this only if:

- `AWS_BOOTSTRAP_ROLE_ARN` is configured
- it points to an external role not created by `medrag-prod`
- it is not equal to `AWS_ROLE_ARN`

Trigger:

```bash
gh workflow run destroy-prod.yml \
  --repo "${GH_REPO}" \
  -f confirmation=DESTROY_MEDRAG_PROD
```

Watch:

```bash
DESTROY_RUN_ID="$(gh run list \
  --repo "${GH_REPO}" \
  --workflow destroy-prod.yml \
  --limit 1 \
  --json databaseId \
  --jq '.[0].databaseId')"

gh run watch "${DESTROY_RUN_ID}" --repo "${GH_REPO}"
```

## 20. Verify the environment is gone

These should fail or return empty after a full destroy:

```bash
aws cloudformation describe-stacks \
  --region "${AWS_REGION}" \
  --stack-name "${STACK_NAME}"

aws ecr describe-repositories \
  --region "${AWS_REGION}" \
  --repository-names "${PROJECT_SLUG}-app"

aws secretsmanager describe-secret \
  --region "${AWS_REGION}" \
  --secret-id "${SECRET_NAME}"

aws s3api head-bucket \
  --region "${AWS_REGION}" \
  --bucket "${DEPLOY_BUCKET_NAME}"
```

If you captured `ELASTIC_IP`, you can verify it is gone too:

```bash
aws ec2 describe-addresses \
  --region "${AWS_REGION}" \
  --public-ips "${ELASTIC_IP}"
```

## 21. Troubleshooting

### AWS CLI says `AuthFailure`, `InvalidClientTokenId`, or `security token included in the request is invalid`

Check:

```bash
aws sts get-caller-identity
aws configure list
env | grep '^AWS_'
```

Do not continue until `aws sts get-caller-identity` works.

### VPC and subnet commands open a pager

Set:

```bash
export AWS_PAGER=""
```

### EC2 is `Online` in SSM but deploy fails with `Missing required command: docker`

That means instance bootstrap did not finish correctly. The known cause on Amazon Linux 2023 is trying to install `docker-compose-plugin` from `dnf`.

Use section 13 and repair the instance. The current bootstrap in this repo already uses the working Compose installation method.

### First deploy fails even though the instance exists

Before retrying, always verify:

```bash
docker --version
docker compose version
docker-compose --version
```

through SSM as shown in section 12.

### Destroy fails with `DELETE_FAILED` and `The security token included in the request is invalid`

This means destroy was run with the stack-managed `AWS_ROLE_ARN`, or a workflow used credentials tied to a role that the stack was deleting.

Fix:

1. make sure `AWS_BOOTSTRAP_ROLE_ARN` is external and not equal to `AWS_ROLE_ARN`
2. rerun destroy locally with stable AWS CLI admin credentials:

```bash
bash scripts/destroy-prod.sh \
  --stack-name "${STACK_NAME}" \
  --region "${AWS_REGION}" \
  --confirm DESTROY_MEDRAG_PROD
```

In our real teardown, the second pass succeeded because most resources had already been deleted.

### UI opens but the app is not ready

Usually:

- indexing is still running
- or indexing failed on the instance

Inspect:

```bash
aws ssm start-session \
  --region "${AWS_REGION}" \
  --target "${INSTANCE_ID}"
```

Then:

```bash
sudo docker compose --env-file /opt/medrag/runtime/app.env -f /opt/medrag/app/current/docker-compose.prod.yml logs indexer api qdrant
```

## 22. Shortest known-working path

If you just want the shortest operator sequence that we know works:

1. set the environment variables from sections 4 and 5
2. verify AWS CLI with `aws sts get-caller-identity`
3. deploy the stack locally with the AWS CLI command from section 8
4. capture stack outputs from section 9
5. set GitHub deploy variables and repo secrets from sections 10 and 11
6. verify SSM, Docker, and Compose from section 12
7. push to `main`
8. watch `eval.yml` and `deploy-prod.yml`
9. test `http://${ELASTIC_IP}/` and `http://${ELASTIC_IP}/healthz`
10. when done, destroy locally with `bash scripts/destroy-prod.sh --stack-name "${STACK_NAME}" --region "${AWS_REGION}" --confirm DESTROY_MEDRAG_PROD`

That is the cleanest end-to-end path for this repository.
