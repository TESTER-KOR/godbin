#!/bin/bash
# Google Cloud VM 최초 세팅 스크립트
# 실행: bash setup.sh

set -e

echo "=== 패키지 업데이트 ==="
sudo apt-get update -y
sudo apt-get install -y python3 python3-pip git

echo "=== 의존성 설치 ==="
cd ~/godbin
pip3 install -r requirements.txt

echo "=== systemd 서비스 등록 ==="
sudo cp deploy/godbin.service /etc/systemd/system/godbin.service
sudo sed -i "s|{HOME}|$HOME|g" /etc/systemd/system/godbin.service
sudo systemctl daemon-reload
sudo systemctl enable godbin
sudo systemctl start godbin

echo "=== 완료 ==="
sudo systemctl status godbin
