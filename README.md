# matrix-archive

Archive Matrix room messages. Based on the project [matrix-archive](https://github.com/russelldavies/matrix-archive)

Save room messages into SQLite3 database, including media, implemented auto deduplication on media files.

# Installation

Note that at least Python 3.8+ is required.

1. Install [libolm](https://gitlab.matrix.org/matrix-org/olm) 3.1+

    - Debian 11+ (testing/sid) or Ubuntu 19.10+: `sudo apt install libolm-dev`

    - Archlinux based distribution can install the `libolm` package from the Community repository

    - macOS `brew install libolm`

    - Failing any of the above refer to the [olm
      repo](https://gitlab.matrix.org/matrix-org/olm) for build instructions.

2. Install dependencies
    ```
    pip install -r requirements.txt
    ```

# Usage

1. Download your E2E room keys: in the client Element you can do this by
   clicking on your profile icon, _Security & privacy_, _Export E2E room keys_.

2.  Run with an optional directory to store output, e.g.: `./matrix-archive.py chats`

3. You'll be prompted to enter your homeserver, user credentials and the path
   to the room keys you downloaded in step 1.

4. You'll be prompted to select which room you want to archive. Use --all-rooms argument to archive all room messages.

5. Available arguments:

   * --batch: No prompts. You need to specify the following:
      * --server yourhomeserver
      * --user '@user:homeserver'
      * --userpass 'yourpassword'
      * --keys path_to_your_keys_file
      * --keyspass 'your_paassword_for_keys_file'
      * --room: Specify a room or just use --all-rooms
   * --no-media: This is left in the source code by original project. I didn't test that but I kept that in the code anyway.

# Using Docker

```
docker run -it --name matrix-archive \
-v ":/matrix-archive/key.txt" \
-v ":/matrix-archive/chats" \
-e "SERVER=https://yourhomeserver" \
-e "USER=@user:yourhomeserver" \
-e "USERPASS=yourpassword" \
-e "KEYPASS=passwordforkeyfile" \
-e "ROOMSTR=--all-rooms" \
orangemeow/matrix-archive:1.0
```

Note that ROOMSTR can be set to strings like:
```
ROOMSTR=--room !abcdefg:yourhomeserver
```
The latter part(```!abcdefg:yourhomeserver```) is your room id which can be obtained

You can override .py files with volumes:
```
-v "your-.py-file:/matrix-archive/matrix-archive.py" \
-v "your-.py-file:/matrix-archive/db.py" \
-v "your-.py-file:/matrix-archive/utils.py" \
```
