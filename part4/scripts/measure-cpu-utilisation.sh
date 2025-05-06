output_file=$1

# Initialize the CSV file with headers
echo "Time (s),instantaneous CPU Usage (%), cummulative CPU Usage (%)" > "$output_file"

# Initialize previous values
prev_total=0
prev_idle=0

# Infinite loop to monitor CPU usage
while true; do
    # Read the first line of /proc/stat
    time=$(($(date +%s%N)/1000000))
    read -r cpu user nice system idle iowait irq softirq steal guest guest_nice < /proc/stat

    # cumulative CPU usage
    total=$((user + nice + system + idle + iowait + irq + softirq + steal))
    used=$(((total - idle)))
    cum_cpu_usage=$(echo "scale=3; 100*$used / $total" | bc)


    # instantaneous CPU usage
    diff_total=$((total - prev_total))
    diff_idle=$((idle - prev_idle))
    diff_used=$((diff_total - diff_idle))
    inst_cpu_usage=$(echo "scale=3; 100*$diff_used / $diff_total" | bc)


    # Log the time and CPU usage to the CSV file
    echo "$time, $inst_cpu_usage, $cum_cpu_usage" >> "$output_file"

    # Update previous values
    prev_total=$total
    prev_idle=$idle

    # Wait for 5 seconds before the next iteration
    sleep 5
done