#!/usr/bin/env python3
# -*- coding: UTF-8 -*-

import argparse
import asyncio
import datetime
import getpass
import itertools
import json
import os
import re
import sys
from functools import partial
from urllib.parse import urlparse

import aiofiles
from nio import (
    Api,
    AsyncClient,
    AsyncClientConfig,
    MatrixRoom,
    MessageDirection,
    RoomEncryptedMedia,
    StickerEvent,
    RoomMemberEvent,
    RoomAvatarEvent,
    RoomMessageMedia,
    Event,
    crypto,
    store,
    exceptions
)
from nio.responses import (
	RoomMessagesError
)

import utils
from db import (
    DB
)
from utils import (
    put_media,
    generate_uuid1,
    download_url,
    mkdir,
    log,
    ShowProcess,
    NetworkException,
    DatabaseException
)

DEVICE_NAME = "matrix-archive"


def parse_args():
    """Parse arguments from command line call"""

    parser = argparse.ArgumentParser(
        description=__doc__,
        add_help=False,  # Use individual setting below instead
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "folder",
        metavar="FOLDER",
        default=".",
        nargs="?",  # Make positional argument optional
        help="""Set output folder
             """,
    )
    parser.add_argument(
        "--help",
        action="help",
        help="""Show this help message and exit
             """,
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="""Use unattended batch mode
             """,
    )
    parser.add_argument(
        "--server",
        metavar="HOST",
        default="https://matrix-client.matrix.org",
        help="""Set default Matrix homeserver
             """,
    )
    parser.add_argument(
        "--user",
        metavar="USER_ID",
        default="@user:matrix.org",
        help="""Set default user ID
             """,
    )
    parser.add_argument(
        "--userpass",
        metavar="PASSWORD",
        help="""Set default user password
             """,
    )
    parser.add_argument(
        "--keys",
        metavar="FILENAME",
        default="element-keys.txt",
        help="""Set default path to room E2E keys
             """,
    )
    parser.add_argument(
        "--keyspass",
        metavar="PASSWORD",
        help="""Set default passphrase for room E2E keys
             """,
    )
    parser.add_argument(
        "--room",
        metavar="ROOM_ID",
        default=[],
        action="append",
        help="""Add room to list of automatically fetched rooms
             """,
    )
    parser.add_argument(
        "--roomregex",
        metavar="PATTERN",
        default=[],
        action="append",
        help="""Same as --room but by regex pattern
             """,
    )
    parser.add_argument(
        "--all-rooms",
        action="store_true",
        help="""Select all rooms
             """,
    )
    parser.add_argument(
        "--no-media",
        action="store_true",
        help="""Don't download media
             """,
    )
    parser.add_argument(
        "--no-progress-bar",
        dest="no_progress_bar",
        action="store_true",
        help="""Don't show progress bar
             """,
    )
    parser.add_argument(
        "--no-logs",
        dest="no_logs",
        action="store_true",
        help="""Don't log in log files
             """,
    )
    parser.add_argument(
        "--no-avatars",
        dest="no_avatars",
        action="store_true",
        help="""Don't download user avatars
             """,
    )
    return parser.parse_args()


async def create_client() -> AsyncClient:
    homeserver = ARGS.server
    user_id = ARGS.user
    password = ARGS.userpass
    if not ARGS.batch:
        homeserver = input(
            f"Enter URL of your homeserver: [{homeserver}] ") or homeserver
        user_id = input(f"Enter your full user ID: [{user_id}] ") or user_id
        password = getpass.getpass()
    client = AsyncClient(
        homeserver=homeserver,
        user=user_id,
        config=AsyncClientConfig(store=store.SqliteMemoryStore),
    )
    await client.login(password, DEVICE_NAME)
    client.load_store()
    room_keys_path = ARGS.keys
    room_keys_password = ARGS.keyspass
    if not ARGS.batch:
        room_keys_path = input(
            f"Enter full path to room E2E keys: [{room_keys_path}] ") or room_keys_path
        room_keys_password = getpass.getpass("Room keys password: ")
    log("Importing keys. This may take a while...")
    await client.import_keys(room_keys_path, room_keys_password)
    return client


async def select_room(client: AsyncClient) -> MatrixRoom:
    log("\nList of joined rooms (room id, display name):")
    for room_id, room in client.rooms.items():
        log(f"{room_id}, {room.display_name}")
    room_id = input(f"Enter room id: ")
    return client.rooms[room_id]


