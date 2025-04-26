from kafka import KafkaConsumer

TOPIC_NAME = "kafka-test"

consumer = KafkaConsumer(
    TOPIC_NAME,
    bootstrap_servers=f"<ip>:<port>",
    client_id = "CONSUMER_CLIENT_ID",
    group_id = "CONSUMER_GROUP_ID",
    security_protocol="SSL",
    ssl_cafile="ca.cer",
    ssl_certfile="service.cert",
    ssl_keyfile="service.key",
)

while True:
    for message in consumer.poll().values():
        print("Got message using SSL: " + message[0].value.decode('utf-8'))