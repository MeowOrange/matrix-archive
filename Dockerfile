FROM python:3.9.10-slim
ENV TZ=Asia/Shanghai
ENV SERVER=server
ENV USER=user
ENV USERPASS=pass
ENV KEYPASS=keypass
ENV ROOMSTR ${1:+1}
ENV ARGS ${2:+2}
VOLUME /matrix_archive/key.txt
VOLUME /matrix_archive/chats
VOLUME /matrix_archive/logs
#VOLUME /matrix_archive/matrix-archive.py
#VOLUME /matrix_archive/db.py
#VOLUME /matrix_archive/utils.py
COPY matrix-archive.py requirements.txt db.py utils.py /matrix_archive/
RUN apt-get update \
    && apt-get install -y libolm-dev\
    && apt-get install -y python3-pip \
    && cd matrix_archive \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get remove --auto-remove -y python3-pip \
    && apt-get clean
CMD python /matrix_archive/matrix-archive.py /matrix_archive/chats --batch --server $SERVER --user "$USER" --userpass "$USERPASS" --keys /matrix_archive/key.txt --keyspass "$KEYPASS" $ROOMSTR $ARGS