def choose_filename(filename):
    start, ext = os.path.splitext(filename)
    for i in itertools.count(1):
        if not os.path.exists(filename):
            break
        filename = f"{start}({i}){ext}"
    return filename

# log details of an event
def log_event(event : Event):
    if hasattr(event, 'url'):
        log(f'Event Url: {event.url}')

    avatar_url = dict(event.content).get('avatar_url')
    if not (avatar_url is None):
        log(f'Avatar Url: {avatar_url}')

    if hasattr(event, 'body'):
        log(f'Event Body: {event.body}')

    if not dict(event.source).get("origin_server_ts") is None:
        timestamp = dict(event.source).get("origin_server_ts")
        date = datetime.datetime.fromtimestamp(timestamp / 1000)
        log(f'Event Date: {date.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]}')

    if hasattr(event, "source"):
        log(f'Event Source: {json.dumps(event.source, indent=4)}')

async def save_current_avatars(client: AsyncClient, room: MatrixRoom) -> None:
    room_short_id = str(room.room_id).split(':')[0].replace("!", "").replace("/", "_")
    roomdir = mkdir(f"{OUTPUT_DIR}/{room_short_id}")
    avatar_dir = mkdir(
        f"{roomdir}/currentavatars")
    for user in room.users.values():
        if user.avatar_url:
            async with aiofiles.open(f"{avatar_dir}/{user.user_id.replace('/', '_')}", "wb") as f:
                await f.write(await download_mxc(client, user.avatar_url))


async def download_mxc(client: AsyncClient, url: str):
    mxc = urlparse(url)
    http_method, path = Api.download(mxc.netloc, mxc.path.strip("/"))
    content_url = getattr(client, "homeserver", "https://" + mxc.hostname) + path
    return download_url(content_url)


async def fetch_room_events(
        client: AsyncClient,
        start_token: str,
        room: MatrixRoom,
        direction: MessageDirection,
) -> list:
    events = []
    while True:
        response = await client.room_messages(
            room.room_id, start_token, limit=100, direction=direction
        )
        if isinstance(response, RoomMessagesError):
	        break
        if len(response.chunk) == 0:
            break
        events.extend(
            event for event in response.chunk)
        start_token = response.end
        if not ARGS.no_progress_bar:
            sys.stdout.write(
                f"Fetched {str(len(events))} events for room {room.display_name}." + '\r')
            sys.stdout.flush()
    log('Fetch done!')
    return events


# return a dict of needed values to fill in database and write JSON.


