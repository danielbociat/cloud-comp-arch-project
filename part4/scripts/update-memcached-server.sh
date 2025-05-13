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

sudo systemctl restart memcached

#check if restarted
while true; do
    # Check the status of memcached service
    output=$(sudo systemctl status memcached)

    # If memcached is active and running, exit the loop
    if echo "$output" | grep -q "Active: active (running)"; then
        echo "Memcached is running!"
        break
    fi

    echo "Waiting for memcached to start..."
    sleep 10
done

# update cores AFTER server restart
cores=""
if [[ $3 == 1 ]]; then
  cores="0"
elif [[ $3 == 2 ]]; then
  cores="0-1"
fi

pid=$(sudo systemctl show --property MainPID --value memcached)
sudo taskset -a -p --cpu-list $cores $pid

echo -n "Current CPU affinity for PID $pid: "
sudo taskset -cp "$pid"
