set -e

TF_PROJECT_ID={TF_PROJECT_ID}
DM_PROJECT_ID={DM_PROJECT_ID}
KRM_PROJECT_ID={KRM_PROJECT_ID}

# Create DM resources
gcloud config set project $DM_PROJECT_ID

#Authentication
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

gcloud services enable deploymentmanager.googleapis.com
gcloud deployment-manager deployments create d1 --config pubsub.yaml

# Create Terraform resources
pushd alternatives/tf
gcloud config set project $TF_PROJECT_ID

#Authentication
gcloud auth application-default login
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/application_default_credentials.json

# Initialize Terraform and apply resources
terraform init
terraform plan -var="deployment=d1" -var="project_id=${TF_PROJECT_ID}"
terraform apply -auto-approve -var="deployment=d1" -var="project_id=${TF_PROJECT_ID}"
popd

# KCC Configuration
gcloud config set project $KRM_PROJECT_ID
cp -R alternatives/krm /tmp/krm_${KRM_PROJECT_ID}
kpt cfg set . PUBSUB my-pubsub
pushd /tmp/krm_${KRM_PROJECT_ID}
kubectl apply -f pubsub.yaml
kubectl  wait --for=condition=Ready PubSubSubscription --all
popd
rm -rf krm_${KRM_PROJECT_ID}


# Export DM and TF resources for comparison
gcloud pubsub subscriptions list --filter="labels.goog-dm:d1" --project $DM_PROJECT_ID | sed "s/${DM_PROJECT_ID}/PROJECT/" > /tmp/dm.yaml

gcloud pubsub subscriptions list --filter="labels.goog-dm:d1" --project $TF_PROJECT_ID | sed "s/${TF_PROJECT_ID}/PROJECT/"  > /tmp/tf.yaml

gcloud pubsub subscriptions list --filter="labels.goog-dm:d1" --project $KRM_PROJECT_ID | sed "s/${KRM_PROJECT_ID}/PROJECT/" | sed "s/creationTime: .*/creationTime: TIME/" | sed "/cnrm-lease-.*/d" | sed "/managed-by-cnrm.*/d"  > /tmp/krm.yaml


if [[ $(diff /tmp/dm.yaml /tmp/tf.yaml) ]]; then
    echo "TF and DM outputs are NOT identical"
    exit 1
else
    echo "TF and DM outputs are identical"
fi

if [[ $(diff /tmp/dm.yaml /tmp/krm.yaml) ]]; then
    echo "KRM and DM outputs are NOT identical"
    exit 1
else
    echo "KRM and DM outputs are identical"
fi

exit 0
