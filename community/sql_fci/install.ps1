#Copyright 2017 Google, Inc.  All Rights Reserved.

<#
.SYNOPSIS
    script to set up nodes in an SQL FCI deployment.
.DESCRIPTION
    This script will perform the setup required to run an SQL FCI
    deployment based on the metadata. There are 3 roles with different
    (but overlapping) setup processes.
        AD: Active Directory controller
        Master: The first cluster node. This node will be used to install the
                Fail over cluster and enable S2D
        Cluster: All other cluster nodes.
#>


function WaitFor-Agent {
    <#
    .SYNOPSIS
        Wait for the windows agent to come up so that we can access
        the metadata
    #>
    $expire_time = (Get-Date) + (New-TimeSpan -Seconds 120)
    while (!(Get-Process GCEWindowsAgent -ErrorAction SilentlyContinue)) {
        if ((Get-Date) -gt $expire_time) {
            Write-Error 'Windows Agent failed to start.'
        }
        Write-Host 'Waiting for windows agent...'
        Start-Sleep 5
    }
}


# We are using the fact that the agent is running to signal that windows
# has booted up to the point of running services, implying that updates
# are finished.
WaitFor-Agent


# Define constants here.
$script:run_time_base = 'https://runtimeconfig.googleapis.com/v1beta1'
$script:domain_mode = 'Win2012R2'
$script:forest_mode = 'Win2012R2'
$script:access_token_path = 'C:\Program Files\Google\Compute Engine\access_token.txt'
$script:addsforest_flag = 'C:\Program Files\Google\Compute Engine\adds_forest_install.txt'
$script:joined_flag = 'C:\Program Files\Google\Compute Engine\domain_joined.txt'
$script:complete_flag = 'C:\Program Files\Google\Compute Engine\SQLFCI_set_up_complete.txt'
$script:volume_location = 'C:\ClusterStorage\Volume1'


function Get-Metadata {
    <#
    .SYNOPSIS
        Retrieve metadata from the path specified.
    .DESCRIPTION
        Retrieve metadata from the path specified. The metadata could
        come as either an array of bytes, or a string. In case it is
        an array of bytes, convert it to a string before returning.
    #>
    param (
        [Parameter(Mandatory=$true)]
        $Path
    )

    $metadata_base_url = 'http://metadata.google.internal/computeMetadata/v1/'
    $content = (Invoke-WebRequest -Uri "${metadata_base_url}${Path}" `
                                  -Headers @{'Metadata-Flavor'='Google'} `
                                  -UseBasicParsing).content
    if ($content -is [System.Array]) {
        return [System.Text.Encoding]::ASCII.GetString($content)
    }
    else {
        return $content
    }
}


# Gather the necessary data from the metadata.
$script:safe_mode_password = Get-Metadata -Path 'instance/attributes/safe-password'
$script:ad_url= Get-Metadata -Path 'instance/attributes/create-domain-config-url'
$script:join_domain_url = Get-Metadata -Path 'instance/attributes/join-domain-config-url'
$script:create_cluster_url = Get-Metadata -Path 'instance/attributes/create-cluster-config-url'
$script:install_fci_url = Get-Metadata -Path 'instance/attributes/install-fci-config-url'
$script:domain = Get-Metadata -Path 'instance/attributes/ad-domain'
$script:domain_netbios = Get-Metadata -Path 'instance/attributes/domain-netbios'
$script:is_ad_node = Get-Metadata -Path 'instance/attributes/is-ad-node'
$script:is_master = Get-Metadata -Path 'instance/attributes/is-master'
$script:ad_node_ip = Get-Metadata -Path 'instance/attributes/ad-node-ip'
$script:service_account = Get-Metadata -Path 'instance/attributes/service-account'
$script:service_password = Get-Metadata -Path 'instance/attributes/service-password'
$script:node_name = Get-Metadata -Path 'instance/attributes/my-node-name'
$script:ad_node_name = Get-Metadata -Path 'instance/attributes/ad-node-name'
$script:all_nodes = Get-Metadata -Path 'instance/attributes/all-nodes'
$script:cluster_ip = Get-Metadata -Path 'instance/attributes/cluster-ip'
$script:application_ip = Get-Metadata -Path 'instance/attributes/application-ip'
$script:zone = Get-Metadata -Path 'instance/attributes/zone'
$script:instance_group = Get-Metadata -Path 'instance/attributes/instance-group'
$script:health_check_port= Get-Metadata -Path 'instance/attributes/wsfc-agent-port'
$script:is_test = Get-Metadata -Path 'instance/attributes/is-test'

$ErrorActionPreference = 'Stop'

# Interpolated string that will be used as the SQL config file on the
# master node
$script:sql_ini_master =  @"
;SQL Server 2016 Configuration File
[OPTIONS]

; Specifies a Setup work flow, like INSTALL, UNINSTALL, or UPGRADE. This is a required parameter.

ACTION="InstallFailoverCluster"

