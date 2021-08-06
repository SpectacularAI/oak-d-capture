# OAK-D device calibration

To calibrate your OAK-D device you need 1) Docker installed, 2) a screen to display the calibration target on, and 3) a ruler.

1. Allow all users to read and write to Myriad X devices (OAK-D device)
```
echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
sudo udevadm control --reload-rules && sudo udevadm trigger
 ```

2. Download calibration target from [Kalibr](https://github.com/ethz-asl/kalibr/wiki/downloads), direct G-Drive link: https://drive.google.com/file/d/0B0T1sizOvRsUdjFJem9mQXdiMTQ/edit?usp=sharing. Put this in full screen mode on your screen.

3. Record a video session where you move the OAK-D device in 6 degrees of freedom at moderate speed to avoid motion blur while having the target in full sight of the cameras. Record for about 30 seconds from a distances of 0.5 - 1 meters. To start the recording, use command below to start and CTRL+C to stop recording.
```
./docker-record.sh
```
The recording session will be store in `output/<date>` folder, you can check that it looks good before moving forward.

4. Next you need to have the ruler at hand an measure the full width of the AprilTag grid, this means the length of 6 tags plus 7 smaller solid squares in centimeters.

![Measuring calibration target example](./measuring_calibration_target.jpg?raw=true)

5. Use following command to start the calibration, give the measurement in cm as a parameter. The calibration will take several minutes to complete.
```
# For example ./calibrate.sh 20.5
./docker-calibrate.sh <cm>
```

6. You are done! Your calibratation results are in `./tmp/camera_calibration_raw/calibration.json` file!
