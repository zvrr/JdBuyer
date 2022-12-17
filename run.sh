#conda create -n jdbuyer python=3.7

# https://item.m.jd.com/product/100040452006.html?&utm_source=iosapp&utm_medium=appshare&utm_campaign=t_335139774&utm_term=CopyURL&ad_od=share&gx=RnFgwmYNaDbZy9RP--sRLke67LOaCtjldko
# python JdBuyer.py -skuId 100040452006 -skuNum 5  -buyTime "2022-12-17 19:59:40"
# https://item.m.jd.com/product/100021455115.html?&utm_source=iosapp&utm_medium=appshare&utm_campaign=t_335139774&utm_term=CopyURL&ad_od=share&gx=RnFgwmYNaDbZy9RP--sRLke67LOaCtjldko
#python JdBuyer.py -skuId 100021455115 -skuNum 5  -buyTime "2022-12-17 19:59:40"

#python JdBuyer.py -skuId 100021318601 -skuNum 10  -buyTime "2022-12-17 19:59:40"

start(){
    echo "start..."
    mkdir -p /data/log/jdbuyer
    python JdBuyer.py > /data/log/jdbuyer/server.log 2>&1 &
    echo "started"
}

stop(){
    echo "stop..."
    echo `ps auxf |grep JdBuyer.py|grep -v grep`
    kill -9 `ps aux |grep JdBuyer.py|grep -v grep |awk '{print $2}'`
    echo "stoped"
}

cmd="$1"
if [ -z "$cmd" ]; then
    echo "restart all..."
    stop
    start
    echo "restarted all..."
elif [ "$cmd" == "stop" ]; then
    stop
elif [ "$cmd" == "start" ]; then
    start
fi