; Specifies that SQL Server Setup should not display the privacy statement when ran from the command line.

SUPPRESSPRIVACYSTATEMENTNOTICE="False"

; By specifying this parameter and accepting Microsoft R Open and Microsoft R Server terms, you acknowledge that you have read and understood the terms of use.

IACCEPTROPENLICENSETERMS="True"
IAcceptSQLServerLicenseTerms="True"

; Use the /ENU parameter to install the English version of SQL Server on your localized Windows operating system.

ENU="True"

; Setup will not display any user interface.

QUIET="True"

; Specify whether SQL Server Setup should discover and include product updates. The valid values are True and False or 1 and 0. By default SQL Server Setup will include updates that are found.

UpdateEnabled="True"

; If this parameter is provided, then this computer will use Microsoft Update to check for updates.

USEMICROSOFTUPDATE="False"

; Specifies features to install, uninstall, or upgrade. The list of top-level features include SQL, AS, RS, IS, MDS, and Tools. The SQL feature will install the Database Engine, Replication, Full-Text, and Data Quality Services (DQS) server. The Tools feature will install shared components.

FEATURES=SQLENGINE,REPLICATION,FULLTEXT,DQ

; Specify the location where SQL Server Setup will obtain product updates. The valid values are "MU" to search Microsoft Update, a valid folder path, a relative path such as .\MyUpdates or a UNC share. By default SQL Server Setup will search Microsoft Update or a Windows Update service through the Window Server Update Services.

UpdateSource="MU"

; Displays the command line parameters usage

HELP="False"

; Specifies that the detailed Setup log should be piped to the console.

INDICATEPROGRESS="False"

; Specifies that Setup should install into WOW64. This command line argument is not supported on an IA64 or a 32-bit system.

X86="False"

; Specify a default or named instance. MSSQLSERVER is the default instance for non-Express editions and SQLExpress for Express editions. This parameter is required when installing the SQL Server Database Engine (SQL), Analysis Services (AS), or Reporting Services (RS).

INSTANCENAME="MSSQLSERVER"

; Specify the root installation directory for shared components.  This directory remains unchanged after shared components are already installed.

INSTALLSHAREDDIR="C:\Program Files\Microsoft SQL Server"

; Specify the root installation directory for the WOW64 shared components.  This directory remains unchanged after WOW64 shared components are already installed.

INSTALLSHAREDWOWDIR="C:\Program/ Files (x86)\Microsoft SQL Server"

; Specify the Instance ID for the SQL Server features you have specified. SQL Server directory structure, registry structure, and service names will incorporate the instance ID of the SQL Server instance.

INSTANCEID="MSSQLSERVER"

; Specify the installation directory.

INSTANCEDIR="C:\Program Files\Microsoft SQL Server"

; Specifies a cluster shared disk to associate with the SQL Server failover cluster instance.

FAILOVERCLUSTERDISKS="Cluster Virtual Disk (VDisk01)"

; Specifies the name of the cluster group for the SQL Server failover cluster instance.

FAILOVERCLUSTERGROUP="SQL Server (MSSQLSERVER)"

; Specifies an encoded IP address. The encodings are semicolon-delimited (;), and follow the format <IP Type>;<address>;<network name>;<subnet mask>. Supported IP types include DHCP, IPV4, and IPV6.

FAILOVERCLUSTERIPADDRESSES="IPv4;$script:application_ip;Cluster Network 1;255.255.255.0"

; Specifies the name of the SQL Server failover cluster instance.  This name is the network name that is used to connect to SQL Server services.

FAILOVERCLUSTERNETWORKNAME="SQL2016FCI"

; Agent account name

AGTSVCACCOUNT="$script:domain_netbios\$script:service_account"
AGTSVCPASSWORD="$script:service_password"

; CM brick TCP communication port

COMMFABRICPORT="0"

; How matrix will use private networks

COMMFABRICNETWORKLEVEL="0"

; How inter brick communication will be protected

COMMFABRICENCRYPTION="0"

; TCP port used by the CM brick

MATRIXCMBRICKCOMMPORT="0"

; Level to enable FILESTREAM feature at (0, 1, 2 or 3).

FILESTREAMLEVEL="0"

; Specifies a Windows collation or an SQL collation to use for the Database Engine.

SQLCOLLATION="SQL_Latin1_General_CP1_CI_AS"

; Account for SQL Server service: Domain\User or system account.

SQLSVCACCOUNT="$script:domain_netbios\$script:service_account"
SQLSVCPASSWORD="$script:service_password"

; Set to "True" to enable instant file initialization for SQL Server service. If enabled, Setup will grant Perform Volume Maintenance Task privilege to the Database Engine Service SID. This may lead to information disclosure as it could allow deleted content to be accessed by an unauthorized principal.

SQLSVCINSTANTFILEINIT="True"

; Windows account(s) to provision as SQL Server system administrators.

SQLSYSADMINACCOUNTS="$script:domain_netbios\$script:service_account"

