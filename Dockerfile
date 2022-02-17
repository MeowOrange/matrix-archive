FROM python:3.9.10-slim
ENV TZ=Asia/Shanghai
ENV SERVER=server
ENV USER=user
ENV USERPASS=pass
ENV KEYPASS=keypass
ENV ROOMSTR ${1:+1}
VOLUME /matrix-archive/key.txt
VOLUME /matrix-archive/chats
VOLUME /matrix-archive/matrix-archive.py
VOLUME /matrix-archive/db.py
VOLUME /matrix-archive/utils.py
COPY matrix-archive.py requirements.txt db.py utils.py /matrix-archive/
RUN apt-get update \
    && apt-get install -y libolm-dev\
    && apt-get install -y python3-pip \
    && cd matrix-archive \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove --auto-remove -y python3-pip \
    && apt-get clean
CMD python /matrix-archive/matrix-archive.py /matrix-archive/chats --batch --server $SERVER --user "$USER" --userpass "$USERPASS" --keys /matrix-archive/key.txt --keyspass "$KEYPASS" $ROOMSTR