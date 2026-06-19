#!/usr/bin/env bash
# Deploy FinPilot to AWS from scratch.
# Usage: ./scripts/deploy.sh [staging|production]
# Requires: AWS CLI + credentials, Terraform >= 1.7, Docker (for image build+push)
#
# Typical full deploy: ~12–18 min
#   - terraform apply (VPC+RDS+ElastiCache+ECS+ALB): ~10–14 min
#   - ECS image pull + service stabilization: ~2–4 min
set -euo pipefail

ENV="${1:-staging}"
REGION="ap-south-1"
START=$(date +%s)

echo "==> FinPilot deploy: ${ENV} (region: ${REGION})"

# 1. Validate terraform before touching AWS
cd infra/terraform
terraform init -reconfigure -backend-config="key=finpilot/${ENV}/terraform.tfstate"
terraform validate
terraform fmt -check

# 2. Build + push Docker images
ECR_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR_BACKEND="${ECR_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/finpilot-backend"
ECR_FRONTEND="${ECR_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com/finpilot-frontend"

aws ecr get-login-password --region "${REGION}" | \
  docker login --username AWS --password-stdin "${ECR_ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"

GIT_SHA=$(git rev-parse --short HEAD)

docker build -t "${ECR_BACKEND}:${GIT_SHA}" -t "${ECR_BACKEND}:latest" backend/
docker push "${ECR_BACKEND}:${GIT_SHA}"
docker push "${ECR_BACKEND}:latest"

docker build -t "${ECR_FRONTEND}:${GIT_SHA}" -t "${ECR_FRONTEND}:latest" frontend/
docker push "${ECR_FRONTEND}:${GIT_SHA}"
docker push "${ECR_FRONTEND}:latest"

# 3. Apply infrastructure
terraform plan \
  -out=tfplan \
  -var="environment=${ENV}" \
  -var="backend_image=${ECR_BACKEND}:${GIT_SHA}" \
  -var="frontend_image=${ECR_FRONTEND}:${GIT_SHA}"

terraform apply -auto-approve tfplan

# 4. Wait for ECS to stabilize
echo "==> Waiting for ECS service to become stable..."
aws ecs wait services-stable \
  --cluster "finpilot-${ENV}" \
  --services "finpilot-backend-${ENV}" \
  --region "${REGION}"

# 5. Run DB migrations inside the container
CLUSTER="finpilot-${ENV}"
TASK_DEF="finpilot-backend-${ENV}"
SUBNETS=$(aws ecs describe-services \
  --cluster "${CLUSTER}" --services "${TASK_DEF}" \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.subnets' \
  --output text)
SG=$(aws ecs describe-services \
  --cluster "${CLUSTER}" --services "${TASK_DEF}" \
  --query 'services[0].networkConfiguration.awsvpcConfiguration.securityGroups[0]' \
  --output text)

aws ecs run-task \
  --cluster "${CLUSTER}" \
  --task-definition "${TASK_DEF}" \
  --launch-type FARGATE \
  --overrides '{"containerOverrides":[{"name":"backend","command":["alembic","upgrade","head"]}]}' \
  --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS}],securityGroups=[${SG}],assignPublicIp=DISABLED}" \
  --region "${REGION}"

# 6. Smoke test
API_URL=$(terraform output -raw alb_dns_name)
echo "==> Smoke testing https://${API_URL}/health ..."
for i in $(seq 1 10); do
  if curl -sf "https://${API_URL}/health" | grep -q '"status"'; then
    echo "    Health check OK"
    break
  fi
  sleep 5
done

# 7. Report timing
ELAPSED=$(( $(date +%s) - START ))
echo ""
echo "==> Deploy complete: ${ELAPSED}s ($(( ELAPSED / 60 ))m $(( ELAPSED % 60 ))s)"
if [ "${ELAPSED}" -gt 1800 ]; then
  echo "WARN: exceeded 30-minute target"
else
  echo "PASS: within 30-minute target"
fi