async def prepare_event_for_database(event, client, room, db, temp_dir, media_dir):
    # set _sender_name in json
    sender_name = f"<{event.sender}>"
    if event.sender in room.users:
        # If user is still present in room, include current nickname
        sender_name = f"{room.users[event.sender].display_name} {sender_name}"
        event.source["_sender_name"] = sender_name

    event_parsed = dict()
    event_parsed['event_id'] = ""
    event_parsed['category'] = ""
    event_parsed['date'] = ""
    event_parsed['body'] = ""
    event_parsed['sender'] = ""
    event_parsed['media_uuid'] = ""
    event_parsed['source'] = ""

    # set event_id for dict
    if hasattr(event, "event_id"):
        event_parsed['event_id'] = event.event_id

    # set category for dict
    event_parsed['category'] = str(type(event)).replace("<class 'nio.events.room_events.", "") \
        .replace("<class 'nio.events.misc.", "") \
        .replace("<class 'nio.events.", "") \
        .replace("<class 'nio.", "") \
        .replace("'>", "")

    # set message sender and source code for dict
    if hasattr(event, "sender"):
        event_parsed['sender'] = event.sender
    if hasattr(event, "source"):
        event_parsed['source'] = json.dumps(event.source, indent=4)

    # set timestamp for dict
    if not dict(event.source).get("origin_server_ts") is None:
        timestamp = dict(event.source).get("origin_server_ts")
        date = datetime.datetime.fromtimestamp(timestamp / 1000)
        event_parsed['date'] = date.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        event.source["_date"] = event_parsed['date']

    # get message body is exists for database
    if hasattr(event, 'body'):
        event_parsed['body'] = str(event.body)

    # this try block is for all downloading media stuff.
    if not ARGS.no_media:
        try:
            # download media if necessary, and de-duplicate media files, organize them in database.
            # currently for RoomMessageMedia, RoomEncryptedMedia, StickerEvent
            if isinstance(event, (RoomMessageMedia, RoomEncryptedMedia, StickerEvent)):

                # download file first with a random filename.
                media_data = await download_mxc(client, event.url)
                filename = choose_filename(
                    f"{temp_dir}/{str(generate_uuid1())}")
                async with aiofiles.open(filename, "wb") as f_media:
                    try:
                        await f_media.write(
                            crypto.attachments.decrypt_attachment(
                                media_data,
                                event.source["content"]["file"]["key"]["k"],
                                event.source["content"]["file"]["hashes"]["sha256"],
                                event.source["content"]["file"]["iv"],
                            )
                        )
                    except KeyError:  # EAFP: Unencrypted media produces KeyError
                        await f_media.write(media_data)
                # Set atime and mtime of file to event timestamp
                os.utime(filename, ns=(
                        (event.server_timestamp * 1000000,) * 2))

                # oraganize file in database, get new filename.
                new_name = put_media(filename, media_dir, db)
                event.source["_file_path"] = new_name
                event_parsed['media_uuid'] = new_name

            # download avatars for user who changes avatar, and de-duplicate media files, organize them in database.
            # currently for RoomMemberEvent
            # only proceed without --no-avatars flag
            if isinstance(event, (RoomMemberEvent)) and (not ARGS.no_avatars):

                # look for avatar_url
                avatar_url = dict(event.content).get('avatar_url')
                if not (avatar_url is None):

                    # download file first with a random filename.
                    media_data = await download_mxc(client, avatar_url)
                    filename = choose_filename(
                        f"{temp_dir}/{str(generate_uuid1())}")
                    event.source["_file_path"] = filename
                    async with aiofiles.open(filename, "wb") as f_media:
                        try:
                            await f_media.write(
                                crypto.attachments.decrypt_attachment(
                                    media_data,
                                    event.source["content"]["file"]["key"]["k"],
                                    event.source["content"]["file"]["hashes"]["sha256"],
                                    event.source["content"]["file"]["iv"],
                                )
                            )
                        except KeyError:  # EAFP: Unencrypted media produces KeyError
                            await f_media.write(media_data)
                        # Set atime and mtime of file to event timestamp
                        os.utime(filename, ns=(
                                (event.server_timestamp * 1000000,) * 2))

                    # oraganize file in database, get new filename.
                    new_name = put_media(
                        filename, media_dir, db)
                    event.source["_file_path"] = new_name
                    event_parsed['media_uuid'] = new_name

            # download avatars for rooms changing avatar, and de-duplicate media files, organize them in database.
            # currently for RoomAvatarEvent
            if isinstance(event, (RoomAvatarEvent)):

                # look for content
                content = dict(event.source).get('content')
                if not content is None:
                    # look for _url
                    url = dict(content).get('url')
                    if not (url is None):

                        # download file first with a random filename.
                        media_data = await download_mxc(client, url)
                        filename = choose_filename(
                            f"{temp_dir}/{str(generate_uuid1())}")
                        event.source["_file_path"] = filename
                        async with aiofiles.open(filename, "wb") as f_media:
                            try:
                                await f_media.write(
                                    crypto.attachments.decrypt_attachment(
                                        media_data,
                                        event.source["content"]["file"]["key"]["k"],
                                        event.source["content"]["file"]["hashes"]["sha256"],
                                        event.source["content"]["file"]["iv"],
                                    )
                                )
                            except KeyError:  # EAFP: Unencrypted media produces KeyError
                                await f_media.write(media_data)
                            # Set atime and mtime of file to event timestamp
                            os.utime(filename, ns=(
                                    (event.server_timestamp * 1000000,) * 2))

                        # oraganize file in database, get new filename.
                        new_name = put_media(
                            filename, media_dir, db)
                        event.source["_file_path"] = new_name
                        event_parsed['media_uuid'] = new_name
        except TypeError as tperror:
            log(f'Again... TypeError: {tperror}')
            log_event(event)

    return event_parsed


