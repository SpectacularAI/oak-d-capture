# OAK-D data recording tools

## Calibration wizard

_See [CALIBRATION.md](CALIBRATION.md)._

## Installation: USB setup

Run:

    echo 'SUBSYSTEM=="usb", ATTRS{idVendor}=="03e7", MODE="0666"' | sudo tee /etc/udev/rules.d/80-movidius.rules
    sudo udevadm control --reload-rules && sudo udevadm trigger

## Usage with Docker

After the USB setup, run

    ./docker-record.sh

Stop with Ctrl+C. The data should be saved in a timestamped subfolder in `output/`. See `./docker-record.sh --help` for more options.

Note that it may not actually be possible to record all three cameras at full resolution at 25 FPS, even though the examples indicate that it's possible.
In practice, frames will start to be dropped heavily from the stereo global shutter cameras if the system is overwhelmed so be careful with the `--color` and `--color_resolution` options. In particular, do not set color resolution to 4K if you are also planning to record stereo data from the gray cameras.
The manual exposure control seems to also be buggy (may be just this code) if `--color` is used. You have been warned.

Note: It's possible for the device to end up in a bad state so that the recording script fails to produce synchronized stereo output. In that case, try unplugging and replugging the device USB chord.

## Native installation

The driver / SDK software installation instructions can be found here https://docs.luxonis.com/projects/api/en/latest/install.
If you do not like the suggested `wget ... | sudo bash -` method, just check the contents of the script, which lists the packages.
Tested platform-specific instructions below.

### Ubuntu System packages

Note that these are mostly dependencies of OpenCV which you may already have:

    sudo apt install python3 python3-pip udev cmake git \
      build-essential \
      libgtk2.0-dev \
      pkg-config \
      libavcodec-dev \
      libavformat-dev \
      libswscale-dev \
      python-dev \
      libtbb2 \
      libtbb-dev \
      libjpeg-dev \
      libpng-dev \
      libtiff-dev \
      libdc1394-22-dev \
      ffmpeg \
      libsm6 \
      libxext6 \
      libgl1-mesa-glx

The script also suggested `python3-numpy` but I wouldn't recommend to install it from `apt`
and added it to the below list of Python packages too.

### Usage

 1. Install the Python packages (in a virtualenv): `pip install -r requirements.txt`
 2. Record `python record.py`. Stop with Ctrl+C
 3. Get the output from a timestamped subfolder in `output/`

See `python record.py --help` for more options.