; The number of Database Engine TempDB files.

SQLTEMPDBFILECOUNT="4"

; Specifies the initial size of a Database Engine TempDB data file in MB.

SQLTEMPDBFILESIZE="8"

; Specifies the automatic growth increment of each Database Engine TempDB data file in MB.

SQLTEMPDBFILEGROWTH="64"

; Specifies the initial size of the Database Engine TempDB log file in MB.

SQLTEMPDBLOGFILESIZE="8"

; Specifies the automatic growth increment of the Database Engine TempDB log file in MB.

SQLTEMPDBLOGFILEGROWTH="64"

; The Database Engine root data directory.

INSTALLSQLDATADIR="$script:volume_location"

; Add description of input argument FTSVCACCOUNT

FTSVCACCOUNT="NT Service\MSSQLFDLauncher"
"@


# Interpolated string that will be used as the SQL config file for cluster
# nodes.
$script:sql_ini = @"
;SQL Server 2016 Configuration File
[OPTIONS]

; Specifies a Setup work flow, like INSTALL, UNINSTALL, or UPGRADE. This is a required parameter.

ACTION="AddNode"

; Specifies that SQL Server Setup should not display the privacy statement when ran from the command line.

SUPPRESSPRIVACYSTATEMENTNOTICE="False"

; By specifying this parameter and accepting Microsoft R Open and Microsoft R Server terms, you acknowledge that you have read and understood the terms of use.

IACCEPTROPENLICENSETERMS="True"
IAcceptSQLServerLicenseTerms="True"

; Use the /ENU parameter to install the English version of SQL Server on your localized Windows operating system.

ENU="True"

; Setup will not display any user interface.

QUIET="True"

; Specify whether SQL Server Setup should discover and include product updates. The valid values are True and False or 1 and 0. By default SQL Server Setup will include updates that are found.

UpdateEnabled="True"

; If this parameter is provided, then this computer will use Microsoft Update to check for updates.

USEMICROSOFTUPDATE="False"

; Specify the location where SQL Server Setup will obtain product updates. The valid values are "MU" to search Microsoft Update, a valid folder path, a relative path such as .\MyUpdates or a UNC share. By default SQL Server Setup will search Microsoft Update or a Windows Update service through the Window Server Update Services.

UpdateSource="MU"

; Displays the command line parameters usage

HELP="False"

; Specifies that the detailed Setup log should be piped to the console.

INDICATEPROGRESS="True"

; Specifies that Setup should install into WOW64. This command line argument is not supported on an IA64 or a 32-bit system.

X86="False"

; Specify a default or named instance. MSSQLSERVER is the default instance for non-Express editions and SQLExpress for Express editions. This parameter is required when installing the SQL Server Database Engine (SQL), Analysis Services (AS), or Reporting Services (RS).

INSTANCENAME="MSSQLSERVER"

; Specifies the name of the cluster group for the SQL Server failover cluster instance.

FAILOVERCLUSTERGROUP="SQL Server (MSSQLSERVER)"

; Indicates that the change in IP address resource dependency type for the SQL Server multi-subnet failover cluster is accepted.

CONFIRMIPDEPENDENCYCHANGE="False"

; Specifies an encoded IP address. The encodings are semicolon-delimited (;), and follow the format <IP Type>;<address>;<network name>;<subnet mask>. Supported IP types include DHCP, IPV4, and IPV6.

FAILOVERCLUSTERIPADDRESSES="IPv4;$script:application_ip;Cluster Network 1;255.255.255.0"

; Specifies the name of the SQL Server failover cluster instance.  This name is the network name that is used to connect to SQL Server services.

FAILOVERCLUSTERNETWORKNAME="SQL2016FCI"

; Agent account name

AGTSVCACCOUNT="$script:domain_netbios\$script:service_account"
AGTSVCPASSWORD="$script:service_password"

; Account for SQL Server service: Domain\User or system account.

SQLSVCACCOUNT="$script:domain_netbios\$script:service_account"
SQLSVCPASSWORD="$script:service_password"

; Set to "True" to enable instant file initialization for SQL Server service. If enabled, Setup will grant Perform Volume Maintenance Task privilege to the Database Engine Service SID. This may lead to information disclosure as it could allow deleted content to be accessed by an unauthorized principal.

SQLSVCINSTANTFILEINIT="True"

; Add description of input argument FTSVCACCOUNT

FTSVCACCOUNT="NT Service\MSSQLFDLauncher"
"@


function Get-AccessToken {
    <#
    .SYNOPSIS
        Gets the access token for use in web requests.
    .DESCRIPTION
        Gets the access token for use in web requests. This access token has
        an expiration date so is only useful during the execution of this
        script.
    #>
    if (!(Test-Path $script:access_token_path)) {
        $access_token = (Get-Metadata -Path 'instance/service-accounts/default/token' | ConvertFrom-Json).access_token
        $access_token | Set-Content $script:access_token_path
    }

    return (Get-Content $script:access_token_path)
}



