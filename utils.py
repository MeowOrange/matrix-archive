#!/usr/bin/python
# -*- coding: UTF-8 -*-

import uuid
import hashlib
import os
import sys
import os
import shutil
import sys
from urllib.request import urlretrieve
import time
from db import (
    DB
)
import filetype
import requests


class UTILS:

    def __init__(self):
        self.name = "name"

    # returns MEDIA_UUID.extension
    @staticmethod
    def put_media(file, media_dir, db):
        assert isinstance(db, DB)
        hash_current = UTILS.file_hash(file)
        existing_media = db.get_media_with_hash(hash_current)
        size_current = UTILS.file_size(file)
        for media in existing_media:
            if media['size'] == size_current:
                os.unlink(file)
                return media['uuid']
        uuid = UTILS.generate_uuid1()
        db.insert_media(uuid, hash_current, size_current)
        kind = filetype.guess(file)
        if not (kind is None):
            shutil.move(file, f"{media_dir}/{uuid}.{kind.extension}")
            return f"{uuid}.{kind.extension}"
        else:
            shutil.move(file, f"{media_dir}/{uuid}")
            return f"{uuid}"

    @staticmethod
    def file_hash(file):
        BLOCKSIZE = 65536
        sha = hashlib.sha256()
        with open(file, 'rb') as h_file:
            file_buffer = h_file.read(BLOCKSIZE)
            while len(file_buffer) > 0:
                sha.update(file_buffer)
                file_buffer = h_file.read(BLOCKSIZE)
        return sha.hexdigest()

    @staticmethod
    def file_size(file):
        return os.path.getsize(file)

    @staticmethod
    def generate_uuid1():
        return str(uuid.uuid1()).replace("-", "")

class DOWNLOADER:
    def __init__(self):
        self.name = "name"
    
    @staticmethod
    def download_url(url):
        retries = 9
        while retries >= 0 :
            try:
                request = requests.get(url,timeout=10, stream=True)
                #with open(file, 'wb') as fh:
                 #   for chunk in request.iter_content(8192):
                  #      fh.write(chunk)
                return request.content
            except Exception as err:
                print(f"Download failed. {err}")
                if (retries > 0):
                    print("Retrying...")
                    retries = retries - 1
                    continue
                else:
                    print("No more retries")
                    retries = retries - 1
                    raise Exception("Download failed. Please reload this script.")

class ShowProcess():
    i = 0
    max_steps = 0
    max_arrow = 50
    infoDone = 'Phase Accomplished'

    def __init__(self, max_steps, infoDone='Done'):
        self.max_steps = max_steps
        self.i = 0
        self.infoDone = infoDone

    def show_process(self, i=None):
        if i is not None:
            self.i = i
        else:
            self.i += 1
        num_arrow = int(self.i * self.max_arrow / self.max_steps)
        num_line = self.max_arrow - num_arrow
        percent = self.i * 100.0 / self.max_steps
        process_bar = '[' + '>' * num_arrow + '-' * num_line + ']'\
                      + '%.2f' % percent + '% - ' + \
            str(self.i) + ' of ' + str(self.max_steps) + '\r'
        sys.stdout.write(process_bar)
        sys.stdout.flush()
        if self.i >= self.max_steps:
            self.close()

    def close(self):
        print('')
        print(self.infoDone)
        self.i = 0


if __name__ == '__main__':
    max_steps = 100

    process_bar = ShowProcess(max_steps, 'OK')

    for i in range(max_steps):
        process_bar.show_process()
        time.sleep(0.01)
