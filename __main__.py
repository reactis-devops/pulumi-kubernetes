import pulumi
from pulumi_vm import VPS
from vps_config import ServerConfig, NetworkConfig, DiskConfig, SetupConfig
from pulumi import ResourceOptions

stack_name = pulumi.get_stack()
config = pulumi.Config()

db1 = VPS(ServerConfig(
    hostname=f'{stack_name}-db1',
    network=NetworkConfig(ip='10.0.0.8'),
    cpu=4,
    disk=DiskConfig(size='10G'),
    setup=SetupConfig(env={'SERVERID': "11", 'DOMAINID': "1"}, playbook="/playbooks/mariadb.yaml")))

kube1 = VPS(ServerConfig(
    hostname=f'{stack_name}-kube1',
    network=NetworkConfig(ip='10.0.0.9'),
    ram=2048,
    disk=DiskConfig(size='10G'),
    setup=SetupConfig(
        env={'IP': "10.0.0.9"},
        playbook="/playbooks/kubernetes-single-debian11.yaml", 
        artifacts={"k8s_token": "/root/k8s_token", 
                   "k8s_ca": "/root/k8s_ca", 
                   "k8s_config": "/root/.kube/config"})
    ))

node_join_credentials = {
                "CONTROLPLANEIP": kube1.ip, 
                "TOKEN": kube1.artifacts['k8s_token'], 
                "CA": kube1.artifacts['k8s_ca']}

for i in range(9):
    VPS(ServerConfig(
        hostname=f'{stack_name}-node{i+1}',
        network=NetworkConfig(ip=f'10.0.0.{10+i}'),
        setup=SetupConfig(env=node_join_credentials, playbook="/playbooks/kubernetes-node.yaml")),
        opts=ResourceOptions(parent=kube1))

pulumi.export("kubeconfig", kube1.artifacts['k8s_config'])