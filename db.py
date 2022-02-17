#!/usr/bin/python
# -*- coding: UTF-8 -*-
import sqlite3


class DB:

    def __init__(self, filename):
        self.filename = filename
        self.conn = sqlite3.connect(self.filename)
        print("Database opened.")
        try:
            cmd_create_MESSAGE = '''
                CREATE TABLE IF NOT EXISTS MESSAGE
                (EVENT_ID TEXT,
                CATEGORY TEXT,
                DATE TEXT,
                BODY TEXT,
                SENDER TEXT,
                MEDIA_UUID TEXT,
                SOURCE TEXT);
                '''
            cmd_create_MEDIA = '''
                CREATE TABLE IF NOT EXISTS MEDIA
                (UUID TEXT,
                HASH TEXT,
                SIZE INT);
                '''
            self.conn.execute(cmd_create_MESSAGE)
            self.conn.execute(cmd_create_MEDIA)
            print("Tables ready.")
            cmd_create_MESSAGE_INDEX_UNIQUE = '''
                CREATE UNIQUE INDEX IF NOT EXISTS index_eventid ON MESSAGE (EVENT_ID);  
                '''
            cmd_create_MESSAGE_INDEX_DATE = '''
                CREATE INDEX IF NOT EXISTS index_date ON MESSAGE (DATE);
                '''
            cmd_create_MEDIA_INDEX = '''
                CREATE INDEX IF NOT EXISTS index_media ON MEDIA (HASH);
                '''
            self.conn.execute(cmd_create_MESSAGE_INDEX_UNIQUE)
            self.conn.execute(cmd_create_MESSAGE_INDEX_DATE)
            self.conn.execute(cmd_create_MEDIA_INDEX)
            print("Indexes ready.")
        except:
            print("Create table failed.")
            return False
        self.c = self.conn.cursor()
        print("Database ready.")

    def get_media_with_hash(self, hash):
        cursor = self.c.execute(
            "select UUID, SIZE from MEDIA where HASH = ?", (hash, ))
        results = []
        for row in cursor:
            rowdict = dict()
            rowdict['uuid'] = row[0]
            rowdict['size'] = row[1]
            results.append(rowdict)
        return results

    def insert_media(self, uuid, hash, size):
        args = (uuid, hash, str(size))
        self.c.execute(
            "insert into MEDIA (uuid, hash, size) values (?, ?, ?)", args)
        self.conn.commit()

    def insert_event(self, id, category, date, body, sender, media_uuid, source):
        args = (id, category, date, body, sender, media_uuid, source)
        self.c.execute(
            "insert into MESSAGE (EVENT_ID, CATEGORY, DATE, BODY, SENDER, MEDIA_UUID, SOURCE) values (?, ?, ?, ?, ?, ?, ?)", args)
        self.conn.commit()

    def event_exists(self, event_id):
        cursor = self.c.execute(
            "select EVENT_ID from MESSAGE where EVENT_ID = ?", (event_id, ))
        a = 0
        for row in cursor:
            a = a + 1
        if a > 0:
            return True
        else:
            return False
