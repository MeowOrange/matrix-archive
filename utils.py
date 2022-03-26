#!/usr/bin/python
# -*- coding: UTF-8 -*-
import datetime
import hashlib
import os
import shutil
import sys
import time
import uuid
from db import DB

import filetype
import requests

global LOG_NAME
global NO_LOG


def mkdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass
    return path


def log(message: object, file=sys.stdout):
    global LOG_NAME
    global NO_LOG
    if LOG_NAME == '':
        LOG_NAME = datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S")
    print(message, file=file)
    if not NO_LOG:
        log_dir = mkdir('/matrix_archive/logs')
        log_file = f'{log_dir}/{LOG_NAME}.txt'
        try:
            writer = open(log_file, mode='a+', encoding='utf-8')
        except:
            print('Log file error.', file=sys.stderr)
            sys.exit(1)
        writer.write(str(message) + '\n')
        writer.close()


# returns MEDIA_UUID.extension
def put_media(file, media_dir, db):
    assert isinstance(db, DB)
    hash_current = file_hash(file)
    existing_media = db.get_media_with_hash(hash_current)
    size_current = file_size(file)
    for media in existing_media:
        if media['size'] == size_current:
            os.unlink(file)
            return media['uuid']
    uuid = generate_uuid1()
    db.insert_media(uuid, hash_current, size_current)
    kind = filetype.guess(file)
    if not (kind is None):
        shutil.move(file, f"{media_dir}/{uuid}.{kind.extension}")
        return f"{uuid}.{kind.extension}"
    else:
        shutil.move(file, f"{media_dir}/{uuid}")
        return f"{uuid}"


def file_hash(file):
    BLOCKSIZE = 65536
    sha = hashlib.sha256()
    with open(file, 'rb') as h_file:
        file_buffer = h_file.read(BLOCKSIZE)
        while len(file_buffer) > 0:
            sha.update(file_buffer)
            file_buffer = h_file.read(BLOCKSIZE)
    return sha.hexdigest()


def file_size(file):
    return os.path.getsize(file)


def generate_uuid1():
    return str(uuid.uuid1()).replace("-", "")


def download_url(url):
    retries = 9
    while retries >= 0:
        try:
            request = requests.get(url, timeout=10, stream=True)
            # with open(file, 'wb') as fh:
            #   for chunk in request.iter_content(8192):
            #      fh.write(chunk)
            return request.content
        except Exception as err:
            log(f"Download failed. {err}", file=sys.stderr)
            if (retries > 0):
                log("Retrying...")
                retries = retries - 1
                continue
            else:
                log("No more retries")
                retries = retries - 1
                raise NetworkException("Download failed. Please reload this script.", err)


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
        process_bar = '[' + '>' * num_arrow + '-' * num_line + ']' \
                      + '%.2f' % percent + '% - ' + \
                      str(self.i) + ' of ' + str(self.max_steps) + '\r'
        sys.stdout.write(process_bar)
        sys.stdout.flush()
        if self.i >= self.max_steps:
            self.close()

    def close(self):
        print('')
        log(self.infoDone)
        self.i = 0


class DatabaseException(Exception):

    def __init__(self, message, details):
        self.message = message
        self.details = details


class NetworkException(Exception):

    def __init__(self, message, details):
        self.message = message
        self.details = details


if __name__ == '__main__':
    max_steps = 100

    process_bar = ShowProcess(max_steps, 'OK')

    for i in range(max_steps):
        process_bar.show_process()
        time.sleep(0.01)
