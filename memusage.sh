#!/usr/bin/env bash

PORT=49153
DELAY=1
N=11
TEST_IMAGE="${1:-sbc/tests/man_480p.jpg}"


proc_mem() {
    local pid_status="/proc/$1/status"
    if [ -f "${pid_status}" ]; then
        grep -i 'vmrss' "${pid_status}" | awk '{print $2};' -
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

run_in_venv() {
    local dir=$1
    shift 1
    cd "${dir}" || return 2
    ../in_venv.sh .venv $@
    return $?
}

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
    local mn=$(head -n 1 "${memlog}")
    local mx=$(head -n 1 "${memlog}")
    local sum=0

    while IFS= read -r num; do
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


CAMERA_ARGS="-t $(repeat_string "${N}" "../${TEST_IMAGE}")"
echo "Running sbc on port ${PORT}"
echo "Running camera with ${CAMERA_ARGS}"

run_in_venv ./sbc python3 ./sbc.py -P "${PORT}" &
sbc_pid=$!
sleep 3

run_in_venv ./camera python3 ./camera.py -P "${PORT}" "${CAMERA_ARGS}" &
camera_pid=$!

while [ -d "/proc/${camera_pid}" ]; do
    proc_mem "${camera_pid}" >> ./camera.mem
    proc_mem "${sbc_pid}" >> ./sbc.mem
    sleep "${DELAY}"
done

kill -9 $camera_pid
kill -9 $sbc_pid
memstat ./camera.mem
memstat ./sbc.mem
