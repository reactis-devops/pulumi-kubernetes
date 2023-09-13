import pulumi
import os
import yaml
import hashlib
import binascii
import ansible_runner
import subprocess
from pulumi.dynamic import *


class AnsiblePlaybookProvider(ResourceProvider):
    
    def create(self, inputs):
        hash = self.play(inputs["playbook"], inputs["host"], inputs["env"])
        artifacts = self.get_artifacts(inputs["host"], inputs["artifacts_files"])
        return CreateResult(id_=binascii.b2a_hex(os.urandom(16)), outs={"artifacts": artifacts, "hash": hash})
    
    def diff(self, _id, _olds, _news):
        return DiffResult(
            changes=_olds["hash"] != self.calculate_md5(_news["playbook"])
        )
    
    def update(self, _id, _olds, _news):
        hash = self.play(_news["playbook"], _news["host"], _news["env"])
        artifacts = self.get_artifacts(_news["host"], _news["artifacts_files"])
        return UpdateResult(outs={"artifacts": artifacts, "hash": hash})
    
    def play(self, playbook, host, env):
        result = ansible_runner.run(playbook=playbook, inventory=host, extravars=env)
        if result.rc != 0:
            raise RuntimeError(result.stderr)
        hash = self.calculate_md5(playbook)
        return hash

    def calculate_md5(self, file_path):
        """
        Calculate the MD5 hash of a file's content.
        
        :param file_path: Path to the file you want to hash.
        :return: The MD5 hash value as a hexadecimal string.
        """
        md5_hash = hashlib.md5()
        
        with open(file_path, "rb") as file:
            while True:
                data = file.read(65536)  # Read 64 KB at a time
                if not data:
                    break
                md5_hash.update(data)
        
        return md5_hash.hexdigest()
    
    def get_artifacts(self, host, artifacts_files):
        d = {}
        for key in artifacts_files:
            data = subprocess.run(f'ssh {host} cat {artifacts_files[key]}', capture_output=True, shell=True, text=True)
            d[key] = data.stdout.strip()
        return d

class AnsiblePlaybook(Resource, name="AnsiblePlaybook"):
    def __init__(self, name, playbook, host, artifacts = {}, env = {}, opts = None):         
         super().__init__(AnsiblePlaybookProvider(), name, {
             'name': name, 
             'env': env,
             'artifacts_files': artifacts,
             'playbook': os.path.dirname(os.path.abspath(__file__))+playbook, 
             'host': host,
             'artifacts': None}, opts)