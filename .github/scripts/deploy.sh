#!/bin/bash
set -e

SERVICE=${1:-video-processing}
DPM_IMAGE=$2
NLB_TARGET_GROUP_ARN=$3
DEFAULT_REGION=$4

# Install AWS CLI v2 if not already installed
if [ ! -f /usr/local/bin/aws ]; then
  echo "Installing AWS CLI v2..."
  cd /tmp
  curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
  unzip -q awscliv2.zip
  sudo ./aws/install
  rm -rf aws awscliv2.zip
  cd -
fi

# Use AWS CLI v2
export PATH=/usr/local/bin:$PATH

aws eks update-kubeconfig --region $DEFAULT_REGION --name $SERVICE-eks-cluster --alias $SERVICE

TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

for manifest in cfm_database.yaml svc_app.yaml dpm_app.yaml hpa_app.yaml nlb_tgb.yaml; do
  echo "Deploying $manifest..."
  sed \
    -e "s|\${dpm_name}|dpm-${SERVICE}|g" \
    -e "s|\${cfm_name}|cfm-database-${SERVICE}|g" \
    -e "s|\${dpm_image}|${DPM_IMAGE}|g" \
    -e "s|\${load_balancer_name}|svc-app-lb-${SERVICE}|g" \
    -e "s|\${target_group_arn}|${NLB_TARGET_GROUP_ARN}|g" \
    -e "s|\${tgb_name}|tgb-${SERVICE}|g" \
    -e "s|\${hpa_name}|hpa-app-${SERVICE}|g" \
    -e "s|\${region}|${DEFAULT_REGION}|g" \
    "/home/ec2-user/manifests/$manifest" | kubectl apply --validate=false -f -
done

rm -rf $TEMP_DIR