function Check-RuntimeConfigUrl {
    <#
    .SYNOPSIS
        Checks if a config URL exists.
    .DESCRIPTION
        Checks if a config URL exists and returns true or false.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $url
    )
    $access_token = Get-AccessToken
    $header = @{'Authorization'="Bearer $access_token"}

    try {
        if (Invoke-RestMethod -Uri $url -Method GET -Headers $header) {
            return $true
        }
    } catch {
        Write-Host $_
        Write-Host 'Runtime config URL not yet Accessible'
        return $false
    }
    return $false
}


function WaitFor-RuntimeReady {
    <#
    .SYNOPSIS
        Waits for a config URL to exist.
    .DESCRIPTION
        Repeatedly checks the given config URL to see if it exists. This can
        be used to block execution of this script until a a config is ready.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $timeout,
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $url
    )
    $expire_time = (Get-Date) + (New-TimeSpan -Seconds $timeout)
    while ((Get-Date) -lt $expire_time) {
        Write-Host("Checking if $url is accessible...")
        if (Check-RuntimeConfigUrl -url $url) {
            Write-Host("SUCCESS! $url is accessible")
            return $true
        }
        $sleep_time = 10
        Write-Host ("$url is not accessible. Retrying in $sleep_time seconds.")
        Start-Sleep -s $sleep_time
    }
    Write-Host ("Not able to access $url. Aborting.")
    return $false
}


function Mark-RuntimeDone {
    <#
    .SYNOPSIS
        POSTs a variable to a config.
    .DESCRIPTION
        POSTS a variable to a config depending on the "result". These
        variables are monitored by runtime waiters, which will pass
        or fail (or continue waiting) depending on the contents posted.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $url,
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $result
    )
    $path = "$url/variables"
    $config_name = (($path -split "$Script:run_time_base/")[1])
    Write-Host ("Marking $config_name as $result")
    $variable = @{
        name = "$config_name/$result/$script:node_name"
    }
    $var_json = $variable | ConvertTo-Json
    $access_token = Get-AccessToken
    $header = @{'Authorization'="Bearer $access_token"}

    $content_type = 'application/json'

    # Retry for a minute. posting to the runtime variables can be flaky.
    $expire_time = (Get-Date) + (New-TimeSpan -Seconds 60)
    while ($true) {
        try {
            $resp = Invoke-RestMethod -Uri $path `
                                      -ContentType $content_type `
                                      -Method POST `
                                      -Body $var_json `
                                      -Headers $header `
                                      -ErrorAction SilentlyContinue
            break
        } catch {
            Write-Host $_
            if ((Get-Date) -lt $expire_time) {
                throw 'failed to mark the runtime config'
            }
            Write-Host 'Retrying...'
        }
    }
    Write-Host ($resp)
}


function Add-Account {
    <#
    .SYNOPSIS
        Add the service account to the admin group.
    #>
    net user $script:service_account $script:service_password /add /expires:never
    net localgroup administrators $script:service_account /add
}


function Setup-Ad {
    <#
    .SYNOPSIS
        Installs AD on this node.
    .DESCRIPTION
        Installs AD on this node. This is a 2 step process:
        Step 1) Install AD, then restart.
        Step 2) After restart, Verify the Domain is installed then mark the
                runtime as done.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $flag
    )
    $flag = 'C:\Program Files\Google\Compute Engine\sysprep\adds_forest_install.txt'
    if (Test-Path $flag) {
        # AD has already been installed, and we are coming up from a reboot.
        while (-not $ad_node) {
            try {
                $ad_node = Get-ADDomainController -Discover -Domain $script:domain -ErrorAction stop
            } catch {
                Write-Host $_
                Write-Host 'Retrying in 10 seconds.'
                Start-Sleep -second 10
            }
        }
        Write-Host ('AD is now set up.')
        Mark-RuntimeDone -url $script:ad_url -result 'success'
        Write-Host ('AD runtime is now notified. Adding service accounts...')
        Add-Account
        Write-Host ('Service accounts added.')
        Write-Host ('Now running as AD Domain controller.')
    }
    else {
        # We are comming up for the first time. Install AD.

        Install-WindowsFeature -name AD-Domain-Services -IncludeManagementTools
        Import-Module ADDSDeployment

        # Mark the flag so that we know across reboots that AD has been installed.
        'Running Install-ADDSForest.' | Set-Content $flag

        MKDIR C:\SQLBackup
        New-SMBShare -Name 'SQLBackup' -Path 'c:\SQLBackup' -FullAccess 'Everyone'
        MKDIR C:\QWitness
        New-SMBShare -Name 'QWitness' -Path 'c:\QWitness' -FullAccess 'Everyone'

        ipconfig /registerdns
        net user Administrator $script:safe_mode_password
        Install-ADDSForest -CreateDnsDelegation:$false `
                           -DatabasePath 'C:\Windows\NTDS' `
                           -DomainName $script:domain `
                           -DomainNetBIOSName $script:domain_netbios `
                           -DomainMode $script:domain_mode `
                           -ForestMode $script:forest_mode `
                           -InstallDNS:$true `
                           -LogPath 'C:\Windows\NTDS' `
                           -SYSVOLPath 'C:\Windows\SYSVOL' `
                           -Force:$true `
                           -SafeModeAdministratorPassword (ConvertTo-SecureString $script:safe_mode_password -AsPlainText -Force)
        # After setting up an AD the initial time settings are lost
        w32tm /config /manualpeerlist:'metadata.google.internal' `
            /syncfromflags:manual /reliable:yes /update
        Restart-Service w32time

        #The VM will reboot at this point...
    }
}


