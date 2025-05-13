output_file=$1

# Initialize the CSV file with headers
#echo "Time (s), CPU TOTAL, CPU 0, CPU 1, CPU 2, CPU 3 " > "$output_file"



# Initialize previous values
num_cpus=4

for ((i=0; i<num_cpus+1; i++)); do
    prev_total[i]=0
    prev_idle[i]=0
    inst_cpu_usage[i]=0
done


# Infinite loop to monitor CPU usage
while true; do
    # Read the first line of /proc/stat
    time=$(($(date +%s%N)/1000000))

    for ((i=0; i<num_cpus+1; i++)); do

      line=$(head -n $((i+1)) /proc/stat | tail -n 1)


      read -r cpu user nice system idle iowait irq softirq steal guest guest_nice <<< "$line"
      echo "$cpu"

      # cumulative CPU usage
      total=$((user + nice + system + idle + iowait + irq + softirq + steal))
      used=$(((total - idle)))

      # instantaneous CPU usage
      diff_total=$((total - prev_total[i]))
      diff_idle=$((idle - prev_idle[i]))
      diff_used=$((diff_total - diff_idle))
      inst_cpu_usage[i]=$(echo "scale=3; 100*$diff_used / $diff_total" | bc)

      # Update previous values
      prev_total[i]=$total
      prev_idle[i]=$idle
    done
    # Log the time and CPU usage to the CSV file
    output="$time"
    for ((i=0; i<num_cpus+1; i++)); do
        output+=", ${inst_cpu_usage[$i]}"
    done

    echo "$output" >> "$output_file"
    echo "$output"

    # Wait for 5 seconds before the next iteration
    sleep 5
done