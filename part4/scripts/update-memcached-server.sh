#params:
# $1 ip
# $2 threads
# $3 cores

# memory
sudo sed -i "s/^-m .*/-m 1024/" /etc/memcached.conf

#ip
sudo sed -i "s/^-l .*/-l $1/" /etc/memcached.conf

#threads
if grep -q "^-t " /etc/memcached.conf; then
    sudo sed -i "s/^-t .*/-t $2/" /etc/memcached.conf
else
    echo "-t $2" | sudo tee -a /etc/memcached.conf > /dev/null
fi

# cores
cores=""
if [[ $3 == 1 ]]; then
  cores="0"
elif [[ $3 == 2 ]]; then
  cores="0-1"
fi
pid=$(sudo systemctl show --property MainPID --value memcached)
sudo taskset -a -p --cpu-list $cores $pid

#restart
sudo systemctl restart memcached