function Setup-AdNode {
    <#
    .SYNOPSIS
        Overall set up for the AD node.
    .DESCRIPTION
    #>
    Write-Host ('Waiting for the AD set up runtime to be available...')
    WaitFor-RuntimeReady -url $script:ad_url -timeout 60
    Write-Host ('AD runtime ready. Setting up AD...')
    Setup-Ad -flag $script:addsforest_flag
}


function Check-JoinedDomain {
    <#
    .SYNOPSIS
        Verifies that this node has successfully joined the domain.
    .DESCRIPTION
        Verifies that this node has successfully joined the domain by
        executing an arbitrary command as the domain user.
    #>
    try {
        $cred = New-Object System.Management.Automation.PSCredential(
            "$script:domain_netbios\$script:service_account",
            ($script:service_password | ConvertTo-SecureString -AsPlainText -Force))
        Start-Process -Credential $cred cmd.exe -ArgumentList @('/c', 'exit')
        Write-Host ('Successfully joined domain')
        Mark-RuntimeDone -url $script:join_domain_url -result 'success'
        return $true
    } catch {
        Write-Host $_
        Write-Host ('Failed to join domain')
        Mark-RuntimeDone -url $script:join_domain_url -result 'failure'
        return $false
    }
}


function Join-InstanceGroup {
    gcloud compute instance-groups unmanaged add-instances `
        $script:instance_group `
        --instances $script:node_name `
        --zone $script:zone
}


function Join-Domain {
    <#
    .SYNOPSIS
        Adds this computer to the domain at $script:ad_node_ip.
    .DESCRIPTION
        Adds this computer to the domain at $script:ad_node_ip. Assumes that
        the service account information is retrieved from the metadata and set
        globally.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $flag
    )
    try {
        Write-Host ('Waiting for the AD to be ready.')
        WaitFor-RuntimeReady -url $script:join_domain_url -timeout 1600
        Write-Host ('Ready to join domain')
        $adapter = (Get-NetAdapter).Name
        & netsh interface ip set dnsservers name="${adapter}" source=static address=$script:ad_node_ip
        & ipconfig /flushdns
        $cred = New-Object System.Management.Automation.PSCredential(
            "$script:domain_netbios\$script:service_account",
            ($script:service_password | ConvertTo-SecureString -AsPlainText -Force))
        Add-Computer -DomainName $script:domain -Force -Credential $cred
        & net localgroup administrators "$script:domain_netbios\$script:service_account" /add
        Start-Process -Credential $cred cmd.exe -ArgumentList @('/c', 'exit')
        Write-Host $_
        Write-Host ('Domain joined. Restarting...')
        'DOMAIN JOINED!!!' | Set-Content $flag
        Restart-Computer
    } catch {
        Write-Host $_
        Write-Host ('Failed to join domain')
        Mark-RuntimeDone -url $script:join_domain_url -result 'failure'
    }
}


function Start-NewCluster {
    <#
    .SYNOPSIS
        Starts a new scheduled task to create a new fail over cluster.
    #>
    try {
        $command = "New-Cluster -Name wsfc_cluster -Node $script:all_nodes -NoStorage -StaticAddress $script:cluster_ip | " + `
                   "Set-ClusterQuorum -FileShareWitness \\$script:ad_node_name\QWitness"
        Invoke-ScheduleTask -Execute 'powershell.exe' `
                            -Argument $command `
                            -TaskName 'start_new_cluster'
    } catch {
        Mark-RuntimeDone -url $script:create_cluster_url -result 'failure'
        Write-Host $_
        Write-Host ('Creating new cluster has failed')
    }
}


function InvokeAs-Service {
    <#
    .SYNOPSIS
        Invokes a script as the service account
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $scriptblock,
        [Parameter(ValueFromPipelineByPropertyName=$true)]
        $argumentlist
    )
    $cred = New-Object System.Management.Automation.PSCredential(
        "$script:domain_netbios\$script:service_account",
        ($script:service_password | ConvertTo-SecureString -AsPlainText -Force))
    $session_options = New-PSSessionOption -SkipCACheck -SkipCNCheck -SkipRevocationCheck
    $sess = New-PSSession -Credential $cred -SessionOption $session_options

    if ($argumentlist -ne $null) {
        Invoke-Command -Session $sess -ScriptBlock $scriptblock -ArgumentList $argumentlist
    }
    else {
        Invoke-Command -Session $sess -ScriptBlock $scriptblock
    }
}