async def write_room_events(client, room):
    log(
        f"Fetching {room.room_id} room messages (aka {room.display_name}) and writing to disk...")
    sync_resp = await client.sync(
        full_state=True, sync_filter={"room": {"timeline": {"limit": 1}}}
    )
    start_token = sync_resp.rooms.join[room.room_id].timeline.prev_batch

    # Generally, it should only be necessary to fetch back events but,
    # sometimes depending on the sync, front events need to be fetched
    # as well.
    fetch_room_events_ = partial(fetch_room_events, client, start_token, room)
    room_short_id = str(room.room_id).split(':')[0].replace("!", "").replace("/", "_")
    roomdir = mkdir(f"{OUTPUT_DIR}/{room_short_id}")

    # prepare database
    dbfile = f"{roomdir}/data.db"
    db = DB(dbfile, room.display_name)
    if not ARGS.no_media:
        temp_dir = mkdir(
            f"{roomdir}/temp")
        media_dir = mkdir(
            f"{roomdir}/media")

    # get filename for message.json this time:
    messages_json_filename = choose_filename(f"{roomdir}/messages.json")

    async with aiofiles.open(
            messages_json_filename, "w"
    ) as f_json:
        list_all_events = list(reversed(await fetch_room_events_(MessageDirection.back))) + list(
            await fetch_room_events_(MessageDirection.front))
        process_bar = ShowProcess(len(list_all_events), "Export Accomplished!")
        events_parsed = []
        for event in list_all_events:
            if db.event_exists(event) == "insert":
                try:
                    event_parsed = await prepare_event_for_database(event, client, room, db, temp_dir, media_dir)
                    events_parsed.append(event.source)
                    # insert event into database
                    db.insert_event(event_parsed['event_id'], event_parsed['category'], event_parsed['date'],
                                    event_parsed['body'], event_parsed['sender'], event_parsed['media_uuid'],
                                    event_parsed['source'])
                    if not ARGS.no_progress_bar:
                        process_bar.show_process()
                except exceptions.EncryptionError as e:
                    log(e, file=sys.stderr)
            elif db.event_exists(event) == "update":
                try:
                    event_parsed = await prepare_event_for_database(event, client, room, db, temp_dir, media_dir)
                    events_parsed.append(event.source)
                    # update event in database
                    db.update_event(event_parsed['event_id'], event_parsed['category'], event_parsed['date'],
                                    event_parsed['body'], event_parsed['sender'], event_parsed['media_uuid'],
                                    event_parsed['source'])
                    if not ARGS.no_progress_bar:
                        process_bar.show_process()
                except exceptions.EncryptionError as e:
                    log(e, file=sys.stderr)
            else:
                if not ARGS.no_progress_bar:
                    process_bar.show_process()
        if ARGS.no_progress_bar:
            log("Export Accomplished!")
        db.flush_events()
        # serialise message array and write to message.json
        await f_json.write(json.dumps(events_parsed, indent=4))
    if (not ARGS.no_avatars) and (not ARGS.no_media):
        await save_current_avatars(client, room)
    os.rmdir(temp_dir)
    log("Successfully wrote all room events to disk.")


async def main() -> None:
    try:
        client = await create_client()
        await client.sync(
            full_state=True,
            # Limit fetch of room events as they will be fetched later
            sync_filter={"room": {"timeline": {"limit": 1}}})
        for room_id, room in client.rooms.items():
            # Iterate over rooms to see if a room has been selected to
            # be automatically fetched
            if room_id in ARGS.room or any(re.match(pattern, room_id) for pattern in ARGS.roomregex):
                log(f"Selected room: {room_id}")
                await write_room_events(client, room)
        if ARGS.batch:
            # If the program is running in unattended batch mode,
            # then we can quit at this point
            raise SystemExit
        else:
            while True:
                room = await select_room(client)
                await write_room_events(client, room)
    except KeyboardInterrupt as ki:
        log(ki, file=sys.stderr)
        sys.exit(1)
    except NetworkException as ne:
        log(ne.message + ', Details:', file=sys.stderr)
        log(ne.details, file=sys.stderr)
        sys.exit(4)
    except DatabaseException as de:
        log(de.message + ', Details:', file=sys.stderr)
        log(de.details, file=sys.stderr)
        sys.exit(3)
    except Exception as err:
        log(err, file=sys.stderr)
        sys.exit(1)
    finally:
        await client.logout()
        await client.close()


if __name__ == "__main__":
    ARGS = parse_args()
    if ARGS.all_rooms:
        # Select all rooms by adding a regex pattern which matches every string
        ARGS.roomregex.append(".*")
    OUTPUT_DIR = mkdir(ARGS.folder)
    utils.NO_LOG = ARGS.no_logs
    utils.LOG_NAME = ''
    asyncio.run(main())
