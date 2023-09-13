import pulumi
import os
from pulumi import Input, Output, ResourceOptions
from pulumi.dynamic import *
from pulumi.resource import CustomResource, ProviderResource
from typing import Any, Optional
from vps import VPS as VirshVPS
from pulumi_lvm import LogicalVolume
from pulumi_ansible import AnsiblePlaybook
from vps_config import ServerConfig
import yaml

class VirtualMachineProvider(ResourceProvider):
    
    def create(self, inputs):
        
        result = VirshVPS(
            name=inputs['name'], 
            ip=inputs['ip'],
            gateway=inputs['gateway'],
            volume_group=inputs['volume_group'],
            disk_size=inputs['size'],
            cpu=inputs['cpu'],
            ram=inputs['ram'],
            copy_files=inputs['copy_files'],
            setup_env=inputs['setup_env'],
            setup_scripts=inputs['setup_scripts'],
            ).create()
        return CreateResult(id_=inputs['name'], outs={**inputs, "result": result})
    
    def delete(self, _id, _props):
        os.system(f"virsh destroy {_id}")
        os.system(f"virsh undefine {_id}")
        return None

class VirtualMachine(Resource, name="VirtualMachine"):
    def __init__(self, 
                 name,
                 ip,
                 gateway = '10.0.0.1',
                 volume_group = "vg0",
                 size = 10,
                 cpu = 1,
                 ram = 1024,
                 setup_env = {},
                 setup_scripts = [],
                 copy_files = [],
                 opts: Optional[ResourceOptions] = None):
         super().__init__(VirtualMachineProvider(), name, {
             'name': name,
             'size': size,
             'volume_group': volume_group,
             'ip': ip,
             'gateway': gateway,
             'cpu': cpu,
             'ram': ram,
             'setup_env': setup_env,
             'setup_scripts': setup_scripts,
             'copy_files': copy_files,
             'result': None
            }, opts)

class VPS(pulumi.ComponentResource):
    
    @property
    @pulumi.getter
    def artifacts(self):
        return self.playbook.artifacts

    @property
    @pulumi.getter
    def ip(self):
        return self.vm.ip
    
    def __init__(self, 
                 config: ServerConfig,
                 opts = None):
        
        super().__init__('reactis:cloud:VPS', config.hostname, opts=opts)

        self.lvm = LogicalVolume(config.hostname, 
                            size=config.disk.size, 
                            volume_group=config.disk.volume_group, 
                            opts=ResourceOptions(parent=self, delete_before_replace=True))
        
        self.vm = VirtualMachine(config.hostname, 
                       ip=config.network.ip, 
                       gateway=config.network.gateway, 
                       volume_group=config.disk.volume_group, 
                       size=config.disk.size, 
                       cpu=config.cpu,
                       ram=config.ram,
                       setup_env=config.setup.env,
                       setup_scripts=config.setup.scripts,
                       copy_files=config.setup.files,
                       
                       opts=ResourceOptions(depends_on=self.lvm, parent=self, delete_before_replace=True, additional_secret_outputs=['result']))
        
        name = f"{config.hostname}/{os.path.basename(config.setup.playbook).split('.')[0]}"
        self.playbook = AnsiblePlaybook(name, 
                                        playbook=config.setup.playbook, 
                                        host=self.vm.ip, 
                                        env=config.setup.env, 
                                        artifacts=config.setup.artifacts,
                                        opts=ResourceOptions(depends_on=self.vm, parent=self, additional_secret_outputs=['artifacts']))
       
        self.register_outputs({
            "artifacts": self.playbook.artifacts,
            "ip": self.vm.ip
        })

    @classmethod
    def from_config_file(cls, config_file, env={}):
        config = ServerConfig.from_yaml(config_file)
        if (len(env) > 1):
            config.setup.env = env
        return VPS(config)