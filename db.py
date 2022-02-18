#!/usr/bin/python
# -*- coding: UTF-8 -*-
import re
import sqlite3


class DB:

    def __init__(self, filename, roomname):
        self.sqls_insert=[]
        self.sqls_update=[]
        self.filename = filename
        self.conn = sqlite3.connect(self.filename)
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
        except:
            print("Preparing table failed.")
            return False
        self.c = self.conn.cursor()
        print(f"Database ready for room: {roomname}")

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

        self.sqls_insert.append(args)
        if len(self.sqls_insert) >= 100:
            for arg in self.sqls_insert:
                self.c.execute(
                    "insert into MESSAGE (EVENT_ID, CATEGORY, DATE, BODY, SENDER, MEDIA_UUID, SOURCE) values (?, ?, ?, ?, ?, ?, ?)", arg)
            self.sqls_insert.clear()
            self.conn.commit()

    def update_event(self, id, category, date, body, sender, media_uuid, source):
        args = (category, date, body, sender, media_uuid, source, id)

        self.sqls_update.append(args)
        if len(self.sqls_update) >= 100:
            for arg in self.sqls_update:
                self.c.execute(
                    "update MESSAGE set CATEGORY = ?, DATE = ?, BODY = ?, SENDER = ?, MEDIA_UUID = ?, SOURCE = ? where EVENT_ID = ?", arg)
            self.sqls_update.clear()
            self.conn.commit()

    def flush_events(self):
        for arg_insert in self.sqls_insert:
            self.c.execute(
                    "insert into MESSAGE (EVENT_ID, CATEGORY, DATE, BODY, SENDER, MEDIA_UUID, SOURCE) values (?, ?, ?, ?, ?, ?, ?)", arg_insert)
        self.sqls_insert.clear()
        self.conn.commit()
        for arg_update in self.sqls_update:
            self.c.execute(
                    "update MESSAGE set CATEGORY = ?, DATE = ?, BODY = ?, SENDER = ?, MEDIA_UUID = ?, SOURCE = ? where EVENT_ID = ?", arg_update)
        self.sqls_update.clear()
        self.conn.commit()


    def event_exists(self, event):
        cursor = self.c.execute(
            "select EVENT_ID, CATEGORY from MESSAGE where EVENT_ID = ?", (event.event_id, ))
        results = []
        for row in cursor:
            rowdict = dict()
            rowdict['id'] = row[0]
            rowdict['category'] = row[1]
            results.append(rowdict)
        for result in results:
            if ("BadEvent" in str(result['category']) or ("Unknown" in str(result['category']))):
                if ("BadEvent" in str(type(event))) or ("Unknown" in str(type(event))):
                    return "nodo"
                else:
                    return "update"
            else:
                return "nodo"
        return "insert"
