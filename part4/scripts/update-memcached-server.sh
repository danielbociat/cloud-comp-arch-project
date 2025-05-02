sudo sed -i "s/^-m .*/-m 1024/" /etc/memcached.conf
sudo sed -i "s/^-l .*/-l $1/" /etc/memcached.conf