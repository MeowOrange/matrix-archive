# matrix-archive

[![Docker Pulls](https://img.shields.io/docker/pulls/orangemeow/matrix-archive.svg)](https://hub.docker.com/r/orangemeow/matrix-archive)

[![GitHub](https://img.shields.io/static/v1?style=for-the-badge&message=GitHub&color=181717&logo=GitHub&logoColor=FFFFFF&label=)](https://github.com/MeowOrange/matrix-archive)

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

2. Run with an optional directory to store output, e.g.: `./matrix-archive.py chats`

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
   * --no-progress-bar: Disables progress bar while keeps basic log output.
   * --no-logs: Disables log file output.
     * When using docker, these arguments can be added to environment variable ARGS, for example:

        ```
        ARGS=--no-progress-bar --no-logs
        ```
6. Script has exit code:
    * Exit code 0 for successful fetched all events.
    * Exit code 1 for misc errors and exceptions.
    * Exit code 3 for database errors.
    * Exit code 4 for downloading errors.

# Using Docker

```
docker run -it --name matrix-archive \
-v ":/matrix_archive/key.txt" \
-v ":/matrix_archive/chats" \
-v ":/matrix_archive/logs" \
-e "SERVER=https://yourhomeserver" \
-e "USER=@user:yourhomeserver" \
-e "USERPASS=yourpassword" \
-e "KEYPASS=passwordforkeyfile" \
-e "ROOMSTR=--all-rooms" \
-e "ARGS=--no-progress-bar --no-logs" \
orangemeow/matrix-archive:latest
```

Note that ROOMSTR can be set to strings like:
```
ROOMSTR=--room !abcdefg:yourhomeserver
```
The latter part(```!abcdefg:yourhomeserver```) is your room id which can be obtained

You can override .py files with volumes:
```
-v "your-.py-file:/matrix_archive/matrix-archive.py" \
-v "your-.py-file:/matrix_archive/db.py" \
-v "your-.py-file:/matrix_archive/utils.py" \
```

# Using on the same server as Matrix homeserver

## Add host to container

Docker run has an argument: ```--add-host```. If the Matrix homeserver is in your internal network, you may use:
```
docker run --add-host yourhomeserver:internal-ip-address ...
```
to get access to your homeserver.

## Pass through Nginx & Proxy Protocol

In my case, I use [frp](https://github.com/fatedier/frp) to proxy external traffic to homeserver in my internal network, which uses nginx to proxy traffic to Matrix. 

Frp pass the real remote ip to nginx using proxy protocol. When I tried to directly access Matrix with ```--add-host```, nginx stopped me because I'm not using proxy protocol.

And I find [this solution](https://serverfault.com/questions/958608/is-it-possible-to-configure-nginx-to-accept-requests-both-with-and-without-proxy) for this issue. Add the following into the server block in nginx.conf:

```
listen 127.0.0.1:443 ssl http2 proxy_protocol; # ip for proxy to reach homeserver
set_real_ip_from     127.0.0.1;                # ip of proxy
real_ip_header       proxy_protocol;

listen 192.168.0.2:443 ssl; # internal ip of homeserver

...

location / {
   proxy_set_header X-Real-IP $proxy_protocol_addr;
   proxy_set_header X-Forwarded-For $proxy_protocol_addr;
   ...
   proxy_pass http://127.0.0.1:8008;
}
```
