while true; do
    # Check the status of memcached service
    output=$(sudo systemctl status memcached)

    # If memcached is active and running, exit the loop
    if echo "$output" | grep -q "Active: active (running)"; then
        echo "Memcached is running!"
        break
    fi

    echo "Waiting for memcached to start..."
    sleep 15
done