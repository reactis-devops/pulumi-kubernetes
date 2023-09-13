import pulumi
import os
from pulumi import Input, Output, ResourceOptions
from pulumi.dynamic import *
from pulumi.resource import CustomResource, ProviderResource
from typing import Any, Optional

class LogicalVolumelProps(object):
    size: Input[int]
    name: Input[str]
    volume_group: Input[str]
    def __init__(self, name, size = 10, volume_group = 'vg0'):
        self.size = size
        self.name = name
        self.volume_group = volume_group

class LogicalVolumeProvider(ResourceProvider):
    
    def create(self, inputs):
        s = f'lvcreate -L {inputs["size"]}G -n {inputs["name"]} --wipesignatures y --yes --zero y {inputs["volume_group"]} > /dev/null'
        code = os.system(s)
        if (code):
            raise RuntimeError()
        return CreateResult(id_=f"{inputs['volume_group']}/{inputs['name']}", outs={'path': f"/dev/{inputs['volume_group']}/{inputs['name']}"})
    
    def delete(self, _id, _props) -> None:
        code = os.system(f'lvremove /{_props["path"]} --yes')
        if (code):
            raise RuntimeError()
        return None

class LogicalVolume(Resource, name="LogicalVolume"):
    
    def __init__(self, name: str, size: int, volume_group: str, opts: Optional[ResourceOptions] = None):         
         super().__init__(LogicalVolumeProvider(), f'{volume_group}/{name}', {'path': None, **vars(LogicalVolumelProps(name=name, size=size, volume_group=volume_group))}, opts)

