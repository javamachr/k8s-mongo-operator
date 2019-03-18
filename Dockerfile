FROM base-images/rhel7:latest

RUN yum \
-y \
--disablerepo=* \
--enablerepo=rhel-server-rhscl-7-rpms \
--enablerepo=rhel-7-server-rpms \
install rh-python36-python \
        scl-utils \
        rh-mongodb36-mongo-tools;\
yum clean all -y

WORKDIR /usr/src/app

# Install Python dependencies
COPY requirements.txt ./
RUN . /opt/rh/rh-python36/enable && \
    pip install --upgrade pip
RUN . /opt/rh/rh-python36/enable && \
    pip install --no-cache-dir -r requirements.txt

ADD . .

ENV PYTHONUNBUFFERED=0
ENTRYPOINT ["./runoperator.sh"]