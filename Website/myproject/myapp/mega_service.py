import os
from mega import Mega

class MegaService:
    def __init__(self):
        self.email = os.environ.get('MEGA_EMAIL')
        self.password = os.environ.get('MEGA_PASSWORD')
        if not self.email or not self.password:
            raise Exception('MEGA credentials not set in environment variables (MEGA_EMAIL, MEGA_PASSWORD)')
        self.mega = Mega()
        self.m = self.mega.login(self.email, self.password)

    def upload_file(self, file_path, dest_folder=None):
        # dest_folder: MEGA folder node (optional)
        uploaded = self.m.upload(file_path, dest_folder)
        link = self.m.get_upload_link(uploaded)
        return link

    def get_folder(self, folder_name):
        # Return MEGA folder node by name
        folders = self.m.get_files()
        for node_id, node in folders.items():
            if node['t'] == 1 and node['a']['n'] == folder_name:
                return node
        return None
