""" This template creates a Cloud NAT. """
MIN_PORTS_PER_VM = 64
UDP_IDLE_TIMEOUT_SEC = 30
ICMP_IDLE_TIMEOUT_SEC = 30
TCP_ESTABLISHED_IDLE_TIMEOUT_SEC = 1200
TCP_TRANSITORY_IDLE_TIMEOUT_SEC = 30

def get_nat_ip_option_enum(natips):
    """ Returns one of the two supported Enum for Nat IP Option
        AUTO_ONLY or MANUAL_ONLY """
    if natips:
        return 'MANUAL_ONLY'
    return 'AUTO_ONLY'

def generate_config(context):
    """ Entry point for the deployment resources. """

    name = context.properties.get('name', context.env['name'])

    resources = [
        {
            'name': context.env['name'],
            # compute.v1.router seems to be doing the job though
            # doc says compute.beta has the NAT feature.
            'type': 'compute.v1.router',
            'properties':
                {
                    'name':
                        name,
                    'network':
                        generate_network_url(
                            context,
                            context.properties['network']
                        ),
                    'region':
                        context.properties['region'],
                    'nats':
                    [{
                        'name': name,
                        # Force using All subnet all primary IP range by default
                        # Force using one of the two enums below:
                        # ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES and
                        # ALL_SUBNETWORKS_ALL_IP_RANGES
                        'sourceSubnetworkIpRangesToNat': context.properties.get(
                            'sourceSubnetworkIpRangesToNat',
                            'ALL_SUBNETWORKS_ALL_PRIMARY_IP_RANGES'),
                        'natIps': context.properties.get('natIps', []),
                        'natIpAllocateOption': get_nat_ip_option_enum(
                            context.properties.get('natIps')),
                        # A min of 64, anything below will
                        # still be translated to 64 ports
                        'minPortsPerVm': context.properties.get(
                            'minPortsPerVm', MIN_PORTS_PER_VM),
                        'udpIdleTimeoutSec': context.properties.get(
                            'udpIdleTimeoutSec', UDP_IDLE_TIMEOUT_SEC),
                        'icmpIdleTimeoutSec': context.properties.get(
                            'icmpIdleTimeoutSec', ICMP_IDLE_TIMEOUT_SEC),
                        'tcpEstablishedIdleTimeoutSec': context.properties.get(
                            'tcpEstablishedIdleTimeoutSec',
                            TCP_ESTABLISHED_IDLE_TIMEOUT_SEC),
                        'tcpTransitoryIdleTimeoutSec': context.properties.get(
                            'tcpTransitoryIdleTimeoutSec',
                            TCP_TRANSITORY_IDLE_TIMEOUT_SEC)
                    }]
                }
        }
    ]

    return {
        'resources':
            resources,
        'outputs':
            [
                {
                    'name': 'name',
                    'value': name
                },
                {
                    'name': 'selfLink',
                    'value': '$(ref.' + context.env['name'] + '.selfLink)'
                },
                {
                    'name':
                        'nats',
                    'value':
                        '$(ref.' + context.env['name'] + '.nats)'
                }
            ]
    }


def generate_network_url(context, network):
    """Format the resource name as a resource URI."""

    return 'projects/{}/global/networks/{}'.format(
        context.env['project'],
        network
    )