function WaitFor-Cluster {
    <#
    .SYNOPSIS
        Blocks until cluster is available.
    .DESCRIPTION
        This function will block until the cluster deployment is available.
        It will query the cluster, with the service account credentials, in
        a loop until the query returns success.
    #>

    # Simple script to block until the cluster is ready OR timeout
    $wait_for_cluster_script = {
        $expire_time = (Get-Date) + (New-TimeSpan -Seconds 600)
        while ($true) {
            $cluster_info = Get-Cluster -ErrorVariable Err -ErrorAction SilentlyContinue
            if ($Err) {
                Write-Host $Err
                if ((Get-Date) -gt $expire_time) {
                    throw 'Failed to get cluster information'
                }
                Start-Sleep 2
            }
            else {
                break
            }
        }
    }
    Write-Host ('Waiting for cluster to become available.')
    try {
        InvokeAs-Service -ScriptBlock $wait_for_cluster_script
    } catch {
        Write-Host $_
        Write-Host 'The cluster has failed to start.'
        Mark-RuntimeDone -url $script:create_cluster_url -result 'failure'
    }
}


function Enable-S2D {
    <#
    .SYNOPSIS
        Enables S2D.
    .DESCRIPTION
        Enables 2D on the cluster with the service account credentials.
        Because this is the last step in the cluster install phase of the
        deployment, it will mark the cluster config either success or failure.
    #>
    [long] $volume_size_gb = Get-Metadata -Path 'instance/attributes/volume-size-gb'
    $script_enable_s2d = {
        param (
            [Parameter(Mandatory=$true)]
            [long]$volume_size_gb
        )
        # convert to bytes
        $volume_size = $volume_size_gb * 1GB
        Write-Host "$(Get-Date) enable s2d"
        Enable-CLusterS2D -Verbose -Confirm:$false
        New-Volume -StoragePoolFriendlyName S2D* `
                   -FriendlyName VDisk01 `
                   -FileSystem CSVFS_REFS `
                   -Size $volume_size
    }
    try {
        InvokeAs-Service -ScriptBlock $script_enable_s2d -ArgumentList ($volume_size_gb)
        Write-Host ('Successfully set up S2D.')
    } catch {
        Write-Host $_
        Write-Host ('Failed to set up S2D.')
        Mark-RuntimeDone -url $script:create_cluster_url -result 'failure'
    }

}


function Clean-SQL {
    <#
    .SYNOPSIS
        Uninstall SQL server from the system.
    .DESCRIPTION
        It is not possible to upgrade an existing SQL server to an
        SQL FCI node. Therefore we have to uninstall and re-install.
        This is not a required step for the "Join Domain" phase of the
        deployment, however because a restart is required for the
        SQL uninstall and also to join the domain, we can reduce the
        overall deployment by only restarting once after both these
        steps are conplete.
    #>
    try {
        C:\sql_server_install\Setup.exe /Action=Uninstall `
                                        /FEATURES=SQL,AS,IS,RS `
                                        /INSTANCENAME=MSSQLSERVER /Q
        Write-Host ('sql server uninstalled')
    } catch {
        Write-Host $_
        Write-Host('Failed to uninstall sql server')
        Mark-RuntimeDone -url $script:join_domain_url -result 'failure'
    }
}


function Invoke-ScheduleTask {
    <#
    .SYNOPSIS
        Execute a scheduled task and block until the task is in 'Ready' state.
    #>
    param (
        [parameter(Mandatory=$true)]
        [String]$Execute,
        [parameter(Mandatory=$true)]
        [String]$Argument,
        [parameter(Mandatory=$true)]
        [String]$TaskName
    )

    $action = New-ScheduledTaskAction -Execute "`"${Execute}`"" `
                                      -Argument $Argument
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -User $script:domain_netbios\$script:service_account `
        -Password $script:service_password `
        -RunLevel Highest

    Start-ScheduledTask -TaskName $TaskName
    $timeout_seconds = 600
    $expire_time = (Get-Date) + (New-TimeSpan -Seconds $timeout_seconds)
    while ((Get-ScheduledTask -TaskName $TaskName).State  -ne 'Ready') {
        if ((Get-Date) -gt $expire_time) {
            Write-Host "Task did not complete after $timeout_seconds"
            break
        }
        Write-Output 'Waiting on scheduled task...'
        Start-Sleep -Seconds 10
    }

    $task_result = (schtasks /query /FO LIST /V /TN $TaskName |
                    findstr 'Result').Split()[-1]
    Write-Host "Task result: ${task_result}"

    if ($task_result -ne '0') {
        throw "Failed to execute ${TaskName}: $Execute $Argument"
    }
}


function Setup-FCI {
    <#
    .SYNOPSIS
        Installs SQL FCI on this node.
    .DESCRIPTION
        Installs SQL FCI on this node by first checking that S2D is enabled,
        then installing SQL with an ini file that is set up for FCI.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $config_contents
    )
    Write-Host ('Setting up FCI')
    & netsh advfirewall firewall add rule name='Open Port 1433 for sql' `
            dir=in action=allow protocol=TCP localport=1433

    Write-Host "$(Get-Date) Wait for S2D online"
    $expire_time = (Get-Date) + (New-TimeSpan -Seconds 600)
    while (!(Test-Path $script:volume_location)) {
        if ((Get-Date) -gt $expire_time) {
            throw 'S2D failed to come online.'
        }
        Write-Host ('S2D not yet ready')
        Start-Sleep -Seconds 10
    }

    Write-Host ('S2d is online')
    $config_file = 'C:\Program Files\Google\Compute Engine\sql_config.ini'
    $config_contents -replace '\n', "`r`n" | Out-File -FilePath $config_file `
                                                      -Encoding ASCII

    Invoke-ScheduleTask -Execute 'powershell' `
                        -Argument '"Test-Cluster -Include ''Storage Spaces Direct''"' `
                        -TaskName 'verify_cluster'

    $sql_install_path = 'C:\sql_server_install\Setup.exe'
    Invoke-ScheduleTask -Execute $sql_install_path `
                        -Argument "/CONFIGURATIONFILE=`"${config_file}`"" `
                        -TaskName 'install_sql'
    $install_log = Get-Childitem 'C:\Program Files\Microsoft SQL Server\*\Setup Bootstrap\Log\Summary.txt'
    Get-Content $install_log.FullName | Write-Host
}


