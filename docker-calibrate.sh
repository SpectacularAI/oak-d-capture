#!/bin/bash
# Usage:
#
#   ./calibrate.sh recording-folder aprilgrid-in-cm
#
# where the folder should contain the files data.jsonl, data.???. data2.???,
# that represent a sequence where a calibration pattern is filmed appropriately.


#!/bin/bash

set -eu -o pipefail

CAM_MODEL=pinhole-radtan
tmp_dir=tmp
DOCKER_KALIBR_RUN="docker run -v `pwd`/$tmp_dir:/kalibr -it stereolabs/kalibr:kinetic"
DOCKER_DEPTHAI_RUN="docker run -v `pwd`/$tmp_dir:/kalibr -it ghcr.io/spectacularai/depthai-library:1.0"
APRIL_GRID=$2

rm -rf tmp
mkdir -p tmp/allan
cp -R "$1" $tmp_dir/camera_calibration_raw

aprilTag=$(LC_NUMERIC="C" awk "BEGIN {printf \"%.8f\",${APRIL_GRID}/810.0}") # cm -> m and divide by 8.1
printf "target_type: 'aprilgrid'
tagCols: 6
tagRows: 6
tagSize: ${aprilTag}
tagSpacing: 0.3" >> $tmp_dir/april_6x6_80x80cm.yaml

# TODO: These are probably not correct?
printf "accelerometer_noise_density: 0.00074562202949377
accelerometer_random_walk: 0.0011061605306550387
gyroscope_noise_density: 3.115084637301622e-05
gyroscope_random_walk: 1.5610557862757885e-05
rostopic: /imu0
update_rate: 600
" >> $tmp_dir/allan/imu.yaml

$DOCKER_DEPTHAI_RUN python3 /scripts/jsonl-to-kalibr.py /kalibr/camera_calibration_raw -output /kalibr/converted/
$DOCKER_KALIBR_RUN kalibr_bagcreater --folder /kalibr/converted --output-bag /kalibr/data.bag
set +e
$DOCKER_KALIBR_RUN bash -c "cd /kalibr && kalibr_calibrate_cameras --bag data.bag \
    --topics /cam0/image_raw /cam1/image_raw \
    --models $CAM_MODEL $CAM_MODEL \
    --target april_6x6_80x80cm.yaml \
    --dont-show-report"
$DOCKER_KALIBR_RUN bash -c "cd kalibr && kalibr_calibrate_imu_camera --bag data.bag \
    --cams camchain-data.yaml \
    --target april_6x6_80x80cm.yaml \
    --imu allan/imu.yaml  \
    --dont-show-report"
set -e
$DOCKER_DEPTHAI_RUN python3 /scripts/kalibr-to-calibration.py /kalibr/camchain-imucam-data.yaml -output /kalibr/camera_calibration_raw/
