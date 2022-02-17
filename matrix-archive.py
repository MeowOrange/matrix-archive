#!/usr/bin/env python3

"""matrix-archive

Archive Matrix room messages. Creates a YAML log of all room
messages, including media.

Use the unattended batch mode to fetch everything in one go without
having to type anything during script execution. You can set all
the necessary values with arguments to your command call.

If you don't want to put your passwords in the command call, you
can still set the default values for homeserver, user ID and room
keys path already to have them suggested to you during interactive
execution. Rooms that you specify in the command call will be
automatically fetched before prompting for further input.

Example calls:

./matrix-archive.py
    Run program in interactive mode.

./matrix-archive.py backups
    Set output folder for selected rooms.

./matrix-archive.py --batch --server https://matrix.org --user '@user:matrix.org' --userpass secret --keys element-keys.txt --keyspass secret
    Use unattended batch mode to login.

./matrix-archive.py --room '!Abcdefghijklmnopqr:matrix.org'
    Automatically fetch a room.

./matrix-archive.py --room '!Abcdefghijklmnopqr:matrix.org' --room '!Bcdefghijklmnopqrs:matrix.org'
    Automatically fetch two rooms.

./matrix-archive.py --roomregex '.*:matrix.org'
    Automatically fetch every rooms which matches a regex pattern.

./matrix-archive.py --all-rooms
    Automatically fetch all available rooms.

"""

from gc import set_debug
from nio import (
    AsyncClient,
    AsyncClientConfig,
    MatrixRoom,
    MessageDirection,
    RedactedEvent,
    RoomEncryptedMedia,
    StickerEvent,
    RoomMemberEvent,
    RoomAvatarEvent,
    RoomMessage,
    RoomMessageFormatted,
    RoomMessageMedia,
    crypto,
    store,
    exceptions
)

from db import (
    DB
)
from utils import (
    UTILS,
    ShowProcess
)
from functools import partial
from typing import Union, TextIO
from urllib.parse import urlparse
import aiofiles
import argparse
import asyncio
import getpass
import itertools
import os
import re
import sys
import json
import datetime


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
    return parser.parse_args()


def mkdir(path):
    try:
        os.mkdir(path)
    except FileExistsError:
        pass
    return path


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
    print("Importing keys. This may take a while...")
    await client.import_keys(room_keys_path, room_keys_password)
    return client


async def select_room(client: AsyncClient) -> MatrixRoom:
    print("\nList of joined rooms (room id, display name):")
    for room_id, room in client.rooms.items():
        print(f"{room_id}, {room.display_name}")
    room_id = input(f"Enter room id: ")
    return client.rooms[room_id]


def choose_filename(filename):
    start, ext = os.path.splitext(filename)
    for i in itertools.count(1):
        if not os.path.exists(filename):
            break
        filename = f"{start}({i}){ext}"
    return filename


async def save_current_avatars(client: AsyncClient, room: MatrixRoom) -> None:
    room_short_id = str(room.room_id).split(':')[0].replace("!", "")
    roomdir = mkdir(f"{OUTPUT_DIR}/{room_short_id}")
    avatar_dir = mkdir(
        f"{roomdir}/currentavatars")
    for user in room.users.values():
        if user.avatar_url:
            async with aiofiles.open(f"{avatar_dir}/{user.user_id}", "wb") as f:
                await f.write(await download_mxc(client, user.avatar_url))


async def download_mxc(client: AsyncClient, url: str):
    mxc = urlparse(url)
    response = await client.download(mxc.netloc, mxc.path.strip("/"))
    if hasattr(response, "body"):
        return response.body
    else:
        return b''


def is_valid_event(event):
    events = (RoomMessageFormatted, RedactedEvent)
    if not ARGS.no_media:
        events += (RoomMessageMedia, RoomEncryptedMedia)
    # return isinstance(event, events)
    return True


async def fetch_room_events(
    client: AsyncClient,
    start_token: str,
    room: MatrixRoom,
    direction: MessageDirection,
) -> list:
    events = []
    while True:
        response = await client.room_messages(
            room.room_id, start_token, limit=1000, direction=direction
        )
        if len(response.chunk) == 0:
            break
        events.extend(
            event for event in response.chunk if is_valid_event(event))
        start_token = response.end
    return events


