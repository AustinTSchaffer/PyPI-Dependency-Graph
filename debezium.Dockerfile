FROM quay.io/debezium/server:2.5

COPY ./debezium/debezium.rpi-cluster-local-db.properties /debezium/conf/application.properties
