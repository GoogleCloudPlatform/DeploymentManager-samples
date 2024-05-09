#!/usr/bin/env bats

source tests/helpers.bash

TEST_NAME=$(basename "${BATS_TEST_FILENAME}" | cut -d '.' -f 1)

# Create a random 10-char string and save it in a file.
RANDOM_FILE="/tmp/${CLOUD_FOUNDATION_ORGANIZATION_ID}-${TEST_NAME}.txt"
if [[ ! -e "${RANDOM_FILE}" ]]; then
    RAND=$(head /dev/urandom | LC_ALL=C tr -dc a-z0-9 | head -c 10)
    echo ${RAND} > "${RANDOM_FILE}"
fi

# Set variables based on the random string saved in the file.
# envsubst requires all variables used in the example/config to be exported.
if [[ -e "${RANDOM_FILE}" ]]; then
    export RAND=$(cat "${RANDOM_FILE}")
    DEPLOYMENT_NAME="${CLOUD_FOUNDATION_PROJECT_ID}-${TEST_NAME}-${RAND}"
    # Replace underscores with dashes in the deployment name.
    DEPLOYMENT_NAME=${DEPLOYMENT_NAME//_/-}
    CONFIG=".${DEPLOYMENT_NAME}.yaml"
fi

########## HELPER FUNCTIONS ##########

function create_config() {
    echo "Creating ${CONFIG}"
    envsubst < "templates/cloud_nat/tests/integration/${TEST_NAME}.yaml" > "${CONFIG}"
}

function delete_config() {
    echo "Deleting ${CONFIG}"
    rm -f "${CONFIG}"
}

function setup() {
    # Global setup; executed once per test file.
    if [ ${BATS_TEST_NUMBER} -eq 1 ]; then
        gcloud compute networks create network-${RAND} \
            --project "${CLOUD_FOUNDATION_PROJECT_ID}" \
            --description "integration test ${RAND}" \
            --subnet-mode custom
        gcloud compute addresses create ip-${RAND} \
            --region us-east1 \
            --project "${CLOUD_FOUNDATION_PROJECT_ID}" 
        create_config
    fi

  # Per-test setup steps.
  }

function teardown() {
    # Global teardown; executed once per test file.
    if [[ "$BATS_TEST_NUMBER" -eq "${#BATS_TEST_NAMES[@]}" ]]; then
        gcloud compute networks delete network-${RAND} \
            --project "${CLOUD_FOUNDATION_PROJECT_ID}" -q
        gcloud compute addresses delete ip-${RAND} -q --region us-east1
        rm -f "${RANDOM_FILE}"
        delete_config
    fi

    # Per-test teardown steps.
}


@test "Creating deployment ${DEPLOYMENT_NAME} from ${CONFIG}" {
    gcloud deployment-manager deployments create "${DEPLOYMENT_NAME}" \
        --config ${CONFIG} \
        --project "${CLOUD_FOUNDATION_PROJECT_ID}"
}

@test "Verifying that NATS were created in deployment ${DEPLOYMENT_NAME}" {
    run gcloud compute routers nats describe nat-"${RAND}" --router=cloud-nat-"${RAND}" --region=us-east1 --project "${CLOUD_FOUNDATION_PROJECT_ID}"
    echo '---Verification Output Start---'
    echo "$output"
    echo '---Verification Output Complete---'
    [[ "$output" =~ "icmpIdleTimeoutSec: 60" ]]
    [[ "$output" =~ "minPortsPerVm: 96" ]]
    [[ "$output" =~ "name: nat-${RAND}" ]]
    [[ "$output" =~ "tcpEstablishedIdleTimeoutSec: 1140" ]]
    [[ "$output" =~ "tcpTransitoryIdleTimeoutSec: 60" ]]
    [[ "$output" =~ "udpIdleTimeoutSec: 55" ]]
    [[ "$output" =~ "/regions/us-east1/addresses/ip-${RAND}" ]]
}

@test "Deleting deployment" {
    gcloud deployment-manager deployments delete "${DEPLOYMENT_NAME}" \
        --project "${CLOUD_FOUNDATION_PROJECT_ID}" -q

    run gcloud compute nats list --project "${CLOUD_FOUNDATION_PROJECT_ID}"
    [[ ! "$output" =~ "name: cloud-nat-${RAND}" ]]
}