function Prepare-Instance {
    <#
    .SYNOPSIS
        Common steps to take for cluster nodes.
    .DESCRIPTION
        This function executes a few things that are necessary for the rest
        of the deployment process to work. It will:
        1) remove the current version of SQL. The FCI version SQL requires
           that no previous version of SQL is present. There is no way to
           update an SQL installation to an FCI SQL installation.
        2) Join the load balancers instance group.
        3) Join the AD domain.
    .PARAMETER domain_joined_flag
        File path that, if exists, signifies that the domain should already
        have been joined.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        [Alias('flag')]
        $domain_joined_flag
    )
    & netsh advfirewall firewall add rule `
            name="Open Port $script:health_check_port for health check" `
            dir=in action=allow protocol=TCP localport=$script:health_check_port
    Clean-SQL
    Join-InstanceGroup
    Join-Domain -flag $domain_joined_flag
}


<#
 # The "master_sql" text and Setup-MasterTest function are used in testing only.
 # This is required for setting up a test database to make queries to.
 #>
$script:master_sql = @'
USE [master]
GO
EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'LoginMode', REG_DWORD, 2
GO

USE [master]
GO
ALTER LOGIN [sa] WITH PASSWORD = 'remoting@123'
GO
ALTER LOGIN [sa] ENABLE
GO


!!NET STOP MSSQLSERVER /y
!!NET STOP SQLSERVERAGENT /y

!!NET START MSSQLSERVER /y
!!NET START SQLSERVERAGENT /y
'@


function Setup-MasterTest {

    Write-Output "$(Get-Date) Config SQL instance"
    $sql_config = 'C:\Program Files\Google\Compute Engine\sql_config.sql'
    Set-Content -Path $sql_config -Value $master_sql

    # Give a little window for SQL to properly start up and be ready for requests
    Start-Sleep 30
    $sql_cmd = Get-Childitem 'C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\*\Tools\Binn\SQLCMD.exe'
    Invoke-ScheduleTask -Execute $sql_cmd.FullName `
                        -Argument "-S localhost -i `"${sql_config}`"" `
                        -TaskName 'config_test_sql'
    Restart-Service -Force MSSQLSERVER
}

<# End of test-only code #>


function Setup-MasterNode {
    <#
    .SYNOPSIS
        Overall set up for a cluster master node.
    .DESCRIPTION
        Sets up the master cluster node by setting this node up as a cluster
        node, but also starts the Failover Cluster and enables S2D. This will
        be run twice: First before a restart of the VM where we remove SQL and
        join the domain, then a second time where we set up SQL FCI.
    .PARAMETER domain_joined_flag
        File path that, if exists, signifies that the domain should already
        have been joined.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $domain_joined_flag
    )
    if (Test-Path $domain_joined_flag) {
        # Based on the domain_joined_flag, this is the second time this
        # function has been run and so we should now be joined to a domain.
        if (Check-JoinedDomain) {
            WaitFor-RuntimeReady -url $script:create_cluster_url -timeout 1600
            Start-NewCluster
            WaitFor-Cluster
            Start-Sleep 30
            Enable-S2D
            try {
                Setup-FCI -config_contents $script:sql_ini_master
                if ($script:is_test -eq 'true') {
                    Setup-MasterTest
                }
                'Setup Complete!!!' | Set-Content $script:complete_flag
                Mark-RuntimeDone -url $script:create_cluster_url `
                                 -result 'success'
            } catch {
                Write-Host $_
                Write-Host ('Failed to set up FCI')
                Mark-RuntimeDone -url $script:create_cluster_url `
                                 -result 'failure'
            }
        }
    }
    else {
        # We have not yet joined the domain so this is the first time this
        # function is run. First prepare the instance, then restart the VM.
        Prepare-Instance -flag $domain_joined_flag
    }
}


