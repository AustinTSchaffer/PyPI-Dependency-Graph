docker container run -d --restart always -p 5000:5000 --name registry registry

docker swarm init

docker node update --label-add role=app rpi-cluster-4b-4gb-1
docker node update --label-add role=app rpi-cluster-4b-4gb-2
docker node update --label-add role=broker rpi-cluster-4b-4gb-3
docker node update --label-add role=db rpi-cluster-4b-4gb-4
