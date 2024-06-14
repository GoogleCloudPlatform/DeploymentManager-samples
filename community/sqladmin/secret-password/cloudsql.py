def generate_config(context):
    env = context.env
    properties = context.properties

    project = env['project']
    ID = env['deployment'] + '-' + env['name']

    read_password = {
        'name': '{ID}-user-password'.format(ID=ID),
        'action': (
            'gcp-types/runtimeconfig-v1beta1:runtimeconfig.projects.configs.variables.get'
        ),
        'properties': {
            'name': (
                'projects/{project}/configs/{config_name}/variables/{pwd_name}'.format(
                    project=project,
                    config_name=properties['dbUser']['configName'],
                    pwd_name=properties['dbUser']['passwordVariable'],
                )
            ),
        },
        'metadata': {
            'runtimePolicy': ['UPDATE_ALWAYS'],
        },
    }

    instance = {
        'name': '{ID}-master'.format(ID=ID),
        'type': 'sqladmin.v1beta4.instance',
        'properties': {
            'name': env['name'],
            'databaseVersion': 'POSTGRES_12',
            'settings': {
                'tier': 'db-g1-small',
                'storageAutoResize': True,
            },
        },
    }

    database = {
        'name': '{ID}-db'.format(ID=ID),
        'type': 'sqladmin.v1beta4.database',
        'properties': {
            'name': properties['dbUser']['user'],
            'charset': 'utf8',
            'instance': '$(ref.{}.name)'.format(
                instance['name'],
            ),
        },
    }

    user = {
        'name': '{ID}-db-user'.format(ID=ID),
        'type': 'sqladmin.v1beta4.user',
        'properties': {
            'name': properties['dbUser']['user'],
            'password': '$(ref.{}.text)'.format(
                read_password['name'],
            ),
            'instance': '$(ref.{}.name)'.format(
                instance['name'],
            ),
        },
        'metadata': {
            'dependsOn': [
                database['name'],
            ]
        },
    }

    return {
        "resources": [
            read_password,
            instance,
            database,
            user,
        ],
    }
