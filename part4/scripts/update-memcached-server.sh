sudo sed -i "s/^-m .*/-m 1024/" /etc/memcached.conf
sudo sed -i "s/^-l .*/-l $1/" /etc/memcached.conf
if grep -q "^-t " /etc/memcached.conf; then
    sudo sed -i "s/^-t .*/-t $2/" /etc/memcached.conf
else
    echo "-t $2" | sudo tee -a /etc/memcached.conf > /dev/null
fi