function Setup-ClusterNode {
    <#
    .SYNOPSIS
        Overall set up for a cluster node (non-master node)
    .DESCRIPTION
        Executes steps required on the cluster node. This function will be
        run twice: First before a restart of the VM where we remove SQL and
        join the domain, then a second time where we set up SQL FCI.
    .PARAMETER domain_joined_flag
        File path that, if exists, signifies that the domain should already
        have been joined.
    #>
    param (
        [Parameter(Mandatory=$true, ValueFromPipelineByPropertyName=$true)]
        $domain_joined_flag
    )
    if (Test-Path $domain_joined_flag) {
        # Based on the domain_joined_flag, this is the second time this
        # function has been run and so we should now be joined to a domain.
        if (Check-JoinedDomain) {
            WaitFor-RuntimeReady -url $script:install_fci_url -timeout 1600
            try {
                Setup-FCI -config_contents $script:sql_ini
                Mark-RuntimeDone -url $script:install_fci_url `
                                 -result 'success'
                'Setup Complete!!!' | Set-Content $script:complete_flag
            } catch {
                Write-Host $_
                Write-Host ('Failed to set up FCI')
                Mark-RuntimeDone -url $script:install_fci_url `
                                 -result 'failure'
            }
        }
    }
    else {
        # We have not yet joined the domain so this is the first time this
        # function is run. First prepare the instance, then restart the VM.
        Prepare-Instance -flag $domain_joined_flag
    }
}


function Check-SetupNeeded {
    <#
    .SYNOPSIS
        Simple check to verify that the setup process has previously
        completed.
    #>
    return !(Test-Path $script:complete_flag)
}

function WaitFor-S2D {
    <#
    .SYNOPSIS
        Blocks until the S2D virtual disks are in health state.
    .DESCRIPTION
        This code blocks until the S2D virtual disks have successfully reached
        "healthy" state, performing a "repair-virtualdisk" if needed.
        This is helpful in testing because if we take down a node as a part of
        the test, this gives us a way to ensure that the node is back to a state
        where further power-down operations can safely take place.

        If we suddenly power down a node that is part of an S2D cluster, the
        virtual disk will be in a degraded state, which may cause the entire
        S2D deployment to fail if more nodes are powered down.
    #>
    $sw = [Diagnostics.Stopwatch]::StartNew()
    WaitFor-Cluster
    $repair_retry_time = (Get-Date)
    $expire_time = (Get-Date) + (New-TimeSpan -Seconds 700)
    while ((Get-VirtualDisk).HealthStatus -ne 'Healthy') {
        if ((Get-Date) -gt $expire_time) {
            Write-Error 'S2D Failed to come up'
        }
        if ((Get-Date) -gt $repair_retry_time) {
            Repair-VirtualDisk -FriendlyName VDisk01 -Verbose -Confirm:$false -AsJob
            # try again in 2 minutes if it has not succeeded by then. Retrying the
            # operation has a tendency to "just work" sometimes.
            $repair_retry_time = (Get-Date) + (New-TimeSpan -Seconds 120)
        }
        Start-Sleep 1
    }

    $sw.Stop()
    $seconds_elapsed = $sw.Elapsed.TotalSeconds
    Write-Host "S2D UP. Took $seconds_elapsed seconds."
}

# Main. 3 different code paths (with some overlap) for the 3 different node roles.
#    AD node: AD Domain controller
#    Master: The first cluster node. This node will be used to install the Fail over cluster
#            and enable S2D
#    Cluster: All other cluster nodes.
if ($script:is_ad_node -eq 'true') {
    Write-Host('Running as AD Domain controller node.')
    if (Check-SetupNeeded) {
        Setup-AdNode
    }
}
elseif ($script:is_master -eq 'true') {
    Write-Host('Running as master node.')
    if (Check-SetupNeeded) {
        Setup-MasterNode -domain_joined_flag $script:joined_flag
    }
    else {
        # Coming up from a reboot. Make sure S2D is up.
        WaitFor-S2D
    }
}
else {
    Write-Host('Running as cluster node.')
    if (Check-SetupNeeded) {
        Setup-ClusterNode -domain_joined_flag $script:joined_flag
    }
    else {
        # Coming up from a reboot. Make sure S2D is up.
        WaitFor-S2D
    }
}