async def write_room_events(client, room):
    print(f"Fetching {room.room_id} room messages and writing to disk...")
    sync_resp = await client.sync(
        full_state=True, sync_filter={"room": {"timeline": {"limit": 1}}}
    )
    start_token = sync_resp.rooms.join[room.room_id].timeline.prev_batch
    # Generally, it should only be necessary to fetch back events but,
    # sometimes depending on the sync, front events need to be fetched
    # as well.
    fetch_room_events_ = partial(fetch_room_events, client, start_token, room)
    room_short_id = str(room.room_id).split(':')[0].replace("!", "")
    roomdir = mkdir(f"{OUTPUT_DIR}/{room_short_id}")
    dbfile = f"{roomdir}/data.db"
    db = DB(dbfile)
    if not ARGS.no_media:
        temp_dir = mkdir(
            f"{roomdir}/temp")
        media_dir = mkdir(
            f"{roomdir}/media")
    async with aiofiles.open(
        f"{roomdir}/messages.json", "w"
    ) as f_json:
        for events in [
            list(reversed(await fetch_room_events_(MessageDirection.back))),
            await fetch_room_events_(MessageDirection.front),
        ]:
            events_parsed = []
            process_bar = ShowProcess(len(events), "Phase Accomplished!")
            for event in events:
                str_eventid = event.event_id
                if not db.event_exists(str_eventid):
                    try:
                        # get Event Category for Database.
                        str_category = str(type(event)).replace("<class 'nio.events.room_events.", "") \
                                                       .replace("<class 'nio.events.misc.", "") \
                                                       .replace("<class 'nio.events.", "") \
                                                       .replace("<class 'nio.", "") \
                                                       .replace("'>", "")

                        # set _sender_name in json
                        sender_name = f"<{event.sender}>"
                        if event.sender in room.users:
                            # If user is still present in room, include current nickname
                            sender_name = f"{room.users[event.sender].display_name} {sender_name}"
                            event.source["_sender_name"] = sender_name

                        # get timestamp string for both Database and Json output.
                        if not dict(event.source).get("origin_server_ts") is None:
                            timestamp = dict(event.source).get(
                                "origin_server_ts")
                            date = datetime.datetime.fromtimestamp(
                                timestamp/1000)
                            strtimestamp = date.strftime(
                                "%Y-%m-%d %H:%M:%S.%f")[:-3]
                            event.source["_date"] = strtimestamp

                        # download media if necessary, and de-duplicate media files, organize them in database.
                        # currently for RoomMessageMedia, RoomEncryptedMedia, StickerEvent
                        str_media = ""
                        if isinstance(event, (RoomMessageMedia, RoomEncryptedMedia, StickerEvent)):

                            # download file first with a random filename.
                            media_data = await download_mxc(client, event.url)
                            filename = choose_filename(
                                f"{temp_dir}/{str(UTILS.generate_uuid1())}")
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
                            new_name = UTILS.put_media(filename, media_dir, db)
                            event.source["_file_path"] = new_name
                            str_media = new_name

                        # download avatars for user who changes avatar, and de-duplicate media files, organize them in database.
                        # currently for RoomMemberEvent
                        if isinstance(event, (RoomMemberEvent)):

                            # look for avatar_url
                            avatar_url = dict(event.content).get('avatar_url')
                            if not (avatar_url is None):

                                # download file first with a random filename.
                                media_data = await download_mxc(client, avatar_url)
                                filename = choose_filename(
                                    f"{temp_dir}/{str(UTILS.generate_uuid1())}")
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
                                new_name = UTILS.put_media(
                                    filename, media_dir, db)
                                event.source["_file_path"] = new_name
                                str_media = new_name

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
                                        f"{temp_dir}/{str(UTILS.generate_uuid1())}")
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
                                    new_name = UTILS.put_media(
                                        filename, media_dir, db)
                                    event.source["_file_path"] = new_name
                                    str_media = new_name

                        # write out the processed message source
                        events_parsed.append(event.source)

                        # get message body is exists for database
                        str_body = ""
                        if hasattr(event, 'body'):
                            str_body = str(event.body)

                        # get message sender and source code
                        str_sender = event.sender
                        str_source = json.dumps(event.source, indent=4)

                        # insert event into database
                        db.insert_event(str_eventid, str_category, strtimestamp,
                                        str_body, str_sender, str_media, str_source)
                        process_bar.show_process()
                    except exceptions.EncryptionError as e:
                        print(e, file=sys.stderr)

            # serialise message array and write to message.json
            await f_json.write(json.dumps(events_parsed, indent=4))
    await save_current_avatars(client, room)
    os.rmdir(temp_dir)
    print("Successfully wrote all room events to disk.")


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
                print(f"Selected room: {room_id}")
                await write_room_events(client, room)
        if ARGS.batch:
            # If the program is running in unattended batch mode,
            # then we can quit at this point
            raise SystemExit
        else:
            while True:
                room = await select_room(client)
                await write_room_events(client, room)
    except KeyboardInterrupt:
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
    asyncio.run(main())
