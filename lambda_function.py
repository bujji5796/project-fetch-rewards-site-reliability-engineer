#!/usr/bin/env python
# coding: utf-8
import yaml
import json
import boto3

def lambda_handler(event, context):

    region = 'us-east-2' # instance is deployed in Ohio region.
    #Ref : https://docs.amazonaws.cn/en_us/lambda/latest/dg/with-s3-example.html
    s3 = boto3.client('s3')
    bucket = event['Records'][0]['s3']['bucket']['name'] # Get the object from the event and show its content type
    key = event['Records'][0]['s3']['object']['key']        
    response = s3.get_object(Bucket = bucket, Key = key)
    response_data = response['Body'].read().decode('utf-8')
    info = yaml.safe_load(response_data) #Note that the ability to construct an arbitrary Python object may be dangerous if you receive a YAML document from an untrusted source such as the Internet. The function yaml.safe_load limits this ability to simple Python objects like integers or lists.  
    
    image_id = 'ami-05d72852800cbf29e' # Image id for Amazon Linux 2 AMI (HVM), SSD Volume Type in us-east-2 region
    key = 'projectkey' #keypair used for the instance
    region = 'us-east-2' 
    
    #Import the values from the yaml file given
    # Ref: https://pyyaml.org/wiki/PyYAMLDocumentation
    instance_type = info['server']['instance_type']    
    min_count = int(info['server']['min_count'])
    max_count = int(info['server']['max_count'])
    vol_device1 = info['server']['volumes'][0]['device']
    vol_device2 = info['server']['volumes'][1]['device']
    vol_size1 = int(info['server']['volumes'][0]['size_gb'])
    vol_size2 = int(info['server']['volumes'][1]['size_gb'])
    ssh_key1 = info['server']['users'][0]['ssh_key']
    ssh_key2 = info['server']['users'][1]['ssh_key']
    
    #Creating a Security Group for an instance 
    # Ref: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/ec2-example-security-group.html
    ec2 = boto3.client('ec2', region_name=region)
    response = ec2.create_security_group(GroupName='projectsecuritygroupid', Description='lambda project securitygroup')
    security_group_id = response['GroupId']    
    
    data = ec2.authorize_security_group_ingress(
    GroupId=security_group_id,
    IpPermissions=[
        {'IpProtocol': 'tcp',
         'FromPort': 22,
         'ToPort': 22,
         'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
    ])
    group_name = 'projectsecuritygroupid'
    #finding the security group id from security group name
    response = ec2.describe_security_groups(
    Filters=[
         dict(Name='group-name', Values=[group_name])
    ])
    security_group_id = response['SecurityGroups'][0]['GroupId'] 
    print("Security Group created")
    
    #Add userdata script
    # Ref : https://aws.amazon.com/premiumsupport/knowledge-center/ec2-user-account-cloud-init-user-data/
    user_data = f"""#cloud-config
    cloud_final_modules:
    - [users-groups,always]
    users:
    - name: user1
      groups: [ wheel ]
      sudo: [ "ALL=(ALL) NOPASSWD:ALL" ]
      shell: /bin/bash
      ssh-authorized-keys: 
      - {ssh_key1} 
    
    - name: user2
      groups: [ wheel ]
      sudo: [ "ALL=(ALL) NOPASSWD:ALL" ]
      shell: /bin/bash
      ssh-authorized-keys: 
      - {ssh_key2} 
    """
     
    # Creating an Instance in us-east-2 region by using the above created security group and user data.
    # Ref : https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ec2.html#EC2.Client.run_instances
    instance = ec2.run_instances(
        BlockDeviceMappings=
        [
        {
            'DeviceName': vol_device1,
            'Ebs': {
                    'VolumeSize': vol_size1
                   },        
        },
        {
            'DeviceName': vol_device2,
            'Ebs': {
                    'VolumeSize': vol_size2
                   },
        },
        ],
        ImageId=image_id,
        InstanceType=instance_type,
        KeyName=key,
        MaxCount=min_count,
        MinCount=max_count,
        UserData = user_data
    )
    instance_id = instance['Instances'][0]['InstanceId']
    print("Instance created")
    
    #Modifying the instance security group from default to the above created one.
    
    instance_changed = ec2.modify_instance_attribute(InstanceId=instance_id,Groups=[security_group_id])
    return instance_id  