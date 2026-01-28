#!/usr/bin/env bash
set -euo pipefail
SSH="ssh $WAZO_BENCHMARK_HOST"
temp_dir=$($SSH -- sudo -u postgres mktemp -d)
trap "$SSH rm -r $temp_dir" EXIT
#read -p 'Ready to start setup?'
fifo_path=$temp_dir/cel.csv.fifo
$SSH -- sudo -u postgres mkfifo $fifo_path
$SSH -- stat $fifo_path
column_names="eventtype,eventtime,userdeftype,cid_name,cid_num,cid_ani,cid_rdnis,cid_dnid,exten,context,channame,appname,appdata,amaflags,accountcode,peeraccount,uniqueid,linkedid,userfield,peer,call_log_id,extra"
force_not_null="eventtype,eventtime,userdeftype,cid_name,cid_num,cid_ani,cid_rdnis,cid_dnid,exten,context,channame,appname,appdata,amaflags,accountcode,peeraccount,uniqueid,linkedid,userfield,peer"
echo "Starting psql COPY FROM on fifo $fifo_path"
$SSH -- sudo -u postgres psql asterisk -c "\"COPY cel($column_names) \
FROM '$fifo_path' \
(FORMAT csv, HEADER true, DELIMITER '|', FORCE_NOT_NULL($force_not_null));\"" &
#read -p 'Ready to start generating?'
python $(dirname $0)/generate_cels.py | $SSH -C "cat > $fifo_path"
