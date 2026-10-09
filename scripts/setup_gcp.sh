#!/usr/bin/env bash
# Creates a dedicated GCP project for this experiment and wires it to the local repo.
# Prerequisite: Google Cloud CLI installed and logged in (`gcloud auth login`).
set -euo pipefail

# ---- Edit these -------------------------------------------------------------
PROJECT_ID="text2sql-sem-ablation-$(date +%m%d)"   # must be globally unique, 6-30 chars
PROJECT_NAME="Text2SQL Ablation"
BILLING_ACCOUNT_ID=""                          # optional; see `gcloud billing accounts list`
BUDGET_USD=5                                    # budget alert threshold (needs billing)
LOCATION="US"                                  # BigQuery dataset location
DATASET="bird_eval"
# ------------------------------------------------------------------------------

echo ">> Creating project ${PROJECT_ID}"
gcloud projects create "${PROJECT_ID}" --name="${PROJECT_NAME}"
gcloud config set project "${PROJECT_ID}"

if [[ -n "${BILLING_ACCOUNT_ID}" ]]; then
  echo ">> Linking billing account"
  gcloud billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT_ID}"

  echo ">> Creating a budget alert of ${BUDGET_USD} USD"
  gcloud billing budgets create \
    --billing-account="${BILLING_ACCOUNT_ID}" \
    --display-name="${PROJECT_ID}-budget" \
    --budget-amount="${BUDGET_USD}USD" \
    --filter-projects="projects/${PROJECT_ID}" \
    --threshold-rule=percent=0.5 \
    --threshold-rule=percent=0.9 \
    --threshold-rule=percent=1.0 || echo "!! Budget creation failed; set one in the console."
else
  echo "!! No billing account set. BigQuery sandbox limits apply, and data agents may not be available."
fi

echo ">> Enabling APIs"
gcloud services enable \
  bigquery.googleapis.com \
  aiplatform.googleapis.com \
  geminidataanalytics.googleapis.com \
  cloudaicompanion.googleapis.com

echo ">> Application Default Credentials for local code"
gcloud auth application-default login
gcloud auth application-default set-quota-project "${PROJECT_ID}"

echo ">> Creating BigQuery dataset ${DATASET}"
bq --location="${LOCATION}" mk --dataset "${PROJECT_ID}:${DATASET}" || true

echo ">> Writing .env"
if [[ ! -f .env ]]; then cp .env.example .env; fi
sed -i.bak "s/^GCP_PROJECT_ID=.*/GCP_PROJECT_ID=${PROJECT_ID}/" .env && rm -f .env.bak

cat <<EOF

Done. Recommended manual step:
  Console > IAM & Admin > Quotas > BigQuery API > "Query usage per day"
  set a low cap (e.g. 100 GiB) for project ${PROJECT_ID}.
EOF
