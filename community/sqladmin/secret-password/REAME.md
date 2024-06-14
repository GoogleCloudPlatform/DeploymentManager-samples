# Cloud SQL Example

## Avoid keep passwords on yaml files

It differs from the [cloudsql example](https://github.com/GoogleCloudPlatform/deploymentmanager-samples/tree/master/examples/v2/cloudsql)
by not storing the user password into the yaml file. It uses a
[runtame configurator](https://cloud.google.com/deployment-manager/runtime-configurator)
variable to store it.

This allows to commit the yaml file to a git repository without
the password on plain text on it.

## Setup

- create a config

```
gcloud beta runtime-config configs example-cloudsql-config
```
- create the variable containing the password

```
gcloud beta runtime-config configs variables set \
    username/root \
    "secret" \
    --config-name example-cloudsql-config \
    --is-text
```


## More information

[Cloud SQL Documentation](https://cloud.google.com/sql/docs/)

[Creating and Deleting RuntimeConfig Resources](https://cloud.google.com/deployment-manager/runtime-configurator/create-and-delete-runtimeconfig-resources)

[Cloud Runtime Configuration API](https://cloud.google.com/deployment-manager/runtime-configurator/reference/rest)

[gcloud beta runtime-config](https://cloud.google.com/sdk/gcloud/reference/beta/runtime-config)
