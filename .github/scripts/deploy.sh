#!/bin/bash
set -e

SERVICE=${1:-video-processing}
DPM_IMAGE=$2
NLB_TARGET_GROUP_ARN=$3
DEFAULT_REGION=$4

aws eks update-kubeconfig --region $DEFAULT_REGION --name $SERVICE-eks-cluster --alias $SERVICE

TEMP_DIR=$(mktemp -d)
cd $TEMP_DIR

for manifest in cfm_database.yaml sec_app.yaml svc_app.yaml dpm_app.yaml hpa_app.yaml nlb_tgb.yaml; do
  echo "Deploying $manifest..."
  sed \
    -e "s|\${dpm_name}|dpm-${SERVICE}|g" \
    -e "s|\${cfm_name}|cfm-database-${SERVICE}|g" \
    -e "s|\${sec_name}|sec-app-${SERVICE}|g" \
    -e "s|\${app_sec_name}|sec-app-${SERVICE}|g" \
    -e "s|\${dpm_image}|${DPM_IMAGE}|g" \
    -e "s|\${load_balancer_name}|svc-app-lb-${SERVICE}|g" \
    -e "s|\${target_group_arn}|${NLB_TARGET_GROUP_ARN}|g" \
    -e "s|\${tgb_name}|tgb-${SERVICE}|g" \
    -e "s|\${hpa_name}|hpa-app-${SERVICE}|g" \
    -e "s|\${region}|${DEFAULT_REGION}|g" \
    "/home/ec2-user/manifests/$manifest" | kubectl apply --insecure-skip-tls-verify --validate=false -f -
done

rm -rf $TEMP_DIR
