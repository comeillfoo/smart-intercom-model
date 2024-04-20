#!/usr/bin/env bash

PORT=49153
DELAY=0.1
N=11
TEST_IMAGE="${1:-sbc/tests/man_480p.jpg}"


proc_mem() {
    local pid_status="/proc/$1/status"
    local num=$2
    if [ -f "${pid_status}" ]; then
        echo -e "$num\t$(grep -i 'vmrss' "${pid_status}" | awk '{print $2};' -)"
        return 0
    fi
    echo 0
    return 1
}

repeat_string() {
    local n=$1
    local string=$2
    for ((i=0; i < n; ++i)); do
        echo -n "${string} "
    done
}

# run_in_venv() {
#     local dir=$1
#     shift 1
#     cd "${dir}" || return 2
#     ../in_venv.sh .venv $@
#     return $?
# }

pymax() {
    python3 -c 'import sys; print(max(float(sys.argv[1]), float(sys.argv[2])))' $1 $2
}

pymin() {
    python3 -c 'import sys; print(min(float(sys.argv[1]), float(sys.argv[2])))' $1 $2
}

pysum() {
    python3 -c 'import sys; print(float(sys.argv[1]) + float(sys.argv[2]))' $1 $2
}

pydiv() {
    python3 -c 'import sys; print(float(sys.argv[1]) / float(sys.argv[2]))' $1 $2
}

memstat() {
    local memlog=$1
    local n=$(wc -l "${memlog}" | awk '{print $1};')
    local mn=$(head -n 1 "${memlog}" | awk '{print $2};' -)
    local mx=$(head -n 1 "${memlog}" | awk '{print $2};' -)
    local sum=0

    while IFS= read -r line; do
        i=$(echo $line | awk '{print $1};' -)
        num=$(echo $line | awk '{print $2};' -)
        mn=$(pymin $mn $num)
        mx=$(pymax $mn $num)
        sum=$(pysum $sum $num)
    done < "${memlog}"

    avg=$(pydiv $sum $n)
    echo -e "Statistics for ${memlog}:\n"
    echo "Total: ${n}"
    echo "Min: ${mn} Kb"
    echo "Max: ${mx} Kb"
    echo "Avg: ${avg} Kb"
}


INTERCOM_ARGS="-t $(repeat_string "${N}" "../${TEST_IMAGE}")"
echo "Running sbc on port ${PORT}"
echo "Running intercom with ${INTERCOM_ARGS}"

sbc_pid=$(./in_venv.sh ./sbc .venv python3 ./sbc.py -P "${PORT}")
echo "sbc[$sbc_pid]"
sleep 3

intercom_pid=$(./in_venv.sh ./intercom .venv python3 ./intercom.py -P "${PORT}" ${INTERCOM_ARGS})
echo "intercom[$intercom_pid]"

counter=0
while [ -d "/proc/${intercom_pid}" ]; do
    proc_mem "${intercom_pid}" $counter >> ./intercom.mem
    proc_mem "${sbc_pid}" $counter >> ./sbc.mem
    counter=$((counter + 1))
    sleep "${DELAY}"
done

kill -9 $intercom_pid 2>/dev/null
kill -9 $sbc_pid
kill -9 "$(lsof -ti:$PORT)" 2>/dev/null
memstat ./intercom.mem
memstat ./sbc.mem
